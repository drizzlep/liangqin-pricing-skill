import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "classify_quote_role.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("classify_quote_role", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ClassifyQuoteRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context_json = json.dumps(
            {
                "message_id": "om_role_1001",
                "sender_id": "ou_role_123456",
                "sender": "ou_role_123456",
                "timestamp": "Tue 2026-03-31 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

    def test_defaults_to_customer_for_natural_quote_request(self) -> None:
        result = MODULE.classify_role(
            text="我家次卧想做个北美白橡木衣柜，长2米高2.4米，先帮我看看大概多少钱。",
        )

        self.assertEqual(result["audience_role"], "customer")
        self.assertFalse(result["manual_override_active"])
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "precise_need")
        self.assertTrue(any(code.startswith("customer_precise_keyword") for code in result["reason_codes"]))

    def test_detects_designer_for_rule_and_structure_consultation(self) -> None:
        result = MODULE.classify_role(
            text="常规拆装柜体高度1700以内默认做顶盖侧还是侧盖顶？牙称高度一般多少？",
        )

        self.assertEqual(result["audience_role"], "designer")
        self.assertFalse(result["manual_override_active"])
        self.assertEqual(result["entry_mode"], "designer_rule_consultation")
        self.assertTrue(any(code.startswith("designer_keyword") for code in result["reason_codes"]))

    def test_detects_consultant_for_customer_handoff_language(self) -> None:
        result = MODULE.classify_role(
            text="你先帮我整理一版发客户的话术，这个白橡木衣柜 1.8×2.2×0.6 怎么回更合适？",
        )

        self.assertEqual(result["audience_role"], "consultant")
        self.assertFalse(result["manual_override_active"])
        self.assertEqual(result["entry_mode"], "consultant_handoff")
        self.assertTrue(any(code.startswith("consultant_keyword") for code in result["reason_codes"]))

    def test_detects_customer_precise_need_for_product_level_request(self) -> None:
        result = MODULE.classify_role(text="我想定个书柜。")

        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "precise_need")
        self.assertTrue(any(code.startswith("customer_precise_keyword") for code in result["reason_codes"]))

    def test_detects_customer_renovation_browse_for_decoration_stage_browse(self) -> None:
        result = MODULE.classify_role(text="房子在装修，先过来看看。")

        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "renovation_browse")
        self.assertTrue(any(code.startswith("customer_browse_keyword") for code in result["reason_codes"]))

    def test_detects_customer_guided_discovery_for_vague_room_utilization(self) -> None:
        result = MODULE.classify_role(text="我也不知道做什么，就是想把儿童房利用起来。")

        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "guided_discovery")
        self.assertTrue(any(code.startswith("customer_guided_keyword") for code in result["reason_codes"]))

    def test_customer_public_entry_stays_unified_across_diverse_freeform_messages(self) -> None:
        cases = [
            ("我想定个书柜。", "precise_need"),
            ("想做一组柜子，但还没想好怎么做。", "precise_need"),
            ("想做个衣柜，不过还没确定内部怎么分。", "precise_need"),
            ("家里想打一组柜体，先从需求聊起也行。", "precise_need"),
            ("想给孩子房间做个床和柜子一体的。", "precise_need"),
            ("家里准备装修，先来了解下大概要多少钱。", "renovation_browse"),
            ("房子还在装，先看看儿童房能做些什么。", "renovation_browse"),
            ("新房装修中，先做做功课。", "renovation_browse"),
            ("先参考一下你们这边一般怎么做。", "renovation_browse"),
            ("先逛逛，看看次卧能做哪些东西。", "renovation_browse"),
            ("我也不清楚该做什么，就是想把角落利用起来。", "guided_discovery"),
            ("这个房间能做点什么收纳吗？", "guided_discovery"),
            ("不知道该做什么，就想多点收纳。", "guided_discovery"),
            ("儿童房还能怎么利用起来？", "guided_discovery"),
            ("这个空间能做什么？", "guided_discovery"),
            ("想做点什么，但我也说不清。", "guided_discovery"),
            ("先问问看。", "default"),
            ("想先了解一下你们这边怎么报价。", "renovation_browse"),
            ("先咨询一下。", "default"),
            ("大概是怎么个流程？", "default"),
            ("我先来问一下。", "default"),
        ]

        for text, expected_strategy in cases:
            with self.subTest(text=text):
                result = MODULE.classify_role(text=text)
                self.assertEqual(result["audience_role"], "customer")
                self.assertEqual(result["entry_mode"], "customer_guided_discovery")
                self.assertEqual(result["customer_strategy"], expected_strategy)
                self.assertFalse(result["manual_override_active"])

    def test_manual_override_persists_across_turns_for_same_conversation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)

            first = MODULE.classify_role(
                text="这个柜体先别展开工艺，我就是帮客户问个大概。",
                context_json=self.context_json,
                channel="feishu",
                role_override="consultant",
                state_root=state_root,
            )
            second = MODULE.classify_role(
                text="常规拆装柜体高度1700以内默认做顶盖侧还是侧盖顶？",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
            )

        self.assertEqual(first["audience_role"], "consultant")
        self.assertTrue(first["manual_override_active"])
        self.assertEqual(second["audience_role"], "consultant")
        self.assertTrue(second["manual_override_active"])
        self.assertIn("state_manual_override", second["reason_codes"])

    def test_auto_override_value_clears_manual_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)

            MODULE.classify_role(
                text="先按顾问模式来。",
                context_json=self.context_json,
                channel="feishu",
                role_override="consultant",
                state_root=state_root,
            )
            result = MODULE.classify_role(
                text="我家次卧想做个北美白橡木衣柜，长2米高2.4米，先帮我看看大概多少钱。",
                context_json=self.context_json,
                channel="feishu",
                role_override="auto",
                state_root=state_root,
            )

        self.assertEqual(result["audience_role"], "customer")
        self.assertFalse(result["manual_override_active"])


if __name__ == "__main__":
    unittest.main()
