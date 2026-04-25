#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
ADAPTERS_ROOT = APP_ROOT / "adapters"
for root in (CORE_ROOT, ADAPTERS_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from batch_runtime import DEFAULT_RUNTIME_ROOT, materialize_job, write_batch_summary  # noqa: E402
from extraction_router import ExtractionConfig  # noqa: E402
from manual_batch import build_review_jobs  # noqa: E402
from review_pipeline import run_review_job  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process a manual contract-review batch directory.")
    parser.add_argument("--batch-dir", required=True, help="Path to a batch directory that contains raw/ and optional manifest.json.")
    parser.add_argument(
        "--runtime-root",
        default=str(DEFAULT_RUNTIME_ROOT),
        help="Directory used for staged jobs and batch reports.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["text", "json"],
        default="text",
        help="Render a human-readable summary or the full JSON payload.",
    )
    parser.add_argument(
        "--ocr-backend",
        choices=["disabled", "paddleocr", "mineru"],
        default="paddleocr",
        help="OCR backend used for images and scanned PDFs.",
    )
    parser.add_argument(
        "--paddleocr-lang",
        default="ch",
        help="Language hint passed to PaddleOCR when OCR is enabled.",
    )
    parser.add_argument(
        "--paddleocr-device",
        default="cpu",
        help="Device hint passed to PaddleOCR, for example `cpu` or `gpu:0`.",
    )
    parser.add_argument(
        "--force-ocr-for-documents",
        action="store_true",
        help="Run OCR for document assets even when native text preview already exists.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only plan the batch split. Do not write runtime files.")
    return parser.parse_args(argv)


def _emit(payload: dict[str, object], *, output_mode: str) -> None:
    if output_mode == "json":
        json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    sys.stdout.write(
        f"批次：{payload['batch_id']}\n"
        f"来源：{payload['source_type']} / {payload['source_channel']}\n"
        f"任务数：{payload['job_count']}\n"
    )
    if payload.get("dry_run"):
        sys.stdout.write("模式：dry-run\n")
    if payload.get("warnings"):
        sys.stdout.write(f"批次提醒：{len(payload['warnings'])}\n")
    for row in payload.get("jobs", []):
        priority = row.get("review_priority", "normal")
        priority_reason = str(row.get("review_priority_reason") or "").strip()
        priority_suffix = f" / priority={priority}"
        if priority_reason:
            priority_suffix += f" / reason={priority_reason}"
        sys.stdout.write(
            f"- {row['job_id']} / {row['group_key']} / {row['status']} / "
            f"findings={row['finding_count']} / blockers={row['blocking_finding_count']}{priority_suffix}\n"
        )


def run(argv: list[str] | None = None) -> dict[str, object]:
    args = parse_args(argv)
    batch_plan = build_review_jobs(Path(args.batch_dir))
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    extraction_config = ExtractionConfig(
        ocr_backend=args.ocr_backend,
        paddleocr_lang=args.paddleocr_lang,
        paddleocr_device=args.paddleocr_device,
        force_ocr_for_documents=args.force_ocr_for_documents,
    )

    if args.dry_run:
        payload = {
            "batch_id": batch_plan.batch_id,
            "source_type": batch_plan.source_type,
            "source_channel": batch_plan.source_channel,
            "job_count": len(batch_plan.jobs),
            "warnings": batch_plan.warnings,
            "dry_run": True,
            "jobs": [
                {
                    "job_id": job.job_id,
                    "group_key": job.group_key,
                    "status": "planned",
                    "review_priority": "normal",
                    "review_priority_score": 3,
                    "review_priority_reason": "",
                    "finding_count": 0,
                    "blocking_finding_count": 0,
                    "primary_contract_count": len(job.primary_contract_assets()),
                    "review_path": "",
                }
                for job in batch_plan.jobs
            ],
        }
        _emit(payload, output_mode=args.output_mode)
        return payload

    batch_results = []
    for job in batch_plan.jobs:
        job_dir = materialize_job(job, runtime_root=runtime_root)
        batch_results.append(run_review_job(job, job_dir=job_dir, extraction_config=extraction_config))

    summary_payload = write_batch_summary(batch_plan, batch_results=batch_results, runtime_root=runtime_root)
    summary_payload["dry_run"] = False
    _emit(summary_payload, output_mode=args.output_mode)
    return summary_payload


def main(argv: list[str] | None = None) -> int:
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
