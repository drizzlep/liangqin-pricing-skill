import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_addendum_alignment_board.py"
SPEC = importlib.util.spec_from_file_location("build_addendum_alignment_board", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildAddendumAlignmentBoardTests(unittest.TestCase):
    def write_manifest(self, root: Path, layer_id: str, status: str) -> Path:
        layer_dir = root / "references" / "addenda" / layer_id
        report_dir = root / "reports" / "addenda" / layer_id
        layer_dir.mkdir(parents=True)
        report_dir.mkdir(parents=True)
        manifest = {
            "layer_id": layer_id,
            "layer_name": layer_id,
            "status": status,
            "source_file": "../../../sources/manual.pdf",
            "artifacts": {
                "rules_candidate_file": f"../../../reports/addenda/{layer_id}/rules-candidate.json",
                "rules_index_file": f"../../../reports/addenda/{layer_id}/rules-index.json",
                "runtime_rules_file": f"../../../reports/addenda/{layer_id}/runtime-rules.json",
                "knowledge_layer_file": f"../../../reports/addenda/{layer_id}/knowledge-layer.json",
                "coverage_ledger_file": f"../../../reports/addenda/{layer_id}/coverage-ledger.json",
            },
        }
        (layer_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return report_dir

    def write_payloads(self, report_dir: Path, *, topic: str, status: str, publish_target: str) -> None:
        (report_dir / "rules-candidate.json").write_text("{}", encoding="utf-8")
        (report_dir / "rules-index.json").write_text(json.dumps({"entries": [{"clean_title": topic}]}, ensure_ascii=False), encoding="utf-8")
        (report_dir / "runtime-rules.json").write_text(json.dumps({"rules": [{"title": topic}]}, ensure_ascii=False), encoding="utf-8")
        (report_dir / "knowledge-layer.json").write_text(json.dumps({"entries": []}, ensure_ascii=False), encoding="utf-8")
        (report_dir / "coverage-ledger.json").write_text(
            json.dumps(
                {
                    "entry_count": 1,
                    "entries": [
                        {
                            "topic": topic,
                            "status": status,
                            "publish_target": publish_target,
                            "source_title": topic,
                            "source_page": 3,
                            "risk_level": "low",
                        }
                    ],
                    "status_counts": {status: 1},
                    "publish_target_counts": {publish_target: 1},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_build_alignment_model_classifies_candidate_visual_and_removed_topics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_report = self.write_manifest(root, "old", "ACTIVE")
            candidate_report = self.write_manifest(root, "new", "PAUSED")
            self.write_payloads(base_report, topic="旧版限制", status="runtime_hard_rule", publish_target="runtime")
            self.write_payloads(candidate_report, topic="新版规则", status="runtime_hard_rule", publish_target="runtime")
            visual_dir = candidate_report / "visual-evidence" / "岩板"
            visual_dir.mkdir(parents=True)
            (visual_dir / "visual-assets.json").write_text(
                json.dumps(
                    {
                        "topic": "岩板",
                        "asset_count": 1,
                        "page_image_count": 1,
                        "agent_ready_count": 1,
                        "agent_visual_review_count": 0,
                        "needs_human_review_count": 0,
                        "entries": [{"page_image": "/tmp/page.png"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_alignment_model(root, "old", "new")

        statuses = {topic["topic"]: topic["alignment_status"] for topic in model["topics"]}
        self.assertEqual(statuses["新版规则"], "safe_rule_candidate")
        self.assertEqual(statuses["岩板"], "visual_reference_only")
        self.assertIn("conflict_with_active", model["alignment_status_counts"])
        self.assertEqual(model["candidate_layer"]["status"], "PAUSED")

    def test_render_html_contains_decision_summary(self) -> None:
        model = {
            "base_layer": {"layer_id": "old", "status": "ACTIVE"},
            "candidate_layer": {"layer_id": "new", "status": "PAUSED"},
            "alignment_status_counts": {"safe_rule_candidate": 1, "visual_reference_only": 1, "conflict_with_active": 1},
            "recommended_migration_strategy": "先图文，后规则。",
            "topics": [
                {
                    "topic": "岩板",
                    "alignment_status": "visual_reference_only",
                    "risk_level": "low",
                    "evidence_status": "agent_ready",
                    "reason": "可做图文参考",
                    "recommended_action": "先进入图文层",
                    "candidate_refs": [{"title": "岩板", "page": 5}],
                }
            ],
        }

        rendered = MODULE.render_html(model)

        self.assertIn("新旧版整体对齐看板", rendered)
        self.assertIn("旧版 active", rendered)
        self.assertIn("图文参考主题", rendered)
        self.assertNotIn("Signature=", rendered)


if __name__ == "__main__":
    unittest.main()
