#!/usr/bin/env python3
"""Build an independent addendum layer from one designer rule source."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)


def build_seed_knowledge_layer(*, layer_id: str, layer_name: str) -> dict[str, Any]:
    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "entries": [],
    }


def build_status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "unresolved")).strip() or "unresolved"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def entry_matches_override(entry: dict[str, Any], override: dict[str, Any]) -> bool:
    page = override.get("page")
    if page is not None and entry.get("page") != page:
        return False
    current_status = str(override.get("current_status", "")).strip()
    if current_status and str(entry.get("status", "")).strip() != current_status:
        return False
    domain = str(override.get("domain", "")).strip()
    if domain and str(entry.get("domain", "")).strip() != domain:
        return False
    topic = str(entry.get("topic", ""))
    topic_exact = str(override.get("topic", "")).strip()
    if topic_exact and topic != topic_exact:
        return False
    topic_contains = str(override.get("topic_contains", "")).strip()
    if topic_contains and topic_contains not in topic:
        return False
    summary = str(entry.get("summary", ""))
    summary_contains = str(override.get("summary_contains", "")).strip()
    if summary_contains and summary_contains not in summary:
        return False
    return True


def apply_coverage_ledger_overrides(payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    entries = [dict(entry) for entry in payload.get("entries", []) if isinstance(entry, dict)]

    for override in overrides.get("overrides", []):
        if not isinstance(override, dict):
            continue
        update_fields = {
            key: value
            for key, value in override.items()
            if key not in {"page", "current_status", "domain", "topic", "topic_contains", "summary_contains"} and value is not None
        }
        if not update_fields:
            continue
        for entry in entries:
            if entry_matches_override(entry, override):
                entry.update(update_fields)

    for extra_entry in overrides.get("append_entries", []):
        if isinstance(extra_entry, dict):
            entries.append(dict(extra_entry))

    payload = dict(payload)
    payload["entries"] = entries
    payload["entry_count"] = len(entries)
    payload["status_counts"] = build_status_counts(entries)
    return payload


def build_seed_coverage_ledger(
    *,
    layer_id: str,
    layer_name: str,
    index_path: Path,
    runtime_rules_path: Path,
    audit_csv_path: Path | None = None,
) -> dict[str, Any]:
    if audit_csv_path and audit_csv_path.exists():
        entries: list[dict[str, Any]] = []
        with audit_csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                pricing_relevant = str(row.get("pricing_relevant", "")).strip().lower() == "true"
                source_status = str(row.get("status", "")).strip()
                if source_status == "included_runtime":
                    status = "runtime_hard_rule"
                elif source_status == "excluded_non_pricing":
                    status = "excluded_background"
                else:
                    status = "unresolved"
                entries.append(
                    {
                        "page": int(row.get("page", "0") or 0),
                        "topic": str(row.get("clean_title", "")).strip() or str(row.get("heading", "")).strip(),
                        "status": status,
                        "domain": row.get("domain"),
                        "pricing_relevant": pricing_relevant,
                        "rule_type": row.get("rule_type"),
                        "summary": str(row.get("normalized_rule", "")).strip(),
                        "note": str(row.get("reason", "")).strip(),
                        "source": "pdf_coverage_audit",
                    }
                )

        return {
            "layer_id": layer_id,
            "layer_name": layer_name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "entry_count": len(entries),
            "status_counts": build_status_counts(entries),
            "entries": entries,
        }

    index_payload = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"entries": []}
    runtime_payload = json.loads(runtime_rules_path.read_text(encoding="utf-8")) if runtime_rules_path.exists() else {"rules": []}
    runtime_titles = {str(rule.get("title", "")).strip() for rule in runtime_payload.get("rules", []) if str(rule.get("title", "")).strip()}

    entries: list[dict[str, Any]] = []
    for entry in index_payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("clean_title", "")).strip()
        normalized_rule = str(entry.get("normalized_rule", "")).strip()
        pricing_relevant = bool(entry.get("pricing_relevant"))
        if title and title in runtime_titles:
            status = "runtime_hard_rule"
        elif pricing_relevant:
            status = "unresolved"
        else:
            status = "excluded_background"
        entries.append(
            {
                "page": entry.get("page"),
                "topic": title or str(entry.get("heading", "")).strip(),
                "status": status,
                "domain": entry.get("domain"),
                "summary": normalized_rule,
                "source": "rules_index_seed",
            }
        )

    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(entries),
        "status_counts": build_status_counts(entries),
        "entries": entries,
    }


def build_layer_manifest(
    *,
    layer_id: str,
    layer_name: str,
    source_file: Path,
    candidate_path: Path,
    index_path: Path,
    runtime_rules_path: Path,
    knowledge_layer_path: Path,
    coverage_ledger_path: Path,
    coverage_ledger_overrides_path: Path | None,
    source_markdown_path: Path,
    drafts_dir: Path,
    manifest_dir: Path,
    status: str = "ACTIVE",
) -> dict[str, object]:
    drafts_manifest_path = drafts_dir / "manifest.json"
    drafts_manifest = {}
    if drafts_manifest_path.exists():
        drafts_manifest = json.loads(drafts_manifest_path.read_text(encoding="utf-8"))

    artifacts: dict[str, str] = {
        "rules_candidate_file": relativize_path(candidate_path, manifest_dir=manifest_dir),
        "rules_index_file": relativize_path(index_path, manifest_dir=manifest_dir),
        "runtime_rules_file": relativize_path(runtime_rules_path, manifest_dir=manifest_dir),
        "knowledge_layer_file": relativize_path(knowledge_layer_path, manifest_dir=manifest_dir),
        "coverage_ledger_file": relativize_path(coverage_ledger_path, manifest_dir=manifest_dir),
        "rules_source_markdown_file": relativize_path(source_markdown_path, manifest_dir=manifest_dir),
        "rules_drafts_dir": relativize_path(drafts_dir, manifest_dir=manifest_dir),
        "rules_drafts_manifest_file": relativize_path(drafts_manifest_path, manifest_dir=manifest_dir),
    }
    if coverage_ledger_overrides_path and coverage_ledger_overrides_path.exists():
        artifacts["coverage_ledger_overrides_file"] = relativize_path(
            coverage_ledger_overrides_path,
            manifest_dir=manifest_dir,
        )

    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "status": status,
        "source_file": relativize_path(source_file, manifest_dir=manifest_dir),
        "mutates_base_rules": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "artifacts": artifacts,
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
    knowledge_layer_path = reports_dir / "knowledge-layer.json"
    coverage_ledger_path = reports_dir / "coverage-ledger.json"
    coverage_ledger_overrides_path = reports_dir / "coverage-ledger-overrides.json"
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

    write_json(
        knowledge_layer_path,
        build_seed_knowledge_layer(layer_id=args.layer_id, layer_name=args.layer_name),
    )
    write_json(
        coverage_ledger_path,
        apply_coverage_ledger_overrides(
            build_seed_coverage_ledger(
                layer_id=args.layer_id,
                layer_name=args.layer_name,
                index_path=index_path,
                runtime_rules_path=runtime_rules_path,
                audit_csv_path=reports_dir / "pdf-coverage-audit.csv",
            ),
            json.loads((reports_dir / "coverage-ledger-overrides.json").read_text(encoding="utf-8"))
            if (reports_dir / "coverage-ledger-overrides.json").exists()
            else {},
        ),
    )

    layer_dir = addenda_root / layer_slug
    manifest = build_layer_manifest(
        layer_id=args.layer_id,
        layer_name=args.layer_name,
        source_file=archived_source,
        candidate_path=candidate_path,
        index_path=index_path,
        runtime_rules_path=runtime_rules_path,
        knowledge_layer_path=knowledge_layer_path,
        coverage_ledger_path=coverage_ledger_path,
        coverage_ledger_overrides_path=coverage_ledger_overrides_path,
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
