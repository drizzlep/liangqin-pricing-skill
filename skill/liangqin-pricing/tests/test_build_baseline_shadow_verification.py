import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_baseline_shadow_verification.py"
SPEC = importlib.util.spec_from_file_location("build_baseline_shadow_verification", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildBaselineShadowVerificationTests(unittest.TestCase):
    def entry(self, **overrides) -> dict:
        payload = {
            "landing_id": "landing-rule-0001",
            "machine_status": "active_new_baseline_candidate",
            "conflict_status": "old_overlap_shadow_required",
            "landing_action": MODULE.PRECHECK_ACTION,
            "suggested_module": "precheck_quote:dimension_or_limit_gate",
            "risk_level": "P1-影响能否下单",
            "quality_flags": [],
            "source": {"title": "真格栅门", "page": 1},
            "topic": "真格栅门 尺寸限制：单扇门宽≤560mm，门高≤2300mm",
            "expected_behavior": "字段不足时必须先转 precheck。",
            "old_rule_match_count": 2,
            "old_rule_matches": [{"title": "旧真格栅门限制", "match_type": "signal_overlap"}],
        }
        payload.update(overrides)
        return payload

    def test_classifies_old_overlap_precheck_as_config_coverable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            ledger = skill_dir / "baseline-migration-ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            self.entry(),
                            self.entry(
                                landing_id="landing-rule-0002",
                                landing_action=MODULE.QUOTE_CALC_ACTION,
                                suggested_module="pricing_calculation:door_panel_adjustment",
                                risk_level="P0-影响金额",
                            ),
                            self.entry(
                                landing_id="landing-rule-0003",
                                machine_status="paused_unverified",
                                quality_flags=["ocr_low_confidence"],
                            ),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_shadow_model(skill_dir=skill_dir, candidate_layer="new", old_layer="old", ledger_path=ledger)

        self.assertEqual(model["total_shadow_targets"], 3)
        self.assertEqual(model["outcome_counts"]["coverable_by_config_gate"], 1)
        self.assertEqual(model["outcome_counts"]["still_blocked"], 2)
        self.assertEqual(model["runtime_gate_count"], 1)
        gate = model["runtime_gates"][0]
        self.assertEqual(gate["rule_id"], "landing-rule-0001")
        self.assertEqual(gate["missing_field"], "dimension_limit_confirmation")
        self.assertIn("真格栅门", gate["trigger_terms"])


if __name__ == "__main__":
    unittest.main()
