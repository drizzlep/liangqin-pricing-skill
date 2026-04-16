import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

JOB_MODELS_PATH = CORE_ROOT / "job_models.py"
MODULE_PATH = CORE_ROOT / "batch_runtime.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


JOB_MODELS = load_module("contract_review_job_models_for_batch_insights", JOB_MODELS_PATH)
BATCH_RUNTIME = load_module("contract_review_batch_runtime_for_insights", MODULE_PATH)


class BatchRuntimeInsightsTests(unittest.TestCase):
    def test_write_batch_summary_emits_actionable_priority_and_template_stats(self) -> None:
        batch_plan = JOB_MODELS.BatchPlan(
            batch_id="batch-insights",
            batch_dir=Path("/tmp/batch-insights"),
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            jobs=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            job_dir = runtime_root / "jobs" / "batch-insights-001"
            (job_dir / "output").mkdir(parents=True)
            (job_dir / "output" / "pricing-precheck.json").write_text(
                json.dumps({"status": "ready_for_formal_quote"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (job_dir / "output" / "formal-quote.json").write_text(
                json.dumps({"status": "completed", "reason": "formal_quote_completed"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (job_dir / "output" / "replay.json").write_text(
                json.dumps({"status": "completed", "reason": "ok"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (job_dir / "output" / "template-profile.json").write_text(
                json.dumps(
                    {
                        "template_id": "tpl-001",
                        "template_fingerprint": "fp-001",
                        "trust_score": 0.82,
                        "feedback_count": 3,
                        "observed_job_count": 5,
                        "human_decision_breakdown": {"confirmed": 2, "false_positive": 1},
                        "field_aliases": {
                            "width": {"labels": ["宽度"], "confirmed_values": ["1500mm"]},
                            "product_category": {"labels": ["产品名称"], "confirmed_values": ["书柜"]},
                        },
                        "observed_issue_breakdown": {"discount_mismatch": 3, "missing_required_field": 2},
                        "feedback_issue_breakdown": {
                            "discount_mismatch": {"feedback_count": 2, "confirmed_count": 2},
                            "missing_required_field": {"feedback_count": 1, "false_positive_count": 1},
                        },
                        "common_conflict_rules": [{"issue_code": "discount_mismatch", "count": 2}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            BATCH_RUNTIME.write_batch_summary(
                batch_plan,
                batch_results=[
                    {
                        "job_id": "batch-insights-001",
                        "group_key": "case-001",
                        "status": "manual_review_required",
                        "review_priority": "p1",
                        "review_priority_score": 1,
                        "review_priority_reason": "discount_mismatch:manual_review_required",
                        "finding_count": 1,
                        "blocking_finding_count": 0,
                        "primary_contract_count": 1,
                        "automation_state": "ingest_scaffold_ready",
                        "conflict_count": 0,
                        "conflict_fields": [],
                        "manual_review_reasons": ["discount_mismatch:manual_review_required"],
                        "risk_flags": ["pricing_fields_still_missing"],
                        "contract_total": "41085元",
                        "list_price_total": "43708元",
                        "discounted_total": "41085元",
                        "discount_rate": "94折",
                        "pricing_total": "43763元",
                        "pricing_compare_status": "close_match_list_price_total",
                        "pricing_compare_match_band": "close_match",
                        "pricing_compare_best_match_target": "list_price_total",
                        "pricing_compare_best_match_diff": "55元",
                        "pricing_route": "cabinet_projection_area",
                        "review_path": str(job_dir / "output" / "review.md"),
                        "job_dir": str(job_dir),
                        "actionable_priority": "ready_now",
                        "actionable_priority_score": 0,
                        "issue_codes": ["discount_mismatch"],
                        "template_id": "tpl-001",
                        "template_fingerprint": "fp-001",
                    }
                ],
                runtime_root=runtime_root,
            )

            dashboard = json.loads(
                (runtime_root / "batches" / "batch-insights" / "batch-dashboard.json").read_text(encoding="utf-8")
            )
            diagnosis = json.loads(
                (runtime_root / "batches" / "batch-insights" / "pricing-compare-diagnosis.json").read_text(encoding="utf-8")
            )
            workbench_html = (runtime_root / "batches" / "batch-insights" / "workbench.html").read_text(encoding="utf-8")

        self.assertEqual(dashboard["actionable_priority_breakdown"]["ready_now"], 1)
        self.assertEqual(dashboard["root_cause_breakdown"]["discount_mismatch"], 1)
        self.assertEqual(dashboard["template_breakdown"]["tpl-001"], 1)
        self.assertEqual(dashboard["template_learning_overview"]["templates_with_feedback"], 1)
        self.assertEqual(dashboard["template_learning_overview"]["templates_with_false_positive_feedback"], 1)
        self.assertEqual(dashboard["template_learning_top_templates"][0]["learned_field_count"], 2)
        self.assertEqual(dashboard["template_learning_top_templates"][0]["recommended_action"], "优先补字段锚点")
        self.assertIn("缺字段误报", dashboard["template_learning_top_templates"][0]["recommended_reason"])
        self.assertIn("标记已核对", dashboard["template_learning_top_templates"][0]["suggested_feedback_command"])
        self.assertIn("结论=误报", dashboard["template_learning_top_templates"][0]["suggested_feedback_command"])
        self.assertIn("字段=width:1500mm,product_category:书柜", dashboard["template_learning_top_templates"][0]["suggested_feedback_command"])
        self.assertEqual(dashboard["template_learning_top_templates"][0]["quick_actions"][0]["action_type"], "copy_command")
        self.assertEqual(dashboard["template_learning_top_templates"][0]["quick_actions"][1]["action_type"], "filter_issue")
        self.assertIn("discount_mismatch", dashboard["template_learning_top_templates"][0]["quick_actions"][1]["command"])
        self.assertEqual(
            dashboard["template_learning_top_templates"][0]["missing_required_field_false_positive_count"],
            1,
        )
        self.assertEqual(diagnosis["items"][0]["template_id"], "tpl-001")
        self.assertEqual(diagnosis["items"][0]["issue_codes"], ["discount_mismatch"])
        self.assertIn("合同审核工作台", workbench_html)
        self.assertIn("模板学习成效", workbench_html)
        self.assertIn("建议动作", workbench_html)
        self.assertIn("优先补字段锚点", workbench_html)
        self.assertIn("建议反馈命令", workbench_html)
        self.assertIn("快捷操作", workbench_html)
        self.assertIn("复制反馈命令", workbench_html)
        self.assertIn("结论=误报", workbench_html)
        self.assertIn("discount_mismatch", workbench_html)
        self.assertIn("tpl-001", workbench_html)


if __name__ == "__main__":
    unittest.main()
