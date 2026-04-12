import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quote_card_renderer.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("quote_card_renderer", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QuoteCardRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.view_model = {
            "quote_badge": "正式报价",
            "headline": "北美黑胡桃木流云衣柜",
            "quote_total": "39,529 元",
            "confirmed_text": "长 1.8 米 × 深 0.67 米 × 高 2.2 米，材质北美黑胡桃木，门板纹理连续。",
            "item_rows": [
                {"name": "北美黑胡桃木流云衣柜", "amount": "39,529 元", "meta": "按投影面积计价"}
            ],
            "key_basis_lines": [
                "计价方式：按投影面积计价",
                "投影面积：1.8 × 2.2 = 3.96㎡",
                "超深加价：34,372.8 × 15% = 5,155.92 元",
            ],
            "notes": ["如尺寸或材质调整，报价将同步更新。"],
            "version_action_cards": [
                {"title": "当前怎么发", "detail": "先发 V1 当前正式版，先把当前锁价结果发给客户。"},
                {"title": "下一版怎么接", "detail": "如果客户继续压预算，再发 V2 预算收一档对比版。"},
                {"title": "给客户怎么解释", "detail": "如果你想把预算再往下收，我可以先让主体结构先不动，再补你一版预算收一档对比版。"},
            ],
            "action_queue_cards": [
                {
                    "title": "建议先做 1 | 先发当前版",
                    "lines": [
                        "动作：先发 V1 当前正式版，先把当前锁价结果发给客户。",
                        "时机：适合正式报价刚发出这一轮先用。",
                    ],
                },
                {
                    "title": "第 2 步 | 补预算收一档对比",
                    "lines": [
                        "动作：如果客户继续压预算，再发 V2 预算收一档对比版。",
                        "时机：适合客户继续压预算时再接。",
                    ],
                },
            ],
            "quick_action_cards": [
                {"title": "当前发送句", "detail": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。"},
                {"title": "推荐异议回复 | 客户问能不能便宜点", "detail": "如果你更想先控预算，我可以基于这版再补一版预算收一档对比版。"},
            ],
            "objection_action_cards": [
                {
                    "title": "优先处理 | 客户问能不能便宜点",
                    "lines": [
                        "怎么回：如果你更想先控预算，我可以基于这版再补一版预算收一档对比版。",
                        "怎么接：如果你想先控预算，我可以先按同样结构补一版预算收一档对比给你。",
                        "怎么推进：如果这版区间接受，下一步优先约到店或沟通，把预算边界一次收清。",
                    ],
                }
            ],
            "followthrough_action": {
                "label": "约到店确认",
                "text": "如果客户对当前区间接受，下一步优先约到店或约设计沟通，把预算边界和取舍一次收清。",
            },
            "overflow_hint": "完整计算过程见本条文字报价。",
        }

    def test_build_quote_card_html_contains_key_regions(self) -> None:
        html = MODULE.build_quote_card_html(self.view_model)

        self.assertIn("正式报价", html)
        self.assertIn("北美黑胡桃木流云衣柜", html)
        self.assertIn("39,529 元", html)
        self.assertIn("已确认条件", html)
        self.assertIn("关键依据", html)
        self.assertIn("版本建议", html)
        self.assertIn("当前怎么发", html)
        self.assertIn("动作排序", html)
        self.assertIn("建议先做 1 | 先发当前版", html)
        self.assertIn("快捷发送", html)
        self.assertIn("当前发送句", html)
        self.assertIn("异议承接", html)
        self.assertIn("优先处理 | 客户问能不能便宜点", html)
        self.assertIn("怎么推进", html)
        self.assertIn("成交推进", html)
        self.assertIn("约到店确认", html)
        self.assertIn("补充说明", html)
        self.assertIn("完整计算过程见本条文字报价。", html)

    def test_build_quote_card_html_uses_multi_item_detail_layout(self) -> None:
        view_model = {
            "quote_badge": "正式报价",
            "headline": "儿童空间报价",
            "quote_total": "11,585 元",
            "confirmed_text": "共 2 项，包含儿童房半高床、经典双屉书桌。",
            "item_rows": [
                {"name": "儿童房半高床", "amount": "8,505 元", "meta": "按模块组合计价"},
                {"name": "经典双屉书桌", "amount": "3,080 元", "meta": "按单件计价"},
            ],
            "key_basis_lines": [
                "共 2 项，涉及按模块组合计价 / 按单件计价。",
                "儿童房半高床：高架床模块：2 × 1.2 × 2020 = 4848 元",
                "儿童房半高床：篱笆围栏：2 × 0.4 × 696 = 556.8 元",
                "经典双屉书桌：单价：3080 元",
            ],
            "detail_cards": [
                {
                    "name": "儿童房半高床",
                    "amount": "8,505 元",
                    "meta": "按模块组合计价",
                    "highlights": [
                        "高架床模块：2 × 1.2 × 2020 = 4848 元",
                        "篱笆围栏：2 × 0.4 × 696 = 556.8 元",
                        "梯柜（含篱笆围栏）：3100 元",
                    ],
                },
                {
                    "name": "经典双屉书桌",
                    "amount": "3,080 元",
                    "meta": "按单件计价",
                    "highlights": ["单价：3080 元"],
                },
            ],
            "notes": ["完整计算过程见本条文字报价。"],
            "overflow_hint": "",
        }

        html = MODULE.build_quote_card_html(view_model)

        self.assertIn("共 2 项，包含儿童房半高床、经典双屉书桌。", html)
        self.assertIn("报价明细", html)
        self.assertIn("儿童房半高床", html)
        self.assertIn("梯柜（含篱笆围栏）：3100 元", html)
        self.assertIn("经典双屉书桌", html)
        self.assertEqual(html.count("8,505 元"), 1)
        self.assertEqual(html.count("3,080 元"), 1)
        self.assertNotIn("完整计算过程以本条文字报价为准。", html)
        self.assertNotIn("关键依据", html)

    def test_write_quote_card_export_creates_html_and_json_artifacts(self) -> None:
        bundle = {
            "prepared_payload": {"items": [], "total": "39,529 元"},
            "reply_text": "正式报价：39,529 元",
            "quote_kind": "formal",
            "conversation_id": "agent:main:feishu:direct:ou_123456",
            "eligible_for_card": True,
            "created_at": "2026-03-29T10:30:00+08:00",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.write_quote_card_export(
                view_model=self.view_model,
                bundle=bundle,
                output_root=Path(tmpdir),
            )
            payload = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(result["html_path"]).exists())
            self.assertTrue(Path(result["json_path"]).exists())
            self.assertEqual(payload["quote_total"], "39,529 元")
            self.assertEqual(result["width"], 1080)
            self.assertEqual(result["height"], 1920)


if __name__ == "__main__":
    unittest.main()
