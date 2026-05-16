import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_remaining_rule_resolution.py"
SPEC = importlib.util.spec_from_file_location("build_remaining_rule_resolution", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildRemainingRuleResolutionTests(unittest.TestCase):
    def write_manifest(self, skill_dir: Path, layer: str, report_dir: Path) -> None:
        manifest_dir = skill_dir / "references" / "addenda" / layer
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "layer_id": layer,
                    "artifacts": {"rules_candidate_file": str(report_dir / "rules-candidate.json")},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def entry(self, landing_id: str, *, conflict: str, status: str = "paused_unverified") -> dict:
        return {
            "landing_id": landing_id,
            "source_data_point_id": f"data-point-{landing_id[-4:]}",
            "machine_status": status,
            "conflict_status": conflict,
            "risk_level": "P0-影响金额" if conflict == MODULE.MONEY_CONFLICT else "P1-影响能否下单",
            "landing_action": "接入报价计算" if conflict == MODULE.MONEY_CONFLICT else "接入报价前追问/拦截",
            "suggested_module": "pricing_calculation:door_panel_adjustment" if conflict == MODULE.MONEY_CONFLICT else "precheck_quote:dimension_or_limit_gate",
            "required_fields": ["product_or_category", "length"],
            "source": {"title": "测试规则", "page": 1},
            "topic": "测试规则需要加价 100 元，尺寸≤500mm。",
            "expected_behavior": "完整字段时进入报价明细。",
        }

    def test_builds_resolution_ledgers_without_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            report_dir = skill_dir / "reports" / "addenda" / "new"
            report_dir.mkdir(parents=True)
            self.write_manifest(skill_dir, "new", report_dir)
            (report_dir / "full-document-data-certification.json").write_text(
                json.dumps(
                    {
                        "data_points": [
                            {
                                "id": "data-point-0002",
                                "topic": "质量规则",
                                "extracted_data": "足够稳定的文本层" * 10,
                                "needs_human_review": False,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (report_dir / "blocking-pages-review-board.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
            ledger = report_dir / "baseline-migration-ledger.json"
            ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            self.entry("landing-rule-0001", conflict=MODULE.MONEY_CONFLICT, status="conflict_paused"),
                            self.entry("landing-rule-0002", conflict=MODULE.QUALITY_CONFLICT),
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_resolution_model(skill_dir=skill_dir, candidate_layer="new", old_layer="old", ledger_path=ledger)

        self.assertFalse(model["human_rule_by_rule_review_required"])
        self.assertEqual(model["counts"]["money_total"], 1)
        self.assertEqual(model["counts"]["ocr_quality_total"], 1)
        self.assertEqual(model["counts"]["conflict_total"], 1)
        self.assertEqual(model["money_rule_regression_ledger"][0]["runtime_action"], "keep_paused")
        self.assertEqual(model["ocr_quality_resolution_ledger"][0]["runtime_action"], "requeue_for_machine_landing")
        self.assertEqual(model["conflict_resolution_ledger"][0]["machine_resolution_status"], "blocked_by_money_regression")


if __name__ == "__main__":
    unittest.main()
