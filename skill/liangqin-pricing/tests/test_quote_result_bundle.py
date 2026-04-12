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
        payload["consultant_handoff_plan"] = {
            "priority": "budget",
            "priority_label": "预算控制",
            "action_code": "send_current_then_budget_compare",
            "compare_variables": [
                {"code": "addons", "label": "附加项", "instruction": "先只减附加项。"},
            ],
            "keep_fixed_fields": ["主体尺寸", "核心结构"],
        }
        payload["compare_plan"] = {
            "code": "reduce_addons_keep_structure",
            "version_title": "预算收一档对比版",
            "adjustable_variables": [{"code": "addons", "label": "附加项"}],
            "locked_fields": ["主体尺寸", "核心结构"],
        }
        payload["follow_up_script_set"] = {
            "customer_compare_offer": "如果你更在意预算，我可以再补一版预算收一档对比。",
            "consultant_follow_up": "先发当前版，再补一句预算对比。",
            "customer_followthrough_offer": "如果这版区间你能接受，我建议下一步先约到店或约设计沟通，把预算边界和取舍一次收清。",
            "consultant_followthrough_prompt": "这轮重点不是再解释价格，而是把客户往到店/沟通收口。",
        }
        payload["consultant_quick_actions"] = [
            {
                "code": "copy_ready_offer",
                "label": "当前发送句",
                "text": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
                "group": "quote_send",
                "priority": "primary",
                "source": "quote_version_actions.copy_ready_offer",
            },
            {
                "code": "copy_compare_offer",
                "label": "对比邀约句",
                "text": "如果你更在意预算，我可以再补一版预算收一档对比。",
                "group": "compare_offer",
                "priority": "secondary",
                "source": "follow_up_script_set.customer_compare_offer",
            },
        ]
        payload["consultant_action_queue"] = [
            {
                "code": "send_current_quote",
                "title": "先发当前版",
                "text": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                "group": "current_main",
                "priority": "p1",
                "rank": 1,
                "recommended": True,
                "source": "quote_version_actions.current_send_action",
                "stage_code": "formal_quote_waiting_budget_feedback",
                "trigger_hint": "适合正式报价刚生成这一轮，先把当前真实报价结果发出去。",
            },
            {
                "code": "send_current_then_budget_compare",
                "title": "补预算收一档对比",
                "text": "如果客户继续压预算，再发 V2 预算收一档对比版。",
                "group": "compare_next",
                "priority": "p2",
                "rank": 2,
                "recommended": False,
                "source": "quote_version_actions.next_version_offer_action",
                "stage_code": "formal_quote_waiting_budget_feedback",
                "trigger_hint": "适合客户继续压预算时，再切到 V2 预算收一档对比版。",
            },
        ]
        payload["consultant_workbench"] = {
            "header": {
                "title": "正式报价待预算反馈",
                "summary": "客户当前更在意预算控制，建议先发当前版，再补预算收一档对比。",
                "badges": [
                    {"group": "stage", "code": "formal_quote_waiting_budget_feedback", "label": "正式报价待预算反馈"},
                ],
            },
            "primary_action": {
                "code": "send_current_quote",
                "title": "先发当前版",
                "text": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                "recommended": True,
            },
            "action_queue": [
                {
                    "code": "send_current_quote",
                    "title": "先发当前版",
                    "text": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                }
            ],
            "quick_action_groups": [
                {
                    "group": "quote_send",
                    "label": "当前发送",
                    "count": 1,
                    "items": [
                        {
                            "code": "copy_ready_offer",
                            "label": "当前发送句",
                            "text": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
                            "priority": "primary",
                            "source": "quote_version_actions.copy_ready_offer",
                        }
                    ],
                }
            ],
            "info_panels": [
                {
                    "code": "compare_focus",
                    "title": "下一版建议",
                    "lines": ["建议版本：预算收一档对比版", "保持不动：主体尺寸、核心结构"],
                    "action_code": "reduce_addons_keep_structure",
                    "action_label": "预算收一档对比版",
                }
            ],
        }
        payload["post_quote_stage"] = {"code": "formal_quote_waiting_budget_feedback", "label": "正式报价待预算反馈"}
        payload["quote_version_summary"] = {
            "current_version_code": "formal_base",
            "current_version_label": "当前正式版",
            "current_version_index": "V1",
            "next_version_code": "reduce_addons_keep_structure",
            "next_version_label": "预算收一档对比版",
            "next_version_index": "V2",
        }
        payload["quote_version_actions"] = {
            "current_send_action": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
            "next_version_offer_action": "如果客户继续压预算，再发 V2 预算收一档对比版。",
            "customer_transition_line": "如果你想把预算再往下收，我可以在主体结构先不动的前提下，再补你一版预算收一档对比。",
            "consultant_transition_action": "先发当前正式版；客户继续压预算时，只减附加项或收一档门型，不改主体尺寸和核心结构。",
            "recommended_trigger": "继续压预算",
            "copy_ready_offer": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
        }
        payload["objection_playbook"] = {
            "recommended_first_code": "cheaper_option",
            "cheaper_option": {
                "label": "客户问能不能便宜点",
                "customer_reply": "可以先做预算收一档对比。",
                "consultant_tactic": "不要直接打折。",
                "transition_action_code": "send_current_then_budget_compare",
                "transition_action_label": "补预算收一档对比版",
                "transition_line": "如果你想先控预算，我可以先按同样结构补一版预算收一档对比给你。",
                "followthrough_line": "如果这版区间接受，下一步优先约到店或沟通，把预算边界一次收清。",
            },
        }
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
        self.assertEqual(bundle["consultant_handoff_plan"]["priority_label"], "预算控制")
        self.assertEqual(bundle["consultant_handoff_plan"]["compare_variables"][0]["label"], "附加项")
        self.assertEqual(bundle["compare_plan"]["version_title"], "预算收一档对比版")
        self.assertEqual(bundle["follow_up_script_set"]["consultant_follow_up"], "先发当前版，再补一句预算对比。")
        self.assertIn("约到店", bundle["follow_up_script_set"]["customer_followthrough_offer"])
        self.assertEqual(bundle["consultant_quick_actions"][0]["label"], "当前发送句")
        self.assertEqual(bundle["consultant_quick_actions"][1]["group"], "compare_offer")
        self.assertEqual(bundle["consultant_action_queue"][0]["code"], "send_current_quote")
        self.assertEqual(bundle["consultant_action_queue"][1]["rank"], 2)
        self.assertEqual(bundle["consultant_workbench"]["primary_action"]["code"], "send_current_quote")
        self.assertEqual(bundle["consultant_workbench"]["quick_action_groups"][0]["group"], "quote_send")
        self.assertEqual(bundle["post_quote_stage"]["code"], "formal_quote_waiting_budget_feedback")
        self.assertEqual(bundle["quote_version_summary"]["next_version_label"], "预算收一档对比版")
        self.assertEqual(bundle["quote_version_actions"]["recommended_trigger"], "继续压预算")
        self.assertEqual(bundle["objection_playbook"]["recommended_first_code"], "cheaper_option")
        self.assertEqual(
            bundle["objection_playbook"]["cheaper_option"]["transition_action_code"],
            "send_current_then_budget_compare",
        )
        self.assertIn("约到店", bundle["objection_playbook"]["cheaper_option"]["followthrough_line"])

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
