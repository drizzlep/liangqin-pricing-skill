#!/usr/bin/env python3
"""Refresh the Liangqin skill and run one fresh-session smoke test."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_MESSAGE = "我要做个北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，多少钱？"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the shared skill and run a fresh-session test.")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="Test message. Defaults to the standard wardrobe smoke test.")
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
    return parser.parse_args()


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


def main() -> int:
    args = parse_args()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    scripts_dir = skill_dir / "scripts"
    inbox_dir = skill_dir / "sources" / "inbox"
    session_id = args.session_id or f"liangqin-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

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
        reset = run_step([sys.executable, str(scripts_dir / "reset_quote_sessions.py"), "--apply"])
        if reset.returncode != 0:
            return reset.returncode

    print_header("开始 fresh session 测试")
    print(f"session-id: {session_id}")
    print(f"message: {args.message}")

    result = run_step(
        [
            "openclaw",
            "agent",
            "--session-id",
            session_id,
            "--message",
            args.message,
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
    print(f"python3 ~/.openclaw/skills/liangqin-pricing/scripts/refresh_and_test.py --message '{args.message}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
