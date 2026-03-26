import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_modular_child_bed_combo_quote.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_modular_child_bed_combo_quote", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateModularChildBedComboQuoteTests(unittest.TestCase):
    def test_half_loft_with_single_front_wardrobe_sums_bed_and_front_row(self) -> None:
        result = MODULE.calculate_modular_child_bed_combo_quote(
            material="乌拉圭玫瑰木",
            bed_form="半高床",
            width="1.2",
            length="2",
            access_style="梯柜",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_depth="0.45",
            front_cabinet_mode="有门无背板",
        )
        self.assertEqual(result["formal_total"], 19481)
        self.assertNotIn("后排衣柜", "\n".join(result["calculation_steps"]))

    def test_half_loft_with_double_row_wardrobes_sums_bed_and_cabinet_rows(self) -> None:
        result = MODULE.calculate_modular_child_bed_combo_quote(
            material="乌拉圭玫瑰木",
            bed_form="半高床",
            width="1.2",
            length="2",
            access_style="梯柜",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_depth="0.45",
            front_cabinet_mode="有门无背板",
            rear_cabinet_length="2",
            rear_cabinet_height="1.2",
            rear_cabinet_depth="0.45",
            rear_cabinet_mode="无门有背板",
            interconnected_rows=True,
        )
        self.assertEqual(result["formal_total"], 26557)
        steps = "\n".join(result["calculation_steps"])
        self.assertIn("模块化儿童半高床", result["product"])
        self.assertIn("前排衣柜（有门无背板）", steps)
        self.assertIn("后排衣柜（无门有背板）", steps)
        self.assertIn("床下前后双排柜体互通", result["confirmed"])

    def test_white_ash_combo_uses_white_ash_cabinet_prices(self) -> None:
        result = MODULE.calculate_modular_child_bed_combo_quote(
            material="北美白蜡木",
            bed_form="半高床",
            width="1.2",
            length="2",
            access_style="梯柜",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_depth="0.45",
            front_cabinet_mode="有门无背板",
            rear_cabinet_length="2",
            rear_cabinet_height="1.2",
            rear_cabinet_depth="0.45",
            rear_cabinet_mode="无门有背板",
        )
        self.assertEqual(result["formal_total"], 29309)
        self.assertIn("北美白蜡木", result["product"])

    def test_loft_with_single_backboard_front_row_uses_underbed_combo_route(self) -> None:
        result = MODULE.calculate_modular_child_bed_combo_quote(
            material="北美白蜡木",
            bed_form="高架床",
            width="1.2",
            length="2",
            access_style="梯柜",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_depth="0.45",
            front_cabinet_mode="无门有背板",
        )
        self.assertEqual(result["formal_total"], 16445)
        self.assertIn("前排衣柜（无门有背板）", "\n".join(result["calculation_steps"]))

    def test_underbed_projection_area_floor_applies_to_small_row(self) -> None:
        result = MODULE.calculate_modular_child_bed_combo_quote(
            material="北美白蜡木",
            bed_form="半高床",
            width="1",
            length="2",
            access_style="斜梯",
            access_height="1.2",
            guardrail_style="圆柱围栏",
            guardrail_length="2",
            guardrail_height="0.35",
            front_cabinet_length="1",
            front_cabinet_height="1",
            front_cabinet_depth="0.45",
            front_cabinet_mode="无门有背板",
        )
        self.assertEqual(result["formal_total"], 11023)
        self.assertIn("投影面积不足 1.6㎡", "\n".join(result["calculation_steps"]))

    def test_unsupported_underbed_cabinet_mode_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.calculate_modular_child_bed_combo_quote(
                material="北美白蜡木",
                bed_form="半高床",
                width="1",
                length="2",
                access_style="斜梯",
                access_height="1.2",
                guardrail_style="圆柱围栏",
                guardrail_length="2",
                guardrail_height="0.35",
                front_cabinet_length="1",
                front_cabinet_height="1",
                front_cabinet_depth="0.45",
                front_cabinet_mode="经典门柜体",
            )

    def test_underbed_cabinet_depth_over_limit_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.calculate_modular_child_bed_combo_quote(
                material="北美白蜡木",
                bed_form="半高床",
                width="1.2",
                length="2",
                access_style="梯柜",
                guardrail_style="胶囊围栏",
                guardrail_length="2",
                guardrail_height="0.4",
                stair_width="0.52",
                stair_depth="0.5",
                front_cabinet_length="2",
                front_cabinet_height="1.2",
                front_cabinet_depth="0.5",
                front_cabinet_mode="有门无背板",
            )


if __name__ == "__main__":
    unittest.main()
