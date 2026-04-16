import importlib.util
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

MODULE_PATH = CORE_ROOT / "review_issues.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REVIEW_ISSUES = load_module("contract_review_review_issues", MODULE_PATH)


class ReviewIssuesTests(unittest.TestCase):
    def test_build_review_analysis_returns_release_recommendation_for_exact_match(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "19800元"},
                    "list_price_total": {"value": "19800元"},
                    "discounted_total": {"value": "19800元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "ready_for_formal_quote",
                "reason": "pricing_precheck_completed",
                "precheck_result": {"ready_for_formal_quote": True},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "19800元",
                "pricing_total_value": 19800.0,
            },
            pricing_compare_payload={
                "status": "exact_match_contract_total",
                "match_band": "exact_match",
                "best_match_target": "contract_total",
                "best_match_diff": "0元",
                "best_match_diff_value": 0.0,
                "pricing_total": "19800元",
                "pricing_total_value": 19800.0,
            },
        )

        self.assertEqual(payload["review_card"]["verdict"], "recommended_release")
        self.assertEqual(payload["review_card"]["priority"], "normal")
        self.assertEqual(payload["issue_count"], 0)
        self.assertEqual(payload["review_card"]["issue_summary"], "当前未发现高风险差异。")

    def test_detects_discount_mismatch_when_quote_is_closer_to_list_price(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "41085元"},
                    "list_price_total": {"value": "43708元"},
                    "discount_rate": {"value": "94折"},
                    "discounted_total": {"value": "41085元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "ready_for_formal_quote",
                "reason": "pricing_precheck_completed",
                "precheck_result": {"ready_for_formal_quote": True},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "43763元",
                "pricing_total_value": 43763.0,
            },
            pricing_compare_payload={
                "status": "close_match_list_price_total",
                "match_band": "close_match",
                "best_match_target": "list_price_total",
                "best_match_diff": "55元",
                "best_match_diff_value": 55.0,
                "pricing_total": "43763元",
                "pricing_total_value": 43763.0,
                "reference_totals": {
                    "contract_total": {"value": "41085元"},
                    "list_price_total": {"value": "43708元"},
                    "discounted_total": {"value": "41085元"},
                },
            },
        )

        issue_codes = {item["issue_code"] for item in payload["issues"]}
        self.assertIn("discount_mismatch", issue_codes)
        discount_issue = next(item for item in payload["issues"] if item["issue_code"] == "discount_mismatch")
        self.assertIn("折扣", "".join(discount_issue["suspected_causes"]))
        self.assertIn("折扣", discount_issue["recommended_check"])
        self.assertEqual(payload["review_card"]["priority"], "p1")

    def test_detects_quantity_mismatch_when_contract_quantity_exceeds_quote_multiplier(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "5000元"}},
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "ready_for_formal_quote",
                "reason": "pricing_precheck_completed",
                "precheck_result": {"ready_for_formal_quote": True},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "2500元",
                "pricing_total_value": 2500.0,
                "prepared_payload": {"total": "2500元"},
            },
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "best_match_target": "contract_total",
                "best_match_diff": "2500元",
                "best_match_diff_value": 2500.0,
                "pricing_total": "2500元",
                "pricing_total_value": 2500.0,
            },
            single_product_line_item={"quantity": "2", "line_total": "5000元", "product_name": "新Y椅"},
        )

        quantity_issue = next(item for item in payload["issues"] if item["issue_code"] == "quantity_mismatch")
        self.assertEqual(quantity_issue["contract_value"], "2")
        self.assertEqual(quantity_issue["pricing_value"], "1")
        self.assertIn("数量", quantity_issue["recommended_check"])

    def test_detects_add_on_mismatch_when_diff_matches_add_on_total(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "20400元"},
                    "list_price_total": {"value": "19800元"},
                    "discounted_total": {"value": "20400元"},
                    "add_on_items": [{"description": "拉手升级", "amount": "600元", "evidence_refs": []}],
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "ready_for_formal_quote",
                "reason": "pricing_precheck_completed",
                "precheck_result": {"ready_for_formal_quote": True},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "19800元",
                "pricing_total_value": 19800.0,
            },
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "best_match_target": "contract_total",
                "best_match_diff": "600元",
                "best_match_diff_value": 600.0,
                "pricing_total": "19800元",
                "pricing_total_value": 19800.0,
            },
        )

        add_on_issue = next(item for item in payload["issues"] if item["issue_code"] == "add_on_mismatch")
        self.assertEqual(add_on_issue["delta_value"], "600元")
        self.assertIn("增项", "".join(add_on_issue["suspected_causes"]))

    def test_detects_calculation_error_when_discount_math_is_inconsistent(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "9200元"},
                    "list_price_total": {"value": "10000元"},
                    "discount_rate": {"value": "9折"},
                    "discounted_total": {"value": "9200元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "category_missing_or_untrusted",
                "precheck_result": None,
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={"status": "skipped", "match_band": "unavailable"},
        )

        calc_issue = next(item for item in payload["issues"] if item["issue_code"] == "calculation_error")
        self.assertIn("折后", calc_issue["recommended_check"])
        self.assertEqual(payload["review_card"]["priority"], "p0")


if __name__ == "__main__":
    unittest.main()
