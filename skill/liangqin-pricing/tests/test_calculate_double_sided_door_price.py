import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_double_sided_door_price.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_double_sided_door_price", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateDoubleSidedDoorPriceTests(unittest.TestCase):
    def test_black_walnut_frame_flat_uses_deep_band_table_five(self) -> None:
        result = MODULE.calculate_double_sided_price(
            material="北美黑胡桃木",
            depth="0.6",
            side_a_family="frame",
            side_b_family="flat",
        )
        self.assertEqual(result["depth_band"], "450_lt_depth_lte_600")
        self.assertEqual(result["door_combo"], "frame/flat")
        self.assertEqual(result["unit_price"], 10410)

    def test_black_walnut_flat_flat_uses_shallow_band_table_five(self) -> None:
        result = MODULE.calculate_double_sided_price(
            material="北美黑胡桃木",
            depth="0.45",
            side_a_family="flat",
            side_b_family="flat",
        )
        self.assertEqual(result["depth_band"], "depth_lte_450")
        self.assertEqual(result["door_combo"], "flat/flat")
        self.assertEqual(result["unit_price"], 11010)


if __name__ == "__main__":
    unittest.main()
