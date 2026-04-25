from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from job_models import BatchPlan, ReviewJob, SourceAsset  # noqa: E402
from text_preview import extract_text_preview  # noqa: E402


DEFAULT_MANIFEST = {
    "source_type": "manual_batch",
    "source_channel": "manual",
    "requested_actions": ["audit", "replay"],
    "operator": "",
    "received_at": "",
    "notes": "",
}

PRIMARY_DRAWING_HINTS = ("图纸", "附图", "drawing", "cad", "结构图", "节点")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
TEXT_SUFFIXES = {".txt", ".md", ".json", ".csv", ".tsv"}
DOC_SUFFIXES = {".docx", ".pdf"}


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "item"


def load_batch_manifest(batch_dir: Path) -> dict[str, Any]:
    manifest_path = batch_dir / "manifest.json"
    if not manifest_path.exists():
        manifest = dict(DEFAULT_MANIFEST)
        manifest["source_batch_id"] = batch_dir.name
        return manifest

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest.json must be a JSON object: {manifest_path}")

    manifest = dict(DEFAULT_MANIFEST)
    manifest.update(payload)
    manifest["source_batch_id"] = str(
        manifest.get("source_batch_id") or manifest.get("batch_id") or batch_dir.name
    ).strip() or batch_dir.name
    requested_actions = manifest.get("requested_actions") or DEFAULT_MANIFEST["requested_actions"]
    manifest["requested_actions"] = [str(item).strip() for item in requested_actions if str(item).strip()]
    if not manifest["requested_actions"]:
        manifest["requested_actions"] = list(DEFAULT_MANIFEST["requested_actions"])
    return manifest


def _classify_asset(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    normalized_name = path.name.lower()

    if suffix in DOC_SUFFIXES:
        if any(keyword in normalized_name for keyword in PRIMARY_DRAWING_HINTS):
            return "document", "drawing_attachment"
        return "document", "primary_contract"
    if suffix in IMAGE_SUFFIXES:
        return "image", "visual_attachment"
    if suffix in TEXT_SUFFIXES:
        return "text", "note_attachment"
    return "binary", "supporting_attachment"


def _build_asset(path: Path, *, batch_dir: Path, asset_index: int) -> SourceAsset:
    media_kind, role_hint = _classify_asset(path)
    text_preview, text_extract_method = extract_text_preview(path)
    needs_ocr = bool(
        media_kind == "image"
        or (
            path.suffix.lower() == ".pdf"
            and role_hint in {"primary_contract", "drawing_attachment"}
        )
    )
    return SourceAsset(
        asset_id=f"asset-{asset_index:03d}",
        source_path=str(path.resolve()),
        relative_path=str(path.relative_to(batch_dir)),
        file_name=path.name,
        extension=path.suffix.lower(),
        media_kind=media_kind,
        role_hint=role_hint,
        text_preview=text_preview,
        text_extract_method=text_extract_method,
        metadata={
            "size_bytes": path.stat().st_size,
            "preview_available": bool(text_preview),
            "needs_ocr": needs_ocr,
        },
    )


def _explicit_job_groups(batch_dir: Path, manifest: dict[str, Any]) -> list[tuple[str, list[Path], dict[str, Any]]]:
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return []

    explicit_groups: list[tuple[str, list[Path], dict[str, Any]]] = []
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            continue
        raw_paths = job.get("paths") or []
        resolved_paths = [(batch_dir / str(relative_path)) for relative_path in raw_paths]
        missing = [str(path) for path in resolved_paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"manifest job references missing files: {missing}")
        group_key = str(job.get("job_key") or job.get("group_name") or f"job-{index:03d}").strip() or f"job-{index:03d}"
        explicit_groups.append((group_key, resolved_paths, dict(job)))
    return explicit_groups


def _autodiscover_job_groups(batch_dir: Path) -> list[tuple[str, list[Path], dict[str, Any]]]:
    raw_dir = batch_dir / "raw"
    search_root = raw_dir if raw_dir.exists() else batch_dir

    groups: list[tuple[str, list[Path], dict[str, Any]]] = []
    subdirs = sorted(
        path for path in search_root.iterdir()
        if path.is_dir() and path.name != "raw"
    )
    for directory in subdirs:
        files = sorted(path for path in directory.rglob("*") if path.is_file())
        if files:
            groups.append((directory.name, files, {"mode": "subdir_bundle"}))

    direct_files = sorted(path for path in search_root.iterdir() if path.is_file())
    for file_path in direct_files:
        groups.append((file_path.stem, [file_path], {"mode": "single_file"}))

    if not groups:
        if raw_dir.exists():
            raise FileNotFoundError(f"raw directory does not contain any files or subdirectories: {raw_dir}")
        raise FileNotFoundError(
            f"batch directory does not contain a usable raw/ directory or direct files: {batch_dir}"
        )
    return groups


def build_review_jobs(batch_dir: Path) -> BatchPlan:
    batch_dir = batch_dir.expanduser().resolve()
    manifest = load_batch_manifest(batch_dir)
    groups = _explicit_job_groups(batch_dir, manifest) or _autodiscover_job_groups(batch_dir)

    batch_id = str(manifest["source_batch_id"]).strip()
    jobs: list[ReviewJob] = []
    warnings: list[str] = []
    for index, (group_key, file_paths, group_metadata) in enumerate(groups, start=1):
        assets = [_build_asset(path, batch_dir=batch_dir, asset_index=asset_index) for asset_index, path in enumerate(file_paths, start=1)]
        if not any(asset.role_hint == "primary_contract" for asset in assets):
            warnings.append(f"{group_key} 当前没有主合同候选，后续需要人工确认或补文件。")
        jobs.append(
            ReviewJob(
                job_id=f"{slugify(batch_id)}-{index:03d}",
                batch_id=batch_id,
                group_key=group_key,
                source_type=str(manifest["source_type"]).strip() or "manual_batch",
                source_channel=str(manifest["source_channel"]).strip() or "manual",
                requested_actions=list(manifest["requested_actions"]),
                assets=assets,
                metadata={
                    "operator": str(manifest.get("operator", "")).strip(),
                    "received_at": str(manifest.get("received_at", "")).strip(),
                    "notes": str(manifest.get("notes", "")).strip(),
                    "group_metadata": group_metadata,
                },
            )
        )

    return BatchPlan(
        batch_id=batch_id,
        batch_dir=batch_dir,
        source_type=str(manifest["source_type"]).strip() or "manual_batch",
        source_channel=str(manifest["source_channel"]).strip() or "manual",
        requested_actions=list(manifest["requested_actions"]),
        jobs=jobs,
        manifest=manifest,
        warnings=warnings,
    )
