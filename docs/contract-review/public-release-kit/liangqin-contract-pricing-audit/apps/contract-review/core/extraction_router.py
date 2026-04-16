from __future__ import annotations

import json
import os
import subprocess
import hashlib
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from attachment_section import resolve_attachment_anchor_page
from batch_runtime import ensure_dir, write_json, write_markdown
from job_models import SourceAsset
from runtime_paths import resolve_paddleocr_python
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

    if config.ocr_backend != "paddleocr":
        return {
            "asset_id": asset.asset_id,
            "status": "failed",
            "backend": config.ocr_backend,
            "reason": "unsupported_ocr_backend",
            "error": f"unsupported ocr backend: {config.ocr_backend}",
        }

    ocr_source_path, ocr_context = _prepare_ocr_source_path(asset, source_path=source_path, job_dir=job_dir)
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
    return resolve_paddleocr_python()


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
