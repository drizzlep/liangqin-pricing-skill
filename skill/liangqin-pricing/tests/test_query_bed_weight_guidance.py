import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "query_bed_weight_guidance.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("query_bed_weight_guidance", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QueryBedWeightGuidanceTests(unittest.TestCase):
    def test_query_guidance_matches_bed_weight_question_and_returns_strict_reply(self) -> None:
        payload = MODULE.query_guidance(
            "我要做一个尾翻箱体床，1.8乘2米，北美黑胡桃木，床垫重量暂时未知，你先按规则告诉我还需要补什么信息，以及举升器怎么判断。"
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["follow_up_question"], "请确认床垫重量")
        self.assertEqual(payload["route"], "bed_weight_guidance")
        self.assertEqual(payload["question_code"], "bed_weight_guidance.mattress_weight.required")
        self.assertEqual(payload["missing_fields"], ["mattress_weight"])
        self.assertEqual(payload["detail_level_hint"], "single_question_follow_up")
        self.assertIn("床垫重量应≤50kg", payload["suggested_reply"])
        self.assertIn("750N举升器", payload["suggested_reply"])
        self.assertIn("只补问", payload["suggested_reply"])
        self.assertIn("W=1800属于临界值", payload["suggested_reply"])
        self.assertIn("下单备注", payload["suggested_reply"])
        self.assertNotIn("一套750N举升器", payload["suggested_reply"])
        self.assertNotIn("默认一套", payload["suggested_reply"])
        self.assertNotIn("电动举升器", payload["suggested_reply"])
        self.assertNotIn("小蜻蜓举升器", payload["suggested_reply"])
        self.assertNotIn("力矩", payload["suggested_reply"])

    def test_query_guidance_extracts_width_and_length_when_present(self) -> None:
        payload = MODULE.query_guidance("尾翻箱体床，1.9乘2.1米，床垫重量未知，举升器怎么判断？")

        self.assertEqual(payload["width_mm"], 1900)
        self.assertEqual(payload["length_mm"], 2100)
        self.assertIn("W=1900mm", payload["suggested_reply"])
        self.assertIn("L=2100mm", payload["suggested_reply"])

    def test_query_guidance_returns_unmatched_for_irrelevant_text(self) -> None:
        payload = MODULE.query_guidance("无线单面板动能开关能不能配单色温灯带？")

        self.assertFalse(payload["matched"])
        self.assertEqual(payload["suggested_reply"], "")
        self.assertEqual(payload["missing_fields"], [])


if __name__ == "__main__":
    unittest.main()
