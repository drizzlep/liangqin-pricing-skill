import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_hidden_rosewood_discount.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_hidden_rosewood_discount", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateHiddenRosewoodDiscountTests(unittest.TestCase):
    def test_black_walnut_exposed_surface_gets_15_percent_discount(self) -> None:
        result = MODULE.calculate_discount(
            exposed_material="北美黑胡桃木",
            base_unit_price=8680,
        )
        self.assertEqual(result["discount_rate"], 0.15)
        self.assertEqual(result["discount_factor"], 0.85)
        self.assertEqual(result["adjusted_unit_price"], 7378.0)

    def test_cherry_exposed_surface_gets_5_percent_discount(self) -> None:
        result = MODULE.calculate_discount(
            exposed_material="北美樱桃木",
            base_unit_price=5880,
        )
        self.assertEqual(result["discount_rate"], 0.05)
        self.assertEqual(result["discount_factor"], 0.95)
        self.assertEqual(result["adjusted_unit_price"], 5586.0)

    def test_alias_material_name_uses_same_discount_rule(self) -> None:
        result = MODULE.calculate_discount(
            exposed_material="北美白橡",
            base_unit_price=6880,
        )

        self.assertEqual(result["exposed_material"], "北美白橡木")
        self.assertEqual(result["discount_rate"], 0.10)
        self.assertEqual(result["adjusted_unit_price"], 6192.0)

    def test_unknown_material_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.calculate_discount(
                exposed_material="未知木材",
                base_unit_price=6880,
            )


if __name__ == "__main__":
    unittest.main()
