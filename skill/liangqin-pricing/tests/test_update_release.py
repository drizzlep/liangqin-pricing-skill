import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_release.py"
SPEC = importlib.util.spec_from_file_location("update_release", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class UpdateReleaseTests(unittest.TestCase):
    def test_parse_args_accepts_release_gate_options(self) -> None:
        argv = [
            "update_release.py",
            "--prompt-suite-report",
            "/tmp/prompt-suite.json",
            "--required-assertion",
            "output_contract_pass",
            "--runtime-noise-review",
            "/tmp/runtime-noise.md",
            "--max-suspicious-runtime",
            "0",
        ]
        with mock.patch("sys.argv", argv):
            args = MODULE.parse_args()

        self.assertEqual(args.prompt_suite_report, "/tmp/prompt-suite.json")
        self.assertEqual(args.required_assertion, ["output_contract_pass"])
        self.assertEqual(args.runtime_noise_review, "/tmp/runtime-noise.md")
        self.assertEqual(args.max_suspicious_runtime, 0)

    def test_pick_latest_rules_source_prefers_docx_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            pdf_path = inbox / "rules.pdf"
            docx_old = inbox / "rules.docx"
            pdf_path.write_text("pdf", encoding="utf-8")
            docx_old.write_text("docx", encoding="utf-8")
            pdf_path.touch()
            docx_old.touch()

            selected = MODULE.pick_latest_rules_source(inbox)

        self.assertEqual(selected.suffix, ".docx")

    def test_pick_latest_rules_source_falls_back_to_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            pdf_path = inbox / "rules.pdf"
            pdf_path.write_text("pdf", encoding="utf-8")

            selected = MODULE.pick_latest_rules_source(inbox)

        self.assertEqual(selected, pdf_path)


if __name__ == "__main__":
    unittest.main()
