#!/usr/bin/env python3
"""Validate a versioned release snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Liangqin pricing release.")
    parser.add_argument("--version-dir", required=True, help="Path to the version directory.")
    return parser.parse_args()


def ensure_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)


def main() -> int:
    args = parse_args()
    version_dir = Path(args.version_dir).expanduser().resolve()
    required = [
        version_dir / "release.json",
        version_dir / "price-index.json",
        version_dir / "rules" / "rules-candidate.json",
    ]

    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(path)
        return 1

    for path in required:
        ensure_json(path)

    print(f"Release is valid: {version_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
