#!/usr/bin/env python3
"""Compare two addendum layers before promoting an online manual snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two designer addendum layers without mutating either layer.")
    parser.add_argument("--base-layer", required=True, help="Current reference layer id or directory name.")
    parser.add_argument("--candidate-layer", required=True, help="New candidate layer id or directory name.")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parent.parent),
        help="Skill root directory.",
    )
    parser.add_argument("--output", choices=["markdown", "json"], default="markdown", help="Output format.")
    return parser.parse_args(argv)


def normalize_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value)).lower()


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else dict(fallback or {})


def resolve_manifest(addenda_root: Path, layer: str) -> dict[str, Any]:
    direct_manifest = addenda_root / layer / "manifest.json"
    if direct_manifest.exists():
        manifest = load_json(direct_manifest)
        manifest["_manifest_path"] = str(direct_manifest)
        manifest["_manifest_dir"] = str(direct_manifest.parent)
        return manifest

    for manifest_path in sorted(addenda_root.glob("*/manifest.json")):
        manifest = load_json(manifest_path)
        if str(manifest.get("layer_id", "")).strip() == layer:
            manifest["_manifest_path"] = str(manifest_path)
            manifest["_manifest_dir"] = str(manifest_path.parent)
            return manifest

    raise SystemExit(f"Addendum layer not found: {layer}")


def resolve_artifact_path(manifest: dict[str, Any], artifact_name: str) -> Path | None:
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return None
    raw_path = artifacts.get(artifact_name)
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return (Path(str(manifest["_manifest_dir"])) / path).resolve()


def resolve_source_path(manifest: dict[str, Any]) -> str:
    raw_path = manifest.get("source_file")
    if not raw_path:
        return ""
    path = Path(str(raw_path))
    if path.is_absolute():
        return str(path)
    return str((Path(str(manifest["_manifest_dir"])) / path).resolve())


def entry_title(entry: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = str(entry.get(field, "")).strip()
        if value:
            return value
    return ""


def collect_titles(payload: dict[str, Any], list_key: str, fields: tuple[str, ...]) -> dict[str, str]:
    titles: dict[str, str] = {}
    for entry in payload.get(list_key, []):
        if not isinstance(entry, dict):
            continue
        title = entry_title(entry, fields)
        key = normalize_key(title)
        if title and key and key not in titles:
            titles[key] = title
    return titles


def compare_title_sets(base_titles: dict[str, str], candidate_titles: dict[str, str]) -> dict[str, Any]:
    base_keys = set(base_titles)
    candidate_keys = set(candidate_titles)
    added = sorted(candidate_keys - base_keys, key=lambda key: candidate_titles[key])
    removed = sorted(base_keys - candidate_keys, key=lambda key: base_titles[key])
    return {
        "base_count": len(base_titles),
        "candidate_count": len(candidate_titles),
        "common_count": len(base_keys & candidate_keys),
        "added": [candidate_titles[key] for key in added],
        "removed": [base_titles[key] for key in removed],
    }


def compare_artifact_titles(
    *,
    base_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    artifact_name: str,
    list_key: str,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    base_path = resolve_artifact_path(base_manifest, artifact_name)
    candidate_path = resolve_artifact_path(candidate_manifest, artifact_name)
    base_payload = load_json(base_path, {}) if base_path else {}
    candidate_payload = load_json(candidate_path, {}) if candidate_path else {}
    result = compare_title_sets(
        collect_titles(base_payload, list_key, fields),
        collect_titles(candidate_payload, list_key, fields),
    )
    result["base_file"] = str(base_path or "")
    result["candidate_file"] = str(candidate_path or "")
    return result


def coverage_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    path = resolve_artifact_path(manifest, "coverage_ledger_file")
    payload = load_json(path, {}) if path else {}
    return {
        "file": str(path or ""),
        "entry_count": payload.get("entry_count", 0),
        "status_counts": payload.get("status_counts", {}),
        "publish_target_counts": payload.get("publish_target_counts", {}),
    }


def build_layer_diff(skill_dir: Path, base_layer: str, candidate_layer: str) -> dict[str, Any]:
    addenda_root = skill_dir / "references" / "addenda"
    base_manifest = resolve_manifest(addenda_root, base_layer)
    candidate_manifest = resolve_manifest(addenda_root, candidate_layer)

    return {
        "base_layer": {
            "layer_id": base_manifest.get("layer_id", ""),
            "layer_name": base_manifest.get("layer_name", ""),
            "status": base_manifest.get("status", ""),
            "manifest": base_manifest.get("_manifest_path", ""),
            "source_file": resolve_source_path(base_manifest),
        },
        "candidate_layer": {
            "layer_id": candidate_manifest.get("layer_id", ""),
            "layer_name": candidate_manifest.get("layer_name", ""),
            "status": candidate_manifest.get("status", ""),
            "manifest": candidate_manifest.get("_manifest_path", ""),
            "source_file": resolve_source_path(candidate_manifest),
        },
        "rules_index": compare_artifact_titles(
            base_manifest=base_manifest,
            candidate_manifest=candidate_manifest,
            artifact_name="rules_index_file",
            list_key="entries",
            fields=("clean_title", "heading", "normalized_rule"),
        ),
        "runtime_rules": compare_artifact_titles(
            base_manifest=base_manifest,
            candidate_manifest=candidate_manifest,
            artifact_name="runtime_rules_file",
            list_key="rules",
            fields=("title", "normalized_rule", "detail"),
        ),
        "knowledge_layer": compare_artifact_titles(
            base_manifest=base_manifest,
            candidate_manifest=candidate_manifest,
            artifact_name="knowledge_layer_file",
            list_key="entries",
            fields=("topic", "answerable_summary"),
        ),
        "coverage_ledger": {
            "base": coverage_summary(base_manifest),
            "candidate": coverage_summary(candidate_manifest),
        },
    }


def render_title_change_section(title: str, payload: dict[str, Any]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        f"- base_count: {payload['base_count']}",
        f"- candidate_count: {payload['candidate_count']}",
        f"- common_count: {payload['common_count']}",
        f"- added_count: {len(payload['added'])}",
        f"- removed_count: {len(payload['removed'])}",
        "",
    ]
    if payload["added"]:
        lines.append("### Added")
        lines.append("")
        lines.extend(f"- {title}" for title in payload["added"][:50])
        if len(payload["added"]) > 50:
            lines.append(f"- ... {len(payload['added']) - 50} more")
        lines.append("")
    if payload["removed"]:
        lines.append("### Removed")
        lines.append("")
        lines.extend(f"- {title}" for title in payload["removed"][:50])
        if len(payload["removed"]) > 50:
            lines.append(f"- ... {len(payload['removed']) - 50} more")
        lines.append("")
    return lines


def render_markdown(diff: dict[str, Any]) -> str:
    base = diff["base_layer"]
    candidate = diff["candidate_layer"]
    lines = [
        "# Addendum Layer Diff",
        "",
        "## Layers",
        "",
        f"- base: {base['layer_id']} / {base['status']} / {base['source_file']}",
        f"- candidate: {candidate['layer_id']} / {candidate['status']} / {candidate['source_file']}",
        "",
    ]
    lines.extend(render_title_change_section("Rules Index", diff["rules_index"]))
    lines.extend(render_title_change_section("Runtime Rules", diff["runtime_rules"]))
    lines.extend(render_title_change_section("Knowledge Layer", diff["knowledge_layer"]))
    lines.extend(
        [
            "## Coverage Ledger",
            "",
            f"- base_entry_count: {diff['coverage_ledger']['base']['entry_count']}",
            f"- candidate_entry_count: {diff['coverage_ledger']['candidate']['entry_count']}",
            f"- base_status_counts: {json.dumps(diff['coverage_ledger']['base']['status_counts'], ensure_ascii=False, sort_keys=True)}",
            f"- candidate_status_counts: {json.dumps(diff['coverage_ledger']['candidate']['status_counts'], ensure_ascii=False, sort_keys=True)}",
            f"- base_publish_target_counts: {json.dumps(diff['coverage_ledger']['base']['publish_target_counts'], ensure_ascii=False, sort_keys=True)}",
            f"- candidate_publish_target_counts: {json.dumps(diff['coverage_ledger']['candidate']['publish_target_counts'], ensure_ascii=False, sort_keys=True)}",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    diff = build_layer_diff(
        Path(args.skill_dir).expanduser().resolve(),
        args.base_layer,
        args.candidate_layer,
    )
    if args.output == "json":
        print(json.dumps(diff, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(diff))
    return 0


if __name__ == "__main__":
    sys.exit(main())
