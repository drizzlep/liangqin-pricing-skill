import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_rules_drafts.py"
SPEC = importlib.util.spec_from_file_location("build_rules_drafts", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildRulesDraftsTests(unittest.TestCase):
    def test_build_domain_payload_filters_pricing_relevant_entries(self) -> None:
        index = {
            "entries": [
                {
                    "page": 120,
                    "domain": "cabinet",
                    "clean_title": "柜体投影面积保底",
                    "excerpt": "柜体投影面积不足1.6㎡按1.6㎡计算",
                    "tags": ["柜体", "投影面积"],
                    "rule_type": "dimension_threshold",
                    "relevance_score": 8,
                    "pricing_relevant": True,
                },
                {
                    "page": 5,
                    "domain": "cabinet",
                    "clean_title": "品牌说明",
                    "excerpt": "这是一段背景说明",
                    "tags": ["待分类"],
                    "rule_type": "narrative_rule",
                    "relevance_score": 2,
                    "pricing_relevant": False,
                },
            ]
        }

        payload = MODULE.build_domain_payload(index, "cabinet")

        self.assertEqual(payload["domain"], "cabinet")
        self.assertEqual(payload["entry_count"], 1)
        self.assertEqual(payload["entries"][0]["clean_title"], "柜体投影面积保底")

    def test_render_domain_markdown_includes_existing_reference_hint(self) -> None:
        payload = {
            "domain": "bed",
            "entry_count": 1,
            "reference_hint": "rules-beds.md",
            "entries": [
                {
                    "page": 10,
                    "clean_title": "超大床按比例计价",
                    "excerpt": "超大床以1.5米宽价格为基础按比例计算",
                    "rule_type": "formula",
                    "relevance_score": 9,
                    "tags": ["床", "公式"],
                }
            ],
        }

        markdown = MODULE.render_domain_markdown(payload)

        self.assertIn("rules-beds.md", markdown)
        self.assertIn("超大床按比例计价", markdown)

    def test_main_writes_manifest_and_domain_files(self) -> None:
        index = {
            "entries": [
                {
                    "page": 88,
                    "domain": "table",
                    "clean_title": "超长桌按比例计价",
                    "excerpt": "长度超过2m按比例计算",
                    "tags": ["桌", "尺寸阈值"],
                    "rule_type": "dimension_threshold",
                    "relevance_score": 7,
                    "pricing_relevant": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "rules-index.json"
            output_dir = Path(tmpdir) / "drafts"
            input_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

            exit_code = MODULE.main(["--input", str(input_path), "--output-dir", str(output_dir)])

            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            domain_file = output_dir / "rules-draft-table.md"
            domain_file_exists = domain_file.exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["domain_count"], 1)
        self.assertTrue(domain_file_exists)


if __name__ == "__main__":
    unittest.main()
