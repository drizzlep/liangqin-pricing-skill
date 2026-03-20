#!/usr/bin/env python3
"""Activate a versioned release as current."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Activate a Liangqin pricing release.")
    parser.add_argument("--version-dir", required=True, help="Path to the version directory.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version_dir = Path(args.version_dir).expanduser().resolve()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    current_dir = skill_dir / "data" / "current"

    price_index = version_dir / "price-index.json"
    release_json = version_dir / "release.json"
    if not price_index.exists() or not release_json.exists():
        print("Release files missing; activate aborted.")
        return 1
    if price_index.stat().st_size == 0:
        print("Release price index is empty; activate aborted.")
        return 1

    current_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(price_index, current_dir / "price-index.json")

    with release_json.open("r", encoding="utf-8") as handle:
        release = json.load(handle)
    release["status"] = "active"
    current_release = current_dir / "release.json"
    temp_path = current_release.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(release, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, current_release)

    print(f"Activated release {release.get('version', version_dir.name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
