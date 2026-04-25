from __future__ import annotations

import json
import os
import subprocess
import hashlib
import re
import shutil
import sys
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Iterable

from attachment_section import resolve_attachment_anchor_page
from batch_runtime import ensure_dir, write_json, write_markdown
from job_models import SourceAsset
from text_preview import normalize_preview

try:
    from PyPDF2 import PdfReader, PdfWriter
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    PdfReader = None
    PdfWriter = None


@dataclass(frozen=True)
class ExtractionConfig:
    ocr_backend: str = "paddleocr"
    paddleocr_lang: str = "ch"
    paddleocr_device: str = "cpu"
    preview_limit_chars: int = 1600
    force_ocr_for_documents: bool = False


def extract_asset(
    asset: SourceAsset,
    *,
    job_dir: Path,
    config: ExtractionConfig,
) -> dict[str, Any]:
    source_path = Path(str((asset.metadata or {}).get("staged_input_path") or asset.source_path))
    if not source_path.exists():
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": config.ocr_backend,
            "reason": "source_missing",
            "error": f"source file does not exist: {source_path}",
        }

    if not bool((asset.metadata or {}).get("needs_ocr")) and not (
        config.force_ocr_for_documents and asset.media_kind == "document"
    ):
        return {
            "asset_id": asset.asset_id,
            "status": "not_needed",
            "backend": "native",
            "reason": "native_preview_available",
        }

    if config.ocr_backend == "disabled":
        return {
            "asset_id": asset.asset_id,
            "status": "skipped",
            "backend": "disabled",
            "reason": "ocr_backend_disabled",
        }

    if config.ocr_backend not in {"paddleocr", "mineru"}:
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": config.ocr_backend,
            "reason": "unsupported_ocr_backend",
            "error": f"unsupported ocr backend: {config.ocr_backend}",
        }

    ocr_source_path, ocr_context = _prepare_ocr_source_path(asset, source_path=source_path, job_dir=job_dir)
    if config.ocr_backend == "paddleocr":
        cached_record = _load_cached_paddleocr_record(
            asset,
            source_path=ocr_source_path,
            job_dir=job_dir,
            config=config,
        )
        if cached_record is not None:
            for key, value in ocr_context.items():
                if value is None or value == "":
                    continue
                cached_record.setdefault(key, value)
            return cached_record
        record = _extract_with_paddleocr(asset, source_path=ocr_source_path, job_dir=job_dir, config=config)
        _store_cached_paddleocr_record(
            record,
            source_path=ocr_source_path,
            config=config,
        )
    else:
        record = _extract_with_mineru(asset, source_path=ocr_source_path, job_dir=job_dir, config=config)

    for key, value in ocr_context.items():
        if value is None or value == "":
            continue
        record.setdefault(key, value)
    return record


def _extract_with_paddleocr(
    asset: SourceAsset,
    *,
    source_path: Path,
    job_dir: Path,
    config: ExtractionConfig,
) -> dict[str, Any]:
    try:
        from paddleocr import PPStructureV3
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dependency
        external_record = _extract_with_external_paddleocr_python(
            asset,
            source_path=source_path,
            job_dir=job_dir,
            config=config,
        )
        if external_record is not None:
            return external_record
        return {
            "asset_id": asset.asset_id,
            "status": "unavailable",
            "backend": "paddleocr",
            "reason": "paddleocr_not_installed",
            "error": str(exc),
            "install_hint": "先安装 PaddlePaddle，再执行 `python -m pip install \"paddleocr[doc-parser]\"`。",
        }

    try:
        pipeline = _build_paddleocr_pipeline(PPStructureV3, config=config)
        page_results = list(_iterate_predictions(pipeline.predict(str(source_path))))
        output_dir = ensure_dir(job_dir / "normalized" / "ocr" / asset.asset_id)
        page_records: list[dict[str, Any]] = []
        markdown_pages: list[dict[str, Any]] = []

        for index, result in enumerate(page_results, start=1):
            page_dir = ensure_dir(output_dir / f"page-{index:03d}")
            markdown_payload = getattr(result, "markdown", {}) or {}
            markdown_pages.append(markdown_payload)

            if hasattr(result, "save_to_json"):
                result.save_to_json(str(page_dir / "result.json"))
            if hasattr(result, "save_to_markdown"):
                result.save_to_markdown(str(page_dir))

            page_records.append(
                {
                    "page_no": index,
                    "json_path": str(page_dir / "result.json"),
                    "markdown_dir": str(page_dir),
                    "markdown_text_length": len(_extract_markdown_text(markdown_payload)),
                }
            )

        markdown_text = _concatenate_markdown_pages(pipeline, markdown_pages)
        preview_text = normalize_preview(markdown_text, limit_chars=config.preview_limit_chars)
        markdown_path = output_dir / "combined.md"
        summary_path = output_dir / "summary.json"

        write_markdown(markdown_path, (markdown_text or preview_text or "").strip() + "\n")
        write_json(
            summary_path,
            {
                "asset_id": asset.asset_id,
                "backend": "paddleocr",
                "status": "succeeded",
                "source_path": str(source_path),
                "page_count": len(page_records),
                "markdown_path": str(markdown_path),
                "pages": page_records,
            },
        )
        return {
            "asset_id": asset.asset_id,
            "status": "succeeded",
            "backend": "paddleocr",
            "reason": "ocr_completed",
            "text_preview": preview_text,
            "full_text": markdown_text,
            "text_extract_method": "paddleocr_pp_structurev3",
            "output_dir": str(output_dir),
            "markdown_path": str(markdown_path),
            "json_path": str(summary_path),
            "page_count": len(page_records),
        }
    except Exception as exc:  # pragma: no cover - defensive guard for optional backend
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": "paddleocr",
            "reason": "paddleocr_execution_failed",
            "error": str(exc),
        }


