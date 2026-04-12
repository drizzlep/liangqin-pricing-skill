import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quote_flow_state.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("quote_flow_state", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QuoteFlowStateTests(unittest.TestCase):
    def test_store_and_load_round_trip(self) -> None:
        state = MODULE.build_quote_flow_state(
            conversation_id="agent:main:feishu:direct:ou_123456",
            audience_role="consultant",
            manual_override="consultant",
            entry_mode="consultant_handoff",
            confirmed_fields={"items": [{"product": "流云衣柜", "confirmed": "白橡木，1.8×2.2×0.6"}]},
            missing_fields=["door_type"],
            active_route="cabinet",
            last_quote_kind="formal",
            internal_summary="内部完整版",
            customer_forward_text="客户版",
            handoff_summary="已补齐尺寸，待确认门型。",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            MODULE.store_quote_flow_state(state, cache_root=root)
            loaded = MODULE.load_quote_flow_state(state["conversation_id"], cache_root=root)

        self.assertEqual(loaded["audience_role"], "consultant")
        self.assertEqual(loaded["manual_override"], "consultant")
        self.assertEqual(loaded["summaries"]["customer_forward_text"], "客户版")
        self.assertEqual(loaded["last_payload"]["last_quote_kind"], "formal")

    def test_merge_preserves_manual_override_and_updates_latest_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            conversation_id = "agent:main:feishu:direct:ou_123456"
            MODULE.store_quote_flow_state(
                MODULE.build_quote_flow_state(
                    conversation_id=conversation_id,
                    audience_role="consultant",
                    manual_override="consultant",
                    entry_mode="manual_override",
                    internal_summary="旧摘要",
                ),
                cache_root=root,
            )

            merged = MODULE.merge_quote_flow_state(
                conversation_id,
                updates={
                    "audience_role": "consultant",
                    "internal_summary": "新摘要",
                    "missing_fields": ["material"],
                },
                cache_root=root,
            )

        self.assertEqual(merged["manual_override"], "consultant")
        self.assertEqual(merged["summaries"]["internal_summary"], "新摘要")
        self.assertEqual(merged["missing_fields"], ["material"])

    def test_clear_removes_saved_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            conversation_id = "agent:main:feishu:direct:ou_123456"
            MODULE.store_quote_flow_state(
                MODULE.build_quote_flow_state(conversation_id=conversation_id),
                cache_root=root,
            )

            self.assertTrue(MODULE.clear_quote_flow_state(conversation_id, cache_root=root))
            self.assertIsNone(MODULE.load_quote_flow_state(conversation_id, cache_root=root))

    def test_state_round_trip_includes_inquiry_family_and_product_context(self) -> None:
        state = MODULE.build_quote_flow_state(
            conversation_id="agent:main:feishu:direct:ou_123456",
            audience_role="customer",
            active_route="size_spec",
            confirmed_fields={"last_product": "穿衣镜"},
            handoff_summary="已回复目录尺寸，待确认是否继续报价。",
            active_inquiry_family="size_spec",
            captured_product_context={"product_name": "穿衣镜", "product_code": "YGP-01"},
            last_non_quote_reply="这款目录尺寸是长0.6米、深0.12米、高1.8米。",
            last_safe_boundary_reason="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            MODULE.store_quote_flow_state(state, cache_root=root)
            loaded = MODULE.load_quote_flow_state(state["conversation_id"], cache_root=root)

        self.assertEqual(loaded["active_inquiry_family"], "size_spec")
        self.assertEqual(loaded["captured_product_context"]["product_code"], "YGP-01")
        self.assertIn("目录尺寸", loaded["last_non_quote_reply"])

    def test_state_round_trip_includes_conversion_fields(self) -> None:
        state = MODULE.build_quote_flow_state(
            conversation_id="agent:main:feishu:direct:ou_123456",
            audience_role="consultant",
            last_quote_kind="formal",
            quote_confidence="high",
            quote_stage="formal_quote_ready",
            option_set=[{"level": "recommended", "title": "当前确认方案"}],
            budget_adjustment_suggestions=["优先从门型和附加项收一档。"],
            next_best_action={
                "code": "compare_or_generate_card",
                "title": "先发当前版，再补预算对比",
                "text": "下一步建议先发当前正式版锁住结果；如果客户继续压预算，再补一版预算收一档对比版。",
                "card_text": "先发当前版；如果客户继续压预算，再补一版预算收一档对比版。",
                "primary_action_code": "send_current_quote",
                "primary_action_label": "先发当前版",
                "secondary_action_code": "send_current_then_budget_compare",
                "secondary_action_label": "补预算收一档对比",
                "followthrough_action_code": "schedule_store_visit",
                "followthrough_action_label": "约到店确认",
                "followthrough_text": "如果客户对当前区间接受，下一步优先约到店或约设计沟通，把预算边界和取舍一次收清。",
            },
            decision_risk_points=["尺寸、材质、结构一变，价格会同步更新。"],
            conversion_intent_level="high",
            consultant_handoff_plan={
                "priority": "budget",
                "priority_label": "预算控制",
                "action_code": "send_current_then_budget_compare",
                "compare_variables": [
                    {"code": "addons", "label": "附加项", "instruction": "先只减附加项。"},
                    {"code": "door_style", "label": "门型层次", "instruction": "再收一档门型。"},
                ],
                "keep_fixed_fields": ["主体尺寸", "核心结构"],
            },
            compare_plan={
                "code": "reduce_addons_keep_structure",
                "version_title": "预算收一档对比版",
                "adjustable_variables": [{"code": "addons", "label": "附加项"}],
                "locked_fields": ["主体尺寸", "核心结构"],
            },
            follow_up_script_set={
                "customer_compare_offer": "如果你更在意预算，我可以再补一版预算收一档对比。",
                "consultant_follow_up": "先发当前版，再补一句预算对比。",
                "customer_followthrough_offer": "如果这版区间你能接受，我建议下一步先约到店或约设计沟通，把预算边界和取舍一次收清。",
                "consultant_followthrough_prompt": "这轮重点不是再解释价格，而是把客户往到店/沟通收口。",
                "next_touch_followthrough": "如果客户暂时没回，下一次跟进优先推进约到店或沟通，把预算边界收清。",
            },
            consultant_quick_actions=[
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
            ],
            consultant_action_queue=[
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
            ],
            consultant_workbench={
                "header": {
                    "title": "正式报价待预算反馈",
                    "summary": "客户当前更在意预算控制，建议先发当前版，再补预算收一档对比。",
                    "badges": [
                        {"group": "stage", "code": "formal_quote_waiting_budget_feedback", "label": "正式报价待预算反馈"},
                        {"group": "customer_priority", "code": "budget", "label": "预算控制"},
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
            },
            post_quote_stage={"code": "formal_quote_waiting_budget_feedback", "label": "正式报价待预算反馈"},
            quote_version_summary={
                "current_version_code": "formal_base",
                "current_version_label": "当前正式版",
                "current_version_index": "V1",
                "next_version_code": "reduce_addons_keep_structure",
                "next_version_label": "预算收一档对比版",
                "next_version_index": "V2",
                "version_transition_note": "建议先发 V1 当前正式版；如客户继续压预算，再发 V2 预算收一档对比版。",
            },
            quote_version_actions={
                "current_send_action": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                "next_version_offer_action": "如果客户继续压预算，再发 V2 预算收一档对比版。",
                "customer_transition_line": "如果你想把预算再往下收，我可以在主体结构先不动的前提下，再补你一版预算收一档对比。",
                "consultant_transition_action": "先发当前正式版；客户继续压预算时，只减附加项或收一档门型，不改主体尺寸和核心结构。",
                "recommended_trigger": "继续压预算",
                "copy_ready_offer": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
            },
            objection_playbook={
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
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            MODULE.store_quote_flow_state(state, cache_root=root)
            loaded = MODULE.load_quote_flow_state(state["conversation_id"], cache_root=root)

        self.assertEqual(loaded["quote_confidence"], "high")
        self.assertEqual(loaded["quote_stage"], "formal_quote_ready")
        self.assertEqual(loaded["next_best_action"]["code"], "compare_or_generate_card")
        self.assertEqual(loaded["next_best_action"]["title"], "先发当前版，再补预算对比")
        self.assertEqual(loaded["conversion"]["next_best_action"]["secondary_action_code"], "send_current_then_budget_compare")
        self.assertEqual(loaded["next_best_action"]["followthrough_action_code"], "schedule_store_visit")
        self.assertIn("约到店", loaded["conversion"]["next_best_action"]["followthrough_text"])
        self.assertEqual(loaded["conversion_intent_level"], "high")
        self.assertEqual(loaded["consultant_handoff_plan"]["priority"], "budget")
        self.assertEqual(loaded["conversion"]["consultant_handoff_plan"]["action_code"], "send_current_then_budget_compare")
        self.assertEqual(loaded["consultant_handoff_plan"]["compare_variables"][0]["code"], "addons")
        self.assertEqual(loaded["consultant_handoff_plan"]["keep_fixed_fields"], ["主体尺寸", "核心结构"])
        self.assertEqual(loaded["compare_plan"]["version_title"], "预算收一档对比版")
        self.assertEqual(loaded["follow_up_script_set"]["consultant_follow_up"], "先发当前版，再补一句预算对比。")
        self.assertIn("约到店", loaded["follow_up_script_set"]["customer_followthrough_offer"])
        self.assertEqual(loaded["consultant_quick_actions"][0]["label"], "当前发送句")
        self.assertEqual(loaded["conversion"]["consultant_quick_actions"][1]["group"], "compare_offer")
        self.assertEqual(loaded["consultant_action_queue"][0]["code"], "send_current_quote")
        self.assertTrue(loaded["consultant_action_queue"][0]["recommended"])
        self.assertEqual(loaded["conversion"]["consultant_action_queue"][1]["code"], "send_current_then_budget_compare")
        self.assertEqual(loaded["conversion"]["consultant_action_queue"][1]["rank"], 2)
        self.assertEqual(loaded["consultant_workbench"]["header"]["title"], "正式报价待预算反馈")
        self.assertEqual(loaded["consultant_workbench"]["primary_action"]["code"], "send_current_quote")
        self.assertEqual(loaded["conversion"]["consultant_workbench"]["quick_action_groups"][0]["group"], "quote_send")
        self.assertIn("到店/沟通收口", loaded["conversion"]["follow_up_script_set"]["consultant_followthrough_prompt"])
        self.assertEqual(loaded["post_quote_stage"]["code"], "formal_quote_waiting_budget_feedback")
        self.assertEqual(loaded["quote_version_summary"]["current_version_index"], "V1")
        self.assertEqual(loaded["conversion"]["quote_version_summary"]["next_version_label"], "预算收一档对比版")
        self.assertEqual(loaded["quote_version_actions"]["recommended_trigger"], "继续压预算")
        self.assertIn("V2 预算收一档对比版", loaded["conversion"]["quote_version_actions"]["next_version_offer_action"])
        self.assertEqual(loaded["objection_playbook"]["recommended_first_code"], "cheaper_option")
        self.assertEqual(loaded["conversion"]["objection_playbook"]["cheaper_option"]["consultant_tactic"], "不要直接打折。")
        self.assertEqual(
            loaded["conversion"]["objection_playbook"]["cheaper_option"]["transition_action_code"],
            "send_current_then_budget_compare",
        )
        self.assertIn(
            "约到店",
            loaded["objection_playbook"]["cheaper_option"]["followthrough_line"],
        )


if __name__ == "__main__":
    unittest.main()
