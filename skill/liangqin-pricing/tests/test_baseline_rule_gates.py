import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "precheck_quote.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("precheck_quote", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BaselineRuleGateTests(unittest.TestCase):
    def make_args(self, **overrides):
        defaults = dict(
            category="",
            length=None,
            depth=None,
            height=None,
            width=None,
            material=None,
            variant_hint="",
            quote_kind="unknown",
            has_door="unknown",
            door_type="",
            series="",
            shape="",
            bed_form="",
            access_style="",
            lower_bed_type="",
            guardrail_style="",
            guardrail_length="",
            guardrail_height="",
            access_height="",
            stair_width="",
            stair_depth="",
            underbed_cabinet_mode="",
            front_cabinet_length="",
            front_cabinet_height="",
            front_cabinet_depth="",
            front_cabinet_mode="",
            rear_cabinet_length="",
            rear_cabinet_height="",
            rear_cabinet_depth="",
            rear_cabinet_mode="",
            interconnected_rows=False,
            approximate_only=False,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_track_socket_requires_socket_reservation_before_cabinet_quote(self) -> None:
        args = self.make_args(
            category="衣柜",
            length="1.8",
            depth="0.6",
            height="2.2",
            material="北美黑胡桃木",
            shape="轨道插座",
        )

        result = MODULE.precheck_cabinet(args)

        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "wall_or_install_condition")
        self.assertEqual(result["constraint_code"], "baseline.track_socket.power_reservation.required")
        self.assertEqual(result["baseline_rule_gate"]["rule_id"], "landing-rule-0034")
        self.assertIn("预留插座", result["next_question"])

    def test_track_socket_with_machine_verified_reservation_can_continue(self) -> None:
        args = self.make_args(
            category="衣柜",
            length="1.8",
            depth="0.6",
            height="2.2",
            material="北美黑胡桃木",
            shape="轨道插座 已预留插座 不现场接线",
        )

        result = MODULE.precheck_cabinet(args)

        self.assertTrue(result["ready_for_formal_quote"])
        self.assertNotIn("baseline_rule_gate", result)

    def test_wall_mounted_desk_requires_load_bearing_wall_before_quote(self) -> None:
        args = self.make_args(
            category="书桌",
            length="1.2",
            depth="0.55",
            material="北美白橡木",
            shape="挂墙桌",
        )

        result = MODULE.precheck_table(args)

        self.assertFalse(result["ready_for_formal_quote"])
        self.assertEqual(result["next_required_field"], "wall_or_install_condition")
        self.assertEqual(result["constraint_code"], "baseline.wall_mounted_desk.load_bearing_wall.required")
        self.assertIn("承重墙", result["next_question"])

    def test_loads_configured_runtime_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "baseline-runtime-gates.json"
            config_path.write_text(
                json.dumps(
                    {
                        "runtime_gates": [
                            {
                                "rule_id": "landing-rule-test",
                                "source_title": "真格栅门",
                                "source_page": 1,
                                "category_type": "cabinet",
                                "trigger_terms": ["真格栅门"],
                                "required_terms": ["尺寸符合"],
                                "required_quote_fields": ["length"],
                                "missing_field": "dimension_limit_confirmation",
                                "question": "真格栅门需要先确认尺寸是否符合新版手册限制。",
                                "reason": "machine shadow verified",
                                "constraint_code": "baseline.shadow.test.required",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            gates = MODULE.baseline_rule_gates._load_configured_baseline_rule_gates(config_path)

        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].rule_id, "landing-rule-test")
        self.assertEqual(gates[0].trigger_terms, ("真格栅门",))

    def test_configured_shadow_gate_does_not_trigger_on_category_only(self) -> None:
        gate = MODULE.baseline_rule_gates.BaselineRuleGate(
            rule_id="landing-rule-test",
            source_title="钻石柜",
            source_page=1,
            category_type="cabinet",
            trigger_terms=("钻石柜",),
            required_terms=("尺寸符合",),
            required_quote_fields=("length",),
            missing_field="dimension_limit_confirmation",
            question="钻石柜需要先确认尺寸。",
            reason="machine shadow verified",
            constraint_code="baseline.shadow.test.required",
            verification_mode="machine_shadow_config_gate",
        )
        args = self.make_args(category="钻石柜", length="1.2", depth="0.4", height="2.4", material="北美白蜡木")

        self.assertFalse(MODULE.baseline_rule_gates._gate_matches(gate, args, "cabinet"))

        args.shape = "钻石柜特殊尺寸"
        self.assertTrue(MODULE.baseline_rule_gates._gate_matches(gate, args, "cabinet"))


if __name__ == "__main__":
    unittest.main()
