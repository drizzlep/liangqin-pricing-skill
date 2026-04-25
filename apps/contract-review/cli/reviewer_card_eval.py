#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from reviewer_card_eval_core import build_reviewer_card_eval  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate reviewer-card decisions against human labels.")
    parser.add_argument(
        "--summary-path",
        action="append",
        required=True,
        help="Path to reviewer-card-summary.json. Repeat this option for multiple batches.",
    )
    parser.add_argument(
        "--ground-truth-path",
        help="Optional CSV with batch_id, case_key, expected_decision and human_reason.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where reviewer-card-eval.json/md and the labeling template are written.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["text", "json"],
        default="text",
        help="Render a human-readable summary or the full JSON payload.",
    )
    parser.add_argument(
        "--prefill-suggestions",
        action="store_true",
        help="Prefill expected_decision and human_reason in the labeling template from system suggestions.",
    )
    return parser.parse_args(argv)


def _emit(payload: dict[str, object], *, output_mode: str) -> None:
    if output_mode == "json":
        json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    summary = payload["summary"]
    sys.stdout.write(
        f"审核员决策卡验收\n"
        f"样本数：{summary['total_case_count']}\n"
        f"已标注：{summary['labeled_case_count']}\n"
        f"误放行：{summary['false_release_count']}\n"
        f"过度拦截：{summary['over_escalation_count']}\n"
        f"report：{payload['report_markdown_path']}\n"
        f"校准说明：{payload['calibration_markdown_path']}\n"
        f"审核表：{payload['human_review_workbook_path']}\n"
        f"标注模板：{payload['ground_truth_template_path']}\n"
    )


def run(argv: list[str] | None = None) -> dict[str, object]:
    args = parse_args(argv)
    payload = build_reviewer_card_eval(
        summary_paths=[Path(path) for path in args.summary_path],
        ground_truth_path=Path(args.ground_truth_path) if args.ground_truth_path else None,
        output_dir=Path(args.output_dir),
        prefill_suggestions=args.prefill_suggestions,
    )
    _emit(payload, output_mode=args.output_mode)
    return payload


def main(argv: list[str] | None = None) -> int:
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
