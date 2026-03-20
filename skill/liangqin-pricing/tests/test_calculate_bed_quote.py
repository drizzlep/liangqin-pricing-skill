import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_bed_quote.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_bed_quote", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateBedQuoteTests(unittest.TestCase):
    def test_derived_1_2_meter_price_uses_1_5_minus_1_8_gap(self) -> None:
        result = MODULE.calculate_bed_quote(
            name_exact="抛物线架式床",
            material="北美黑胡桃木",
            width="1.2",
            length="2",
        )
        self.assertEqual(result["pricing_rule"], "standard_width_1_2")
        self.assertEqual(result["base_price"], 10220.0)
        self.assertEqual(result["formal_total"], 10220)

    def test_oversized_bed_uses_1_5_meter_base_price_for_proportion(self) -> None:
        result = MODULE.calculate_bed_quote(
            name_exact="经典箱体床",
            material="北美黑胡桃木",
            width="2",
            length="2",
        )
        self.assertEqual(result["pricing_rule"], "oversize_proportion")
        self.assertEqual(result["base_price"], 12800.0)
        self.assertAlmostEqual(result["final_price"], 17066.67, places=2)
        self.assertEqual(result["formal_total"], 17067)

    def test_raised_frame_bed_adds_15_percent_on_whole_bed(self) -> None:
        result = MODULE.calculate_bed_quote(
            name_exact="抛物线架式床",
            material="北美黑胡桃木",
            width="1.8",
            length="2",
            raise_height=True,
        )
        self.assertEqual(result["pricing_rule"], "standard_width_1_8")
        self.assertEqual(result["base_price"], 12980.0)
        self.assertEqual(result["height_markup_amount"], 1947.0)
        self.assertEqual(result["formal_total"], 14927)


if __name__ == "__main__":
    unittest.main()
