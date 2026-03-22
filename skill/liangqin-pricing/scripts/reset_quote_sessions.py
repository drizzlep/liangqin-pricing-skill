#!/usr/bin/env python3
"""Reset stale Liangqin quote sessions that keep replaying old pricing logic."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_STORE = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset stale Liangqin quote sessions without touching unrelated sessions.")
    parser.add_argument(
        "--store",
        default=str(DEFAULT_STORE),
        help="Path to OpenClaw sessions.json.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matched sessions. Without this flag, only print the dry-run result.",
    )
    parser.add_argument(
        "--include-feishu",
        action="store_true",
        help="Also reset Feishu quote sessions.",
    )
    parser.add_argument(
        "--dingtalk-chat-type",
        choices=("all", "group", "direct"),
        default="all",
        help="Only reset DingTalk sessions for the selected chat type. Defaults to all.",
    )
    return parser.parse_args()


def matches_dingtalk_chat_type(key: str, dingtalk_chat_type: str) -> bool:
    if dingtalk_chat_type == "all":
        return True
    if f":dingtalk:{dingtalk_chat_type}:" in key:
        return True
    if f":dingtalk-connector:{dingtalk_chat_type}:" in key:
        return True
    if f'"chattype":"{dingtalk_chat_type}"' in key:
        return True
    return False


def should_reset_session_key(
    key: str,
    *,
    include_feishu: bool = False,
    dingtalk_chat_type: str = "all",
) -> bool:
    if key == "agent:main:main":
        return dingtalk_chat_type == "all"
    if (":dingtalk:" in key or ":dingtalk-connector:" in key or '"channel":"dingtalk-connector"' in key) and matches_dingtalk_chat_type(
        key, dingtalk_chat_type
    ):
        return True
    if include_feishu and (":feishu:" in key or '"channel":"feishu"' in key):
        return True
    return False


def load_sessions(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"会话文件格式不对：{path}")
    return payload


def collect_targets(
    sessions: dict[str, dict[str, Any]],
    *,
    include_feishu: bool = False,
    dingtalk_chat_type: str = "all",
) -> dict[str, dict[str, Any]]:
    return {
        key: value
        for key, value in sessions.items()
        if should_reset_session_key(
            key,
            include_feishu=include_feishu,
            dingtalk_chat_type=dingtalk_chat_type,
        )
    }


def backup_store(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_suffix(path.suffix + f".bak.{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def candidate_session_files(store_path: Path, session: dict[str, Any]) -> list[Path]:
    files: list[Path] = []
    raw_session_file = session.get("sessionFile")
    if raw_session_file:
        files.append(Path(str(raw_session_file)).expanduser())
    raw_session_id = str(session.get("sessionId") or "").strip()
    if raw_session_id:
        files.append(store_path.parent / f"{raw_session_id}.jsonl")

    unique_files: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_files.append(resolved)
    return unique_files


def print_targets(targets: dict[str, dict[str, Any]], store_path: Path) -> None:
    if not targets:
        print("没有发现需要清理的旧报价会话。")
        return

    print(f"命中的旧报价会话：{len(targets)}")
    for key, session in targets.items():
        session_id = session.get("sessionId") or "-"
        print(f"- {key}")
        print(f"  sessionId: {session_id}")
        for session_file in candidate_session_files(store_path, session):
            if session_file.exists():
                print(f"  file: {session_file}")


def apply_reset(store_path: Path, sessions: dict[str, dict[str, Any]], targets: dict[str, dict[str, Any]]) -> Path:
    backup_path = backup_store(store_path)

    remaining = {key: value for key, value in sessions.items() if key not in targets}
    with store_path.open("w", encoding="utf-8") as handle:
        json.dump(remaining, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    for session in targets.values():
        for session_file in candidate_session_files(store_path, session):
            if session_file.exists():
                session_file.unlink()

    return backup_path


def main() -> int:
    args = parse_args()
    store_path = Path(args.store).expanduser().resolve()
    sessions = load_sessions(store_path)
    targets = collect_targets(
        sessions,
        include_feishu=args.include_feishu,
        dingtalk_chat_type=args.dingtalk_chat_type,
    )

    print_targets(targets, store_path)
    if not targets:
        return 0

    if not args.apply:
        print("\n当前是 dry-run。确认无误后执行：")
        command = "python3 ~/.openclaw/skills/liangqin-pricing/scripts/reset_quote_sessions.py --apply"
        if args.include_feishu:
            command += " --include-feishu"
        if args.dingtalk_chat_type != "all":
            command += f" --dingtalk-chat-type {args.dingtalk_chat_type}"
        print(command)
        return 0

    backup_path = apply_reset(store_path, sessions, targets)
    print(f"\n已清理 {len(targets)} 条旧报价会话。")
    print(f"备份文件：{backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
