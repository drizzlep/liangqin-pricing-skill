#!/usr/bin/env python3
"""Sync the shared Liangqin skill into the OpenClaw skill stores."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


IGNORE_NAMES = {
    "__pycache__",
    ".DS_Store",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy the shared Liangqin skill into the OpenClaw skill stores.")
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parent.parent),
        help="Shared skill source directory.",
    )
    parser.add_argument(
        "--dest",
        action="append",
        dest="dests",
        help="Skill destination directory. Repeat to sync multiple destinations.",
    )
    return parser.parse_args()


def ignore_filter(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES}


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    raw_dests = args.dests or [
        str(Path.home() / ".openclaw" / "skills" / "liangqin-pricing"),
        str(Path.home() / ".openclaw" / "workspace" / "skills" / "liangqin-pricing"),
    ]
    dests = [Path(raw_dest).expanduser().resolve() for raw_dest in raw_dests]

    if not source.exists():
        raise SystemExit(f"Source skill directory not found: {source}")

    seen: set[Path] = set()
    normalized_dests: list[Path] = []
    for dest in dests:
        if dest in seen:
            continue
        if dest == source:
            raise SystemExit("Source and destination must be different directories.")
        seen.add(dest)
        normalized_dests.append(dest)

    for dest in normalized_dests:
        if dest.exists():
            shutil.rmtree(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, dest, ignore=ignore_filter)
        print(f"Synced skill to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
