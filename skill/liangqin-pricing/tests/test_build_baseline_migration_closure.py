import importlib.util
import json
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_baseline_migration_closure.py"
SPEC = importlib.util.spec_from_file_location("build_baseline_migration_closure", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildBaselineMigrationClosureTests(unittest.TestCase):
    def write_runtime_gates(self, skill_dir: Path) -> None:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "baseline_rule_gates.py").write_text(
            textwrap.dedent(
                """
                from dataclasses import dataclass

                @dataclass(frozen=True)
                class Gate:
                    rule_id: str

                BASELINE_RULE_GATES = (Gate("landing-rule-0001"), Gate("landing-rule-0002"))
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def write_manifest(self, skill_dir: Path, layer: str) -> Path:
        report_dir = skill_dir / "reports" / "addenda" / layer
        report_dir.mkdir(parents=True)
        manifest_dir = skill_dir / "references" / "addenda" / layer
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "layer_id": layer,
                    "artifacts": {
                        "rules_candidate_file": str(report_dir / "rules-candidate.json"),
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return report_dir

    def entry(self, landing_id: str, *, status: str, conflict: str, module: str = "precheck_quote:safety_or_install_gate") -> dict:
        return {
            "landing_id": landing_id,
            "machine_status": status,
            "baseline_decision": "new_rule_addition",
            "conflict_status": conflict,
            "risk_level": "P0-影响安全/安装",
            "landing_action": "接入报价前追问/拦截",
            "suggested_module": module,
            "source": {"title": "测试规则", "page": 1},
            "topic": "测试规则",
            "machine_reason": "机器判断",
            "old_rule_match_count": 0,
        }

    def test_builds_machine_closure_without_human_rule_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            self.write_runtime_gates(skill_dir)
            report_dir = self.write_manifest(skill_dir, "new")
            ledger = report_dir / "baseline-migration-ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            self.entry("landing-rule-0001", status="active_new_baseline_candidate", conflict="no_old_overlap"),
                            self.entry("landing-rule-0002", status="active_new_baseline_candidate", conflict="old_overlap_shadow_required"),
                            self.entry(
                                "landing-rule-0003",
                                status="conflict_paused",
                                conflict="money_rule_paused",
                                module="pricing_calculation:door_panel_adjustment",
                            ),
                            self.entry("landing-rule-0004", status="paused_unverified", conflict="paused_quality_or_ocr"),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_closure_model(skill_dir=skill_dir, candidate_layer="new", old_layer="old", ledger_path=ledger)

        self.assertEqual(model["contract_status"]["t_plus_1"], "complete")
        self.assertEqual(model["contract_status"]["t_plus_24"], "complete")
        self.assertFalse(model["contract_status"]["human_rule_by_rule_review_required"])
        self.assertEqual(model["counts"]["runtime_precheck_gate_count"], 2)
        self.assertEqual(model["counts"]["precheck_runtime_gap_count"], 0)
        self.assertEqual(model["counts"]["shadow_required_count"], 1)
        self.assertEqual(model["counts"]["shadow_runtime_gate_count"], 1)
        self.assertEqual(model["counts"]["money_rule_paused_count"], 1)
        self.assertEqual(model["counts"]["quality_or_ocr_paused_count"], 1)
        self.assertTrue(model["counts"]["money_rules_are_parked"])
        self.assertTrue(model["counts"]["quality_rules_are_parked"])
        self.assertTrue(model["counts"]["shadow_rules_are_covered"])


if __name__ == "__main__":
    unittest.main()