def _extract_with_external_paddleocr_python(
    asset: SourceAsset,
    *,
    source_path: Path,
    job_dir: Path,
    config: ExtractionConfig,
) -> dict[str, Any] | None:
    python_path = _project_paddleocr_python()
    if python_path is None:
        return None

    runner_path = Path(__file__).with_name("paddleocr_runner.py")
    output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
    env = dict(os.environ)
    env.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    command = [
        str(python_path),
        str(runner_path),
        "--asset-id",
        asset.asset_id,
        "--source-path",
        str(source_path),
        "--output-dir",
        str(output_dir),
        "--lang",
        config.paddleocr_lang,
        "--device",
        config.paddleocr_device,
        "--preview-limit-chars",
        str(config.preview_limit_chars),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": "paddleocr",
            "reason": "external_paddleocr_execution_failed",
            "error": (result.stderr or "").strip() or f"external paddleocr exited with code {result.returncode}",
        }
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": "paddleocr",
            "reason": "external_paddleocr_invalid_json",
            "error": str(exc),
        }
    payload.setdefault("asset_id", asset.asset_id)
    payload.setdefault("backend", "paddleocr")
    payload.setdefault("execution_env", "project_venv")
    return payload


def _project_paddleocr_python() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[3] / ".venv-paddleocr310-arm64" / "bin" / "python",
        Path(__file__).resolve().parents[3] / ".venv-paddleocr310-arm64" / "bin" / "python3",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _extract_with_mineru(
    asset: SourceAsset,
    *,
    source_path: Path,
    job_dir: Path,
    config: ExtractionConfig,
) -> dict[str, Any]:
    mineru_bin = _resolve_mineru_command()
    if mineru_bin is None:
        return {
            "asset_id": asset.asset_id,
            "status": "unavailable",
            "backend": "mineru",
            "reason": "mineru_not_installed",
            "error": "mineru command not found",
            "install_hint": "先按 MinerU 官方文档安装 CLI，例如 `pip install -U mineru`，再确认 `mineru` 命令可用。",
        }

    output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir)
    raw_output_dir = ensure_dir(output_dir / "_mineru_raw")
    env = dict(os.environ)
    command = [
        str(mineru_bin),
        "-p",
        str(source_path),
        "-o",
        str(raw_output_dir),
        "-b",
        "pipeline",
        "-m",
        "auto",
    ]
    if str(config.paddleocr_lang or "").strip():
        command.extend(["-l", str(config.paddleocr_lang).strip()])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": "mineru",
            "reason": "mineru_execution_failed",
            "error": (result.stderr or "").strip() or f"mineru exited with code {result.returncode}",
            "command": command,
        }

    artifacts = _locate_mineru_output_artifacts(raw_output_dir=raw_output_dir)
    content_entries = _load_mineru_content_entries(artifacts)
    page_payloads = _group_mineru_content_entries_by_page(content_entries)
    if not page_payloads:
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": "mineru",
            "reason": "mineru_output_incomplete",
            "error": "MinerU completed but no readable page content was found.",
        }

    page_records: list[dict[str, Any]] = []
    for page_no, page_payload in sorted(page_payloads.items()):
        page_dir = ensure_dir(output_dir / f"page-{page_no:03d}")
        page_text = "\n".join(page_payload["rec_texts"]).strip()
        write_json(page_dir / "result.json", {"overall_ocr_res": page_payload})
        write_markdown(page_dir / "page.md", (page_text + "\n") if page_text else "")
        page_records.append(
            {
                "page_no": page_no,
                "json_path": str(page_dir / "result.json"),
                "markdown_dir": str(page_dir),
                "markdown_text_length": len(page_text),
            }
        )

    markdown_text = _read_text_if_exists(artifacts.get("markdown_path")) or _build_mineru_combined_markdown(page_payloads)
    preview_text = normalize_preview(markdown_text, limit_chars=config.preview_limit_chars)
    markdown_path = output_dir / "combined.md"
    summary_path = output_dir / "summary.json"
    write_markdown(markdown_path, (markdown_text or preview_text or "").strip() + "\n")
    write_json(
        summary_path,
        {
            "asset_id": asset.asset_id,
            "backend": "mineru",
            "status": "succeeded",
            "source_path": str(source_path),
            "markdown_path": str(markdown_path),
            "page_count": len(page_records),
            "pages": page_records,
            "raw_output_dir": str(raw_output_dir),
            "raw_markdown_path": str(artifacts.get("markdown_path") or ""),
            "raw_content_list_path": str(artifacts.get("content_list_path") or ""),
            "raw_content_list_v2_path": str(artifacts.get("content_list_v2_path") or ""),
            "raw_middle_json_path": str(artifacts.get("middle_json_path") or ""),
        },
    )
    return {
        "asset_id": asset.asset_id,
        "status": "succeeded",
        "backend": "mineru",
        "reason": "ocr_completed",
        "text_preview": preview_text,
        "full_text": markdown_text,
        "text_extract_method": "mineru_pipeline_auto",
        "output_dir": str(output_dir),
        "markdown_path": str(markdown_path),
        "json_path": str(summary_path),
        "page_count": len(page_records),
        "command": command,
    }


