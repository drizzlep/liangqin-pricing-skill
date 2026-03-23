import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_rock_slab_price.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_rock_slab_price", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateRockSlabPriceTests(unittest.TestCase):
    def test_countertop_adds_1460_per_meter_to_base_subtotal(self) -> None:
        result = MODULE.calculate_rock_slab_price(
            scenario="rock_slab_countertop",
            slab_length="1.8",
            base_subtotal=34372.8,
        )

        self.assertEqual(result["scenario"], "rock_slab_countertop")
        self.assertAlmostEqual(result["rock_slab_addition"], 2628.0, places=2)
        self.assertAlmostEqual(result["side_panel_addition"], 0.0, places=2)
        self.assertAlmostEqual(result["final_subtotal"], 37000.8, places=2)
        self.assertIn("1460", result["calculation_steps"][1])

    def test_aluminum_frame_door_adds_1860_per_meter_to_base_subtotal(self) -> None:
        result = MODULE.calculate_rock_slab_price(
            scenario="rock_slab_aluminum_frame_door",
            slab_length="2",
            base_subtotal=18800,
        )

        self.assertAlmostEqual(result["rock_slab_addition"], 3720.0, places=2)
        self.assertAlmostEqual(result["final_subtotal"], 22520.0, places=2)
        self.assertIn("无门柜体", result["calculation_steps"][0])

    def test_backboard_below_55cm_skips_side_panel_addition(self) -> None:
        result = MODULE.calculate_rock_slab_price(
            scenario="rock_slab_backboard",
            slab_length="1.2",
            opening_height="0.54",
            cabinet_material="北美白橡木",
            base_subtotal=12000,
        )

        self.assertAlmostEqual(result["rock_slab_addition"], 1752.0, places=2)
        self.assertAlmostEqual(result["side_panel_addition"], 0.0, places=2)
        self.assertAlmostEqual(result["final_subtotal"], 13752.0, places=2)

    def test_backboard_at_or_above_55cm_requires_side_panel_area_price(self) -> None:
        result = MODULE.calculate_rock_slab_price(
            scenario="rock_slab_backboard",
            slab_length="1.5",
            opening_height="0.55",
            cabinet_material="北美黑胡桃木",
            side_panel_area="0.36",
            base_subtotal=15000,
        )

        self.assertAlmostEqual(result["rock_slab_addition"], 2190.0, places=2)
        self.assertAlmostEqual(result["side_panel_addition"], 730.08, places=2)
        self.assertAlmostEqual(result["final_subtotal"], 17920.08, places=2)
        self.assertIn("2028", result["calculation_steps"][2])

    def test_backboard_at_or_above_55cm_without_side_panel_area_raises(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.calculate_rock_slab_price(
                scenario="rock_slab_backboard",
                slab_length="1.5",
                opening_height="0.8",
                cabinet_material="北美黑胡桃木",
                base_subtotal=15000,
            )


if __name__ == "__main__":
    unittest.main()
