#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from batch_runtime import ensure_dir, write_json, write_markdown
from extraction_router import (
    _build_paddleocr_pipeline,
    _concatenate_markdown_pages,
    _extract_markdown_text,
    _iterate_predictions,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PaddleOCR in the project venv and emit a JSON result.")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--preview-limit-chars", type=int, default=1600)
    return parser.parse_args()


def main() -> int:
    from paddleocr import PPStructureV3
    from text_preview import normalize_preview

    args = parse_args()
    source_path = Path(args.source_path)
    output_dir = ensure_dir(Path(args.output_dir))
    pipeline = _build_paddleocr_pipeline(
        PPStructureV3,
        config=SimpleNamespace(
            paddleocr_lang=args.lang,
            paddleocr_device=args.device,
            preview_limit_chars=args.preview_limit_chars,
        ),
    )
    page_results = list(_iterate_predictions(pipeline.predict(str(source_path))))
    page_records: list[dict[str, object]] = []
    markdown_pages: list[dict[str, object]] = []

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
    preview_text = normalize_preview(markdown_text, limit_chars=args.preview_limit_chars)
    markdown_path = output_dir / "combined.md"
    summary_path = output_dir / "summary.json"

    write_markdown(markdown_path, (markdown_text or preview_text or "").strip() + "\n")
    write_json(
        summary_path,
        {
            "asset_id": args.asset_id,
            "backend": "paddleocr",
            "status": "succeeded",
            "source_path": str(source_path),
            "page_count": len(page_records),
            "markdown_path": str(markdown_path),
            "pages": page_records,
        },
    )
    payload = {
        "asset_id": args.asset_id,
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
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
