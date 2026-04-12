import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "format_quote_reply.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("format_quote_reply", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FormatQuoteReplyTests(unittest.TestCase):
    def test_render_bundle_exposes_conversion_metadata_for_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": [
                        "投影面积：1.8 × 2.2 = 3.96㎡",
                        "基础价格：3.96 × 8,680 = 34,372.8 元",
                    ],
                    "subtotal": "34,372.8 元",
                }
            ],
            "total": "34,372.8 元",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="consultant", output_profile="consultant_dual")
        prepared = rendered["prepared_payload"]

        self.assertEqual(prepared["quote_confidence"], "high")
        self.assertEqual(prepared["quote_stage"], "formal_quote_ready")
        self.assertEqual(prepared["conversion_intent_level"], "high")
        self.assertEqual(prepared["next_best_action"]["code"], "compare_or_generate_card")
        self.assertEqual(prepared["next_best_action"]["title"], "先发当前版，再看是否补对比")
        self.assertEqual(prepared["next_best_action"]["primary_action_code"], "send_current_quote")
        self.assertEqual(prepared["next_best_action"]["secondary_action_code"], "offer_compare_version")
        self.assertIn("生成报价卡", prepared["next_best_action"]["card_text"])
        self.assertEqual(prepared["next_best_action"]["followthrough_action_code"], "schedule_store_or_design_followup")
        self.assertEqual(prepared["next_best_action"]["followthrough_action_label"], "约沟通推进")
        self.assertIn("约一次沟通", prepared["next_best_action"]["followthrough_text"])
        self.assertGreaterEqual(len(prepared["option_set"]), 3)
        self.assertGreaterEqual(len(prepared["budget_adjustment_suggestions"]), 2)
        self.assertGreaterEqual(len(prepared["decision_risk_points"]), 2)
        self.assertEqual(prepared["post_quote_stage"]["code"], "formal_quote_waiting_reply")
        self.assertEqual(prepared["compare_plan"]["code"], "standard_compare")
        self.assertIn("customer_compare_offer", prepared["follow_up_script_set"])
        self.assertEqual(prepared["quote_version_summary"]["current_version_index"], "V1")
        self.assertEqual(prepared["quote_version_summary"]["next_version_index"], "V2")
        self.assertEqual(prepared["quote_version_summary"]["current_version_label"], "当前正式版")
        self.assertEqual(prepared["quote_version_summary"]["next_version_label"], "方案对比版")
        self.assertIn("V1 当前正式版", prepared["quote_version_actions"]["current_send_action"])
        self.assertIn("V2 方案对比版", prepared["quote_version_actions"]["next_version_offer_action"])
        self.assertEqual(prepared["quote_version_actions"]["recommended_trigger"], "想继续横向比较")
        self.assertEqual(prepared["consultant_quick_actions"][0]["code"], "copy_ready_offer")
        self.assertEqual(prepared["consultant_quick_actions"][0]["label"], "当前发送句")
        self.assertEqual(prepared["consultant_quick_actions"][0]["group"], "quote_send")
        self.assertEqual(prepared["consultant_quick_actions"][3]["group"], "objection_reply")
        self.assertEqual(prepared["consultant_quick_actions"][4]["group"], "objection_transition")
        self.assertEqual(prepared["consultant_action_queue"][0]["code"], "send_current_quote")
        self.assertEqual(prepared["consultant_action_queue"][0]["title"], "先发当前版")
        self.assertEqual(prepared["consultant_action_queue"][0]["group"], "current_main")
        self.assertTrue(prepared["consultant_action_queue"][0]["recommended"])
        self.assertEqual(prepared["consultant_action_queue"][1]["code"], "offer_compare_version")
        self.assertEqual(prepared["consultant_action_queue"][1]["rank"], 2)
        self.assertEqual(prepared["consultant_action_queue"][2]["code"], "schedule_store_or_design_followup")
        self.assertIn("客户接受当前方向后", prepared["consultant_action_queue"][2]["trigger_hint"])
        self.assertEqual(prepared["consultant_action_queue"][3]["code"], "handle_price_high")
        self.assertIn("客户说价格偏高", prepared["consultant_action_queue"][3]["title"])
        self.assertEqual(prepared["consultant_action_queue"][4]["code"], "next_touch_follow_up")
        self.assertEqual(prepared["consultant_action_queue"][4]["priority"], "p3")
        self.assertEqual(prepared["consultant_workbench"]["header"]["title"], "正式报价待回复")
        self.assertEqual(prepared["consultant_workbench"]["primary_action"]["code"], "send_current_quote")
        self.assertEqual(prepared["consultant_workbench"]["action_queue"][1]["code"], "offer_compare_version")
        self.assertEqual(prepared["consultant_workbench"]["quick_action_groups"][0]["group"], "quote_send")
        self.assertEqual(prepared["consultant_workbench"]["quick_action_groups"][1]["group"], "compare_offer")
        self.assertTrue(
            any(
                badge["label"] == "正式报价待回复"
                for badge in prepared["consultant_workbench"]["header"]["badges"]
            )
        )
        self.assertTrue(
            any(
                panel["code"] == "followthrough_focus"
                for panel in prepared["consultant_workbench"]["info_panels"]
            )
        )
        self.assertEqual(prepared["objection_playbook"]["recommended_first_code"], "price_high")
        self.assertIn("客户说价格偏高", prepared["objection_playbook"]["price_high"]["label"])
        self.assertIn("方案对比版", prepared["objection_playbook"]["cheaper_option"]["customer_reply"])
        self.assertEqual(prepared["objection_playbook"]["price_high"]["transition_action_code"], "offer_compare_version")
        self.assertIn("方案对比版", prepared["objection_playbook"]["price_high"]["transition_action_label"])
        self.assertIn("方案对比版", prepared["objection_playbook"]["price_high"]["transition_line"])
        self.assertIn("约一次沟通", prepared["objection_playbook"]["need_time"]["followthrough_line"])
        self.assertIn("约一次沟通", prepared["follow_up_script_set"]["customer_followthrough_offer"])
        self.assertIn("到店还是转深化", prepared["follow_up_script_set"]["consultant_followthrough_prompt"])
        self.assertIn("约一次沟通", prepared["follow_up_script_set"]["next_touch_followthrough"])

    def test_reference_quote_exposes_reference_to_formal_version_summary(self) -> None:
        payload = {
            "reference": True,
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，长度待确认，先按当前条件预估",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["先按当前条件预估：34,372.8 元"],
                    "subtotal": "34,372.8 元",
                }
            ],
            "total": "34,372.8 元",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="consultant", output_profile="consultant_dual")
        prepared = rendered["prepared_payload"]

        self.assertEqual(prepared["quote_version_summary"]["current_version_label"], "当前参考版")
        self.assertEqual(prepared["quote_version_summary"]["next_version_label"], "正式报价版")
        self.assertIn("关键条件补齐后", prepared["quote_version_summary"]["next_version_reason"])
        self.assertEqual(prepared["quote_version_summary"]["current_version_index"], "V1")
        self.assertEqual(prepared["quote_version_summary"]["next_version_index"], "V2")
        self.assertEqual(prepared["next_best_action"]["code"], "confirm_key_fields")
        self.assertEqual(prepared["next_best_action"]["title"], "先补关键条件，再转正式报价")
        self.assertEqual(prepared["next_best_action"]["primary_action_code"], "confirm_key_fields")
        self.assertEqual(prepared["next_best_action"]["secondary_action_code"], "upgrade_to_formal_quote")
        self.assertIn("转正式报价", prepared["next_best_action"]["card_text"])
        self.assertEqual(prepared["next_best_action"]["followthrough_action_code"], "lock_formal_quote")
        self.assertEqual(prepared["next_best_action"]["followthrough_action_label"], "锁正式报价")
        self.assertIn("锁正式报价", prepared["next_best_action"]["followthrough_text"])
        self.assertIn("V1 当前参考版", prepared["quote_version_actions"]["current_send_action"])
        self.assertIn("V2 正式报价版", prepared["quote_version_actions"]["next_version_offer_action"])
        self.assertEqual(prepared["quote_version_actions"]["recommended_trigger"], "关键条件补齐后")
        self.assertIn("关键条件补齐", prepared["follow_up_script_set"]["customer_followthrough_offer"])
        self.assertIn("锁正式报价", prepared["follow_up_script_set"]["consultant_followthrough_prompt"])
        self.assertIn("补齐", prepared["follow_up_script_set"]["next_touch_followthrough"])
        self.assertEqual(prepared["consultant_quick_actions"][0]["label"], "当前发送句")
        self.assertIn("正式报价", prepared["consultant_quick_actions"][0]["text"])
        self.assertIn("锁正式报价", prepared["consultant_quick_actions"][2]["text"])
        self.assertIn("为什么是这个价", prepared["consultant_quick_actions"][3]["label"])
        self.assertEqual(prepared["consultant_action_queue"][0]["code"], "confirm_key_fields")
        self.assertEqual(prepared["consultant_action_queue"][0]["title"], "补关键条件")
        self.assertEqual(prepared["consultant_action_queue"][1]["code"], "upgrade_to_formal_quote")
        self.assertEqual(prepared["consultant_action_queue"][1]["title"], "转正式报价")
        self.assertEqual(prepared["consultant_action_queue"][2]["code"], "lock_formal_quote")
        self.assertEqual(prepared["consultant_action_queue"][3]["code"], "handle_why_this_price")
        self.assertEqual(prepared["consultant_action_queue"][4]["stage_code"], "reference_quote_pending_confirmation")
        self.assertEqual(prepared["objection_playbook"]["why_this_price"]["transition_action_code"], "confirm_key_fields")
        self.assertIn("补关键条件", prepared["objection_playbook"]["why_this_price"]["transition_action_label"])
        self.assertIn("补齐", prepared["objection_playbook"]["why_this_price"]["transition_line"])
        self.assertIn("锁正式报价", prepared["objection_playbook"]["need_time"]["followthrough_line"])

    def test_render_bundle_preserves_original_quote_amounts(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
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

        rendered = MODULE.render_for_output_profile(payload, audience_role="consultant", output_profile="consultant_dual")
        prepared = rendered["prepared_payload"]
        card_payload = rendered["quote_card_payload"]

        self.assertEqual(prepared["items"][0]["subtotal"], "39,529 元")
        self.assertEqual(prepared["total"], "39,529 元")
        self.assertEqual(card_payload["items"][0]["subtotal"], "39,529 元")
        self.assertEqual(card_payload["total"], "39,529 元")
        self.assertIn("正式报价：39,529 元", rendered["internal_summary"])
        self.assertIn("正式报价：39,529 元", rendered["customer_forward_text"])

    def test_priority_can_personalize_budget_suggestion_without_changing_amount(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "customer_priority": "budget",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="customer", output_profile="customer_simple")

        self.assertIn("我会先按更省预算的路径", rendered["reply_text"])
        self.assertIn("如果你想先把预算往下收", rendered["reply_text"])
        self.assertIn("正式报价：34372.8元", rendered["reply_text"])
        self.assertEqual(rendered["prepared_payload"]["total"], "34372.8元")
        self.assertEqual(rendered["prepared_payload"]["option_set"][0]["title"], "预算优先方案")
        self.assertIn("主体结构", rendered["prepared_payload"]["option_set"][1]["description"])

    def test_priority_can_personalize_option_set_for_aesthetics(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "customer_priority": "aesthetics",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="customer", output_profile="customer_simple")

        self.assertEqual(rendered["prepared_payload"]["option_set"][0]["title"], "效果优先方案")
        self.assertIn("门型层次", rendered["prepared_payload"]["option_set"][2]["description"])
        self.assertEqual(rendered["prepared_payload"]["total"], "34372.8元")

    def test_render_customer_simple_prioritizes_conclusion_over_full_calculation(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
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

        rendered = MODULE.render_for_output_profile(payload, audience_role="customer", output_profile="customer_simple")

        self.assertIn("这次可以正式报价", rendered["reply_text"])
        self.assertIn("正式报价：39,529 元", rendered["reply_text"])
        self.assertIn("适合场景：", rendered["reply_text"])
        self.assertIn("如果你想先把预算往下收", rendered["reply_text"])
        self.assertIn("如果你更想把效果往上提", rendered["reply_text"])
        self.assertIn("下一步：", rendered["reply_text"])
        self.assertNotIn("计算过程：", rendered["reply_text"])
        self.assertEqual(rendered["customer_forward_text"], rendered["reply_text"])

    def test_render_consultant_dual_generates_internal_and_customer_versions(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                    "addendum_decisions": {
                        "adjustments": [{"title": "纹理连续补差", "detail": "门板单价差 +900 元/㎡"}],
                        "constraints": [],
                        "follow_up_questions": [],
                    },
                }
            ],
            "total": "34372.8元",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="consultant", output_profile="consultant_dual")

        self.assertEqual(rendered["output_profile"], "consultant_dual")
        self.assertIn("正式报价：34372.8元", rendered["internal_summary"])
        self.assertIn("这次可以正式报价", rendered["customer_forward_text"])
        self.assertNotIn("追加规则：纹理连续补差", rendered["customer_forward_text"])
        self.assertEqual(rendered["reply_text"], rendered["customer_forward_text"])

    def test_consultant_internal_summary_includes_customer_priority_focus(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "customer_priority": "budget",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="consultant", output_profile="consultant_dual")

        self.assertIn("客户当前更在意：预算控制", rendered["internal_summary"])
        self.assertIn("建议跟进：先围绕预算收口", rendered["internal_summary"])
        self.assertIn("建议动作：先发当前版；如客户继续压预算，再补一版降配对比。", rendered["internal_summary"])
        self.assertIn("对比指令：下一版优先只减附加项或收一档门型，不改主体尺寸和核心结构。", rendered["internal_summary"])
        self.assertIn("动作排序：", rendered["internal_summary"])
        self.assertIn("建议先做：先发当前版。", rendered["internal_summary"])
        self.assertIn("第 2 步：补预算收一档对比版。", rendered["internal_summary"])
        self.assertEqual(rendered["prepared_payload"]["consultant_handoff_plan"]["priority"], "budget")
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["action_code"],
            "send_current_then_budget_compare",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["compare_code"],
            "reduce_addons_keep_structure",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["compare_version_title"],
            "预算收一档对比版",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["compare_variables"][0]["label"],
            "附加项",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["compare_variables"][1]["code"],
            "door_style",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["keep_fixed_fields"],
            ["主体尺寸", "核心结构"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["compare_plan"]["version_title"],
            "预算收一档对比版",
        )
        self.assertEqual(
            rendered["prepared_payload"]["compare_plan"]["adjustable_variables"][0]["code"],
            "addons",
        )
        self.assertEqual(
            rendered["prepared_payload"]["compare_plan"]["locked_fields"],
            ["主体尺寸", "核心结构"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["post_quote_stage"]["code"],
            "formal_quote_waiting_budget_feedback",
        )
        self.assertEqual(
            rendered["prepared_payload"]["quote_version_summary"]["next_version_label"],
            "预算收一档对比版",
        )
        self.assertIn(
            "继续压预算",
            rendered["prepared_payload"]["quote_version_summary"]["version_transition_note"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["title"],
            "先发当前版，再补预算对比",
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["secondary_action_code"],
            "send_current_then_budget_compare",
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["followthrough_action_code"],
            "schedule_store_visit",
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["followthrough_action_label"],
            "约到店确认",
        )
        self.assertIn(
            "预算收一档对比版",
            rendered["prepared_payload"]["next_best_action"]["card_text"],
        )
        self.assertIn(
            "约到店",
            rendered["prepared_payload"]["next_best_action"]["followthrough_text"],
        )
        self.assertIn(
            "V1 当前正式版",
            rendered["prepared_payload"]["quote_version_actions"]["current_send_action"],
        )
        self.assertIn(
            "V2 预算收一档对比版",
            rendered["prepared_payload"]["quote_version_actions"]["next_version_offer_action"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_quick_actions"][0]["label"],
            "当前发送句",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_workbench"]["primary_action"]["code"],
            "send_current_quote",
        )
        self.assertIn(
            "预算控制",
            rendered["prepared_payload"]["consultant_workbench"]["header"]["summary"],
        )
        compare_panel = next(
            panel
            for panel in rendered["prepared_payload"]["consultant_workbench"]["info_panels"]
            if panel["code"] == "compare_focus"
        )
        self.assertIn("主体尺寸、核心结构", " ".join(compare_panel["lines"]))
        objection_panel = next(
            panel
            for panel in rendered["prepared_payload"]["consultant_workbench"]["info_panels"]
            if panel["code"] == "objection_focus"
        )
        self.assertEqual(objection_panel["action_code"], "send_current_then_budget_compare")
        self.assertIn(
            "预算收一档对比",
            rendered["prepared_payload"]["consultant_quick_actions"][1]["text"],
        )
        self.assertIn(
            "客户问能不能便宜点",
            rendered["prepared_payload"]["consultant_quick_actions"][3]["label"],
        )
        self.assertIn(
            "主体结构先不动",
            rendered["prepared_payload"]["quote_version_actions"]["customer_transition_line"],
        )
        self.assertIn(
            "预算收一档对比",
            rendered["prepared_payload"]["follow_up_script_set"]["customer_compare_offer"],
        )
        self.assertIn(
            "约到店",
            rendered["prepared_payload"]["follow_up_script_set"]["customer_followthrough_offer"],
        )
        self.assertIn(
            "这轮重点不是再解释价格",
            rendered["prepared_payload"]["follow_up_script_set"]["consultant_followthrough_prompt"],
        )
        self.assertIn(
            "约到店",
            rendered["prepared_payload"]["follow_up_script_set"]["next_touch_followthrough"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["objection_playbook"]["recommended_first_code"],
            "cheaper_option",
        )
        self.assertIn(
            "不要直接打折",
            rendered["prepared_payload"]["objection_playbook"]["cheaper_option"]["consultant_tactic"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["objection_playbook"]["cheaper_option"]["transition_action_code"],
            "send_current_then_budget_compare",
        )
        self.assertIn(
            "预算收一档对比版",
            rendered["prepared_payload"]["objection_playbook"]["cheaper_option"]["transition_line"],
        )
        self.assertIn(
            "约到店",
            rendered["prepared_payload"]["objection_playbook"]["cheaper_option"]["followthrough_line"],
        )
        self.assertIn(
            "预算收一档对比版",
            rendered["prepared_payload"]["objection_playbook"]["cheaper_option"]["recommended_action"],
        )
        self.assertIn("建议对比变量：先看附加项，再看门型层次", rendered["internal_summary"])
        self.assertIn("客户当前更在意预算控制", rendered["prepared_payload"]["consultant_handoff_plan"]["handoff_focus_note"])
        self.assertIn("正式报价：34372.8元", rendered["internal_summary"])
        self.assertNotIn("客户当前更在意：预算控制", rendered["customer_forward_text"])

    def test_consultant_internal_summary_can_surface_aesthetics_action_hint(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "customer_priority": "aesthetics",
        }

        rendered = MODULE.render_for_output_profile(payload, audience_role="consultant", output_profile="consultant_dual")

        self.assertIn("客户当前更在意：整体效果", rendered["internal_summary"])
        self.assertIn("建议动作：先发当前版；如客户想看效果，再补一版门型/材质升级对比。", rendered["internal_summary"])
        self.assertIn("对比指令：下一版保持结构不变，只替换门型层次或材质表达。", rendered["internal_summary"])
        self.assertIn("建议对比变量：先看门型层次，再看材质表达", rendered["internal_summary"])
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["compare_version_title"],
            "效果升级对比版",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["compare_variables"][0]["instruction"],
            "先替换门型层次，看整体气质变化。",
        )
        self.assertEqual(
            rendered["prepared_payload"]["consultant_handoff_plan"]["keep_fixed_fields"],
            ["主体结构", "主体尺寸"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["compare_plan"]["adjustable_variables"][1]["code"],
            "material_finish",
        )
        self.assertEqual(
            rendered["prepared_payload"]["post_quote_stage"]["code"],
            "formal_quote_waiting_finish_feedback",
        )
        self.assertEqual(
            rendered["prepared_payload"]["quote_version_summary"]["next_version_label"],
            "效果升级对比版",
        )
        self.assertIn(
            "想看更高一级效果",
            rendered["prepared_payload"]["quote_version_summary"]["version_transition_note"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["title"],
            "先发当前版，再补效果升级对比",
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["secondary_action_code"],
            "send_current_then_finish_upgrade_compare",
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["followthrough_action_code"],
            "request_design_deepening",
        )
        self.assertEqual(
            rendered["prepared_payload"]["next_best_action"]["followthrough_action_label"],
            "转深化/出图",
        )
        self.assertIn(
            "效果升级对比版",
            rendered["prepared_payload"]["next_best_action"]["text"],
        )
        self.assertIn(
            "出图前确认",
            rendered["prepared_payload"]["next_best_action"]["followthrough_text"],
        )
        self.assertIn(
            "转深化",
            rendered["prepared_payload"]["follow_up_script_set"]["customer_followthrough_offer"],
        )
        self.assertIn(
            "出图前确认",
            rendered["prepared_payload"]["follow_up_script_set"]["consultant_followthrough_prompt"],
        )
        self.assertIn(
            "V2 效果升级对比版",
            rendered["prepared_payload"]["quote_version_actions"]["next_version_offer_action"],
        )
        self.assertEqual(
            rendered["prepared_payload"]["quote_version_actions"]["recommended_trigger"],
            "想看更高一级效果",
        )
        self.assertEqual(
            rendered["prepared_payload"]["objection_playbook"]["why_this_price"]["transition_action_code"],
            "send_current_then_finish_upgrade_compare",
        )
        self.assertIn(
            "效果升级对比版",
            rendered["prepared_payload"]["objection_playbook"]["why_this_price"]["transition_line"],
        )
        self.assertRegex(
            rendered["prepared_payload"]["objection_playbook"]["why_this_price"]["followthrough_line"],
            "深化|出图前确认",
        )

    def test_validate_output_contract_accepts_well_formed_formal_quote(self) -> None:
        rendered = "\n".join(
            [
                "产品：流云衣柜",
                "已确认：北美黑胡桃木，1.8m*2.2m*0.6m",
                "这次按投影面积计价。",
                "计算过程：",
                "- 基础价格 = 1.8 × 2.2 × 8680 = 34372.8",
                "小计：34372.8元",
                "",
                "正式报价：34372.8元",
            ]
        )

        validation = MODULE.validate_output_contract(rendered, reference=False)

        self.assertTrue(validation["passed"])
        self.assertTrue(validation["assertions"]["output_contract_pass"]["passed"])

    def test_render_rejects_internal_process_leak_in_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "note": "我先运行预检再继续。",
        }

        with self.assertRaises(SystemExit):
            MODULE.render(payload)

    def test_main_appends_quote_card_prompt_and_writes_bundle_when_context_present(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m，纹理连续",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }
        context_json = json.dumps(
            {
                "message_id": "om_x100b53cafe",
                "sender_id": "ou_123456",
                "sender": "ou_123456",
                "timestamp": "Sun 2026-03-29 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            argv = [
                "format_quote_reply.py",
                "--input-json",
                json.dumps(payload, ensure_ascii=False),
                "--disable-addenda",
                "--context-json",
                context_json,
                "--channel",
                "feishu",
                "--bundle-root",
                tmpdir,
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                MODULE.main()

            rendered = stdout.getvalue()
            bundle_files = list(Path(tmpdir).rglob("latest.json"))

        self.assertIn("正式报价：34372.8元", rendered)
        self.assertIn("如果你需要，我可以把这次报价整理成一张图片发到当前会话。你回复“生成图片”就可以。", rendered)
        self.assertEqual(len(bundle_files), 1)

    def test_main_stores_role_aware_flow_state_when_context_present(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }
        context_json = json.dumps(
            {
                "message_id": "om_role_store",
                "sender_id": "ou_123456",
                "sender": "ou_123456",
                "timestamp": "Sun 2026-03-29 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            argv = [
                "format_quote_reply.py",
                "--input-json",
                json.dumps(payload, ensure_ascii=False),
                "--disable-addenda",
                "--context-json",
                context_json,
                "--channel",
                "feishu",
                "--audience-role",
                "consultant",
                "--output-profile",
                "consultant_dual",
                "--bundle-root",
                str(Path(tmpdir) / "bundles"),
                "--flow-state-root",
                str(Path(tmpdir) / "states"),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", new_callable=io.StringIO):
                MODULE.main()

            state_files = list((Path(tmpdir) / "states").rglob("latest.json"))
            self.assertEqual(len(state_files), 1)
            saved = json.loads(state_files[0].read_text(encoding="utf-8"))

        self.assertEqual(saved["audience_role"], "consultant")
        self.assertIn("customer_forward_text", saved["summaries"])
        self.assertIn("internal_summary", saved["summaries"])
        self.assertEqual(saved["quote_stage"], "formal_quote_ready")
        self.assertEqual(saved["next_best_action"]["code"], "compare_or_generate_card")
        self.assertEqual(saved["next_best_action"]["primary_action_code"], "send_current_quote")
        self.assertEqual(saved["next_best_action"]["secondary_action_code"], "offer_compare_version")
        self.assertEqual(saved["next_best_action"]["followthrough_action_code"], "schedule_store_or_design_followup")
        self.assertGreaterEqual(len(saved["budget_adjustment_suggestions"]), 2)
        self.assertEqual(saved["consultant_handoff_plan"], {})
        self.assertEqual(saved["compare_plan"]["code"], "standard_compare")
        self.assertEqual(saved["post_quote_stage"]["code"], "formal_quote_waiting_reply")
        self.assertIn("consultant_follow_up", saved["follow_up_script_set"])
        self.assertIn("customer_followthrough_offer", saved["follow_up_script_set"])
        self.assertIn("consultant_followthrough_prompt", saved["follow_up_script_set"])
        self.assertIn("next_touch_followthrough", saved["follow_up_script_set"])
        self.assertEqual(saved["quote_version_summary"]["current_version_index"], "V1")
        self.assertEqual(saved["quote_version_summary"]["next_version_index"], "V2")
        self.assertIn("quote_version_actions", saved)
        self.assertIn("V2 方案对比版", saved["quote_version_actions"]["next_version_offer_action"])
        self.assertEqual(saved["consultant_action_queue"][0]["code"], "send_current_quote")
        self.assertEqual(saved["consultant_action_queue"][0]["rank"], 1)
        self.assertTrue(saved["consultant_action_queue"][0]["recommended"])
        self.assertEqual(saved["consultant_workbench"]["primary_action"]["code"], "send_current_quote")
        self.assertEqual(saved["consultant_workbench"]["action_queue"][1]["code"], "offer_compare_version")
        self.assertEqual(saved["consultant_action_queue"][3]["code"], "handle_price_high")
        self.assertEqual(saved["objection_playbook"]["recommended_first_code"], "price_high")

    def test_main_handoff_summary_carries_customer_priority_focus(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "customer_priority": "budget",
        }
        context_json = json.dumps(
            {
                "message_id": "om_role_handoff",
                "sender_id": "ou_123456",
                "sender": "ou_123456",
                "timestamp": "Sun 2026-03-29 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            argv = [
                "format_quote_reply.py",
                "--input-json",
                json.dumps(payload, ensure_ascii=False),
                "--disable-addenda",
                "--context-json",
                context_json,
                "--channel",
                "feishu",
                "--audience-role",
                "consultant",
                "--output-profile",
                "consultant_dual",
                "--bundle-root",
                str(Path(tmpdir) / "bundles"),
                "--flow-state-root",
                str(Path(tmpdir) / "states"),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", new_callable=io.StringIO):
                MODULE.main()

            state_files = list((Path(tmpdir) / "states").rglob("latest.json"))
            saved = json.loads(state_files[0].read_text(encoding="utf-8"))

        self.assertIn("客户当前更在意预算控制", saved["handoff_summary"])
        self.assertIn("先发当前版", saved["handoff_summary"])
        self.assertIn("只减附加项或收一档门型", saved["handoff_summary"])
        self.assertIn("建议对比变量：先看附加项，再看门型层次", saved["handoff_summary"])
        self.assertIn("V1 当前正式版", saved["handoff_summary"])
        self.assertIn("V2 预算收一档对比版", saved["handoff_summary"])
        self.assertIn("如果客户继续压预算", saved["handoff_summary"])
        self.assertIn("动作排序：1. 先发当前版；2. 补预算收一档对比版；3. 约到店确认。", saved["handoff_summary"])
        self.assertIn("正式报价", saved["handoff_summary"])
        self.assertEqual(saved["next_best_action"]["title"], "先发当前版，再补预算对比")
        self.assertEqual(saved["next_best_action"]["secondary_action_code"], "send_current_then_budget_compare")
        self.assertEqual(saved["next_best_action"]["followthrough_action_code"], "schedule_store_visit")
        self.assertEqual(saved["consultant_handoff_plan"]["priority"], "budget")
        self.assertEqual(saved["consultant_handoff_plan"]["compare_code"], "reduce_addons_keep_structure")
        self.assertEqual(saved["consultant_handoff_plan"]["compare_variables"][0]["code"], "addons")
        self.assertEqual(saved["quote_version_summary"]["next_version_label"], "预算收一档对比版")
        self.assertEqual(saved["quote_version_actions"]["recommended_trigger"], "继续压预算")
        self.assertEqual(saved["consultant_action_queue"][0]["code"], "send_current_quote")
        self.assertEqual(saved["consultant_action_queue"][1]["code"], "send_current_then_budget_compare")
        self.assertEqual(saved["consultant_action_queue"][2]["code"], "schedule_store_visit")
        self.assertEqual(saved["consultant_action_queue"][3]["code"], "handle_cheaper_option")
        self.assertEqual(saved["objection_playbook"]["recommended_first_code"], "cheaper_option")

    def test_prepare_payload_applies_active_addendum_layers(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m，纹理连续",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-a"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            index_path = reports_dir / "rules-index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "domain": "cabinet",
                                "pricing_relevant": True,
                                "clean_title": "流云门板纹理连续超过0.9m需补差",
                                "excerpt": "流云/飞瀑平板门纹理连续超过0.9m时按平板门差价补差",
                                "tags": ["柜体", "门型", "流云"],
                                "relevance_score": 9,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            layer_dir.mkdir()
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "designer-a",
                        "layer_name": "设计师追加规则 A",
                        "status": "ACTIVE",
                        "artifacts": {"rules_index_file": str(index_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            prepared = MODULE.prepare_payload(payload, addenda_root=addenda_root, disable_addenda=False)

        self.assertIn("addendum_notes", prepared)
        self.assertIn("设计师追加规则 A", prepared["addendum_notes"][0])
        self.assertIn("addendum_adjustments", prepared["items"][0])

    def test_render_keeps_addendum_adjustments_in_single_unified_block(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                    "addendum_adjustments": [
                        "追加规则：纹理连续超过0.9m，门板差价 +900元/㎡路径复核",
                        "追加规则说明：该条来自设计师补充手册 A",
                    ],
                }
            ],
            "total": "34372.8元",
            "note": "按当前规则可正式报价",
            "addendum_notes": ["已套用设计师追加规则：手册 A"],
        }

        rendered = MODULE.render(payload)

        self.assertIn("计算过程：", rendered)
        self.assertIn("这次按投影面积计价。", rendered)
        self.assertIn("追加规则：纹理连续超过0.9m", rendered)
        self.assertEqual(rendered.count("正式报价："), 1)
        self.assertNotIn("追加规则1：", rendered)
        self.assertIn("补充：按当前规则可正式报价；已套用设计师追加规则：手册 A", rendered)
        self.assertNotIn("计价方式：", rendered)

    def test_render_does_not_duplicate_pricing_method_prefix(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }

        rendered = MODULE.render(payload)

        self.assertIn("这次按投影面积计价。", rendered)
        self.assertNotIn("这次按按投影面积计价。", rendered)

    def test_render_reads_structured_addendum_decisions(self) -> None:
        payload = {
            "items": [
                {
                    "product": "箱体床",
                    "confirmed": "北美黑胡桃木，1.8m*2m",
                    "pricing_method": "单件计价",
                    "calculation_steps": ["基础价格 = 12800"],
                    "subtotal": "12800元",
                    "addendum_decisions": {
                        "adjustments": [
                            {"title": "举升器需单独收费", "detail": "如床垫超重，需改用两套750N举升器并单独收费"}
                        ],
                        "constraints": [
                            {"title": "床垫重量应≤50kg", "detail": "超过时需改用更高规格举升器"}
                        ],
                        "follow_up_questions": [],
                    },
                }
            ],
            "total": "12800元",
        }

        rendered = MODULE.render(payload)

        self.assertIn("追加规则：举升器需单独收费", rendered)
        self.assertIn("追加限制：床垫重量应≤50kg", rendered)

    def test_render_reads_follow_up_questions_in_unified_block(self) -> None:
        payload = {
            "items": [
                {
                    "product": "箱体床",
                    "confirmed": "北美黑胡桃木，1.8m*2m，床垫重量未知",
                    "pricing_method": "单件计价",
                    "calculation_steps": ["基础价格 = 12800"],
                    "subtotal": "12800元",
                    "addendum_decisions": {
                        "adjustments": [],
                        "constraints": [],
                        "follow_up_questions": [
                            {"question": "请确认床垫重量", "detail": "床垫超重需改用两套750N举升器并单独收费"}
                        ],
                    },
                }
            ],
            "total": "12800元",
        }

        rendered = MODULE.render(payload)

        self.assertIn("追加确认：请确认床垫重量", rendered)
        self.assertEqual(rendered.count("正式报价："), 1)

    def test_render_keeps_rock_slab_calculation_steps_in_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "玄关柜",
                    "confirmed": "北美白橡木，岩板台面，岩板长度1.8m",
                    "pricing_method": "投影面积计价+岩板加价",
                    "calculation_steps": [
                        "基础柜体价格 = 1.6 × 2.2 × 6380 = 22457.6",
                        "岩板台面加价 = 1460 × 1.8 = 2628",
                        "小计 = 22457.6 + 2628 = 25085.6",
                    ],
                    "subtotal": "25085.6元",
                }
            ],
            "total": "25085.6元",
        }

        rendered = MODULE.render(payload)

        self.assertIn("岩板台面加价 = 1460 × 1.8 = 2628", rendered)
        self.assertIn("正式报价：25085.6元", rendered)

    def test_render_keeps_rock_slab_backboard_side_panel_steps_in_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "玄关柜",
                    "confirmed": "北美黑胡桃木，岩板背板，岩板长度1.5m，空区高度0.55m，超出侧板面积0.36㎡",
                    "pricing_method": "投影面积计价+岩板加价",
                    "calculation_steps": [
                        "基础柜体价格 = 15000",
                        "岩板背板加价 = 1460 × 1.5 = 2190",
                        "侧板加价 = 0.36 × 2028 = 730.08",
                        "小计 = 15000 + 2190 + 730.08 = 17920.08",
                    ],
                    "subtotal": "17920.08元",
                }
            ],
            "total": "17920.08元",
        }

        rendered = MODULE.render(payload)

        self.assertIn("岩板背板加价 = 1460 × 1.5 = 2190", rendered)
        self.assertIn("侧板加价 = 0.36 × 2028 = 730.08", rendered)
        self.assertIn("正式报价：17920.08元", rendered)


if __name__ == "__main__":
    unittest.main()
