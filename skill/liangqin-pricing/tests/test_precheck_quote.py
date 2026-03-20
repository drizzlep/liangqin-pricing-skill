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

    def test_generic_cabinet_with_unique_dimension_match_also_asks_door_type(self) -> None:
        args = self.make_args(category="玄关柜", length="1.2", depth="0.4", height="2.4", material="北美黑胡桃木")
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "door_type")

    def test_generic_bookcase_with_nonstandard_dimensions_skips_quote_kind_and_asks_door_path(self) -> None:
        args = self.make_args(category="书柜", length="2", depth="0.35", height="2.4", material="北美樱桃木")
        result = MODULE.precheck_cabinet(args)
        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "has_door")

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


if __name__ == "__main__":
    unittest.main()
