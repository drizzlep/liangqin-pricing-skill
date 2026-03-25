import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_addendum_layer.py"
SPEC = importlib.util.spec_from_file_location("update_addendum_layer", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class UpdateAddendumLayerTests(unittest.TestCase):
    def test_apply_coverage_ledger_overrides_updates_entries_and_appends_entries(self) -> None:
        payload = {
            "entries": [
                {"page": 10, "topic": "A", "status": "unresolved"},
                {"page": 11, "topic": "B 安装说明", "status": "unresolved"},
            ]
        }
        overrides = {
            "overrides": [
                {"page": 10, "status": "excluded_background", "note": "背景页"},
                {"page": 11, "topic_contains": "安装说明", "status": "knowledge_ready", "note": "知识层"},
            ],
            "append_entries": [
                {"page": 12, "topic": "C", "status": "covered_existing", "note": "已覆盖"}
            ],
        }

        merged = MODULE.apply_coverage_ledger_overrides(payload, overrides)

        self.assertEqual(merged["entry_count"], 3)
        self.assertEqual(merged["entries"][0]["status"], "excluded_background")
        self.assertEqual(merged["entries"][0]["note"], "背景页")
        self.assertEqual(merged["entries"][1]["status"], "knowledge_ready")
        self.assertEqual(merged["entries"][1]["note"], "知识层")
        self.assertEqual(merged["entries"][2]["status"], "covered_existing")
        self.assertEqual(merged["status_counts"]["covered_existing"], 1)
        self.assertEqual(merged["status_counts"]["excluded_background"], 1)
        self.assertEqual(merged["status_counts"]["knowledge_ready"], 1)

    def test_apply_coverage_ledger_overrides_can_match_same_topic_by_summary_contains(self) -> None:
        payload = {
            "entries": [
                {"page": 20, "topic": "订制款：", "summary": "1400*1400*780；桌面直径≤1400mm", "status": "unresolved"},
                {"page": 20, "topic": "订制款：", "summary": "1600*700*780；桌长≥1400mm时", "status": "unresolved"},
            ]
        }
        overrides = {
            "overrides": [
                {
                    "page": 20,
                    "topic": "订制款：",
                    "summary_contains": "1400*1400*780",
                    "status": "knowledge_ready",
                    "note": "圆桌上限",
                }
            ]
        }

        merged = MODULE.apply_coverage_ledger_overrides(payload, overrides)

        self.assertEqual(merged["entries"][0]["status"], "knowledge_ready")
        self.assertEqual(merged["entries"][0]["note"], "圆桌上限")
        self.assertEqual(merged["entries"][1]["status"], "unresolved")

    def test_build_seed_coverage_ledger_includes_entry_count_and_status_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            index.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "page": 1,
                                "clean_title": "已入 runtime 的规则",
                                "heading": "已入 runtime 的规则",
                                "pricing_relevant": True,
                                "domain": "cabinet",
                                "normalized_rule": "规则一",
                            },
                            {
                                "page": 2,
                                "clean_title": "待人工复核的规则",
                                "heading": "待人工复核的规则",
                                "pricing_relevant": True,
                                "domain": "cabinet",
                                "normalized_rule": "规则二",
                            },
                            {
                                "page": 3,
                                "clean_title": "背景说明",
                                "heading": "背景说明",
                                "pricing_relevant": False,
                                "domain": "general",
                                "normalized_rule": "规则三",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            runtime_rules.write_text(
                json.dumps({"rules": [{"title": "已入 runtime 的规则"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            payload = MODULE.build_seed_coverage_ledger(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                index_path=index,
                runtime_rules_path=runtime_rules,
            )

        self.assertEqual(payload["entry_count"], 3)
        self.assertEqual(payload["status_counts"]["runtime_hard_rule"], 1)
        self.assertEqual(payload["status_counts"]["unresolved"], 1)
        self.assertEqual(payload["status_counts"]["excluded_background"], 1)

    def test_build_seed_coverage_ledger_prefers_audit_csv_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audit_csv = root / "pdf-coverage-audit.csv"
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            audit_csv.write_text(
                "\n".join(
                    [
                        "status,page,domain,rule_type,relevance_score,pricing_relevant,clean_title,heading,tags,excerpt,normalized_rule,runtime_title,runtime_action,reason",
                        "included_runtime,11,material,formula,9,True,规则A,规则A,尺寸阈值,excerpt-a,summary-a,标题A,constraint,已进入运行时追加规则，action_type=constraint",
                        "excluded_non_pricing,12,general,narrative_rule,2,False,规则B,规则B,待分类,excerpt-b,summary-b,,,背景说明",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            index.write_text('{"entries": []}', encoding="utf-8")
            runtime_rules.write_text('{"rules": []}', encoding="utf-8")

            payload = MODULE.build_seed_coverage_ledger(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                index_path=index,
                runtime_rules_path=runtime_rules,
                audit_csv_path=audit_csv,
            )

        self.assertEqual(payload["entry_count"], 2)
        self.assertEqual(payload["entries"][0]["status"], "runtime_hard_rule")
        self.assertEqual(payload["entries"][0]["note"], "已进入运行时追加规则，action_type=constraint")
        self.assertEqual(payload["entries"][1]["status"], "excluded_background")
        self.assertEqual(payload["entries"][1]["source"], "pdf_coverage_audit")

    def test_build_layer_manifest_keeps_layer_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            layer_dir = root / "references" / "addenda" / "designer-a"
            layer_dir.mkdir(parents=True)
            candidate = root / "rules-candidate.json"
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            knowledge_layer = root / "knowledge-layer.json"
            coverage_ledger = root / "coverage-ledger.json"
            coverage_ledger_overrides = root / "coverage-ledger-overrides.json"
            drafts_dir = root / "drafts"
            source_md = root / "rules-source.md"
            candidate.write_text("{}", encoding="utf-8")
            index.write_text("{}", encoding="utf-8")
            runtime_rules.write_text("{}", encoding="utf-8")
            knowledge_layer.write_text("{}", encoding="utf-8")
            coverage_ledger.write_text("{}", encoding="utf-8")
            coverage_ledger_overrides.write_text("{}", encoding="utf-8")
            drafts_dir.mkdir()
            (drafts_dir / "manifest.json").write_text('{"domain_count": 2}', encoding="utf-8")
            source_md.write_text("# draft", encoding="utf-8")

            manifest = MODULE.build_layer_manifest(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                source_file=Path("/tmp/source.pdf"),
                candidate_path=candidate,
                index_path=index,
                runtime_rules_path=runtime_rules,
                knowledge_layer_path=knowledge_layer,
                coverage_ledger_path=coverage_ledger,
                coverage_ledger_overrides_path=coverage_ledger_overrides,
                source_markdown_path=source_md,
                drafts_dir=drafts_dir,
                manifest_dir=layer_dir,
            )

        self.assertEqual(manifest["layer_id"], "designer-a")
        self.assertEqual(manifest["layer_name"], "设计师追加规则 A")
        self.assertEqual(manifest["status"], "ACTIVE")
        self.assertFalse(manifest["mutates_base_rules"])
        self.assertIn("rules_index_file", manifest["artifacts"])
        self.assertIn("runtime_rules_file", manifest["artifacts"])
        self.assertIn("knowledge_layer_file", manifest["artifacts"])
        self.assertIn("coverage_ledger_file", manifest["artifacts"])
        self.assertIn("coverage_ledger_overrides_file", manifest["artifacts"])
        self.assertFalse(str(manifest["source_file"]).startswith("/"))
        self.assertFalse(str(manifest["artifacts"]["runtime_rules_file"]).startswith("/"))

    def test_write_manifest_creates_layer_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "layer"
            manifest = {"layer_id": "designer-b", "status": "ACTIVE"}

            MODULE.write_manifest(output_dir, manifest)

            written = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(written["layer_id"], "designer-b")


if __name__ == "__main__":
    unittest.main()
