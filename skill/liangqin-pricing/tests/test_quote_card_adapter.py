import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quote_card_adapter.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("quote_card_adapter", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QuoteCardAdapterTests(unittest.TestCase):
    def test_adapts_single_formal_quote_to_card_view_model(self) -> None:
        payload = {
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
            "note": "如尺寸或材质调整，报价将同步更新。",
            "option_set": [
                {"level": "recommended", "title": "当前确认方案", "description": "按当前尺寸、材质和做法继续深化。"},
                {"level": "budget_friendly", "title": "预算收一档", "description": "如果先控预算，优先从门型、材质或附加项收一档。"},
                {"level": "upgraded", "title": "效果升级版", "description": "如果更看重整体效果，可往门型或材质层次升级。"},
            ],
            "quote_version_actions": {
                "current_send_action": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                "next_version_offer_action": "如果客户继续压预算，再发 V2 预算收一档对比版。",
                "customer_transition_line": "如果你想把预算再往下收，我可以先让主体结构先不动，再补你一版预算收一档对比版。",
                "consultant_transition_action": "先发当前正式版；客户继续压预算时，只减附加项或收一档门型，不改主体尺寸和核心结构。",
                "recommended_trigger": "继续压预算",
                "copy_ready_offer": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
            },
            "consultant_action_queue": [
                {
                    "code": "send_current_quote",
                    "title": "先发当前版",
                    "text": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                    "group": "current_main",
                    "priority": "p1",
                    "rank": 1,
                    "recommended": True,
                    "source": "quote_version_actions.current_send_action",
                    "trigger_hint": "适合正式报价刚发出这一轮先用。",
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
                    "trigger_hint": "适合客户继续压预算时再接。",
                },
            ],
            "next_best_action": {
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
            "consultant_quick_actions": [
                {
                    "code": "copy_ready_offer",
                    "label": "当前发送句",
                    "text": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
                    "group": "quote_send",
                    "priority": "primary",
                    "source": "quote_version_actions.copy_ready_offer",
                },
                {
                    "code": "copy_recommended_objection_reply",
                    "label": "推荐异议回复 | 客户问能不能便宜点",
                    "text": "如果你更想先控预算，我可以基于这版再补一版预算收一档对比版。",
                    "group": "objection_reply",
                    "priority": "primary",
                    "source": "objection_playbook.cheaper_option.customer_reply",
                },
            ],
            "decision_risk_points": [
                "这次报价基于已确认的尺寸、材质和结构；任一项变化，价格会同步更新。",
                "如果后续增加灯带、抽屉、特殊门型或超常规进深，价格会重新计算。",
            ],
            "objection_playbook": {
                "recommended_first_code": "cheaper_option",
                "price_high": {
                    "label": "客户说价格偏高",
                    "customer_reply": "可以理解，这版是按当前确认条件锁出来的。",
                    "transition_line": "如果你愿意，我也可以基于这版再补一版预算收一档对比版。",
                    "followthrough_line": "如果这版区间接受，下一步优先约到店或沟通，把预算边界一次收清。",
                },
                "cheaper_option": {
                    "label": "客户问能不能便宜点",
                    "customer_reply": "如果你更想先控预算，我可以基于这版再补一版预算收一档对比版。",
                    "transition_line": "如果你想先控预算，我可以先按同样结构补一版预算收一档对比给你。",
                    "followthrough_line": "如果这版区间接受，下一步优先约到店或沟通，把预算边界一次收清。",
                },
                "need_time": {
                    "label": "客户说再考虑下",
                    "customer_reply": "没问题，这版你可以先留着内部讨论。",
                    "transition_line": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
                    "followthrough_line": "如果客户暂时没回，下一次跟进优先推进约到店或沟通，把预算边界收清。",
                },
            },
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["quote_badge"], "正式报价")
        self.assertEqual(result["headline"], "北美黑胡桃木流云衣柜")
        self.assertEqual(result["quote_total"], "39,529 元")
        self.assertEqual(result["item_rows"][0]["name"], "北美黑胡桃木流云衣柜")
        self.assertEqual(result["item_rows"][0]["amount"], "39,529 元")
        self.assertTrue(any("按投影面积计价" in line for line in result["key_basis_lines"]))
        self.assertEqual(result["notes"], ["如尺寸或材质调整，报价将同步更新。"])
        self.assertEqual(result["next_action_text"], "先发当前版；如果客户继续压预算，再补一版预算收一档对比版。")
        self.assertEqual(result["followthrough_action"]["label"], "约到店确认")
        self.assertIn("约到店", result["followthrough_action"]["text"])
        self.assertEqual(len(result["option_cards"]), 3)
        self.assertEqual(len(result["version_action_cards"]), 3)
        self.assertEqual(result["version_action_cards"][0]["title"], "当前怎么发")
        self.assertIn("V2 预算收一档对比版", result["version_action_cards"][1]["detail"])
        self.assertEqual(len(result["action_queue_cards"]), 2)
        self.assertIn("建议先做 1", result["action_queue_cards"][0]["title"])
        self.assertIn("先发当前版", result["action_queue_cards"][0]["title"])
        self.assertIn("动作：先发 V1 当前正式版", result["action_queue_cards"][0]["lines"][0])
        self.assertIn("时机：适合正式报价刚发出这一轮先用。", result["action_queue_cards"][0]["lines"][1])
        self.assertIn("第 2 步", result["action_queue_cards"][1]["title"])
        self.assertEqual(len(result["quick_action_cards"]), 2)
        self.assertEqual(result["quick_action_cards"][0]["title"], "当前发送句")
        self.assertIn("预算收一档对比", result["quick_action_cards"][0]["detail"])
        self.assertIn("客户问能不能便宜点", result["quick_action_cards"][1]["title"])
        self.assertEqual(len(result["objection_action_cards"]), 3)
        self.assertIn("优先处理", result["objection_action_cards"][0]["title"])
        self.assertIn("怎么回", result["objection_action_cards"][0]["lines"][0])
        self.assertIn("怎么接", result["objection_action_cards"][0]["lines"][1])
        self.assertIn("怎么推进", result["objection_action_cards"][0]["lines"][2])
        self.assertEqual(len(result["decision_risk_points"]), 2)
        self.assertEqual(result["overflow_hint"], "")

    def test_card_view_model_keeps_priority_specific_option_cards(self) -> None:
        payload = {
            "items": [
                {
                    "product": "北美黑胡桃木流云衣柜",
                    "confirmed": "长 1.8 米 × 深 0.6 米 × 高 2.2 米。",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["基础价格：34,372.8 元"],
                    "subtotal": "34,372.8 元",
                }
            ],
            "total": "34,372.8 元",
            "option_set": [
                {"level": "recommended", "title": "预算优先方案", "description": "先锁主体结构和核心收纳。"},
                {"level": "budget_friendly", "title": "主体先落地", "description": "门型层次和附加项先后置。"},
                {"level": "upgraded", "title": "预算有余量再升级", "description": "后续再补门型和材质层次。"},
            ],
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["option_cards"][0]["title"], "预算优先方案")
        self.assertEqual(result["option_cards"][1]["detail"], "门型层次和附加项先后置。")

    def test_card_view_model_can_include_reference_version_actions(self) -> None:
        payload = {
            "reference": True,
            "items": [
                {
                    "product": "北美白橡木书柜",
                    "confirmed": "长度待确认，先按当前条件预估。",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["先按当前条件预估：30,624 元"],
                    "subtotal": "30,624 元",
                }
            ],
            "total": "30,624 元",
            "quote_version_actions": {
                "current_send_action": "先发 V1 当前参考版，明确这是基于当前条件的参考估算。",
                "next_version_offer_action": "关键条件补齐后，再转 V2 正式报价版。",
                "customer_transition_line": "这版我先按当前条件给你做参考，等关键条件补齐后，我再转正式报价给你。",
                "consultant_transition_action": "先发参考版，不急着谈收价；优先补齐关键条件后再转正式报价。",
                "recommended_trigger": "关键条件补齐后",
                "copy_ready_offer": "这版你可以先作为参考看一下；等关键条件补齐后，我再给你转正式报价版。",
            },
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["quote_badge"], "参考报价（仅供参考）")
        self.assertEqual(result["version_action_cards"][0]["title"], "当前怎么发")
        self.assertIn("V1 当前参考版", result["version_action_cards"][0]["detail"])
        self.assertIn("V2 正式报价版", result["version_action_cards"][1]["detail"])

    def test_card_view_model_can_include_followthrough_action_for_reference_quote(self) -> None:
        payload = {
            "reference": True,
            "items": [
                {
                    "product": "北美白橡木书柜",
                    "confirmed": "长度待确认，先按当前条件预估。",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["先按当前条件预估：30,624 元"],
                    "subtotal": "30,624 元",
                }
            ],
            "total": "30,624 元",
            "next_best_action": {
                "code": "confirm_key_fields",
                "title": "先补关键条件，再转正式报价",
                "text": "下一步先补关键条件；补齐后直接转正式报价版。",
                "card_text": "先补关键条件；补齐后转正式报价。",
                "primary_action_code": "confirm_key_fields",
                "primary_action_label": "补关键条件",
                "secondary_action_code": "upgrade_to_formal_quote",
                "secondary_action_label": "转正式报价",
                "followthrough_action_code": "lock_formal_quote",
                "followthrough_action_label": "锁正式报价",
                "followthrough_text": "关键条件补齐并确认无误后，下一步就直接锁正式报价，再往下推进。",
            },
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["followthrough_action"]["label"], "锁正式报价")
        self.assertIn("锁正式报价", result["followthrough_action"]["text"])

    def test_card_view_model_can_include_reference_objection_action_cards(self) -> None:
        payload = {
            "reference": True,
            "items": [
                {
                    "product": "北美白橡木书柜",
                    "confirmed": "长度待确认，先按当前条件预估。",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["先按当前条件预估：30,624 元"],
                    "subtotal": "30,624 元",
                }
            ],
            "total": "30,624 元",
            "objection_playbook": {
                "recommended_first_code": "why_this_price",
                "why_this_price": {
                    "label": "客户追问为什么是这个价",
                    "customer_reply": "这次还是参考阶段，我先按你目前确认的条件估出来。",
                    "transition_line": "这版我先按当前条件给你做参考，等关键条件补齐后，我再转正式报价给你。",
                    "followthrough_line": "关键条件补齐并确认无误后，下一步就直接锁正式报价，再往下推进。",
                }
            },
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(len(result["objection_action_cards"]), 1)
        self.assertIn("优先处理", result["objection_action_cards"][0]["title"])
        self.assertIn("补齐", result["objection_action_cards"][0]["lines"][1])
        self.assertIn("锁正式报价", result["objection_action_cards"][0]["lines"][2])

    def test_adapts_reference_multi_item_quote_to_summary_card(self) -> None:
        payload = {
            "reference": True,
            "items": [
                {
                    "product": "儿童房半高床",
                    "confirmed": "榉木，1.2 米床垫",
                    "pricing_method": "按模块组合计价",
                    "calculation_steps": ["床体模块：18,600 元"],
                    "subtotal": "18,600 元",
                },
                {
                    "product": "书桌",
                    "confirmed": "榉木，长 1.4 米",
                    "pricing_method": "按单件计价",
                    "calculation_steps": ["书桌：6,800 元"],
                    "subtotal": "6,800 元",
                },
                {
                    "product": "椅子",
                    "confirmed": "榉木",
                    "pricing_method": "按单件计价",
                    "calculation_steps": ["椅子：1,200 元"],
                    "subtotal": "1,200 元",
                },
            ],
            "total": "26,600 元",
            "note": "完整尺寸确认后可转正式报价。",
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["quote_badge"], "参考报价（仅供参考）")
        self.assertEqual(result["headline"], "儿童空间报价")
        self.assertEqual(len(result["item_rows"]), 3)
        self.assertEqual(result["item_rows"][1]["name"], "书桌")
        self.assertTrue(any("共 3 项" in line for line in result["key_basis_lines"]))
        self.assertEqual(result["notes"], ["完整尺寸确认后可转正式报价。"])

    def test_multi_item_quote_keeps_child_room_detail_highlights(self) -> None:
        payload = {
            "items": [
                {
                    "product": "儿童房半高床",
                    "confirmed": "乌拉圭玫瑰木，半高床，1.2 米床垫，梯柜上下。",
                    "pricing_method": "按模块组合计价",
                    "calculation_steps": [
                        "高架床模块：2 × 1.2 × 2020 = 4848 元",
                        "篱笆围栏：2 × 0.4 × 696 = 556.8 元",
                        "梯柜（含篱笆围栏）：3100 元",
                        "小计：8505 元",
                    ],
                    "subtotal": "8,505 元",
                },
                {
                    "product": "经典双屉书桌",
                    "confirmed": "乌拉圭玫瑰木，1.2 米。",
                    "pricing_method": "按单件计价",
                    "calculation_steps": [
                        "单价：3080 元",
                    ],
                    "subtotal": "3,080 元",
                },
            ],
            "total": "11,585 元",
            "note": "椅子未含在本次报价内。",
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["headline"], "儿童空间报价")
        self.assertEqual(result["confirmed_text"], "共 2 项，包含儿童房半高床、经典双屉书桌。")
        self.assertTrue(any("儿童房半高床：高架床模块" in line for line in result["key_basis_lines"]))
        self.assertTrue(any("儿童房半高床：篱笆围栏" in line for line in result["key_basis_lines"]))
        self.assertIn("detail_cards", result)
        self.assertEqual(len(result["detail_cards"]), 2)
        self.assertEqual(result["detail_cards"][0]["name"], "儿童房半高床")
        self.assertEqual(result["detail_cards"][0]["amount"], "8,505 元")
        self.assertIn("梯柜（含篱笆围栏）：3100 元", result["detail_cards"][0]["highlights"])
        self.assertEqual(result["detail_cards"][1]["highlights"], ["单价：3080 元"])

    def test_filters_internal_rule_notes(self) -> None:
        payload = {
            "items": [
                {
                    "product": "北美白橡木书柜",
                    "confirmed": "长 2 米 × 高 2.4 米",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": ["基础价格：2 × 2.4 × 6380 = 30,624 元"],
                    "subtotal": "30,624 元",
                }
            ],
            "total": "30,624 元",
            "note": "按当前规则可正式报价。",
            "addendum_notes": ["已套用设计师追加规则：设计师补充手册 A。"],
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["notes"], [])

    def test_trims_overlong_summary_and_sets_overflow_hint(self) -> None:
        payload = {
            "items": [
                {
                    "product": f"产品 {index + 1}",
                    "confirmed": "尺寸待深化",
                    "pricing_method": "按投影面积计价",
                    "calculation_steps": [f"基础价格：步骤 {index + 1}"],
                    "subtotal": f"{(index + 1) * 1000} 元",
                }
                for index in range(10)
            ],
            "total": "55,000 元",
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["headline"], "定制报价汇总")
        self.assertEqual(len(result["item_rows"]), 6)
        self.assertIn("完整计算过程见本条文字报价", result["overflow_hint"])


if __name__ == "__main__":
    unittest.main()
