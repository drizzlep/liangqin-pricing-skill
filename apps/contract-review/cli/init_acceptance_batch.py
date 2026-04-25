#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_ROOT = APP_ROOT / "templates"

DEFAULT_CASE_KEYS = [
    "case-001-normal",
    "case-002-calc-error",
    "case-003-quote-conflict",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize an acceptance batch scaffold for contract review.")
    parser.add_argument("--batch-dir", required=True, help="Directory to create the acceptance batch scaffold in.")
    parser.add_argument(
        "--ground-truth-path",
        help="Optional CSV path for the copied ground-truth template. Defaults to a sibling file beside batch-dir.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["text", "json"],
        default="text",
        help="Render a human-readable summary or the full JSON payload.",
    )
    return parser.parse_args(argv)


def _emit(payload: dict[str, object], *, output_mode: str) -> None:
    if output_mode == "json":
        json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    sys.stdout.write(
        f"已初始化验收批次：{payload['batch_dir']}\n"
        f"ground_truth：{payload['ground_truth_path']}\n"
        f"case_count：{len(payload['case_keys'])}\n"
    )
    for case_key in payload["case_keys"]:
        sys.stdout.write(f"- {case_key}\n")


def _manifest_payload(batch_id: str) -> dict[str, object]:
    return {
        "source_type": "manual_batch",
        "source_channel": "manual",
        "source_batch_id": batch_id,
        "requested_actions": ["audit", "replay"],
        "operator": "",
        "received_at": "",
        "notes": "发布前真实验收批次。",
    }


def run(argv: list[str] | None = None) -> dict[str, object]:
    args = parse_args(argv)
    batch_dir = Path(args.batch_dir).expanduser().resolve()
    ground_truth_path = (
        Path(args.ground_truth_path).expanduser().resolve()
        if args.ground_truth_path
        else batch_dir.parent / "acceptance-ground-truth.csv"
    )

    batch_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = batch_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    created_case_dirs: list[str] = []
    for case_key in DEFAULT_CASE_KEYS:
        case_dir = raw_dir / case_key
        case_dir.mkdir(parents=True, exist_ok=True)
        created_case_dirs.append(case_key)

    manifest_path = batch_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_payload(batch_dir.name), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    template_csv_path = TEMPLATES_ROOT / "acceptance-ground-truth.example.csv"
    ground_truth_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_csv_path, ground_truth_path)

    payload = {
        "batch_dir": str(batch_dir),
        "manifest_path": str(manifest_path),
        "ground_truth_path": str(ground_truth_path),
        "case_keys": created_case_dirs,
    }
    _emit(payload, output_mode=args.output_mode)
    return payload


def main(argv: list[str] | None = None) -> int:
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
