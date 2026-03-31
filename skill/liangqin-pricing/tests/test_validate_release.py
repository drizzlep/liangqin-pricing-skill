import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_release.py"
SPEC = importlib.util.spec_from_file_location("validate_release", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateReleaseTests(unittest.TestCase):
    def test_validate_prompt_suite_report_requires_zero_failed_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "prompt-suite.json"
            report_path.write_text(
                json.dumps(
                    {
                        "case_count": 1,
                        "passed_count": 1,
                        "failed_count": 0,
                        "validation_assertion_summary": {
                            "output_contract_pass": {"passed": 1, "failed": 0},
                            "no_boundary_pollution": {"passed": 1, "failed": 0},
                        },
                        "results": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = MODULE.validate_prompt_suite_report(
                report_path,
                required_assertions=["output_contract_pass", "no_boundary_pollution"],
            )

        self.assertEqual(summary["failed_count"], 0)
        self.assertEqual(summary["validation_assertion_summary"]["output_contract_pass"]["failed"], 0)

    def test_validate_prompt_suite_report_rejects_failed_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "prompt-suite.json"
            report_path.write_text(
                json.dumps(
                    {
                        "case_count": 1,
                        "passed_count": 0,
                        "failed_count": 1,
                        "validation_assertion_summary": {
                            "output_contract_pass": {"passed": 0, "failed": 1},
                        },
                        "results": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(SystemExit):
                MODULE.validate_prompt_suite_report(report_path, required_assertions=["output_contract_pass"])

    def test_read_runtime_noise_count_supports_markdown_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "noise-review.md"
            report_path.write_text("# Included Runtime 噪声复核表\n\n- suspicious_count: 2\n", encoding="utf-8")

            self.assertEqual(MODULE.read_runtime_noise_count(report_path), 2)


if __name__ == "__main__":
    unittest.main()
