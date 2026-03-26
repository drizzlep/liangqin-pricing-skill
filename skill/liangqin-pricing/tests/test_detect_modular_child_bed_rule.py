import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "detect_modular_child_bed_rule.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("detect_modular_child_bed_rule", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DetectModularChildBedRuleTests(unittest.TestCase):
    def test_detects_width_limit_for_loft_bed(self) -> None:
        result = MODULE.detect_rule("做一张定制高架床，1.35米乘2米，北美白橡木，梯柜款，胶囊围栏。")
        self.assertTrue(result["matched"])
        self.assertEqual(result["recommended_reply_mode"], "constraint")
        self.assertEqual(result["next_required_field"], "width")
        self.assertIn("1.2 米", result["next_question"])

    def test_detects_rear_depth_missing_without_confusing_stair_depth(self) -> None:
        text = (
            "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，胶囊围栏，围栏长2米高0.4米，"
            "梯柜踏步宽520，进深500。床下前后双排衣柜，前后柜体互通形式。前排衣柜深450，"
            "有门无背板，长2米高1.2米；后方无门有背板的衣柜长2米高1.2米。请帮忙看下多少钱。"
        )
        result = MODULE.detect_rule(text)
        self.assertTrue(result["matched"])
        self.assertEqual(result["recommended_reply_mode"], "follow_up")
        self.assertEqual(result["next_required_field"], "rear_cabinet_depth")
        self.assertIn("后排柜体", result["next_question"])
        self.assertIn("梯柜进深", result["next_question"])

    def test_detects_underbed_depth_limit(self) -> None:
        result = MODULE.detect_rule(
            "一张北美白蜡木半高梯柜上铺床1.2*2米床垫尺寸的，胶囊围栏。床下前排做有门无背板衣柜，长2米高1.2米深500。请直接正式报价。"
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["recommended_reply_mode"], "constraint")
        self.assertEqual(result["next_required_field"], "front_cabinet_depth")
        self.assertIn("450mm", result["next_question"])

    def test_detects_guardrail_alias(self) -> None:
        result = MODULE.detect_rule("做一张定制半高床，1.2米乘2米，北美白蜡木，梯柜款，经典护栏款。")
        self.assertTrue(result["matched"])
        self.assertEqual(result["recommended_reply_mode"], "follow_up")
        self.assertEqual(result["next_required_field"], "guardrail_style")
        self.assertIn("标准围栏名称", result["next_question"])


if __name__ == "__main__":
    unittest.main()
