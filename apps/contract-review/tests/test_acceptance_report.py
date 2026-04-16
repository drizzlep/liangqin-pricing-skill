from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CLI_ROOT = APP_ROOT / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

MODULE_PATH = CLI_ROOT / "acceptance_report.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ACCEPTANCE_REPORT = load_module("contract_review_acceptance_report_cli", MODULE_PATH)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_ground_truth(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_key",
                "expected_bucket",
                "expected_verdict",
                "expected_issue_codes",
                "expected_primary_check",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_review_payload(
    job_dir: Path,
    *,
    verdict: str,
    issue_codes: list[str],
    next_actions: list[str],
    issue_checks: list[str] | None = None,
) -> None:
    write_json(
        job_dir / "output" / "review.json",
        {
            "review_card": {
                "verdict": verdict,
                "priority": "p1" if verdict == "manual_review_required" else "normal",
                "next_actions": next_actions,
            },
            "review_analysis": {
                "issue_codes": issue_codes,
            },
            "issues": [
                {
                    "issue_code": issue_code,
                    "recommended_check": (issue_checks or next_actions or [""])[min(index, len((issue_checks or next_actions or [""])) - 1)],
                }
                for index, issue_code in enumerate(issue_codes)
            ],
        },
    )


class AcceptanceReportTests(unittest.TestCase):
    def test_cli_builds_acceptance_report_with_false_negative_and_primary_check_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "acceptance-batch-2026-04-16"
            runtime_root = root / "runtime"
            batch_output_dir = runtime_root / "batches" / batch_dir.name
            ground_truth_path = root / "acceptance-ground-truth.csv"

            write_ground_truth(
                ground_truth_path,
                [
                    {
                        "case_key": "case-001-normal",
                        "expected_bucket": "normal",
                        "expected_verdict": "recommended_release",
                        "expected_issue_codes": "",
                        "expected_primary_check": "无",
                        "notes": "正常样本",
                    },
                    {
                        "case_key": "case-002-calc-error",
                        "expected_bucket": "calc_error",
                        "expected_verdict": "manual_review_required",
                        "expected_issue_codes": "calculation_error",
                        "expected_primary_check": "核对折扣",
                        "notes": "折扣计算错误",
                    },
                    {
                        "case_key": "case-003-quote-conflict",
                        "expected_bucket": "quote_conflict",
                        "expected_verdict": "manual_review_required",
                        "expected_issue_codes": "quote_conflict|discount_mismatch",
                        "expected_primary_check": "核对报价口径",
                        "notes": "报价冲突",
                    },
                ],
            )

            jobs = []
            for index, case_key in enumerate(
                ["case-001-normal", "case-002-calc-error", "case-003-quote-conflict"],
                start=1,
            ):
                job_id = f"{batch_dir.name}-{index:03d}"
                job_dir = runtime_root / "jobs" / job_id
                jobs.append(
                    {
                        "job_id": job_id,
                        "group_key": case_key,
                        "job_dir": str(job_dir),
                        "review_path": str(job_dir / "output" / "review.md"),
                    }
                )

            write_json(
                batch_output_dir / "batch-summary.json",
                {
                    "batch_id": batch_dir.name,
                    "source_type": "manual_batch",
                    "source_channel": "manual",
                    "job_count": len(jobs),
                    "jobs": jobs,
                },
            )

            write_review_payload(
                runtime_root / "jobs" / f"{batch_dir.name}-001",
                verdict="recommended_release",
                issue_codes=[],
                next_actions=[],
            )
            write_review_payload(
                runtime_root / "jobs" / f"{batch_dir.name}-002",
                verdict="manual_review_required",
                issue_codes=["calculation_error"],
                next_actions=["请先核对折前合计、折扣和折后合计三者是否一致，再继续审单。"],
            )
            write_review_payload(
                runtime_root / "jobs" / f"{batch_dir.name}-003",
                verdict="manual_review_required",
                issue_codes=["quote_conflict"],
                next_actions=["请先核对数量、折扣、增项，以及门型/材质等默认条件是否一致。"],
            )

            with contextlib.redirect_stdout(io.StringIO()):
                payload = ACCEPTANCE_REPORT.run(
                    [
                        "--batch-dir",
                        str(batch_dir),
                        "--runtime-root",
                        str(runtime_root),
                        "--output-mode",
                        "json",
                    ]
                )

            report_json_path = batch_output_dir / "acceptance-report.json"
            report_markdown_path = batch_output_dir / "acceptance-report.md"
            self.assertTrue(report_json_path.exists())
            self.assertTrue(report_markdown_path.exists())
            self.assertEqual(payload["summary"]["total_case_count"], 3)
            self.assertEqual(payload["summary"]["verdict_match_count"], 3)
            self.assertEqual(payload["summary"]["issue_match_count"], 2)
            self.assertEqual(payload["summary"]["false_negative_count"], 1)
            self.assertEqual(payload["summary"]["false_positive_count"], 0)
            self.assertEqual(payload["summary"]["primary_check_count"], 2)
            self.assertEqual(payload["summary"]["primary_check_hit_count"], 1)

            quote_conflict_case = next(item for item in payload["items"] if item["case_key"] == "case-003-quote-conflict")
            self.assertEqual(quote_conflict_case["case_status"], "reviewed")
            self.assertEqual(quote_conflict_case["missing_issue_codes"], ["discount_mismatch"])
            self.assertFalse(quote_conflict_case["issue_match"])
            self.assertFalse(quote_conflict_case["primary_check_match"])

    def test_cli_marks_missing_and_unexpected_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "acceptance-batch-2026-04-17"
            runtime_root = root / "runtime"
            batch_output_dir = runtime_root / "batches" / batch_dir.name
            ground_truth_path = root / "acceptance-ground-truth.csv"

            write_ground_truth(
                ground_truth_path,
                [
                    {
                        "case_key": "case-001-normal",
                        "expected_bucket": "normal",
                        "expected_verdict": "recommended_release",
                        "expected_issue_codes": "",
                        "expected_primary_check": "无",
                        "notes": "",
                    },
                    {
                        "case_key": "case-002-calc-error",
                        "expected_bucket": "calc_error",
                        "expected_verdict": "manual_review_required",
                        "expected_issue_codes": "calculation_error",
                        "expected_primary_check": "核对折扣",
                        "notes": "",
                    },
                ],
            )

            present_job_dir = runtime_root / "jobs" / f"{batch_dir.name}-001"
            extra_job_dir = runtime_root / "jobs" / f"{batch_dir.name}-002"
            write_json(
                batch_output_dir / "batch-summary.json",
                {
                    "batch_id": batch_dir.name,
                    "source_type": "manual_batch",
                    "source_channel": "manual",
                    "job_count": 2,
                    "jobs": [
                        {
                            "job_id": f"{batch_dir.name}-001",
                            "group_key": "case-001-normal",
                            "job_dir": str(present_job_dir),
                            "review_path": str(present_job_dir / "output" / "review.md"),
                        },
                        {
                            "job_id": f"{batch_dir.name}-002",
                            "group_key": "case-extra-unexpected",
                            "job_dir": str(extra_job_dir),
                            "review_path": str(extra_job_dir / "output" / "review.md"),
                        },
                    ],
                },
            )
            write_review_payload(
                present_job_dir,
                verdict="recommended_release",
                issue_codes=[],
                next_actions=[],
            )
            write_review_payload(
                extra_job_dir,
                verdict="manual_review_required",
                issue_codes=["quote_conflict"],
                next_actions=["请优先核对数量、折扣、增项，以及门型/材质等默认条件是否一致。"],
            )

            with contextlib.redirect_stdout(io.StringIO()):
                payload = ACCEPTANCE_REPORT.run(
                    [
                        "--batch-dir",
                        str(batch_dir),
                        "--runtime-root",
                        str(runtime_root),
                        "--output-mode",
                        "json",
                    ]
                )

            self.assertEqual(payload["summary"]["missing_case_count"], 1)
            self.assertEqual(payload["summary"]["unexpected_case_count"], 1)
            missing_case = next(item for item in payload["items"] if item["case_key"] == "case-002-calc-error")
            unexpected_case = next(item for item in payload["items"] if item["case_key"] == "case-extra-unexpected")
            self.assertEqual(missing_case["case_status"], "missing_runtime_case")
            self.assertEqual(unexpected_case["case_status"], "unexpected_runtime_case")


if __name__ == "__main__":
    unittest.main()
