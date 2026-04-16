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

from acceptance_report import build_acceptance_report  # noqa: E402
from batch_runtime import DEFAULT_RUNTIME_ROOT  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a release-acceptance report for a contract-review batch.")
    parser.add_argument("--batch-dir", required=True, help="Acceptance batch directory.")
    parser.add_argument(
        "--runtime-root",
        default=str(DEFAULT_RUNTIME_ROOT),
        help="Runtime root that contains batches/ and jobs/ outputs.",
    )
    parser.add_argument(
        "--ground-truth-path",
        help="Optional path to acceptance-ground-truth.csv. Defaults to a sibling file beside batch-dir.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["text", "json"],
        default="text",
        help="Render a human-readable summary or the full JSON payload.",
    )
    parser.add_argument(
        "--fail-on-blocking",
        action="store_true",
        help="Return a non-zero exit code when the acceptance report is not ready_to_release.",
    )
    return parser.parse_args(argv)


def _emit(payload: dict[str, object], *, output_mode: str) -> None:
    if output_mode == "json":
        json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    summary = payload["summary"]
    sys.stdout.write(
        f"验收批次：{payload['batch_id']}\n"
        f"ready_to_release：{summary['ready_to_release']}\n"
        f"false_negative_count：{summary['false_negative_count']}\n"
        f"false_positive_count：{summary['false_positive_count']}\n"
        f"report：{payload['report_markdown_path']}\n"
    )


def run(argv: list[str] | None = None) -> dict[str, object]:
    args = parse_args(argv)
    payload = build_acceptance_report(
        batch_dir=Path(args.batch_dir),
        runtime_root=Path(args.runtime_root),
        ground_truth_path=Path(args.ground_truth_path) if args.ground_truth_path else None,
    )
    _emit(payload, output_mode=args.output_mode)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_acceptance_report(
        batch_dir=Path(args.batch_dir),
        runtime_root=Path(args.runtime_root),
        ground_truth_path=Path(args.ground_truth_path) if args.ground_truth_path else None,
    )
    _emit(payload, output_mode=args.output_mode)
    if args.fail_on_blocking and not bool((payload.get("summary") or {}).get("ready_to_release")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
