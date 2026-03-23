import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_rules_index.py"
SPEC = importlib.util.spec_from_file_location("build_rules_index", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildRulesIndexTests(unittest.TestCase):
    def test_build_index_adds_catalog_option_entry_from_visual_pdf_page(self) -> None:
        payload = {
            "source_file": "/tmp/rules.pdf",
            "source_format": "pdf",
            "pages": [
                {
                    "page": 279,
                    "extract_method": "hybrid",
                    "image_count": 8,
                    "raw_text": "可选色样 圣勃朗鱼肚白 保加利亚浅灰 劳伦特黑金 极光黑 极光白 阿勒山闪电黑 岩板",
                    "normalized_explanation": "本段主要是业务说明，可作为规则注释或补充前提。识别标签：待分类。关键信息：可选色样；圣勃朗鱼肚白；劳伦特黑金。",
                    "tags": ["待分类"],
                    "rule_type": "narrative_rule",
                    "confidence": 0.86,
                }
            ],
            "sections": [],
        }

        index = MODULE.build_rules_index(payload)
        entry = index["entries"][0]

        self.assertEqual(entry["response_kind"], "catalog_option")
        self.assertTrue(entry["runtime_relevant"])
        self.assertIn("可选色样", entry["clean_title"])

    def test_build_index_classifies_domain_and_relevance(self) -> None:
        payload = {
            "source_file": "/tmp/rules.pdf",
            "source_format": "pdf",
            "sections": [
                {
                    "page": 120,
                    "heading": "600mm＜柜体进深≤700mm，加价15%",
                    "content": ["衣柜按投影面积计价", "超深柜体在基础单价上加价15%"],
                    "tags": ["柜体", "超深", "投影面积", "尺寸阈值"],
                    "rule_type": "special_adjustment",
                    "normalized_rule": "本段主要描述加价、折减或特殊修正条件。",
                    "confidence": 0.95,
                    "extract_method": "text_layer",
                }
            ],
        }

        index = MODULE.build_rules_index(payload)
        entry = index["entries"][0]

        self.assertEqual(entry["domain"], "cabinet")
        self.assertTrue(entry["pricing_relevant"])
        self.assertGreaterEqual(entry["relevance_score"], 5)
        self.assertIn("柜体", entry["clean_title"])

    def test_choose_clean_title_falls_back_to_meaningful_content(self) -> None:
        title = MODULE.choose_clean_title(
            heading="2s —— — Mb Tr",
            content=["柜体投影面积不足1.6㎡按1.6㎡计算", "衣柜类按投影面积计价"],
            tags=["柜体", "投影面积"],
        )

        self.assertIn("柜体投影面积不足1.6㎡按1.6㎡计算", title)

    def test_main_writes_json_and_markdown(self) -> None:
        payload = {
            "source_file": "/tmp/rules.pdf",
            "source_format": "pdf",
            "sections": [
                {
                    "page": 10,
                    "heading": "表1",
                    "content": ["黑胡桃木", "流云衣柜 8680"],
                    "tags": ["表格", "材质", "柜体"],
                    "rule_type": "table_pricing",
                    "normalized_rule": "价格表规则。",
                    "confidence": 0.92,
                    "extract_method": "text_layer",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "candidate.json"
            output_path = Path(tmpdir) / "rules-index.json"
            markdown_path = Path(tmpdir) / "rules-index.md"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            exit_code = MODULE.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--markdown-output",
                    str(markdown_path),
                ]
            )

            written = json.loads(output_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(written["entry_count"], 1)
        self.assertIn("table_pricing", markdown)


if __name__ == "__main__":
    unittest.main()
