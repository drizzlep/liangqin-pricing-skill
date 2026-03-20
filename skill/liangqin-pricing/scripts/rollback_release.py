#!/usr/bin/env python3
"""Rollback current data to a previous version."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import subprocess


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rollback current Liangqin pricing data to a previous version.")
    parser.add_argument("--version-dir", required=True, help="Path to the version directory to reactivate.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script = Path(__file__).resolve().parent / "activate_release.py"
    command = [
        sys.executable,
        str(script),
        "--version-dir",
        str(Path(args.version_dir).expanduser().resolve()),
        "--skill-dir",
        str(Path(args.skill_dir).expanduser().resolve()),
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
