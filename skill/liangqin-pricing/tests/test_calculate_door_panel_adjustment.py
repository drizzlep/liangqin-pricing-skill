import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_door_panel_adjustment.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_door_panel_adjustment", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateDoorPanelAdjustmentTests(unittest.TestCase):
    def test_same_material_texture_continuity_uses_frame_to_flat_difference(self) -> None:
        result = MODULE.calculate_adjustment(
            cabinet_material="北美黑胡桃木",
            target_door_material="北美黑胡桃木",
            base_unit_price=8680,
            cabinet_door_family="frame",
            target_door_family="flat",
        )
        self.assertEqual(result["cabinet_door_unit_price"], 2980)
        self.assertEqual(result["target_door_unit_price"], 3880)
        self.assertEqual(result["door_unit_diff"], 900)
        self.assertEqual(result["adjusted_base_unit"], 9580)

    def test_mixed_material_flowyun_door_uses_door_panel_difference_not_cabinet_difference(self) -> None:
        result = MODULE.calculate_adjustment(
            cabinet_material="北美白橡木",
            target_door_material="北美黑胡桃木",
            base_unit_price=6880,
            cabinet_door_family="flat",
            target_door_family="flat",
        )
        self.assertEqual(result["cabinet_door_unit_price"], 2980)
        self.assertEqual(result["target_door_unit_price"], 3880)
        self.assertEqual(result["door_unit_diff"], 900)
        self.assertEqual(result["adjusted_base_unit"], 7780)


if __name__ == "__main__":
    unittest.main()
