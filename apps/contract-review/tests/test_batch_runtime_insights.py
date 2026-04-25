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
    def test_write_batch_summary_emits_reviewer_card_summary(self) -> None:
        batch_plan = JOB_MODELS.BatchPlan(
            batch_id="batch-reviewer-cards",
            batch_dir=Path("/tmp/batch-reviewer-cards"),
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            jobs=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            job_auto = runtime_root / "jobs" / "batch-reviewer-cards-001"
            job_manual = runtime_root / "jobs" / "batch-reviewer-cards-002"
            (job_auto / "output").mkdir(parents=True)
            (job_manual / "output").mkdir(parents=True)
            (job_auto / "output" / "reviewer-card.json").write_text(
                json.dumps(
                    {
                        "decision": "auto_pass",
                        "decision_label": "可自动通过",
                        "primary_reason": "金额差异在可自动通过范围内（差额4元）。",
                        "amounts": {
                            "contract_amount": "19800元",
                            "pricing_amount": "19796元",
                            "difference": "4元",
                            "comparison_basis_label": "合同总金额",
                        },
                        "line_items": [
                            {
                                "product_name": "书柜",
                                "review_status": "compared",
                                "review_status_label": "已核对",
                            }
                        ],
                        "next_actions": ["可低风险通过，建议保留本次金额核对记录。"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (job_manual / "output" / "reviewer-card.json").write_text(
                json.dumps(
                    {
                        "decision": "manual_required",
                        "decision_label": "必须人工确认",
                        "primary_reason": "存在1个品项未入账，不能判断整单金额是否正确。",
                        "amounts": {
                            "contract_amount": "41085元",
                            "pricing_amount": "26325元",
                            "difference": "14760元",
                            "comparison_basis_label": "合同总金额",
                        },
                        "line_items": [
                            {
                                "product_name": "衣柜",
                                "review_status": "compared",
                                "review_status_label": "已核对",
                            },
                            {
                                "product_name": "衣柜组合",
                                "review_status": "manual_required",
                                "review_status_label": "必须人工确认",
                                "manual_hint": "该品项未形成报价，请人工确认后再判断整单金额。",
                            },
                        ],
                        "next_actions": ["优先确认未入账品项：衣柜组合。"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary_payload = BATCH_RUNTIME.write_batch_summary(
                batch_plan,
                batch_results=[
                    {
                        "job_id": "batch-reviewer-cards-001",
                        "group_key": "case-auto",
                        "status": "compared",
                        "review_priority": "normal",
                        "review_priority_score": 3,
                        "review_priority_reason": "",
                        "finding_count": 0,
                        "blocking_finding_count": 0,
                        "primary_contract_count": 1,
                        "automation_state": "review_completed",
                        "conflict_count": 0,
                        "conflict_fields": [],
                        "manual_review_reasons": [],
                        "risk_flags": [],
                        "contract_total": "19800元",
                        "list_price_total": "",
                        "discounted_total": "",
                        "discount_rate": "",
                        "pricing_total": "19796元",
                        "pricing_compare_status": "close_match_contract_total",
                        "pricing_compare_match_band": "close_match",
                        "pricing_compare_best_match_target": "contract_total",
                        "pricing_compare_best_match_diff": "4元",
                        "pricing_route": "cabinet_projection_area",
                        "review_path": str(job_auto / "output" / "review.md"),
                        "job_dir": str(job_auto),
                        "actionable_priority": "auto_pass_candidate",
                        "actionable_priority_score": 4,
                        "issue_codes": [],
                        "template_id": "",
                        "template_fingerprint": "",
                    },
                    {
                        "job_id": "batch-reviewer-cards-002",
                        "group_key": "case-manual",
                        "status": "manual_review_required",
                        "review_priority": "p1",
                        "review_priority_score": 1,
                        "review_priority_reason": "pricing_total:manual_required",
                        "finding_count": 1,
                        "blocking_finding_count": 0,
                        "primary_contract_count": 1,
                        "automation_state": "review_completed",
                        "conflict_count": 0,
                        "conflict_fields": [],
                        "manual_review_reasons": ["pricing_total:manual_required"],
                        "risk_flags": [],
                        "contract_total": "41085元",
                        "list_price_total": "",
                        "discounted_total": "",
                        "discount_rate": "",
                        "pricing_total": "26325元",
                        "pricing_compare_status": "mismatch_contract_total",
                        "pricing_compare_match_band": "mismatch",
                        "pricing_compare_best_match_target": "contract_total",
                        "pricing_compare_best_match_diff": "14760元",
                        "pricing_route": "multi_product_aggregate",
                        "review_path": str(job_manual / "output" / "review.md"),
                        "job_dir": str(job_manual),
                        "actionable_priority": "need_user_input",
                        "actionable_priority_score": 1,
                        "issue_codes": ["pricing_total_missing"],
                        "template_id": "",
                        "template_fingerprint": "",
                    },
                ],
                runtime_root=runtime_root,
            )

            output_dir = runtime_root / "batches" / "batch-reviewer-cards"
            persisted_batch_summary = json.loads((output_dir / "batch-summary.json").read_text(encoding="utf-8"))
            reviewer_summary = json.loads((output_dir / "reviewer-card-summary.json").read_text(encoding="utf-8"))
            reviewer_markdown = (output_dir / "reviewer-card-summary.md").read_text(encoding="utf-8")
            manual_queue = json.loads((output_dir / "manual-review-queue.json").read_text(encoding="utf-8"))
            dashboard_payload = json.loads((output_dir / "batch-dashboard.json").read_text(encoding="utf-8"))

        self.assertEqual(summary_payload["reviewer_card_summary"]["decision_breakdown"]["auto_pass"], 1)
        self.assertEqual(summary_payload["reviewer_card_summary"]["decision_breakdown"]["manual_required"], 1)
        self.assertEqual(persisted_batch_summary["reviewer_card_summary"]["decision_breakdown"]["auto_pass"], 1)
        self.assertEqual(reviewer_summary["decision_breakdown"]["review_recommended"], 0)
        self.assertEqual(reviewer_summary["items"][0]["decision"], "manual_required")
        self.assertEqual(reviewer_summary["items"][0]["manual_required_item_count"], 1)
        self.assertEqual(reviewer_summary["items"][1]["decision"], "auto_pass")
        self.assertIn("审核员批量决策汇总", reviewer_markdown)
        self.assertIn("case-manual", reviewer_markdown)
        self.assertIn("必须人工确认", reviewer_markdown)
        self.assertIn("优先确认未入账品项：衣柜组合。", reviewer_markdown)
        self.assertEqual(manual_queue["queue_count"], 1)
        self.assertEqual(manual_queue["items"][0]["job_id"], "batch-reviewer-cards-002")
        self.assertEqual(dashboard_payload["manual_queue_count"], 1)
        self.assertEqual(dashboard_payload["top_priority_job_ids"], ["batch-reviewer-cards-002"])

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
