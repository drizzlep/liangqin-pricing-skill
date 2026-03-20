#!/usr/bin/env python3
"""Show the current active Liangqin pricing release."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show the current Liangqin pricing release metadata.")
    parser.add_argument(
        "--release",
        default=str(Path(__file__).resolve().parent.parent / "data" / "current" / "release.json"),
        help="Path to current release.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.release).expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
