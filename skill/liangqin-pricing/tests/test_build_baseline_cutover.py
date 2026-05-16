import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_baseline_cutover.py"
SPEC = importlib.util.spec_from_file_location("build_baseline_cutover", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildBaselineCutoverTests(unittest.TestCase):
    def write_manifest(self, skill_dir: Path, layer: str, status: str) -> None:
        manifest_dir = skill_dir / "references" / "addenda" / layer
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps({"layer_id": layer, "status": status}, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_scripts(self, skill_dir: Path) -> None:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        shutil.copy2(
            Path(__file__).resolve().parents[1] / "scripts" / "build_baseline_shadow_verification.py",
            scripts_dir / "build_baseline_shadow_verification.py",
        )

    def write_money_pack(self, skill_dir: Path, layer: str, *, activated_count: int = 20, paused_count: int = 0) -> None:
        report_dir = skill_dir / "reports" / "addenda" / layer
        report_dir.mkdir(parents=True, exist_ok=True)
        rules = []
        for index in range(activated_count + paused_count):
            active = index < activated_count
            runtime_route = "special_adjustment.manual_zero_impact" if index == 0 else "catalog_unit_price"
            expected_amount = 0 if runtime_route == "special_adjustment.manual_zero_impact" else 1000 + index
            rules.append(
                {
                    "landing_id": f"landing-rule-{index:04d}",
                    "runtime_action": "activate_formal_amount_calculation" if active else "keep_paused",
                    "amount_source": {
                        "status": "ready" if active else "not_found",
                        "source_type": "designer_manual_zero_impact_structure_rule" if runtime_route == "special_adjustment.manual_zero_impact" else "price_index_exact_catalog_unit_price",
                        "runtime_route": runtime_route,
                        "expected_amount": expected_amount,
                    },
                    "regression_result": {
                        "status": "passed" if active else "skipped",
                        "actual_amount": expected_amount if active else None,
                    },
                }
            )
        (report_dir / "money-rule-regression-pack.json").write_text(
            json.dumps(
                {
                    "counts": {
                        "money_rule_total": activated_count + paused_count,
                        "golden_amount_ready_count": activated_count,
                        "golden_amount_blocked_count": paused_count,
                        "activated_count": activated_count,
                        "still_paused_count": paused_count,
                    },
                    "rules": rules,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def entry(self, landing_id: str, *, status: str = "active_new_baseline_candidate", conflict: str = "no_old_overlap") -> dict:
        return {
            "landing_id": landing_id,
            "machine_status": status,
            "conflict_status": conflict,
            "landing_action": "接入报价前追问/拦截",
            "suggested_module": "precheck_quote:dimension_or_limit_gate",
            "risk_level": "P1-影响能否下单",
            "quality_flags": [],
            "source": {"title": "真格栅门", "page": 1},
            "topic": "真格栅门 尺寸限制：单扇门宽≤560mm，门高≤2300mm",
            "expected_behavior": "字段不足时必须先转 precheck。",
        }

    def test_cutover_completes_when_new_layer_active_and_old_layer_archived(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            self.write_scripts(skill_dir)
            self.write_manifest(skill_dir, "new", "ACTIVE")
            self.write_manifest(skill_dir, "old", "ARCHIVED")
            self.write_money_pack(skill_dir, "new")
            ledger = skill_dir / "baseline-migration-ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            self.entry("landing-rule-0001"),
                            self.entry("landing-rule-0002", conflict="old_overlap_shadow_required"),
                            self.entry(
                                "landing-rule-0003",
                                status="conflict_paused",
                                conflict="money_rule_paused",
                            ),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_cutover_model(skill_dir=skill_dir, candidate_layer="new", old_layer="old", ledger_path=ledger)

        self.assertEqual(model["cutover_status"], "complete")
        self.assertEqual(model["layer_status"]["candidate"], "ACTIVE")
        self.assertEqual(model["layer_status"]["old"], "ARCHIVED")
        self.assertEqual(model["layer_status"]["old_runtime_truth"], "disabled")
        self.assertEqual(model["counts"]["ready_precheck_rules"], 2)
        self.assertEqual(model["counts"]["runtime_gate_count"], 2)
        self.assertEqual(model["counts"]["money_rule_historical_paused_count"], 1)
        self.assertEqual(model["counts"]["money_rule_paused_count"], 0)
        self.assertEqual(model["counts"]["money_rule_activated_count"], 20)
        self.assertEqual(model["money_cutover_guard"]["status"], "passed")

    def test_cutover_blocks_when_money_regression_is_not_20_of_20(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            self.write_scripts(skill_dir)
            self.write_manifest(skill_dir, "new", "ACTIVE")
            self.write_manifest(skill_dir, "old", "ARCHIVED")
            self.write_money_pack(skill_dir, "new", activated_count=19, paused_count=1)
            ledger = skill_dir / "baseline-migration-ledger.json"
            ledger.write_text(json.dumps({"entries": [self.entry("landing-rule-0001")]}, ensure_ascii=False), encoding="utf-8")

            model = MODULE.build_cutover_model(skill_dir=skill_dir, candidate_layer="new", old_layer="old", ledger_path=ledger)

        self.assertEqual(model["cutover_status"], "in_progress")
        self.assertEqual(model["money_cutover_guard"]["status"], "failed")
        self.assertIn("activated_count_mismatch", model["money_cutover_guard"]["failures"])
        self.assertIn("still_paused_count_not_zero", model["money_cutover_guard"]["failures"])

    def test_cutover_blocks_when_zero_impact_rule_changes_amount(self) -> None:
        money_pack = {
            "counts": {
                "money_rule_total": 20,
                "golden_amount_ready_count": 20,
                "golden_amount_blocked_count": 0,
                "activated_count": 20,
                "still_paused_count": 0,
            },
            "rules": [
                {
                    "landing_id": "landing-rule-zero",
                    "runtime_action": "activate_formal_amount_calculation",
                    "amount_source": {
                        "status": "ready",
                        "runtime_route": "special_adjustment.manual_zero_impact",
                        "source_type": "designer_manual_zero_impact_structure_rule",
                        "expected_amount": 0,
                    },
                    "regression_result": {"status": "passed", "actual_amount": 1},
                },
                *[
                    {
                        "landing_id": f"landing-rule-{index:04d}",
                        "runtime_action": "activate_formal_amount_calculation",
                        "amount_source": {
                            "status": "ready",
                            "runtime_route": "catalog_unit_price",
                            "source_type": "price_index_exact_catalog_unit_price",
                            "expected_amount": 1000 + index,
                        },
                        "regression_result": {"status": "passed", "actual_amount": 1000 + index},
                    }
                    for index in range(19)
                ],
            ],
        }

        guard = MODULE.money_cutover_guard(money_pack)

        self.assertEqual(guard["status"], "failed")
        self.assertIn("zero_impact_amount_changed", guard["failures"])
        self.assertEqual(guard["zero_impact_amount_failures"], ["landing-rule-zero"])


if __name__ == "__main__":
    unittest.main()