def _resolve_mineru_command() -> Path | None:
    override = str(os.environ.get("LIANGQIN_CONTRACT_REVIEW_MINERU_BIN") or "").strip()
    if override:
        candidate = Path(override).expanduser()
        if candidate.exists():
            return candidate
    resolved = shutil.which("mineru")
    return Path(resolved) if resolved else None


def _locate_mineru_output_artifacts(*, raw_output_dir: Path) -> dict[str, Path | None]:
    markdown_candidates = sorted(
        path for path in raw_output_dir.rglob("*.md")
        if path.is_file() and path.name.lower() not in {"page.md", "combined.md"}
    )
    content_list_candidates = sorted(
        path for path in raw_output_dir.rglob("*content_list.json")
        if path.is_file()
    )
    content_list_v2_candidates = sorted(
        path for path in raw_output_dir.rglob("*content_list_v2.json")
        if path.is_file()
    )
    middle_json_candidates = sorted(
        path for path in raw_output_dir.rglob("*middle.json")
        if path.is_file()
    )
    return {
        "markdown_path": markdown_candidates[0] if markdown_candidates else None,
        "content_list_path": content_list_candidates[0] if content_list_candidates else None,
        "content_list_v2_path": content_list_v2_candidates[0] if content_list_v2_candidates else None,
        "middle_json_path": middle_json_candidates[0] if middle_json_candidates else None,
    }


def _load_mineru_content_entries(artifacts: dict[str, Path | None]) -> list[dict[str, Any]]:
    content_list_path = artifacts.get("content_list_path")
    if content_list_path is not None:
        payload = _read_json_file(content_list_path)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

    content_list_v2_path = artifacts.get("content_list_v2_path")
    if content_list_v2_path is not None:
        payload = _read_json_file(content_list_v2_path)
        if isinstance(payload, list):
            return _flatten_mineru_content_list_v2(payload)
    return []


