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
        }

        result = MODULE.adapt_quote_card_payload(payload)

        self.assertEqual(result["quote_badge"], "正式报价")
        self.assertEqual(result["headline"], "北美黑胡桃木流云衣柜")
        self.assertEqual(result["quote_total"], "39,529 元")
        self.assertEqual(result["item_rows"][0]["name"], "北美黑胡桃木流云衣柜")
        self.assertEqual(result["item_rows"][0]["amount"], "39,529 元")
        self.assertTrue(any("按投影面积计价" in line for line in result["key_basis_lines"]))
        self.assertEqual(result["notes"], ["如尺寸或材质调整，报价将同步更新。"])
        self.assertEqual(result["overflow_hint"], "")

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
