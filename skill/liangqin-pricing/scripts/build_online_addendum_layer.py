#!/usr/bin/env python3
"""Build a paused addendum layer from a DingTalk workspace snapshot."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an addendum layer from a local DingTalk designer-manual snapshot.")
    parser.add_argument("--snapshot-dir", required=True, help="Directory produced by snapshot_dingtalk_designer_manual.py.")
    parser.add_argument("--layer-id", required=True, help="Stable layer id.")
    parser.add_argument("--layer-name", required=True, help="Human readable layer name.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--status", default="PAUSED", choices=["ACTIVE", "PAUSED"], help="Layer status.")
    parser.add_argument(
        "--ocr-min-chars",
        type=int,
        default=-1,
        help="OCR threshold for PDF pages. Negative disables OCR and uses the PDF text layer only.",
    )
    parser.add_argument(
        "--ocr-backend",
        choices=["tesseract", "paddleocr"],
        default="paddleocr",
        help="OCR backend used when PDF pages need visual text extraction.",
    )
    parser.add_argument("--paddleocr-lang", default="ch", help="Language hint passed to PaddleOCR when used.")
    parser.add_argument("--paddleocr-device", default="cpu", help="Device hint passed to PaddleOCR when used.")
    return parser.parse_args(argv)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_step(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)


def attach_source_metadata(entry: dict[str, Any], artifact: dict[str, Any], *, source_page: int | None = None) -> dict[str, Any]:
    enriched = dict(entry)
    enriched["source_path"] = artifact.get("path", "")
    enriched["source_title"] = artifact.get("name", "")
    enriched["source_node_id"] = artifact.get("nodeId", "")
    enriched["source_local_path"] = artifact.get("local_path", "")
    if source_page is not None:
        enriched["source_page"] = source_page
    return enriched


def remap_page_number(*, artifact_index: int, local_page: int) -> int:
    return artifact_index * 1000 + max(local_page, 1)


def build_markdown_sections(
    *,
    extract_module: Any,
    artifact: dict[str, Any],
    artifact_index: int,
) -> list[dict[str, Any]]:
    path = Path(str(artifact.get("local_path", "")))
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections = extract_module.sectionize_lines(
        lines,
        page=remap_page_number(artifact_index=artifact_index, local_page=1),
        extract_method="dingtalk_markdown",
    )
    return [attach_source_metadata(section, artifact, source_page=1) for section in sections]


def build_pdf_payload(
    *,
    extract_module: Any,
    artifact: dict[str, Any],
    artifact_index: int,
    ocr_min_chars: int,
    ocr_backend: str,
    paddleocr_lang: str,
    paddleocr_device: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = Path(str(artifact.get("local_path", "")))
    payload = extract_module.build_candidate_payload(
        path,
        ocr_min_chars=ocr_min_chars,
        ocr_backend=ocr_backend,
        paddleocr_lang=paddleocr_lang,
        paddleocr_device=paddleocr_device,
    )
    pages: list[dict[str, Any]] = []
    for page in payload.get("pages", []):
        if not isinstance(page, dict):
            continue
        local_page = int(page.get("page", 1) or 1)
        remapped = attach_source_metadata(page, artifact, source_page=local_page)
        remapped["page"] = remap_page_number(artifact_index=artifact_index, local_page=local_page)
        pages.append(remapped)

    sections: list[dict[str, Any]] = []
    for section in payload.get("sections", []):
        if not isinstance(section, dict):
            continue
        local_page = int(section.get("page", 1) or 1)
        remapped = attach_source_metadata(section, artifact, source_page=local_page)
        remapped["page"] = remap_page_number(artifact_index=artifact_index, local_page=local_page)
        sections.append(remapped)
    return pages, sections


def load_snapshot_artifacts(snapshot_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = snapshot_dir / "snapshot-manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing snapshot manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = [artifact for artifact in manifest.get("artifacts", []) if isinstance(artifact, dict)]
    return manifest, artifacts


def build_combined_candidate_payload(
    *,
    snapshot_dir: Path,
    extract_module: Any,
    ocr_min_chars: int,
    ocr_backend: str = "paddleocr",
    paddleocr_lang: str = "ch",
    paddleocr_device: str = "cpu",
) -> dict[str, Any]:
    snapshot_manifest, artifacts = load_snapshot_artifacts(snapshot_dir)
    sections: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for artifact_index, artifact in enumerate(artifacts, start=1):
        snapshot_type = str(artifact.get("snapshot_type", "")).strip()
        local_path = Path(str(artifact.get("local_path", "")))
        if not local_path.exists():
            skipped.append({**artifact, "reason": "missing_local_path"})
            continue
        if snapshot_type == "markdown" or local_path.suffix.lower() == ".md":
            sections.extend(
                build_markdown_sections(
                    extract_module=extract_module,
                    artifact=artifact,
                    artifact_index=artifact_index,
                )
            )
        elif local_path.suffix.lower() == ".pdf":
            pdf_pages, pdf_sections = build_pdf_payload(
                extract_module=extract_module,
                artifact=artifact,
                artifact_index=artifact_index,
                ocr_min_chars=ocr_min_chars,
                ocr_backend=ocr_backend,
                paddleocr_lang=paddleocr_lang,
                paddleocr_device=paddleocr_device,
            )
            pages.extend(pdf_pages)
            sections.extend(pdf_sections)
        else:
            skipped.append({**artifact, "reason": f"unsupported_suffix:{local_path.suffix}"})

    return {
        "source_file": str(snapshot_dir.resolve()),
        "source_format": "dingtalk_workspace_snapshot",
        "snapshot_manifest_file": str((snapshot_dir / "snapshot-manifest.json").resolve()),
        "snapshot_workspace": snapshot_manifest.get("workspace", ""),
        "artifact_count": len(artifacts),
        "processed_artifact_count": len(artifacts) - len(skipped),
        "skipped_artifact_count": len(skipped),
        "skipped_artifacts": skipped,
        "ocr_backend": ocr_backend if ocr_min_chars >= 0 else "disabled",
        "page_count": len(pages),
        "sections": sections,
        "pages": pages,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    scripts_dir = skill_dir / "scripts"
    snapshot_dir = Path(args.snapshot_dir).expanduser().resolve()

    extract_module = load_module("extract_rules_candidate_for_snapshot", scripts_dir / "extract_rules_candidate.py")
    update_module = load_module("update_addendum_layer_for_snapshot", scripts_dir / "update_addendum_layer.py")

    layer_slug = update_module.slugify_layer_id(args.layer_id)
    reports_dir = skill_dir / "reports" / "addenda" / layer_slug
    layer_dir = skill_dir / "references" / "addenda" / layer_slug
    reports_dir.mkdir(parents=True, exist_ok=True)
    layer_dir.mkdir(parents=True, exist_ok=True)

    candidate_path = reports_dir / "rules-candidate.json"
    source_markdown_path = reports_dir / "rules-source.md"
    index_path = reports_dir / "rules-index.json"
    index_markdown_path = reports_dir / "rules-index.md"
    runtime_rules_path = reports_dir / "runtime-rules.json"
    runtime_rules_overrides_path = reports_dir / "runtime-rules-overrides.json"
    knowledge_layer_path = reports_dir / "knowledge-layer.json"
    knowledge_layer_overrides_path = reports_dir / "knowledge-layer-overrides.json"
    coverage_ledger_path = reports_dir / "coverage-ledger.json"
    coverage_ledger_overrides_path = reports_dir / "coverage-ledger-overrides.json"
    drafts_dir = reports_dir / "rules-drafts"

    payload = build_combined_candidate_payload(
        snapshot_dir=snapshot_dir,
        extract_module=extract_module,
        ocr_min_chars=args.ocr_min_chars,
        ocr_backend=args.ocr_backend,
        paddleocr_lang=args.paddleocr_lang,
        paddleocr_device=args.paddleocr_device,
    )
    write_json(candidate_path, payload)
    extract_module.write_markdown_output(source_markdown_path, payload)

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

    raw_runtime_payload = json.loads(runtime_rules_path.read_text(encoding="utf-8")) if runtime_rules_path.exists() else {}
    coverage_ledger_payload = update_module.finalize_coverage_ledger(
        update_module.apply_coverage_ledger_overrides(
            update_module.build_seed_coverage_ledger(
                layer_id=args.layer_id,
                layer_name=args.layer_name,
                index_path=index_path,
                runtime_rules_path=runtime_rules_path,
            ),
            json.loads(coverage_ledger_overrides_path.read_text(encoding="utf-8"))
            if coverage_ledger_overrides_path.exists()
            else {},
        )
    )
    write_json(coverage_ledger_path, coverage_ledger_payload)
    write_json(
        runtime_rules_path,
        update_module.apply_runtime_rules_overrides(
            update_module.build_published_runtime_rules(raw_runtime_payload, coverage_ledger_payload),
            json.loads(runtime_rules_overrides_path.read_text(encoding="utf-8"))
            if runtime_rules_overrides_path.exists()
            else {},
        ),
    )
    write_json(
        knowledge_layer_path,
        update_module.apply_knowledge_layer_overrides(
            update_module.build_published_knowledge_layer(
                layer_id=args.layer_id,
                layer_name=args.layer_name,
                coverage_ledger=coverage_ledger_payload,
            ),
            json.loads(knowledge_layer_overrides_path.read_text(encoding="utf-8"))
            if knowledge_layer_overrides_path.exists()
            else {},
        ),
    )

    manifest = update_module.build_layer_manifest(
        layer_id=args.layer_id,
        layer_name=args.layer_name,
        source_file=snapshot_dir,
        candidate_path=candidate_path,
        index_path=index_path,
        runtime_rules_path=runtime_rules_path,
        runtime_rules_overrides_path=runtime_rules_overrides_path,
        knowledge_layer_path=knowledge_layer_path,
        knowledge_layer_overrides_path=knowledge_layer_overrides_path,
        coverage_ledger_path=coverage_ledger_path,
        coverage_ledger_overrides_path=coverage_ledger_overrides_path,
        source_markdown_path=source_markdown_path,
        drafts_dir=drafts_dir,
        manifest_dir=layer_dir,
        status=args.status,
    )
    manifest["source_kind"] = "dingtalk_workspace_snapshot"
    manifest["snapshot_manifest_file"] = update_module.relativize_path(
        snapshot_dir / "snapshot-manifest.json",
        manifest_dir=layer_dir,
    )
    update_module.write_manifest(layer_dir, manifest)

    print(
        json.dumps(
            {
                "layer_dir": str(layer_dir),
                "reports_dir": str(reports_dir),
                "status": args.status,
                "candidate_sections": len(payload.get("sections", [])),
                "candidate_pages": len(payload.get("pages", [])),
                "skipped_artifacts": payload.get("skipped_artifact_count", 0),
                "runtime_rules": json.loads(runtime_rules_path.read_text(encoding="utf-8")).get("rule_count", 0),
                "knowledge_entries": len(json.loads(knowledge_layer_path.read_text(encoding="utf-8")).get("entries", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
