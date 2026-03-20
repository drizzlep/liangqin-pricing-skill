import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_price_index.py"
SPEC = importlib.util.spec_from_file_location("extract_price_index", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ExtractPriceIndexTests(unittest.TestCase):
    def test_child_bed_variant_tag(self) -> None:
        self.assertEqual(MODULE.child_bed_variant_tag("下床（抽屉）"), "下床抽屉款")
        self.assertEqual(MODULE.child_bed_variant_tag("下床（架式）"), "下床架式款")
        self.assertEqual(MODULE.child_bed_variant_tag("下床（箱体）"), "下床箱体款")
        self.assertEqual(MODULE.child_bed_variant_tag("上床"), "")


if __name__ == "__main__":
    unittest.main()
