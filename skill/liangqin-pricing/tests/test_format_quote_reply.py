import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "format_quote_reply.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("format_quote_reply", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FormatQuoteReplyTests(unittest.TestCase):
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
