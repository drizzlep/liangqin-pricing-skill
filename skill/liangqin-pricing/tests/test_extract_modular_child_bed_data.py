import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_modular_child_bed_data.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("extract_modular_child_bed_data", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ExtractModularChildBedDataTests(unittest.TestCase):
    def test_general_component_prices_expand_shared_material_column(self) -> None:
        prices = MODULE.material_prices_from_general_row(["1068", "1208", "1506", "1798"])
        self.assertEqual(prices["玫瑰木"], 1068.0)
        self.assertEqual(prices["樱桃木"], 1208.0)
        self.assertEqual(prices["白蜡木"], 1208.0)
        self.assertEqual(prices["白橡木"], 1506.0)
        self.assertEqual(prices["黑胡桃"], 1798.0)

    def test_size_label_normalization(self) -> None:
        self.assertEqual(MODULE.normalize_size_label("1.2*2米"), "1.2x2")
        self.assertEqual(MODULE.normalize_size_label("0.9*2 米"), "0.9x2")

    def test_stair_width_band_detection(self) -> None:
        self.assertEqual(MODULE.stair_width_band("0.48"), "450-500")
        self.assertEqual(MODULE.stair_width_band("0.55"), "500-600")


if __name__ == "__main__":
    unittest.main()
