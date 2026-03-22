#!/usr/bin/env python3
"""Build an independent addendum layer from one designer rule source."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a standalone designer addendum layer without mutating base rules.")
    parser.add_argument("--rules-source", required=True, help="Path to the addendum source file (docx/pdf).")
    parser.add_argument("--layer-id", required=True, help="Stable layer id, for example designer-manual-a.")
    parser.add_argument("--layer-name", required=True, help="Human readable layer name.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--status", default="ACTIVE", choices=["ACTIVE", "PAUSED"], help="Layer status.")
    return parser.parse_args(argv)


def slugify_layer_id(layer_id: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in layer_id).strip("-")
    return slug or "designer-addendum"


def run_step(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def relativize_path(path: Path, *, manifest_dir: Path) -> str:
    try:
        return os.path.relpath(path, start=manifest_dir)
    except ValueError:
        return str(path)


def build_layer_manifest(
    *,
    layer_id: str,
    layer_name: str,
    source_file: Path,
    candidate_path: Path,
    index_path: Path,
    runtime_rules_path: Path,
    source_markdown_path: Path,
    drafts_dir: Path,
    manifest_dir: Path,
    status: str = "ACTIVE",
) -> dict[str, object]:
    drafts_manifest_path = drafts_dir / "manifest.json"
    drafts_manifest = {}
    if drafts_manifest_path.exists():
        drafts_manifest = json.loads(drafts_manifest_path.read_text(encoding="utf-8"))

    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "status": status,
        "source_file": relativize_path(source_file, manifest_dir=manifest_dir),
        "mutates_base_rules": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "artifacts": {
            "rules_candidate_file": relativize_path(candidate_path, manifest_dir=manifest_dir),
            "rules_index_file": relativize_path(index_path, manifest_dir=manifest_dir),
            "runtime_rules_file": relativize_path(runtime_rules_path, manifest_dir=manifest_dir),
            "rules_source_markdown_file": relativize_path(source_markdown_path, manifest_dir=manifest_dir),
            "rules_drafts_dir": relativize_path(drafts_dir, manifest_dir=manifest_dir),
            "rules_drafts_manifest_file": relativize_path(drafts_manifest_path, manifest_dir=manifest_dir),
        },
        "draft_domains": drafts_manifest.get("domains", []),
    }


def write_manifest(output_dir: Path, manifest: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    temp_path = manifest_path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, manifest_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    scripts_dir = skill_dir / "scripts"
    addenda_root = skill_dir / "references" / "addenda"
    archived_root = skill_dir / "sources" / "archived" / "addenda"
    reports_root = skill_dir / "reports" / "addenda"

    layer_slug = slugify_layer_id(args.layer_id)
    source_path = Path(args.rules_source).expanduser().resolve()
    archived_dir = archived_root / layer_slug
    archived_dir.mkdir(parents=True, exist_ok=True)
    archived_source = archived_dir / source_path.name
    shutil.copy2(source_path, archived_source)

    reports_dir = reports_root / layer_slug
    reports_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = reports_dir / "rules-candidate.json"
    source_markdown_path = reports_dir / "rules-source.md"
    index_path = reports_dir / "rules-index.json"
    index_markdown_path = reports_dir / "rules-index.md"
    runtime_rules_path = reports_dir / "runtime-rules.json"
    drafts_dir = reports_dir / "rules-drafts"

    run_step(
        [
            sys.executable,
            str(scripts_dir / "extract_rules_candidate.py"),
            "--input",
            str(source_path),
            "--output",
            str(candidate_path),
            "--markdown-output",
            str(source_markdown_path),
        ]
    )
    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_rules_index.py"),
            "--input",
            str(candidate_path),
            "--output",
            str(index_path),
            "--markdown-output",
            str(index_markdown_path),
        ]
    )
    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_addendum_runtime_rules.py"),
            "--input",
            str(index_path),
            "--output",
            str(runtime_rules_path),
            "--layer-id",
            args.layer_id,
            "--layer-name",
            args.layer_name,
        ]
    )
    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_rules_drafts.py"),
            "--input",
            str(index_path),
            "--output-dir",
            str(drafts_dir),
        ]
    )

    layer_dir = addenda_root / layer_slug
    manifest = build_layer_manifest(
        layer_id=args.layer_id,
        layer_name=args.layer_name,
        source_file=archived_source,
        candidate_path=candidate_path,
        index_path=index_path,
        runtime_rules_path=runtime_rules_path,
        source_markdown_path=source_markdown_path,
        drafts_dir=drafts_dir,
        manifest_dir=layer_dir,
        status=args.status,
    )
    write_manifest(layer_dir, manifest)

    print(f"Built addendum layer at {layer_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
