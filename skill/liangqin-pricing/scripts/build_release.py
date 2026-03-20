#!/usr/bin/env python3
"""Build a versioned release snapshot for the Liangqin pricing skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a versioned release snapshot.")
    parser.add_argument("--version", required=True, help="Version label, for example 2025-06-01.")
    parser.add_argument("--price-index", required=True, help="Path to a normalized price-index.json.")
    parser.add_argument("--rules-candidate", required=True, help="Path to a rules candidate JSON.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    version_dir = skill_dir / "data" / "versions" / args.version
    rules_dir = version_dir / "rules"
    version_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.mkdir(parents=True, exist_ok=True)

    price_index_src = Path(args.price_index).expanduser().resolve()
    rules_candidate_src = Path(args.rules_candidate).expanduser().resolve()
    if price_index_src.stat().st_size == 0:
        raise SystemExit(f"Refusing to build from empty price index: {price_index_src}")
    if rules_candidate_src.stat().st_size == 0:
        raise SystemExit(f"Refusing to build from empty rules candidate: {rules_candidate_src}")

    shutil.copy2(price_index_src, version_dir / "price-index.json")
    shutil.copy2(rules_candidate_src, rules_dir / "rules-candidate.json")

    release = {
        "version": args.version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "status": "candidate",
        "price_index_file": "price-index.json",
        "rules_candidate_file": "rules/rules-candidate.json",
    }
    release_path = version_dir / "release.json"
    temp_path = release_path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(release, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, release_path)

    print(f"Built release snapshot at {version_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
