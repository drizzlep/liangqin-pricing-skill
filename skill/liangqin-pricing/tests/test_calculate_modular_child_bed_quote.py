import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "calculate_modular_child_bed_quote.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("calculate_modular_child_bed_quote", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CalculateModularChildBedQuoteTests(unittest.TestCase):
    def test_bunk_bed_uses_frame_railing_and_ladder_modules(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="上下床",
            material="北美樱桃木",
            width="1.2",
            length="2",
            access_style="直梯",
            access_height="1.5",
            lower_bed_type="架式床",
            guardrail_style="篱笆围栏",
            guardrail_length="2",
            guardrail_height="0.4",
        )
        self.assertEqual(result["formal_total"], 11736)
        self.assertEqual(result["pricing_method"], "模块化儿童床组合计价")
        self.assertIn("高架床模块", "\n".join(result["calculation_steps"]))
        self.assertIn("直梯", "\n".join(result["calculation_steps"]))

    def test_stair_cabinet_uses_width_band_pricing(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="上下床",
            material="北美白橡木",
            width="1.2",
            length="2",
            access_style="梯柜",
            stair_width="0.52",
            stair_depth="0.5",
            lower_bed_type="箱体床",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
        )
        self.assertEqual(result["formal_total"], 20275)
        self.assertIn("500-600", "\n".join(result["calculation_steps"]))

    def test_semi_loft_maps_to_single_high_bed_combo(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="半高床",
            material="北美黑胡桃木",
            width="1",
            length="2",
            access_style="斜梯",
            access_height="1.2",
            guardrail_style="圆柱围栏",
            guardrail_length="2",
            guardrail_height="0.35",
        )
        self.assertEqual(result["formal_total"], 8915)
        self.assertIn("半高床按高架床单层模块组合", "\n".join(result["calculation_steps"]))

    def test_bunk_bed_with_slanted_ladder_uses_linear_ladder_pricing(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="上下床",
            material="北美白蜡木",
            width="1",
            length="2",
            access_style="斜梯",
            access_height="1.3",
            lower_bed_type="架式床",
            guardrail_style="圆柱围栏",
            guardrail_length="2",
            guardrail_height="0.35",
        )
        self.assertEqual(result["formal_total"], 9955)
        self.assertIn("斜梯", "\n".join(result["calculation_steps"]))

    def test_loft_bed_with_stair_cabinet_uses_high_bed_combo_without_lower_bed(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="高架床",
            material="北美白橡木",
            width="1.2",
            length="2",
            access_style="梯柜",
            stair_width="0.51",
            stair_depth="0.5",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
        )
        self.assertEqual(result["formal_total"], 10685)
        self.assertNotIn("箱体床模块", "\n".join(result["calculation_steps"]))
        self.assertNotIn("架式床模块", "\n".join(result["calculation_steps"]))

    def test_stair_width_band_boundary_uses_450_500_band_at_exact_500mm(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="高架床",
            material="北美白橡木",
            width="1.2",
            length="2",
            access_style="梯柜",
            stair_width="0.5",
            stair_depth="0.5",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
        )
        self.assertEqual(result["formal_total"], 10340)
        self.assertIn("450-500", "\n".join(result["calculation_steps"]))

    def test_staggered_bed_general_formula_combines_upper_lower_railing_and_access(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="错层床",
            material="北美白橡木",
            width="1.2",
            length="2",
            access_style="斜梯",
            access_height="1.4",
            lower_bed_type="架式床",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
        )
        self.assertEqual(result["formal_total"], 15262)
        self.assertIn("错层床当前按高架床上层 + 下层床架模块组合", "\n".join(result["calculation_steps"]))

    def test_rosewood_special_modules_override_general_formula(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="上下床",
            material="乌拉圭玫瑰木",
            width="1.2",
            length="2",
            access_style="梯柜",
            lower_bed_type="架式床",
            guardrail_style="篱笆围栏",
            stair_width="0.52",
            stair_depth="0.5",
        )
        self.assertEqual(result["formal_total"], 12970)
        text = "\n".join(result["calculation_steps"])
        self.assertIn("玫瑰木特价", text)
        self.assertNotIn("高架床模块：2 × 1.2", text)

    def test_staggered_rosewood_special_overrides_general_formula(self) -> None:
        result = MODULE.calculate_modular_child_bed_quote(
            bed_form="错层床",
            material="乌拉圭玫瑰木",
            width="1.2",
            length="2",
            access_style="斜梯",
            access_height="1.4",
            lower_bed_type="架式床",
            guardrail_style="城堡围栏",
        )
        self.assertEqual(result["formal_total"], 11370)
        text = "\n".join(result["calculation_steps"])
        self.assertIn("玫瑰木特价上床模块", text)
        self.assertNotIn("高架床模块：2 × 1.2", text)

    def test_upper_width_over_limit_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.calculate_modular_child_bed_quote(
                bed_form="上下床",
                material="北美樱桃木",
                width="1.35",
                length="2",
                access_style="直梯",
                access_height="1.5",
                lower_bed_type="架式床",
                guardrail_style="篱笆围栏",
                guardrail_length="2",
                guardrail_height="0.4",
            )


if __name__ == "__main__":
    unittest.main()
