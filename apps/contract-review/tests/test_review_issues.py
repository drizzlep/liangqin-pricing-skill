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

    def test_raises_high_priority_ocr_issue_for_child_bed_strict_fields(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "34523元"}},
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "child_bed_primary_drawing_review_required",
                "precheck_result": None,
                "blocked_fields": ["bed_form", "stair_depth"],
                "withheld_source_fields": ["bed_form", "stair_depth"],
                "strict_ocr_blocked_fields": ["bed_form", "stair_depth"],
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "primary_drawing_file_name": "大尺寸图.png",
                },
            },
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={"status": "skipped", "match_band": "unavailable"},
        )

        ocr_issue = next(item for item in payload["issues"] if item["issue_code"] == "ocr_low_confidence")
        self.assertEqual(ocr_issue["severity"], "high")
        self.assertIn("主尺寸图", ocr_issue["title"])
        self.assertIn("主尺寸图", ocr_issue["recommended_check"])
        self.assertIn("大尺寸图.png", "".join(ocr_issue["suspected_causes"]))
        self.assertEqual(payload["review_card"]["priority"], "p1")

    def test_child_bed_ocr_issue_asks_human_to_confirm_likely_bunk_route(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "20560元"}},
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "child_bed_primary_drawing_review_required",
                "precheck_result": None,
                "blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                "withheld_source_fields": ["bed_form", "guardrail_style"],
                "strict_ocr_blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                "route_evidence": {
                    "recommended_route": "modular_child_bed",
                    "candidates": [
                        {
                            "route": "modular_child_bed",
                            "score": 12,
                            "signals": ["上下床", "箱体床"],
                            "evidence_snippets": ["图下注：下床为侧翻箱体床，上下铺结构"],
                            "source_asset_ids": ["asset-child-bed"],
                            "inferred_overrides": {
                                "bed_form": "上下床",
                                "lower_bed_type": "箱体床",
                            },
                        }
                    ],
                },
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "primary_drawing_file_name": "合同页.png",
                    "suggested_pricing_route": "modular_child_bed",
                },
            },
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={"status": "skipped", "match_band": "unavailable"},
        )

        ocr_issue = next(item for item in payload["issues"] if item["issue_code"] == "ocr_low_confidence")
        self.assertIn("上下床", "".join(ocr_issue["suspected_causes"]))
        self.assertIn("请先向人工确认", ocr_issue["recommended_check"])
        self.assertIn("梯柜", ocr_issue["recommended_check"])
        self.assertIn("请先向人工确认", payload["next_question"])

    def test_multi_product_follow_up_question_becomes_optional_when_amount_already_ran(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "138825元"}},
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "child_bed_primary_drawing_review_required",
                "precheck_result": {"next_required_field": "bed_form"},
                "blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                "withheld_source_fields": ["bed_form", "guardrail_style"],
                "strict_ocr_blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                "route_evidence": {
                    "recommended_route": "modular_child_bed",
                    "candidates": [
                        {
                            "route": "modular_child_bed",
                            "score": 12,
                            "signals": ["上下床", "箱体床"],
                            "evidence_snippets": ["图下注：下床为侧翻箱体床，上下铺结构"],
                            "source_asset_ids": ["asset-child-bed"],
                            "inferred_overrides": {
                                "bed_form": "上下床",
                                "lower_bed_type": "箱体床",
                            },
                        }
                    ],
                },
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "primary_drawing_file_name": "合同页.png",
                    "suggested_pricing_route": "modular_child_bed",
                },
            },
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "pricing_total": "125582元",
                "excluded_items": [
                    {
                        "product_name": "其他儿童床",
                        "product_code": "04004",
                        "follow_up_question": "请人工确认：这是不是梯柜上下床儿童床，下层结构是否为箱体床？若是，再补充围栏样式、梯柜参数和上下床尺寸。",
                    }
                ],
            },
        )

        self.assertEqual(payload["next_question"], "")
        self.assertEqual(
            payload["review_card"]["next_actions"][0],
            "儿童床已先按现有信息试算并用于金额核对；如后续还要继续收缩差额，再补充围栏样式、梯柜参数和上下床尺寸。",
        )
        self.assertNotIn("bed_form", payload["next_question"])
        self.assertFalse(
            any("bed_form" in action for action in payload["review_card"]["next_actions"])
        )
        self.assertFalse(
            any("儿童床主尺寸图" in action for action in payload["review_card"]["next_actions"])
        )
        issue_codes = {item["issue_code"] for item in payload["issues"]}
        self.assertNotIn("missing_required_field", issue_codes)
        self.assertNotIn("ocr_low_confidence", issue_codes)
        self.assertNotIn("正式报价还缺", payload["review_card"]["issue_summary"])
        self.assertNotIn("儿童床主尺寸图", payload["review_card"]["issue_summary"])
        self.assertNotIn("当前还有待确认的拆单品项", payload["review_card"]["issue_summary"])

    def test_stair_cabinet_child_bed_mismatch_adds_nonstandard_variant_watch_hint(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "138825元"}},
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "needs_input",
                "reason": "pricing_precheck_completed",
                "precheck_result": {
                    "ready_for_formal_quote": False,
                    "pricing_route": "modular_child_bed",
                    "next_required_field": "stair_depth",
                },
                "precheck_args": {
                    "bed_form": "上下床",
                    "access_style": "梯柜",
                    "stair_width": "520mm",
                },
                "blocked_fields": [],
                "withheld_source_fields": [],
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "suggested_pricing_route": "modular_child_bed",
                },
            },
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "pricing_total": "125582元",
                "best_match_target": "contract_total",
                "best_match_diff": "13243元",
                "best_match_diff_value": 13243.0,
            },
        )

        self.assertTrue(
            any("开放格/无抽屉" in action for action in payload["review_card"]["next_actions"])
        )

    def test_multi_product_stair_cabinet_follow_up_adds_nonstandard_variant_watch_hint(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "138825元"}},
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
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "pricing_total": "125582元",
                "best_match_target": "contract_total",
                "best_match_diff": "13243元",
                "best_match_diff_value": 13243.0,
                "excluded_items": [
                    {
                        "product_name": "其他儿童床",
                        "product_code": "20260391004004",
                        "follow_up_question": "这个梯柜我还需要确认进深，请问大概做多深？",
                    }
                ],
            },
        )

        self.assertEqual(payload["next_question"], "")
        self.assertTrue(
            any("开放格/无抽屉" in action for action in payload["review_card"]["next_actions"])
        )
        self.assertTrue(
            any("儿童床已先按现有信息试算并用于金额核对" in action for action in payload["review_card"]["next_actions"])
        )

    def test_multi_product_stair_cabinet_follow_up_prefers_explicit_open_grid_watch_hint(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {"contract_total": {"value": "138825元"}},
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
            formal_quote_payload={"status": "skipped", "reason": "formal_quote_not_ready"},
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "pricing_total": "125582元",
                "best_match_target": "contract_total",
                "best_match_diff": "13243元",
                "best_match_diff_value": 13243.0,
                "excluded_items": [
                    {
                        "product_name": "其他儿童床",
                        "product_code": "20260391004004",
                        "follow_up_question": "这个梯柜我还需要确认进深，请问大概做多深？",
                        "stair_storage_mode": "open_grid",
                        "stair_storage_evidence_snippets": ["图下注：左侧开放格梯柜，无抽屉，层板可调"],
                    }
                ],
            },
        )

        self.assertEqual(payload["next_question"], "")
        self.assertTrue(
            any("图下注释更像开放格/无抽屉梯柜" in action for action in payload["review_card"]["next_actions"])
        )
        self.assertTrue(
            any("左侧开放格梯柜" in action for action in payload["review_card"]["next_actions"])
        )

    def test_adds_combo_route_hint_for_child_bed_combo_release(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "34523元"},
                    "list_price_total": {"value": "34523元"},
                    "discounted_total": {"value": "34523元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "ready_for_formal_quote",
                "reason": "pricing_precheck_completed",
                "precheck_result": {
                    "ready_for_formal_quote": True,
                    "pricing_route": "modular_child_bed_combo",
                },
                "precheck_args": {
                    "category": "高架床",
                    "bed_form": "高架床",
                    "access_style": "直梯",
                    "width": "1080mm",
                    "length": "2096mm",
                    "front_cabinet_length": "2096mm",
                    "front_cabinet_height": "1600mm",
                    "front_cabinet_depth": "550mm",
                    "rear_cabinet_length": "2096mm",
                    "rear_cabinet_height": "1600mm",
                    "rear_cabinet_depth": "350mm",
                    "interconnected_rows": True,
                },
                "blocked_fields": [],
                "withheld_source_fields": [],
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "suggested_pricing_route": "modular_child_bed_combo",
                    "combo_candidate_signals": ["双面柜", "活动层板", "朝外柜"],
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "34524元",
                "pricing_total_value": 34524.0,
            },
            pricing_compare_payload={
                "status": "exact_match_contract_total",
                "match_band": "exact_match",
                "best_match_target": "contract_total",
                "best_match_diff": "1元",
                "best_match_diff_value": 1.0,
                "pricing_total": "34524元",
                "pricing_total_value": 34524.0,
            },
        )

        self.assertEqual(payload["review_card"]["verdict"], "recommended_release")
        self.assertEqual(payload["issue_count"], 0)
        self.assertTrue(
            any("床体+床下组合柜路线" in action for action in payload["review_card"]["next_actions"])
        )
        self.assertTrue(any("双面柜" in action for action in payload["review_card"]["next_actions"]))

    def test_approximate_quote_can_suppress_follow_up_when_amount_matches(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "32820元"},
                    "list_price_total": {"value": "32820元"},
                    "discounted_total": {"value": "32820元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "needs_input",
                "reason": "pricing_precheck_completed",
                "precheck_result": {
                    "ready_for_formal_quote": False,
                    "pricing_route": "modular_child_bed_combo",
                    "next_required_field": "guardrail_length",
                },
                "blocked_fields": [],
                "withheld_source_fields": [],
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "suggested_pricing_route": "modular_child_bed_combo",
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "approximate_quote_completed",
                "pricing_total": "32820元",
                "pricing_total_value": 32820.0,
                "assumed_defaults": [
                    {"field": "guardrail_length", "value": "2096mm"},
                    {"field": "guardrail_height", "value": "320mm"},
                ],
            },
            pricing_compare_payload={
                "status": "exact_match_contract_total",
                "match_band": "exact_match",
                "best_match_target": "contract_total",
                "best_match_diff": "0元",
                "best_match_diff_value": 0.0,
                "pricing_total": "32820元",
                "pricing_total_value": 32820.0,
            },
        )

        issue_codes = {item["issue_code"] for item in payload["issues"]}
        self.assertNotIn("missing_required_field", issue_codes)
        self.assertEqual(payload["review_card"]["verdict"], "pass_with_watch")
        self.assertEqual(payload["next_question"], "")
        self.assertTrue(
            any("轻量试算" in action for action in payload["review_card"]["next_actions"])
        )

    def test_approximate_quote_surfaces_route_evidence_hint(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "29184元"},
                    "list_price_total": {"value": "29184元"},
                    "discounted_total": {"value": "29184元"},
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
                "route_evidence": {
                    "recommended_route": "cabinet",
                    "candidates": [
                        {
                            "route": "cabinet",
                            "score": 9,
                            "signals": ["开放书柜"],
                            "evidence_snippets": ["图下注：开放书柜，层板可调"],
                            "source_asset_ids": ["asset-visual"],
                            "inferred_overrides": {"category": "书柜", "has_door": "no"},
                        }
                    ],
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "approximate_quote_completed",
                "pricing_total": "29184元",
                "pricing_total_value": 29184.0,
                "assumed_defaults": [
                    {"field": "category", "value": "书柜"},
                    {"field": "has_door", "value": "no"},
                ],
            },
            pricing_compare_payload={
                "status": "exact_match_contract_total",
                "match_band": "exact_match",
                "best_match_target": "contract_total",
                "best_match_diff": "0元",
                "best_match_diff_value": 0.0,
                "pricing_total": "29184元",
                "pricing_total_value": 29184.0,
            },
        )

        self.assertTrue(
            any("图下说明" in action and "开放书柜" in action for action in payload["review_card"]["next_actions"])
        )

    def test_quote_conflict_uses_cabinet_route_evidence_for_open_cabinet_diagnosis(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "29184元"},
                    "list_price_total": {"value": "29184元"},
                    "discounted_total": {"value": "29184元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "ready_for_formal_quote",
                "reason": "pricing_precheck_completed",
                "precheck_result": {
                    "ready_for_formal_quote": True,
                    "pricing_route": "cabinet_projection_area",
                },
                "blocked_fields": [],
                "withheld_source_fields": [],
                "route_evidence": {
                    "recommended_route": "cabinet",
                    "candidates": [
                        {
                            "route": "cabinet",
                            "score": 10,
                            "signals": ["开放书柜"],
                            "evidence_snippets": ["图下注：开放书柜，层板可调"],
                            "source_asset_ids": ["asset-visual"],
                            "inferred_overrides": {"category": "书柜", "has_door": "no"},
                        }
                    ],
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "33600元",
                "pricing_total_value": 33600.0,
            },
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "best_match_target": "contract_total",
                "best_match_diff": "4416元",
                "best_match_diff_value": 4416.0,
                "pricing_total": "33600元",
                "pricing_total_value": 33600.0,
            },
        )

        quote_issue = next(item for item in payload["issues"] if item["issue_code"] == "quote_conflict")
        self.assertTrue(any("开放书柜" in cause and "带门路线" in cause for cause in quote_issue["suspected_causes"]))
        self.assertIn("开放柜/无门路线", quote_issue["recommended_check"])

    def test_quote_conflict_uses_child_bed_combo_route_evidence_for_route_diagnosis(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "32820元"},
                    "list_price_total": {"value": "32820元"},
                    "discounted_total": {"value": "32820元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "child_bed_primary_drawing_review_required",
                "precheck_result": None,
                "blocked_fields": [],
                "withheld_source_fields": [],
                "route_evidence": {
                    "recommended_route": "modular_child_bed_combo",
                    "candidates": [
                        {
                            "route": "modular_child_bed_combo",
                            "score": 16,
                            "signals": ["双面柜", "活动层板", "柜体互通"],
                            "evidence_snippets": ["图下注：床下柜子为双面柜，前后双排互通"],
                            "source_asset_ids": ["asset-bed-layout"],
                            "inferred_overrides": {},
                        }
                    ],
                },
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "suggested_pricing_route": "modular_child_bed_combo",
                    "combo_candidate_signals": ["双面柜", "活动层板", "柜体互通"],
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_total": "37180元",
                "pricing_total_value": 37180.0,
            },
            pricing_compare_payload={
                "status": "mismatch_contract_total",
                "match_band": "mismatch",
                "best_match_target": "contract_total",
                "best_match_diff": "4360元",
                "best_match_diff_value": 4360.0,
                "pricing_total": "37180元",
                "pricing_total_value": 37180.0,
            },
        )

        quote_issue = next(item for item in payload["issues"] if item["issue_code"] == "quote_conflict")
        self.assertTrue(
            any("床体+床下组合柜路线" in cause and "组合识别" in cause for cause in quote_issue["suspected_causes"])
        )
        self.assertIn("床体+床下组合柜路线", quote_issue["recommended_check"])

    def test_approximate_quote_adds_route_uncertainty_hint_when_candidates_are_close(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "21000元"},
                    "list_price_total": {"value": "21000元"},
                    "discounted_total": {"value": "21000元"},
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
                "route_evidence": {
                    "recommended_route": "cabinet",
                    "candidates": [
                        {
                            "route": "cabinet",
                            "score": 9,
                            "signals": ["开放书柜"],
                            "evidence_snippets": ["图下注：开放书柜，层板可调"],
                            "source_asset_ids": ["asset-visual"],
                            "inferred_overrides": {"category": "书柜", "has_door": "no"},
                        }
                    ],
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "approximate_quote_completed",
                "pricing_total": "21020元",
                "pricing_total_value": 21020.0,
                "route_uncertainty": True,
                "selected_vs_runner_up_diff": "40元",
                "selected_vs_runner_up_diff_value": 40.0,
                "selected_route_candidate": {
                    "route": "cabinet",
                    "signals": ["开放书柜"],
                    "evidence_snippets": ["图下注：开放书柜，层板可调"],
                    "inferred_overrides": {"category": "书柜", "has_door": "no"},
                    "match_diff": "20元",
                    "match_diff_value": 20.0,
                },
                "runner_up_route_candidate": {
                    "route": "cabinet",
                    "signals": ["带门书柜"],
                    "evidence_snippets": ["图下注：封闭书柜"],
                    "inferred_overrides": {"category": "书柜", "has_door": "yes"},
                    "match_diff": "60元",
                    "match_diff_value": 60.0,
                },
                "route_candidates": [
                    {
                        "route": "cabinet",
                        "signals": ["开放书柜"],
                        "evidence_snippets": ["图下注：开放书柜，层板可调"],
                        "inferred_overrides": {"category": "书柜", "has_door": "no"},
                        "match_diff": "20元",
                        "match_diff_value": 20.0,
                    },
                    {
                        "route": "cabinet",
                        "signals": ["带门书柜"],
                        "evidence_snippets": ["图下注：封闭书柜"],
                        "inferred_overrides": {"category": "书柜", "has_door": "yes"},
                        "match_diff": "60元",
                        "match_diff_value": 60.0,
                    },
                ],
            },
            pricing_compare_payload={
                "status": "close_match_contract_total",
                "match_band": "close_match",
                "best_match_target": "contract_total",
                "best_match_diff": "20元",
                "best_match_diff_value": 20.0,
                "pricing_total": "21020元",
                "pricing_total_value": 21020.0,
            },
        )

        self.assertEqual(payload["review_card"]["verdict"], "pass_with_watch")
        self.assertTrue(
            any("解释不唯一" in action and "次优路线也接近" in action for action in payload["review_card"]["next_actions"])
        )

    def test_quote_conflict_highlights_dominant_multi_product_item_for_aggregate_mismatch(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "49700元"},
                    "list_price_total": {"value": "52319元"},
                    "discounted_total": {"value": "49700元"},
                    "discount_rate": {"value": "95折"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "needs_input",
                "reason": "pricing_precheck_completed",
                "precheck_result": {"next_required_field": "series"},
                "blocked_fields": [],
                "withheld_source_fields": [],
                "route_evidence": {
                    "recommended_route": "cabinet",
                    "candidates": [
                        {
                            "route": "cabinet",
                            "score": 8,
                            "signals": ["其他书柜"],
                            "evidence_snippets": ["图纸备注命中：36140 其他书柜 20260333003004 北美樱桃。"],
                            "inferred_overrides": {"category": "书柜"},
                        }
                    ],
                },
            },
            formal_quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_route": "multi_product_aggregate",
                "pricing_total": "54109元",
                "pricing_total_value": 54109.0,
            },
            pricing_compare_payload={
                "status": "mismatch_list_price_total",
                "reason": "multi_product_aggregate_pricing_total_compared",
                "match_band": "mismatch",
                "best_match_target": "list_price_total",
                "best_match_diff": "1790元",
                "best_match_diff_value": 1790.0,
                "pricing_total": "54109元",
                "pricing_total_value": 54109.0,
                "aggregation_scope": "multi_product_split_sum",
                "included_items": [
                    {"product_name": "经典箱体床", "product_code": "20260333003002", "line_total": "8800元", "pricing_total": "8528元"},
                    {
                        "product_name": "其他衣柜",
                        "product_code": "20260333003003",
                        "line_total": "36140元",
                        "pricing_total": "37812元",
                        "pricing_route": "cabinet_projection_area_fallback",
                        "fallback_strategy": "generic_cabinet_projection_profile",
                        "fallback_detail": {
                            "profile_key": "衣柜",
                            "matched_product_code": "YG-22",
                            "candidate_quote_diff": "1672元",
                            "candidate_quote_diff_value": 1672.0,
                        },
                    },
                    {"product_name": "其他书柜", "product_code": "20260333003004", "line_total": "7379元", "pricing_total": "7769元"},
                ],
                "excluded_items": [],
            },
        )

        quote_issue = next(item for item in payload["issues"] if item["issue_code"] == "quote_conflict")
        self.assertTrue(any("其他衣柜" in cause and "1672元" in cause for cause in quote_issue["suspected_causes"]))
        self.assertFalse(any("书柜路线" in cause for cause in quote_issue["suspected_causes"]))
        self.assertTrue(any("通用衣柜投影面积" in cause for cause in quote_issue["suspected_causes"]))
        self.assertIn("其他衣柜", quote_issue["recommended_check"])
        self.assertIn("投影面积", quote_issue["recommended_check"])

    def test_complete_multi_product_list_price_match_uses_watch_mode_without_child_bed_blockers(self) -> None:
        payload = REVIEW_ISSUES.build_review_analysis(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "146132元"},
                    "list_price_total": {"value": "146150元"},
                    "discount_rate": {"value": "95折"},
                    "discounted_total": {"value": "138842元"},
                },
                "field_conflicts": [],
                "special_notes": [],
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "child_bed_primary_drawing_review_required",
                "precheck_result": {"next_required_field": "bed_form"},
                "blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                "withheld_source_fields": ["bed_form", "guardrail_style"],
                "strict_ocr_blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                "route_evidence": {
                    "recommended_route": "modular_child_bed",
                    "candidates": [
                        {
                            "route": "modular_child_bed",
                            "score": 12,
                            "signals": ["上下床", "梯柜"],
                            "evidence_snippets": ["图下注：上铺护栏+左侧梯柜结构"],
                            "source_asset_ids": ["asset-child-bed"],
                            "inferred_overrides": {
                                "bed_form": "上下床",
                                "access_style": "梯柜",
                            },
                        }
                    ],
                },
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "primary_drawing_file_name": "儿童床主图.png",
                    "suggested_pricing_route": "modular_child_bed",
                },
            },
            formal_quote_payload={
                "status": "skipped",
                "reason": "formal_quote_not_ready",
                "pricing_total": "",
                "pricing_total_value": None,
            },
            pricing_compare_payload={
                "status": "close_match_list_price_total",
                "reason": "multi_product_aggregate_pricing_total_compared",
                "match_band": "close_match",
                "best_match_target": "list_price_total",
                "best_match_diff": "9元",
                "best_match_diff_value": 9.0,
                "pricing_total": "146141元",
                "pricing_total_value": 146141.0,
                "aggregation_scope": "multi_product_split_sum",
                "aggregation_complete": True,
                "compared_item_count": 6,
                "excluded_item_count": 0,
                "included_items": [
                    {"product_code": "04001", "pricing_total": "10000元"},
                    {"product_code": "04002", "pricing_total": "20000元"},
                    {"product_code": "04003", "pricing_total": "30000元"},
                    {"product_code": "04004", "pricing_total": "20559元"},
                    {"product_code": "04005", "pricing_total": "40000元"},
                    {"product_code": "04006", "pricing_total": "25582元"},
                ],
                "excluded_items": [],
                "reference_totals": {
                    "contract_total": {"value": "146132元"},
                    "list_price_total": {"value": "146150元"},
                    "discounted_total": {"value": "138842元"},
                },
            },
        )

        issue_codes = {item["issue_code"] for item in payload["issues"]}
        self.assertEqual(payload["review_card"]["verdict"], "pass_with_watch")
        self.assertNotIn(payload["review_card"]["priority"], {"p0", "p1"})
        self.assertIn("discount_mismatch", issue_codes)
        self.assertNotIn("missing_required_field", issue_codes)
        self.assertNotIn("ocr_low_confidence", issue_codes)
        self.assertNotIn("quote_conflict", issue_codes)
        self.assertEqual(payload["next_question"], "")
        self.assertIn("折前价", payload["review_card"]["issue_summary"])
        self.assertFalse(any("bed_form" in action for action in payload["review_card"]["next_actions"]))
        self.assertFalse(any("儿童床主尺寸图" in action for action in payload["review_card"]["next_actions"]))
        self.assertTrue(any("折扣口径" in action for action in payload["review_card"]["next_actions"]))


if __name__ == "__main__":
    unittest.main()
