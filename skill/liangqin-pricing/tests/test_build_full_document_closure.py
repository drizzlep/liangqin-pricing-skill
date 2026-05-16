import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_full_document_closure.py"
SPEC = importlib.util.spec_from_file_location("build_full_document_closure", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildFullDocumentClosureTests(unittest.TestCase):
    def write_manifest(self, skill_dir: Path, layer: str, report_dir: Path) -> None:
        manifest_dir = skill_dir / "references" / "addenda" / layer
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "layer_id": layer,
                    "artifacts": {
                        "rules_candidate_file": str(report_dir / "rules-candidate.json"),
                        "coverage_ledger_file": str(report_dir / "coverage-ledger.json"),
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def write_certification_builder(self, skill_dir: Path) -> None:
        source = Path(__file__).resolve().parents[1] / "scripts" / "build_full_document_data_certification.py"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "build_full_document_data_certification.py").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def test_closes_manual_review_and_unknown_pages_without_human_limbo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            report_dir = skill_dir / "reports" / "addenda" / "online"
            report_dir.mkdir(parents=True)
            self.write_manifest(skill_dir, "online", report_dir)
            self.write_certification_builder(skill_dir)

            (report_dir / "rules-candidate.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "source_title": "图示页",
                                "source_page": 1,
                                "extract_method": "unknown",
                                "image_count": 4,
                                "source_local_path": "/tmp/page.pdf",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (report_dir / "blocking-pages-review-board.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "source_title": "图示页",
                                "source_page": 1,
                                "image_count": 4,
                                "default_decision": "必须看图",
                                "ocr": {"status": "empty", "text": "", "char_count": 0},
                                "image": {"status": "succeeded", "path": "/tmp/page.png"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (report_dir / "quality-sample-board.json").write_text(json.dumps({"samples": []}), encoding="utf-8")
            (report_dir / "coverage-ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "topic": "可讲知识",
                                "status": "unresolved",
                                "publish_target": "manual_review",
                                "rule_layer_status": "manual_review",
                                "domain": "general",
                                "source_title": "知识页",
                                "source_page": 2,
                                "summary": "这是稳定的知识说明，不含报价和安全限制。",
                            },
                            {
                                "topic": "报价规则",
                                "status": "unresolved",
                                "publish_target": "manual_review",
                                "rule_layer_status": "manual_review",
                                "domain": "cabinet",
                                "source_title": "报价页",
                                "source_page": 3,
                                "summary": "这里涉及报价公式和加价。",
                            },
                            {
                                "topic": "运行规则",
                                "status": "runtime_hard_rule",
                                "publish_target": "runtime",
                                "rule_layer_status": "runtime",
                                "domain": "cabinet",
                                "source_title": "运行页",
                                "source_page": 4,
                                "summary": "必须确认尺寸。",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="online")
            closed = json.loads((report_dir / "coverage-ledger.json").read_text(encoding="utf-8"))
            unknown = json.loads((report_dir / "unknown-page-resolution-ledger.json").read_text(encoding="utf-8"))
            certification = json.loads((report_dir / "full-document-data-certification.json").read_text(encoding="utf-8"))

        self.assertEqual(model["closure_status"], "complete")
        self.assertFalse(model["human_rule_by_rule_review_required"])
        self.assertEqual(model["closed_review_item_count"], 2)
        self.assertEqual(model["closed_review_resolution_counts"][MODULE.KNOWLEDGE_READY], 1)
        self.assertEqual(model["closed_review_resolution_counts"][MODULE.NOT_SAFE], 1)
        self.assertEqual(unknown["entries"][0]["resolution_status"], "manual_source_only")
        self.assertNotIn("unresolved", closed["status_counts"])
        self.assertNotIn("manual_review", closed["publish_target_counts"])
        self.assertEqual(closed["closure_resolution_counts"][MODULE.KNOWLEDGE_READY], 1)
        self.assertEqual(closed["closure_resolution_counts"][MODULE.NOT_SAFE], 1)
        self.assertEqual(closed["closure_resolution_counts"][MODULE.RUNTIME_RULE], 1)
        self.assertEqual(certification["review_count"], 0)
        self.assertIn("全书数据闭环已完成", certification["recommended_action"])

    def test_repeated_runs_preserve_original_review_state_for_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            report_dir = skill_dir / "reports" / "addenda" / "online"
            report_dir.mkdir(parents=True)
            self.write_manifest(skill_dir, "online", report_dir)
            self.write_certification_builder(skill_dir)

            (report_dir / "rules-candidate.json").write_text(
                json.dumps({"pages": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (report_dir / "blocking-pages-review-board.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
            (report_dir / "quality-sample-board.json").write_text(json.dumps({"samples": []}), encoding="utf-8")
            (report_dir / "coverage-ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "topic": "可讲知识",
                                "status": "unresolved",
                                "publish_target": "manual_review",
                                "rule_layer_status": "manual_review",
                                "domain": "general",
                                "source_title": "知识页",
                                "source_page": 2,
                                "summary": "这是稳定的知识说明，主要解释背景做法。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="online")
            MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="online")
            closed = json.loads((report_dir / "coverage-ledger.json").read_text(encoding="utf-8"))

        entry = closed["entries"][0]
        self.assertEqual(entry["status"], MODULE.KNOWLEDGE_READY)
        self.assertEqual(entry["publish_target"], "knowledge")
        self.assertEqual(entry["original_status"], "unresolved")
        self.assertEqual(entry["original_publish_target"], "manual_review")
        self.assertEqual(entry["original_rule_layer_status"], "manual_review")

    def test_repeated_runs_preserve_not_safe_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            report_dir = skill_dir / "reports" / "addenda" / "online"
            report_dir.mkdir(parents=True)
            self.write_manifest(skill_dir, "online", report_dir)
            self.write_certification_builder(skill_dir)

            (report_dir / "rules-candidate.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
            (report_dir / "blocking-pages-review-board.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
            (report_dir / "quality-sample-board.json").write_text(json.dumps({"samples": []}), encoding="utf-8")
            (report_dir / "coverage-ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "topic": "报价规则",
                                "status": "unresolved",
                                "publish_target": "manual_review",
                                "rule_layer_status": "manual_review",
                                "domain": "cabinet",
                                "source_title": "报价页",
                                "source_page": 3,
                                "summary": "这里涉及报价公式和加价。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="online")
            MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="online")
            closed = json.loads((report_dir / "coverage-ledger.json").read_text(encoding="utf-8"))

        entry = closed["entries"][0]
        self.assertEqual(entry["status"], MODULE.NOT_SAFE)
        self.assertEqual(entry["publish_target"], "none")
        self.assertEqual(entry["rule_layer_status"], "not_auto")
        self.assertEqual(closed["closure_resolution_counts"][MODULE.NOT_SAFE], 1)
        self.assertEqual(entry["original_status"], "unresolved")
        self.assertEqual(entry["original_publish_target"], "manual_review")

    def test_recovers_not_safe_bucket_from_preserved_original_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            report_dir = skill_dir / "reports" / "addenda" / "online"
            report_dir.mkdir(parents=True)
            self.write_manifest(skill_dir, "online", report_dir)
            self.write_certification_builder(skill_dir)

            (report_dir / "rules-candidate.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
            (report_dir / "blocking-pages-review-board.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
            (report_dir / "quality-sample-board.json").write_text(json.dumps({"samples": []}), encoding="utf-8")
            (report_dir / "coverage-ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "topic": "报价规则",
                                "status": "excluded_background",
                                "publish_target": "none",
                                "rule_layer_status": "excluded",
                                "original_status": "not_safe_for_auto_answer",
                                "original_publish_target": "none",
                                "original_rule_layer_status": "not_auto",
                                "closure_resolution": "excluded_background",
                                "domain": "cabinet",
                                "source_title": "报价页",
                                "source_page": 3,
                                "summary": "这里涉及报价公式和加价。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="online")
            closed = json.loads((report_dir / "coverage-ledger.json").read_text(encoding="utf-8"))

        entry = closed["entries"][0]
        self.assertEqual(entry["status"], MODULE.NOT_SAFE)
        self.assertEqual(entry["rule_layer_status"], "not_auto")
        self.assertEqual(entry["closure_resolution"], MODULE.NOT_SAFE)


if __name__ == "__main__":
    unittest.main()
