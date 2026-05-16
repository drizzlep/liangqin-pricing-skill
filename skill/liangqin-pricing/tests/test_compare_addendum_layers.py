import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "compare_addendum_layers.py"
SPEC = importlib.util.spec_from_file_location("compare_addendum_layers", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CompareAddendumLayersTests(unittest.TestCase):
    def write_layer(self, root: Path, layer_id: str, *, status: str, titles: list[str]) -> None:
        layer_dir = root / "references" / "addenda" / layer_id
        reports_dir = root / "reports" / "addenda" / layer_id
        layer_dir.mkdir(parents=True)
        reports_dir.mkdir(parents=True)
        (reports_dir / "rules-index.json").write_text(
            json.dumps({"entries": [{"clean_title": title} for title in titles]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (reports_dir / "runtime-rules.json").write_text(
            json.dumps({"rules": [{"title": title} for title in titles[:1]]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (reports_dir / "knowledge-layer.json").write_text(
            json.dumps({"entries": [{"topic": title} for title in titles[1:]]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (reports_dir / "coverage-ledger.json").write_text(
            json.dumps(
                {
                    "entry_count": len(titles),
                    "status_counts": {"runtime_hard_rule": 1},
                    "publish_target_counts": {"runtime": 1},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (layer_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "layer_id": layer_id,
                    "layer_name": layer_id,
                    "status": status,
                    "source_file": f"../../../sources/archived/addenda/{layer_id}/manual.pdf",
                    "artifacts": {
                        "rules_index_file": f"../../../reports/addenda/{layer_id}/rules-index.json",
                        "runtime_rules_file": f"../../../reports/addenda/{layer_id}/runtime-rules.json",
                        "knowledge_layer_file": f"../../../reports/addenda/{layer_id}/knowledge-layer.json",
                        "coverage_ledger_file": f"../../../reports/addenda/{layer_id}/coverage-ledger.json",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_build_layer_diff_reports_added_and_removed_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_layer(root, "designer-old", status="ACTIVE", titles=["流云门规则", "床垫限位器"])
            self.write_layer(root, "designer-online", status="PAUSED", titles=["流云门规则", "岩板台面"])

            diff = MODULE.build_layer_diff(root, "designer-old", "designer-online")

        self.assertEqual(diff["base_layer"]["status"], "ACTIVE")
        self.assertEqual(diff["candidate_layer"]["status"], "PAUSED")
        self.assertEqual(diff["rules_index"]["added"], ["岩板台面"])
        self.assertEqual(diff["rules_index"]["removed"], ["床垫限位器"])
        self.assertEqual(diff["coverage_ledger"]["candidate"]["entry_count"], 2)

    def test_render_markdown_includes_counts_and_titles(self) -> None:
        diff = {
            "base_layer": {"layer_id": "old", "status": "ACTIVE", "source_file": "/old.pdf"},
            "candidate_layer": {"layer_id": "new", "status": "PAUSED", "source_file": "/new.pdf"},
            "rules_index": {"base_count": 1, "candidate_count": 2, "common_count": 1, "added": ["新增规则"], "removed": []},
            "runtime_rules": {"base_count": 1, "candidate_count": 1, "common_count": 1, "added": [], "removed": []},
            "knowledge_layer": {"base_count": 0, "candidate_count": 1, "common_count": 0, "added": ["新增知识"], "removed": []},
            "coverage_ledger": {
                "base": {"entry_count": 1, "status_counts": {}, "publish_target_counts": {}},
                "candidate": {"entry_count": 2, "status_counts": {"runtime_hard_rule": 1}, "publish_target_counts": {"runtime": 1}},
            },
        }

        rendered = MODULE.render_markdown(diff)

        self.assertIn("candidate: new / PAUSED / /new.pdf", rendered)
        self.assertIn("- added_count: 1", rendered)
        self.assertIn("- 新增规则", rendered)
        self.assertIn("- 新增知识", rendered)
