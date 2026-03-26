import argparse
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "precheck_quote.py"
SPEC = importlib.util.spec_from_file_location("precheck_quote", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PrecheckQuoteTests(unittest.TestCase):
    def make_args(self, **overrides):
        defaults = dict(
            category="",
            length=None,
            depth=None,
            height=None,
            width=None,
            material=None,
            quote_kind="unknown",
            has_door="unknown",
            door_type="",
            series="",
            shape="",
            bed_form="",
            access_style="",
            lower_bed_type="",
            guardrail_style="",
            guardrail_length="",
            guardrail_height="",
            access_height="",
            stair_width="",
            stair_depth="",
            underbed_cabinet_mode="",
            front_cabinet_length="",
            front_cabinet_height="",
            front_cabinet_depth="",
            front_cabinet_mode="",
            rear_cabinet_length="",
            rear_cabinet_height="",
            rear_cabinet_depth="",
            rear_cabinet_mode="",
            interconnected_rows=False,
            approximate_only=False,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_explicit_standard_table_product_with_standard_length_does_not_require_depth(self) -> None:
        args = self.make_args(category="罗胖餐桌", length="1.8", material="北美樱桃木")
        result = MODULE.precheck_table(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertIsNone(result["next_required_field"])

    def test_explicit_unique_standard_cabinet_product_does_not_require_dimensions(self) -> None:
        args = self.make_args(category="经典电视柜", material="北美黑胡桃木")
        result = MODULE.precheck_cabinet(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertIsNone(result["next_required_field"])

    def test_explicit_child_bed_with_multiple_variants_asks_lower_bed_structure(self) -> None:
        args = self.make_args(category="经典挂梯上下床", width="1.2", length="2", material="北美樱桃木")
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "shape")
        self.assertIn("抽屉", result["next_question"])
        self.assertIn("架式", result["next_question"])

    def test_explicit_cabinet_with_dimension_match_asks_door_type_instead_of_quote_kind(self) -> None:
        args = self.make_args(category="经典玄关柜", length="1.2", depth="0.4", height="2.4", material="北美黑胡桃木")
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "door_type")

    def test_explicit_bookcase_product_without_depth_uses_catalog_default_depth(self) -> None:
        args = self.make_args(category="飘飘书柜", length="1.5", height="1", material="北美黑胡桃木")
        result = MODULE.precheck_cabinet(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertIsNone(result["next_required_field"])
        self.assertEqual(result["assumed_defaults"][0]["field"], "depth")
        self.assertEqual(result["assumed_defaults"][0]["value"], "0.35")
        self.assertEqual(result["default_quote_profile"]["name"], "飘飘家开放书柜")

    def test_generic_cabinets_with_defaults_are_ready_for_formal_quote(self) -> None:
        cases = [
            ("书柜", "2", None, "2.4", "北美樱桃木", "飘飘家开放书柜", "0.35", "no"),
            ("衣柜", "1.8", None, "2.2", "北美黑胡桃木", "升级经典门衣柜", "0.6", "yes"),
            ("玄关柜", "1.2", None, "2.4", "北美黑胡桃木", "经典玄关柜", "0.4", "yes"),
            ("电视柜", "2.2", None, "1.85", "北美黑胡桃木", "简美电视柜及配柜", "0.45", "unknown"),
            ("餐边柜", "1.5", None, "2.2", "北美黑胡桃木", "简美餐边柜高柜", "0.45", "unknown"),
        ]

        for category, length, depth, height, material, anchor_name, default_depth, default_has_door in cases:
            with self.subTest(category=category):
                args = self.make_args(
                    category=category,
                    length=length,
                    depth=depth,
                    height=height,
                    material=material,
                )
                result = MODULE.precheck_cabinet(args)
                self.assertTrue(result["ready_for_formal_quote"])
                self.assertIsNone(result["next_required_field"])
                self.assertEqual(result["default_quote_profile"]["name"], anchor_name)
                self.assertEqual(result["default_quote_profile"]["assumed_depth"], default_depth)
                self.assertEqual(result["default_quote_profile"]["assumed_has_door"], default_has_door)

    def test_generic_bookcase_with_explicit_depth_still_uses_default_open_profile(self) -> None:
        args = self.make_args(category="书柜", length="2", depth="0.35", height="2.4", material="北美樱桃木")
        result = MODULE.precheck_cabinet(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertEqual(result["default_quote_profile"]["name"], "飘飘家开放书柜")
        self.assertEqual(result["default_quote_profile"]["assumed_has_door"], "no")

    def test_generic_bookcase_with_adjustment_keyword_does_not_use_default_profile(self) -> None:
        args = self.make_args(category="书柜", length="2", height="2.4", material="北美樱桃木", shape="带抽屉")
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "depth")
        self.assertNotIn("default_quote_profile", result)

    def test_diamond_cabinet_asks_structure_rule_instead_of_generic_door_path(self) -> None:
        args = self.make_args(category="钻石柜", length="1.2", depth="0.4", height="2.4", material="北美白蜡木")
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "shape")
        self.assertIn("钻石柜", result["next_question"])
        self.assertIn("开放", result["next_question"])

    def test_generic_adult_frame_bed_asks_style_instead_of_quote_kind(self) -> None:
        args = self.make_args(category="架式床", width="1.2", length="2", material="北美黑胡桃木")
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "series")
        self.assertIn("具体款式", result["next_question"])
        self.assertIn("抛物线架式床", result["next_question"])

    def test_custom_child_bed_routes_to_modular_path_and_asks_bed_form(self) -> None:
        args = self.make_args(category="定制儿童床", width="1.2", length="2", material="北美樱桃木")
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed")
        self.assertEqual(result["next_required_field"], "bed_form")
        self.assertIn("上下床", result["next_question"])
        self.assertIn("半高床", result["next_question"])

    def test_custom_semi_loft_child_bed_asks_access_style_after_bed_form(self) -> None:
        args = self.make_args(
            category="定制半高床",
            width="1.2",
            length="2",
            material="北美樱桃木",
            bed_form="半高床",
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed")
        self.assertEqual(result["next_required_field"], "access_style")
        self.assertIn("直梯", result["next_question"])
        self.assertIn("梯柜", result["next_question"])

    def test_explicit_catalog_child_bed_keeps_catalog_route(self) -> None:
        args = self.make_args(category="经典梯柜上下床", width="1.2", length="2", material="北美樱桃木")
        result = MODULE.precheck_bed(args)
        self.assertEqual(result["pricing_route"], "catalog_child_bed")

    def test_ready_custom_bunk_bed_uses_modular_route(self) -> None:
        args = self.make_args(
            category="定制上下床",
            width="1.2",
            length="2",
            material="北美白橡木",
            bed_form="上下床",
            access_style="梯柜",
            lower_bed_type="箱体床",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
        )
        result = MODULE.precheck_bed(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed")

    def test_modular_child_bed_with_nonstandard_guardrail_alias_asks_for_standard_guardrail_name(self) -> None:
        args = self.make_args(
            category="半高床",
            quote_kind="custom",
            bed_form="半高床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
            guardrail_style="经典护栏款",
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "guardrail_style")
        self.assertIn("标准围栏", result["next_question"])

    def test_half_loft_with_underbed_double_row_cabinets_asks_front_depth_before_quote(self) -> None:
        args = self.make_args(
            category="半高床",
            quote_kind="custom",
            bed_form="半高床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_mode="有门无背板",
            rear_cabinet_length="2",
            rear_cabinet_height="1.2",
            rear_cabinet_mode="无门有背板",
            interconnected_rows=True,
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(result["next_required_field"], "front_cabinet_depth")
        self.assertIn("前排", result["next_question"])
        self.assertIn("进深", result["next_question"])

    def test_half_loft_with_underbed_double_row_cabinets_is_ready_when_combo_fields_complete(self) -> None:
        args = self.make_args(
            category="半高床",
            quote_kind="custom",
            bed_form="半高床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
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
        result = MODULE.precheck_bed(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")

    def test_half_loft_with_underbed_double_row_cabinets_asks_rear_depth_after_front_is_complete(self) -> None:
        args = self.make_args(
            category="半高床",
            quote_kind="custom",
            bed_form="半高床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
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
            rear_cabinet_mode="无门有背板",
            interconnected_rows=True,
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(result["next_required_field"], "rear_cabinet_depth")
        self.assertIn("后排", result["next_question"])

    def test_half_loft_with_invalid_front_underbed_mode_asks_for_supported_structure_name(self) -> None:
        args = self.make_args(
            category="半高床",
            quote_kind="custom",
            bed_form="半高床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            stair_width="0.52",
            stair_depth="0.5",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_depth="0.45",
            front_cabinet_mode="经典门柜体",
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "front_cabinet_mode")
        self.assertIn("标准结构名称", result["next_question"])

    def test_loft_with_single_underbed_row_is_ready_for_combo_route(self) -> None:
        args = self.make_args(
            category="高架床",
            quote_kind="custom",
            bed_form="高架床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
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
        result = MODULE.precheck_bed(args)
        self.assertTrue(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")

    def test_underbed_combo_depth_limit_is_checked_before_stair_follow_up(self) -> None:
        args = self.make_args(
            category="半高床",
            quote_kind="custom",
            bed_form="半高床",
            access_style="梯柜",
            width="1.2",
            length="2",
            material="北美白蜡木",
            guardrail_style="胶囊围栏",
            guardrail_length="2",
            guardrail_height="0.4",
            front_cabinet_length="2",
            front_cabinet_height="1.2",
            front_cabinet_depth="0.5",
            front_cabinet_mode="有门无背板",
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(result["next_required_field"], "front_cabinet_depth")
        self.assertIn("450mm", result["next_question"])
        self.assertNotIn("踏步宽度", result["next_question"])

    def test_loft_width_limit_returns_constraint_before_more_questions(self) -> None:
        args = self.make_args(
            category="高架床",
            quote_kind="custom",
            bed_form="高架床",
            access_style="梯柜",
            width="1.35",
            length="2",
            material="北美白蜡木",
        )
        result = MODULE.precheck_bed(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["pricing_route"], "modular_child_bed")
        self.assertEqual(result["next_required_field"], "width")
        self.assertIn("不大于 1.2 米", result["next_question"])

    def test_open_wardrobe_with_backboard_does_not_use_default_door_profile(self) -> None:
        args = self.make_args(
            category="衣柜",
            quote_kind="custom",
            length="2",
            height="1.2",
            material="北美白蜡木",
            has_door="no",
            shape="有背板",
        )
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "depth")
        self.assertNotIn("default_quote_profile", result)

    def test_double_row_interconnected_cabinet_does_not_use_generic_default_profile(self) -> None:
        args = self.make_args(
            category="衣柜",
            quote_kind="custom",
            length="2",
            height="1.2",
            material="乌拉圭玫瑰木",
            has_door="yes",
            door_type="带门",
            shape="前后双排互通 无背板",
        )
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "depth")
        self.assertNotIn("default_quote_profile", result)


if __name__ == "__main__":
    unittest.main()
