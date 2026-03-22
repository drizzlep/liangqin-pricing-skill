import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_and_test.py"
SPEC = importlib.util.spec_from_file_location("refresh_and_test", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RefreshAndTestTests(unittest.TestCase):
    def test_has_ready_sources_accepts_pdf_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            (inbox / "catalog.xlsx").write_text("xlsx", encoding="utf-8")
            (inbox / "rules.pdf").write_text("pdf", encoding="utf-8")

            self.assertTrue(MODULE.has_ready_sources(inbox))


if __name__ == "__main__":
    unittest.main()