def _flatten_mineru_content_list_v2(payload: list[Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for page_index, page in enumerate(payload):
        if not isinstance(page, dict):
            continue
        page_idx = int(page.get("page_idx") or page.get("page_no") or page_index)
        for item in list(page.get("items") or page.get("content") or []):
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            normalized.setdefault("page_idx", page_idx)
            flattened.append(normalized)
    return flattened


def _group_mineru_content_entries_by_page(entries: list[dict[str, Any]]) -> dict[int, dict[str, list[Any]]]:
    grouped: dict[int, dict[str, list[Any]]] = {}
    for item in entries:
        page_idx = int(item.get("page_idx") or item.get("page_no") or 0)
        page_no = page_idx + 1 if page_idx >= 0 else 1
        page_payload = grouped.setdefault(page_no, {"rec_texts": [], "rec_boxes": [], "rec_scores": []})
        texts = _extract_mineru_item_texts(item)
        if not texts:
            continue
        bbox = _coerce_mineru_bbox(item.get("bbox"))
        for text in texts:
            normalized_text = str(text or "").strip()
            if not normalized_text:
                continue
            page_payload["rec_texts"].append(normalized_text)
            page_payload["rec_boxes"].append(bbox or [0.0, 0.0, 1.0, 1.0])
            page_payload["rec_scores"].append(float(item.get("score") or 1.0))
    return {page_no: payload for page_no, payload in grouped.items() if payload["rec_texts"]}


def _extract_mineru_item_texts(item: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in (
        "text",
        "html",
        "latex",
        "table_body",
        "table_caption",
        "table_footnote",
        "image_caption",
        "image_footnote",
    ):
        value = item.get(key)
        texts.extend(_normalize_mineru_text_values(value))

    nested = item.get("blocks") or item.get("items") or item.get("content")
    if isinstance(nested, list):
        for child in nested:
            if isinstance(child, dict):
                texts.extend(_extract_mineru_item_texts(child))
    return _dedupe_texts(texts)


def _normalize_mineru_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = _strip_markup_text(value)
        return [normalized] if normalized else []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_normalize_mineru_text_values(item))
        return texts
    if isinstance(value, dict):
        texts: list[str] = []
        for child in value.values():
            texts.extend(_normalize_mineru_text_values(child))
        return texts
    return []


def _strip_markup_text(text: str) -> str:
    normalized = re.sub(r"<[^>]+>", " ", unescape(str(text or "")))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _coerce_mineru_bbox(value: Any) -> list[float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        return [float(item) for item in value]
    return None


def _build_mineru_combined_markdown(page_payloads: dict[int, dict[str, list[Any]]]) -> str:
    parts = []
    for page_no in sorted(page_payloads):
        page_text = "\n".join(str(item) for item in page_payloads[page_no]["rec_texts"]).strip()
        if page_text:
            parts.append(f"第{page_no}页\n{page_text}")
    return "\n\n".join(parts).strip()


def _read_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_json_file(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_cached_paddleocr_record(
    asset: SourceAsset,
    *,
    source_path: Path,
    job_dir: Path,
    config: ExtractionConfig,
) -> dict[str, Any] | None:
    cache_dir = _resolve_paddleocr_cache_dir(source_path, config=config)
    payload_path = cache_dir / "payload.json"
    artifact_dir = cache_dir / "artifacts"
    if not payload_path.exists() or not artifact_dir.exists():
        return None

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir.parent)
    shutil.copytree(artifact_dir, output_dir)

    summary_path = output_dir / "summary.json"
    summary_payload = _rewrite_cached_summary_paths(
        summary_path=summary_path,
        output_dir=output_dir,
        source_path=source_path,
        asset_id=asset.asset_id,
    )

    cached_payload = dict(payload)
    cached_payload.update(
        {
            "asset_id": asset.asset_id,
            "backend": "paddleocr",
            "status": "succeeded",
            "reason": "ocr_cache_hit",
            "output_dir": str(output_dir),
            "markdown_path": str(output_dir / "combined.md"),
            "json_path": str(summary_path),
            "page_count": int(summary_payload.get("page_count") or cached_payload.get("page_count") or 0),
            "cache_status": "hit",
            "cache_key": cache_dir.name,
        }
    )
    return cached_payload


def _store_cached_paddleocr_record(
    record: dict[str, Any],
    *,
    source_path: Path,
    config: ExtractionConfig,
) -> None:
    if str(record.get("status") or "").strip() != "succeeded":
        return

    output_dir = Path(str(record.get("output_dir") or "")).expanduser()
    if not output_dir.exists():
        return

    cache_dir = _resolve_paddleocr_cache_dir(source_path, config=config)
    artifact_dir = cache_dir / "artifacts"
    payload_path = cache_dir / "payload.json"
    if artifact_dir.exists() and payload_path.exists():
        return

    ensure_dir(cache_dir)
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    shutil.copytree(output_dir, artifact_dir)
    payload = dict(record)
    payload["cache_status"] = "stored"
    payload["cache_key"] = cache_dir.name
    write_json(payload_path, payload)


def _resolve_paddleocr_cache_dir(source_path: Path, *, config: ExtractionConfig) -> Path:
    fingerprint = _build_paddleocr_cache_key(source_path, config=config)
    return _paddleocr_cache_root() / fingerprint


def _build_paddleocr_cache_key(source_path: Path, *, config: ExtractionConfig) -> str:
    digest = hashlib.sha256()
    digest.update(f"ppstructurev3|{config.paddleocr_lang}|{config.preview_limit_chars}".encode("utf-8"))
    with source_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paddleocr_cache_root() -> Path:
    override = str(os.environ.get("LIANGQIN_CONTRACT_REVIEW_OCR_CACHE_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "liangqin-contract-review" / "paddleocr"
    return Path.home() / ".cache" / "liangqin-contract-review" / "paddleocr"


def _rewrite_cached_summary_paths(
    *,
    summary_path: Path,
    output_dir: Path,
    source_path: Path,
    asset_id: str,
) -> dict[str, Any]:
    summary_payload: dict[str, Any]
    if summary_path.exists():
        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary_payload = {}
    else:
        summary_payload = {}

    pages = list(summary_payload.get("pages") or [])
    for index, page in enumerate(pages, start=1):
        page_no = int(page.get("page_no") or index)
        page_dir = output_dir / f"page-{page_no:03d}"
        page["page_no"] = page_no
        page["json_path"] = str(page_dir / "result.json")
        page["markdown_dir"] = str(page_dir)

    summary_payload.update(
        {
            "asset_id": asset_id,
            "backend": "paddleocr",
            "status": "succeeded",
            "source_path": str(source_path),
            "markdown_path": str(output_dir / "combined.md"),
            "page_count": len(pages) if pages else int(summary_payload.get("page_count") or 0),
            "pages": pages,
        }
    )
    write_json(summary_path, summary_payload)
    return summary_payload


def _prepare_ocr_source_path(
    asset: SourceAsset,
    *,
    source_path: Path,
    job_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    context: dict[str, Any] = {
        "ocr_source_path": str(source_path),
        "ocr_scope": "full_document",
    }
    if source_path.suffix.lower() != ".pdf":
        return source_path, context

    attachment_anchor_page = resolve_attachment_anchor_page(str(asset.text_preview or ""))
    if attachment_anchor_page is None or attachment_anchor_page <= 1:
        return source_path, context

    subset_path = _write_pdf_subset_from_page(
        source_path,
        start_page=attachment_anchor_page,
        output_path=job_dir
        / "normalized"
        / "ocr-sources"
        / f"{asset.asset_id}-attachment-from-page-{attachment_anchor_page:03d}.pdf",
    )
    if subset_path is None:
        return source_path, context

    return subset_path, {
        "ocr_source_path": str(subset_path),
        "ocr_scope": "attachment_pages_only",
        "ocr_start_page": attachment_anchor_page,
    }


def _write_pdf_subset_from_page(source_path: Path, *, start_page: int, output_path: Path) -> Path | None:
    if PdfReader is None or PdfWriter is None:
        return None
    if start_page <= 1:
        return None

    reader = PdfReader(str(source_path))
    total_pages = len(reader.pages)
    if start_page > total_pages:
        return None

    writer = PdfWriter()
    for page_index in range(start_page - 1, total_pages):
        writer.add_page(reader.pages[page_index])

    ensure_dir(output_path.parent)
    with output_path.open("wb") as handle:
        writer.write(handle)
    return output_path


def _build_paddleocr_pipeline(pipeline_cls: type, *, config: ExtractionConfig):
    init_attempts = [
        {"lang": config.paddleocr_lang, "device": config.paddleocr_device},
        {"lang": config.paddleocr_lang},
        {},
    ]
    last_error: Exception | None = None
    for init_kwargs in init_attempts:
        try:
            return pipeline_cls(**init_kwargs)
        except TypeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return pipeline_cls()


def _iterate_predictions(predictions: Iterable[Any]) -> Iterable[Any]:
    for item in predictions:
        yield item


def _concatenate_markdown_pages(pipeline: Any, markdown_pages: list[dict[str, Any]]) -> str:
    if hasattr(pipeline, "concatenate_markdown_pages"):
        combined = pipeline.concatenate_markdown_pages(markdown_pages)
        if isinstance(combined, str):
            return combined
    return "\n\n".join(
        text for text in (_extract_markdown_text(page) for page in markdown_pages) if text.strip()
    )


def _extract_markdown_text(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""
    text = payload.get("markdown_texts")
    if isinstance(text, str):
        return text
    text = payload.get("text")
    if isinstance(text, str):
        return text
    return ""
