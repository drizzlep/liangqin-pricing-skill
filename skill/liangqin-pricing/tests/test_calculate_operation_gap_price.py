import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_operation_gap_price.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_operation_gap_price", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateOperationGapPriceTests(unittest.TestCase):
    def test_black_walnut_gap_area_uses_table_six_price(self) -> None:
        result = MODULE.calculate_operation_gap_price(
            material="北美黑胡桃木",
            width="1.2",
            height="0.6",
        )
        self.assertEqual(result["unit_price"], 2002)
        self.assertAlmostEqual(result["area"], 0.72, places=2)
        self.assertAlmostEqual(result["subtotal"], 1441.44, places=2)

    def test_luminous_backboard_uses_white_oak_price(self) -> None:
        result = MODULE.calculate_operation_gap_price(
            material="北美白橡木",
            width="1",
            height="0.5",
            luminous_backboard=True,
        )
        self.assertEqual(result["unit_price"], 1630)
        self.assertAlmostEqual(result["subtotal"], 815.0, places=2)


if __name__ == "__main__":
    unittest.main()
