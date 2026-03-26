#!/usr/bin/env python3
"""Refresh the Liangqin skill and run one fresh-session smoke test."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PRESET_MESSAGES = {
    "wardrobe-smoke": "我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？",
    "modular-child-bed": "做一张定制上下床，1.2米乘2米，北美白橡木，梯柜款，下层箱体床，胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500，直接正式报价。",
    "loft-double-row-wardrobe": "一张半高梯柜上铺床1.2*2米床垫尺寸的，胶囊围栏，围栏长2米高0.4米。床下前后双排衣柜，前后柜体互通形式，前后两排都深450。前面有门无背板的衣柜长2米高1.2米，后方无门有背板的衣柜也是长2米高1.2米。请帮忙看下用玫瑰木和白蜡木做的话分别是多少钱。",
    "child-bed-rosewood-special": "做一张乌拉圭玫瑰木定制错层床，1.2米乘2米，城堡围栏，斜梯，直接正式报价。",
    "child-bed-width-limit": "做一张定制高架床，1.35米乘2米，北美白橡木，梯柜款，胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500，这种能直接正式报价吗？",
}
DEFAULT_PRESET = "wardrobe-smoke"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the shared skill and run a fresh-session test.")
    parser.add_argument("--message", help="Explicit test message. Overrides preset if provided.")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_MESSAGES),
        default=DEFAULT_PRESET,
        help="Named smoke-test preset. Defaults to wardrobe-smoke.",
    )
    parser.add_argument("--session-id", help="Optional explicit session id. Defaults to an auto-generated fresh test id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--timeout", type=int, default=120, help="Agent timeout in seconds.")
    parser.add_argument("--thinking", default="minimal", help="Agent thinking level.")
    parser.add_argument("--no-update", action="store_true", help="Skip update_release.py even if inbox contains xlsx + rule files.")
    parser.add_argument(
        "--reset-quote-sessions",
        action="store_true",
        help="Reset stale Liangqin quote sessions before running the fresh-session test.",
    )
    parser.add_argument(
        "--include-feishu",
        action="store_true",
        help="When resetting quote sessions, also reset Feishu quote sessions.",
    )
    return parser.parse_args()


def resolve_test_message(message: str | None, preset: str) -> str:
    if message:
        return message
    return PRESET_MESSAGES[preset]


def run_step(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=capture,
    )


def has_ready_sources(inbox_dir: Path) -> bool:
    has_xlsx = any(inbox_dir.glob("*.xlsx"))
    has_rules = any(inbox_dir.glob("*.docx")) or any(inbox_dir.glob("*.pdf"))
    return has_xlsx and has_rules


def extract_json_payload(raw: str) -> dict[str, object]:
    lines = [line for line in raw.splitlines() if line.strip()]
    for start in range(len(lines)):
        candidate = "\n".join(lines[start:])
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise SystemExit("未能从 OpenClaw 输出里解析到 JSON 结果，请稍后重试。")


def print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def build_reset_command(scripts_dir: Path, *, include_feishu: bool) -> list[str]:
    command = [sys.executable, str(scripts_dir / "reset_quote_sessions.py"), "--apply"]
    if include_feishu:
        command.append("--include-feishu")
    return command


def main() -> int:
    args = parse_args()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    scripts_dir = skill_dir / "scripts"
    inbox_dir = skill_dir / "sources" / "inbox"
    session_id = args.session_id or f"liangqin-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    message = resolve_test_message(args.message, args.preset)

    if not args.no_update and has_ready_sources(inbox_dir):
        print_header("检测到 inbox 里有 xlsx + 规则文件，先更新当前版本")
        update = run_step([sys.executable, str(scripts_dir / "update_release.py"), "--skill-dir", str(skill_dir)])
        if update.returncode != 0:
            return update.returncode
    else:
        print_header("未检测到成套更新文件，直接发布当前 skill")
        publish = run_step([sys.executable, str(scripts_dir / "publish_skill.py"), "--source", str(skill_dir)])
        if publish.returncode != 0:
            return publish.returncode

    if args.reset_quote_sessions:
        print_header("清理旧报价会话，避免继续复用旧上下文")
        reset = run_step(build_reset_command(scripts_dir, include_feishu=args.include_feishu))
        if reset.returncode != 0:
            return reset.returncode

    print_header("开始 fresh session 测试")
    print(f"session-id: {session_id}")
    print(f"message: {message}")

    result = run_step(
        [
            "openclaw",
            "agent",
            "--session-id",
            session_id,
            "--message",
            message,
            "--json",
            "--thinking",
            args.thinking,
            "--timeout",
            str(args.timeout),
        ],
        capture=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode

    if result.stderr:
        # OpenClaw frequently prints warnings to stderr before the JSON body.
        print(result.stderr, file=sys.stderr)

    payload = extract_json_payload(result.stdout)
    texts = [item.get("text", "") for item in payload.get("result", {}).get("payloads", []) if item.get("text")]

    print_header("测试结果")
    if texts:
        print(texts[-1])
    else:
        print(result.stdout)

    print_header("后续可复用命令")
    reset_suffix = " --reset-quote-sessions --include-feishu" if args.reset_quote_sessions and args.include_feishu else ""
    if args.message:
        print(f"python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message '{message}'{reset_suffix}")
    else:
        print(f"python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --preset {args.preset}{reset_suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
