import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_baseline_migration_ledger.py"
SPEC = importlib.util.spec_from_file_location("build_baseline_migration_ledger", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildBaselineMigrationLedgerTests(unittest.TestCase):
    def write_manifest(self, skill_dir: Path, layer: str, runtime_rules: Path | None = None) -> None:
        manifest_dir = skill_dir / "references" / "addenda" / layer
        manifest_dir.mkdir(parents=True)
        artifacts = {}
        if runtime_rules is not None:
            artifacts["runtime_rules_file"] = str(runtime_rules)
        (manifest_dir / "manifest.json").write_text(
            json.dumps({"layer_id": layer, "artifacts": artifacts}, ensure_ascii=False),
            encoding="utf-8",
        )

    def landing_rule(self, **overrides) -> dict:
        rule = {
            "landing_id": "landing-rule-0001",
            "source_data_point_id": "data-point-0001",
            "landing_confidence": "high",
            "quality_flags": [],
            "risk_level": "P0-影响安全/安装",
            "landing_action": MODULE.PRECHECK_ACTION,
            "suggested_module": "precheck_quote:safety_or_install_gate",
            "source": {"title": "悬空电视柜", "page": 1},
            "topic": "悬空电视柜需要固定在承重墙上",
            "required_fields": ["wall_or_install_condition"],
            "expected_behavior": "缺安装条件先追问",
            "test_suggestion": "precheck 回归",
        }
        rule.update(overrides)
        return rule

    def test_builds_machine_statuses_without_human_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            old_runtime = skill_dir / "old-runtime.json"
            old_runtime.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "title": "悬空电视柜固定要求",
                                "detail": "悬空电视柜需要固定在承重墙上。",
                                "trigger_terms": ["悬空电视柜", "承重墙"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.write_manifest(skill_dir, "old", runtime_rules=old_runtime)
            self.write_manifest(skill_dir, "new")
            pack = skill_dir / "agent-rule-landing-pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "rules": [
                            self.landing_rule(),
                            self.landing_rule(
                                landing_id="landing-rule-0002",
                                source_data_point_id="data-point-0002",
                                landing_action=MODULE.QUOTE_CALC_ACTION,
                                suggested_module="pricing_calculation:door_panel_adjustment",
                                risk_level="P0-影响金额",
                                source={"title": "门板补差", "page": 1},
                                topic="门板补差需要加价",
                            ),
                            self.landing_rule(
                                landing_id="landing-rule-0003",
                                source_data_point_id="data-point-0003",
                                landing_confidence="low",
                                quality_flags=["fragmented_topic"],
                                source={"title": "片段", "page": 2},
                                topic="面时,应将这些撑杆拆除。",
                            ),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_ledger_model(skill_dir=skill_dir, candidate_layer="new", old_layer="old", pack_path=pack)

        statuses = {entry["landing_id"]: entry["machine_status"] for entry in model["entries"]}
        self.assertEqual(statuses["landing-rule-0001"], "active_new_baseline_candidate")
        self.assertEqual(statuses["landing-rule-0002"], "conflict_paused")
        self.assertEqual(statuses["landing-rule-0003"], "paused_unverified")
        self.assertEqual(model["ready_for_auto_landing_count"], 1)
        first_entry = model["entries"][0]
        self.assertEqual(first_entry["conflict_status"], "old_overlap_shadow_required")
        self.assertEqual(first_entry["old_rule_match_count"], 1)


if __name__ == "__main__":
    unittest.main()
