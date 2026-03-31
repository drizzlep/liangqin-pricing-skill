#!/usr/bin/env python3
"""Validate a versioned release snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Liangqin pricing release.")
    parser.add_argument("--version-dir", required=True, help="Path to the version directory.")
    parser.add_argument("--prompt-suite-report", help="Optional prompt suite report JSON used for release gating.")
    parser.add_argument(
        "--required-assertion",
        action="append",
        default=[],
        help="Validation assertion name that must have zero failures in the prompt suite report.",
    )
    parser.add_argument("--runtime-noise-review", help="Optional runtime noise review report (.md/.json).")
    parser.add_argument(
        "--max-suspicious-runtime",
        type=int,
        default=None,
        help="Maximum allowed suspicious runtime entries when --runtime-noise-review is provided.",
    )
    return parser.parse_args()


def ensure_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        json.load(handle)


def build_validation_assertion_summary(payload: dict[str, object]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        evaluation = result.get("evaluation", {})
        if not isinstance(evaluation, dict):
            continue
        for assertion_name, assertion_result in (evaluation.get("validation_assertions") or {}).items():
            if not isinstance(assertion_result, dict):
                continue
            entry = summary.setdefault(str(assertion_name), {"passed": 0, "failed": 0})
            if assertion_result.get("passed"):
                entry["passed"] += 1
            else:
                entry["failed"] += 1
    return summary


def validate_prompt_suite_report(path: Path, *, required_assertions: list[str]) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("case_count", 0) or 0) <= 0:
        raise SystemExit(f"Prompt suite report is empty: {path}")
    if int(payload.get("failed_count", 0) or 0) != 0:
        raise SystemExit(f"Prompt suite report contains failed cases: {path}")

    summary = payload.get("validation_assertion_summary")
    if not isinstance(summary, dict):
        summary = build_validation_assertion_summary(payload)
        payload["validation_assertion_summary"] = summary

    for assertion_name in required_assertions:
        assertion_summary = summary.get(assertion_name)
        if not isinstance(assertion_summary, dict):
            raise SystemExit(f"Prompt suite report missing required assertion summary: {assertion_name}")
        if int(assertion_summary.get("failed", 0) or 0) != 0:
            raise SystemExit(f"Prompt suite assertion failed: {assertion_name}")
    return payload


def read_runtime_noise_count(path: Path) -> int:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return int(payload.get("suspicious_count", 0) or 0)

    text = path.read_text(encoding="utf-8")
    match = re.search(r"suspicious_count\s*:\s*(\d+)", text)
    if not match:
        raise SystemExit(f"Unable to determine suspicious runtime count from: {path}")
    return int(match.group(1))


def main() -> int:
    args = parse_args()
    version_dir = Path(args.version_dir).expanduser().resolve()
    required = [
        version_dir / "release.json",
        version_dir / "price-index.json",
        version_dir / "rules" / "rules-candidate.json",
    ]

    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(path)
        return 1

    for path in required:
        ensure_json(path)

    if args.prompt_suite_report:
        validate_prompt_suite_report(
            Path(args.prompt_suite_report).expanduser().resolve(),
            required_assertions=[str(name) for name in args.required_assertion if str(name).strip()],
        )

    if args.runtime_noise_review:
        suspicious_count = read_runtime_noise_count(Path(args.runtime_noise_review).expanduser().resolve())
        max_allowed = 0 if args.max_suspicious_runtime is None else int(args.max_suspicious_runtime)
        if suspicious_count > max_allowed:
            raise SystemExit(
                f"Suspicious runtime entries exceed threshold: {suspicious_count} > {max_allowed}"
            )

    print(f"Release is valid: {version_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
