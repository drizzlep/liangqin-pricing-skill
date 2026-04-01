import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quote_result_bundle.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("quote_result_bundle", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QuoteResultBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "items": [
                {
                    "product": "北美黑胡桃木流云衣柜",
                    "confirmed": "长 1.8 米 × 深 0.67 米 × 高 2.2 米，材质北美黑胡桃木，门板纹理连续。",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": [
                        "投影面积：1.8 × 2.2 = 3.96㎡",
                        "基础价格：3.96 × 8,680 = 34,372.8 元",
                        "超深加价：34,372.8 × 15% = 5,155.92 元",
                    ],
                    "subtotal": "39,529 元",
                }
            ],
            "total": "39,529 元",
        }
        self.context_json = json.dumps(
            {
                "message_id": "om_x100b53cafe",
                "sender_id": "ou_123456",
                "sender": "ou_123456",
                "timestamp": "Sun 2026-03-29 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

    def test_resolve_direct_conversation_context_for_feishu(self) -> None:
        context = MODULE.resolve_conversation_context(self.context_json, channel="feishu")

        self.assertEqual(context["message_id"], "om_x100b53cafe")
        self.assertEqual(context["sender_id"], "ou_123456")
        self.assertEqual(context["conversation_id"], "agent:main:feishu:direct:ou_123456")
        self.assertFalse(context["is_group_chat"])

    def test_resolve_group_conversation_context_prefers_group_channel(self) -> None:
        context = MODULE.resolve_conversation_context(
            json.dumps(
                {
                    "message_id": "msg_group",
                    "sender_id": "190019093236500005",
                    "group_channel": "agent:main:dingtalk:group:cidazdwvib9manokwa4myhyuw==",
                    "conversation_label": "龙虾体验 - 邹洪玖",
                    "group_subject": "龙虾体验",
                    "is_group_chat": True,
                },
                ensure_ascii=False,
            ),
            channel="dingtalk-connector",
        )

        self.assertEqual(context["conversation_id"], "agent:main:dingtalk:group:cidazdwvib9manokwa4myhyuw==")
        self.assertTrue(context["is_group_chat"])

    def test_should_generate_quote_card_only_for_clear_positive_intent(self) -> None:
        self.assertTrue(MODULE.should_generate_quote_card("生成图片"))
        self.assertTrue(MODULE.should_generate_quote_card("帮我发报价卡"))
        self.assertFalse(MODULE.should_generate_quote_card("先不要生成图片"))
        self.assertFalse(MODULE.should_generate_quote_card("继续算一下儿童房报价"))

    def test_build_bundle_marks_reference_quote_kind(self) -> None:
        payload = dict(self.payload)
        payload["reference"] = True
        context = MODULE.resolve_conversation_context(self.context_json, channel="feishu")

        bundle = MODULE.build_quote_result_bundle(
            prepared_payload=payload,
            reply_text="参考总价：39,529 元",
            conversation_id=context["conversation_id"],
        )

        self.assertEqual(bundle["quote_kind"], "reference")
        self.assertTrue(bundle["eligible_for_card"])

    def test_build_bundle_keeps_quote_card_payload_and_customer_forward_text(self) -> None:
        payload = dict(self.payload)
        payload["customer_forward_text"] = "客户版正式报价：39,529 元"
        payload["quote_card_payload"] = {
            "items": [
                {
                    "product": "客户版流云衣柜",
                    "confirmed": "白橡木，1.8×2.2×0.6",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["按当前尺寸和材质计算"],
                    "subtotal": "39,529 元",
                }
            ],
            "total": "39,529 元",
        }
        context = MODULE.resolve_conversation_context(self.context_json, channel="feishu")

        bundle = MODULE.build_quote_result_bundle(
            prepared_payload=payload,
            reply_text="客户版正式报价：39,529 元",
            conversation_id=context["conversation_id"],
        )

        self.assertIn("quote_card_payload", bundle)
        self.assertEqual(bundle["customer_forward_text"], "客户版正式报价：39,529 元")

    def test_build_bundle_marks_missing_total_as_ineligible(self) -> None:
        payload = dict(self.payload)
        payload.pop("total")
        context = MODULE.resolve_conversation_context(self.context_json, channel="feishu")

        bundle = MODULE.build_quote_result_bundle(
            prepared_payload=payload,
            reply_text="还需要补充信息",
            conversation_id=context["conversation_id"],
        )

        self.assertFalse(bundle["eligible_for_card"])

    def test_store_and_load_bundle_overwrites_previous_quote_for_same_conversation(self) -> None:
        context = MODULE.resolve_conversation_context(self.context_json, channel="feishu")

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            first_bundle = MODULE.build_quote_result_bundle(
                prepared_payload=self.payload,
                reply_text="第一次报价",
                conversation_id=context["conversation_id"],
                created_at="2026-03-29T10:00:00+08:00",
            )
            second_payload = dict(self.payload)
            second_payload["total"] = "42,000 元"
            second_bundle = MODULE.build_quote_result_bundle(
                prepared_payload=second_payload,
                reply_text="第二次报价",
                conversation_id=context["conversation_id"],
                created_at="2026-03-29T10:05:00+08:00",
            )

            first_path = MODULE.store_latest_quote_result_bundle(first_bundle, cache_root=cache_root)
            second_path = MODULE.store_latest_quote_result_bundle(second_bundle, cache_root=cache_root)
            loaded = MODULE.load_latest_quote_result_bundle(context["conversation_id"], cache_root=cache_root)

        self.assertEqual(first_path, second_path)
        self.assertEqual(loaded["reply_text"], "第二次报价")
        self.assertEqual(loaded["prepared_payload"]["total"], "42,000 元")

    def test_clear_latest_bundle_removes_cached_quote(self) -> None:
        context = MODULE.resolve_conversation_context(self.context_json, channel="feishu")

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            bundle = MODULE.build_quote_result_bundle(
                prepared_payload=self.payload,
                reply_text="第一次报价",
                conversation_id=context["conversation_id"],
            )
            MODULE.store_latest_quote_result_bundle(bundle, cache_root=cache_root)

            self.assertTrue(MODULE.clear_latest_quote_result_bundle(context["conversation_id"], cache_root=cache_root))
            self.assertIsNone(MODULE.load_latest_quote_result_bundle(context["conversation_id"], cache_root=cache_root))


if __name__ == "__main__":
    unittest.main()
