import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "detect_special_cabinet_rule.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("detect_special_cabinet_rule", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DetectSpecialCabinetRuleTests(unittest.TestCase):
    def test_detects_hidden_rosewood_discount(self) -> None:
        result = MODULE.detect_rule("做个北美黑胡桃木流云衣柜，见光面黑胡桃，非见光面玫瑰木，1.8乘2.2乘0.6，多少钱？")
        self.assertEqual(result["special_rule"], "hidden_rosewood_discount")
        self.assertEqual(result["constraint_code"], "special_cabinet_rule.hidden_rosewood_discount")
        self.assertEqual(result["detail_level_hint"], "rule_routing")

    def test_detects_double_sided_door(self) -> None:
        result = MODULE.detect_rule("做个北美黑胡桃木双面门柜体，长1.8米，高2.4米，深600，多少钱？")
        self.assertEqual(result["special_rule"], "double_sided_door")
        self.assertEqual(result["next_required_field"], "door_type")
        self.assertEqual(result["question_code"], "special_cabinet_rule.door_type.required")
        self.assertEqual(result["missing_fields"], ["door_type"])
        self.assertEqual(result["route"], "special_cabinet_rule")
        self.assertEqual(result["detail_level_hint"], "single_question_follow_up")
        self.assertIn("两边分别", result["next_question"])
        self.assertIn("拼框/平板", result["next_question"])

    def test_detects_operation_gap(self) -> None:
        result = MODULE.detect_rule("做个北美白橡木电视背景柜，中间留操作空区，长2.4米，高2.4米，深400，多少钱？")
        self.assertEqual(result["special_rule"], "operation_gap")
        self.assertEqual(result["next_required_field"], "gap_size")
        self.assertIn("空区", result["next_question"])
        self.assertIn("宽和高", result["next_question"])

    def test_detects_diamond_cabinet_and_returns_single_question(self) -> None:
        result = MODULE.detect_rule("做个北美白蜡木钻石柜，长1.2米，高2.4米，深400，多少钱？")
        self.assertEqual(result["special_rule"], "diamond_cabinet")
        self.assertEqual(result["next_required_field"], "shape")
        self.assertIn("钻石柜", result["next_question"])

    def test_detects_fridge_cabinet_and_asks_opening_height(self) -> None:
        result = MODULE.detect_rule("做个北美白橡木冰箱柜，长0.9米，高2.4米，深650，多少钱？")
        self.assertEqual(result["special_rule"], "fridge_cabinet")
        self.assertEqual(result["next_required_field"], "fridge_opening_height")
        self.assertIn("冰箱净高", result["next_question"])


if __name__ == "__main__":
    unittest.main()
