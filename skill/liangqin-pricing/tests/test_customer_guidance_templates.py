import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "customer_guidance_templates.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("customer_guidance_templates", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CustomerGuidanceTemplatesTests(unittest.TestCase):
    def test_precise_need_template_uses_product_name_and_goal_question(self) -> None:
        summary = MODULE.summarize_customer_guidance_template(
            customer_strategy="precise_need",
            response_stage="direction_confirm",
            signals={"product": ["书柜"], "goal": [], "space": [], "user": []},
        )

        self.assertEqual(summary["question_code"], "customer.precise_need.goal")
        self.assertIn("先按书柜方向帮你看", summary["reply_text"])
        self.assertIn("不急着区分目录成品还是定制", summary["reply_text"])
        self.assertIn("展示、收纳", summary["reply_text"])
        self.assertIn("下一步我先只确认一个问题", summary["reply_text"])

    def test_renovation_browse_template_keeps_space_first_question(self) -> None:
        summary = MODULE.summarize_customer_guidance_template(
            customer_strategy="renovation_browse",
            response_stage="direction_confirm",
            signals={"product": [], "goal": [], "space": [], "user": []},
        )

        self.assertEqual(summary["question_code"], "customer.renovation_browse.space")
        self.assertIn("装修前期", summary["reply_text"])
        self.assertIn("最想先看哪个空间", summary["reply_text"])

    def test_guided_discovery_template_adds_range_hint_for_proposal_stage(self) -> None:
        summary = MODULE.summarize_customer_guidance_template(
            customer_strategy="guided_discovery",
            response_stage="proposal_range",
            signals={"product": [], "goal": [], "space": [], "user": []},
        )

        self.assertEqual(summary["question_code"], "customer.guided_discovery.goal")
        self.assertIn("不急着帮你定具体家具", summary["reply_text"])
        self.assertIn("比较宽的预算区间", summary["reply_text"])

    def test_default_template_adds_reference_quote_hint_when_signals_are_nearly_ready(self) -> None:
        summary = MODULE.summarize_customer_guidance_template(
            customer_strategy="default",
            response_stage="reference_quote",
            signals={"product": [], "goal": ["空间利用"], "space": [], "user": []},
        )

        self.assertEqual(summary["question_code"], "customer.guided_discovery.user")
        self.assertIn("这种情况很常见", summary["reply_text"])
        self.assertIn("接近可以给参考报价", summary["reply_text"])
        self.assertIn("给谁用", summary["reply_text"])

    def test_second_turn_template_switches_to_follow_up_tone(self) -> None:
        summary = MODULE.summarize_customer_guidance_template(
            customer_strategy="precise_need",
            response_stage="direction_confirm",
            signals={"product": ["书柜"], "goal": ["收纳"], "space": [], "user": []},
            turn_index=2,
        )

        self.assertEqual(summary["question_code"], "customer.precise_need.space")
        self.assertIn("继续按书柜方向帮你往下收", summary["reply_text"])
        self.assertIn("不重复问前面已经确认过的方向", summary["reply_text"])


if __name__ == "__main__":
    unittest.main()
