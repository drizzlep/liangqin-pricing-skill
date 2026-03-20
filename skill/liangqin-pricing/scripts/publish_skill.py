#!/usr/bin/env python3
"""Validate and publish the shared Liangqin skill into the OpenClaw workspace."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml


ALLOWED_FRONTMATTER_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}
IGNORE_NAMES = {"__pycache__", ".DS_Store"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and publish the Liangqin skill to the OpenClaw workspace.")
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parent.parent),
        help="Shared skill source directory.",
    )
    parser.add_argument(
        "--dest",
        default=str(Path.home() / ".openclaw" / "workspace" / "skills" / "liangqin-pricing"),
        help="Workspace skill destination directory.",
    )
    return parser.parse_args()


def validate_skill_dir(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SystemExit(f"SKILL.md not found: {skill_md}")

    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise SystemExit("No YAML frontmatter found at the top of SKILL.md")

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise SystemExit("Invalid frontmatter format in SKILL.md")

    frontmatter = yaml.safe_load(match.group(1))
    if not isinstance(frontmatter, dict):
        raise SystemExit("Frontmatter must be a YAML mapping")

    unexpected = set(frontmatter) - ALLOWED_FRONTMATTER_KEYS
    if unexpected:
        raise SystemExit(f"Unexpected frontmatter keys: {', '.join(sorted(unexpected))}")

    name = str(frontmatter.get("name", "")).strip()
    description = str(frontmatter.get("description", "")).strip()
    if not name or not description:
        raise SystemExit("Frontmatter requires non-empty name and description")
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise SystemExit("Frontmatter name must be kebab-case")
    if "<" in description or ">" in description:
        raise SystemExit("Frontmatter description cannot contain angle brackets")


def ignore_filter(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES}


def publish(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, ignore=ignore_filter)

    for directory in [dest, *[path for path in dest.rglob("*") if path.is_dir()]]:
        directory.chmod(0o700)
    for file_path in [path for path in dest.rglob("*") if path.is_file()]:
        file_path.chmod(0o600)


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve()

    if source == dest:
        raise SystemExit("Source and destination must be different.")

    validate_skill_dir(source)
    publish(source, dest)
    validate_skill_dir(dest)

    print(f"Published skill to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
