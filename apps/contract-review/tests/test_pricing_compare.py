import importlib.util
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

MODULE_PATH = CORE_ROOT / "pricing_compare.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PRICING_COMPARE = load_module("contract_review_pricing_compare", MODULE_PATH)


class PricingCompareTests(unittest.TestCase):
    def test_prefers_list_price_when_formal_quote_matches_pre_discount_amount(self) -> None:
        result = PRICING_COMPARE.build_pricing_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "41085元"},
                    "list_price_total": {"value": "43708元"},
                    "discount_rate": {"value": "94折"},
                    "discounted_total": {"value": "41085元"},
                }
            },
            pricing_bridge_payload={"status": "ready_for_formal_quote"},
            quote_payload={
                "status": "completed",
                "reason": "formal_quote_completed",
                "pricing_route": "cabinet_projection_area",
                "pricing_total": "43763元",
            },
        )

        self.assertEqual(result["match_band"], "close_match")
        self.assertEqual(result["best_match_target"], "list_price_total")
        self.assertEqual(result["best_match_diff"], "55元")
        self.assertEqual(result["status"], "close_match_list_price_total")

    def test_builds_multi_product_aggregate_comparison(self) -> None:
        result = PRICING_COMPARE.build_multi_product_aggregate_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "80809元"},
                    "list_price_total": {"value": "82459元"},
                    "discounted_total": {"value": "80809元"},
                }
            },
            product_split_payload={
                "items": [
                    {
                        "product_name": "其他餐边柜",
                        "product_code": "20260379013001",
                        "line_total": "31631元",
                        "split_status": "compared",
                        "formal_quote": {"pricing_total": "45200元"},
                        "pricing_compare": {"pricing_total": "45200元"},
                    },
                    {
                        "product_name": "定制组合餐边柜",
                        "product_code": "20260379013002",
                        "line_total": "50828元",
                        "split_status": "compared",
                        "formal_quote": {"pricing_total": "54101元"},
                        "pricing_compare": {"pricing_total": "54101元"},
                    },
                ]
            },
        )

        self.assertEqual(result["pricing_total"], "99301元")
        self.assertEqual(result["best_match_target"], "list_price_total")
        self.assertEqual(result["best_match_diff"], "16842元")
        self.assertEqual(result["status"], "mismatch_list_price_total")
        self.assertEqual(result["aggregation_scope"], "multi_product_split_sum")
        self.assertEqual(result["compared_item_count"], 2)
        self.assertEqual(result["excluded_item_count"], 0)

    def test_multi_product_aggregate_carries_item_fallback_metadata(self) -> None:
        result = PRICING_COMPARE.build_multi_product_aggregate_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "49700元"},
                    "list_price_total": {"value": "54109元"},
                    "discounted_total": {"value": "49700元"},
                }
            },
            product_split_payload={
                "items": [
                    {
                        "product_name": "其他衣柜",
                        "product_code": "20260333003003",
                        "line_total": "36140元",
                        "split_status": "compared",
                        "formal_quote": {
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
                        "pricing_compare": {"pricing_total": "37812元"},
                    },
                    {
                        "product_name": "其他书柜",
                        "product_code": "20260333003004",
                        "line_total": "7379元",
                        "split_status": "compared",
                        "formal_quote": {"pricing_total": "7769元"},
                        "pricing_compare": {"pricing_total": "7769元"},
                    },
                ]
            },
        )

        wardrobe_item = next(item for item in result["included_items"] if item["product_name"] == "其他衣柜")
        self.assertEqual(wardrobe_item["pricing_route"], "cabinet_projection_area_fallback")
        self.assertEqual(wardrobe_item["fallback_strategy"], "generic_cabinet_projection_profile")
        self.assertEqual(wardrobe_item["fallback_detail"]["matched_product_code"], "YG-22")
        wardrobe_ledger = next(item for item in result["item_ledger"] if item["product_name"] == "其他衣柜")
        self.assertEqual(wardrobe_ledger["ledger_status"], "compared")
        self.assertEqual(wardrobe_ledger["contract_amount"], "36140元")
        self.assertEqual(wardrobe_ledger["pricing_amount"], "37812元")
        self.assertEqual(wardrobe_ledger["difference"], "1672元")
        self.assertEqual(wardrobe_ledger["fallback_strategy"], "generic_cabinet_projection_profile")
        self.assertEqual(wardrobe_ledger["fallback_label"], "通用衣柜投影面积估算")
        self.assertEqual(wardrobe_ledger["fallback_detail"]["matched_product_code"], "YG-22")

    def test_multi_product_aggregate_exposes_follow_up_question_for_child_bed_manual_confirmation(self) -> None:
        result = PRICING_COMPARE.build_multi_product_aggregate_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "20560元"},
                    "list_price_total": {"value": "20560元"},
                    "discounted_total": {"value": "20560元"},
                }
            },
            product_split_payload={
                "items": [
                    {
                        "product_name": "其他儿童床",
                        "product_code": "20260391004004",
                        "line_total": "20560元",
                        "split_status": "manual_confirmation_required",
                        "formal_quote": {"reason": "formal_quote_not_ready"},
                        "pricing_compare": {},
                        "pricing_precheck": {
                            "blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                            "strict_ocr_blocked_fields": ["bed_form", "access_style", "guardrail_style"],
                            "route_evidence": {
                                "recommended_route": "modular_child_bed",
                                "candidates": [
                                    {
                                        "route": "modular_child_bed",
                                        "signals": ["上下床", "箱体床"],
                                        "inferred_overrides": {
                                            "bed_form": "上下床",
                                            "lower_bed_type": "箱体床",
                                        },
                                    }
                                ],
                            },
                        },
                    }
                ]
            },
        )

        self.assertEqual(result["excluded_item_count"], 1)
        self.assertIn("梯柜上下床儿童床", result["excluded_items"][0]["follow_up_question"])
        self.assertEqual(result["item_ledger"][0]["ledger_status"], "pending")
        self.assertEqual(result["item_ledger"][0]["reason"], "formal_quote_not_ready")
        self.assertIn("梯柜上下床儿童床", result["item_ledger"][0]["follow_up_question"])

    def test_multi_product_aggregate_exposes_follow_up_question_when_detail_anchor_is_missing(self) -> None:
        result = PRICING_COMPARE.build_multi_product_aggregate_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "34142元"},
                    "list_price_total": {"value": "34142元"},
                    "discounted_total": {"value": "34142元"},
                }
            },
            product_split_payload={
                "items": [
                    {
                        "product_name": "其他衣柜",
                        "product_code": "20260391004005",
                        "line_total": "34142元",
                        "split_status": "manual_confirmation_required",
                        "formal_quote": {"reason": "formal_quote_not_ready"},
                        "pricing_compare": {},
                        "detail_resolution": {
                            "status": "detail_anchor_missing",
                            "detail_page_no": None,
                            "anchor_method": "",
                            "anchor_confidence": "low",
                            "linked_contract_page_range": {"start": None, "end": None},
                            "stop_reason": "detail_anchor_missing",
                            "evidence_scope": "none",
                        },
                    }
                ]
            },
        )

        self.assertEqual(result["excluded_item_count"], 1)
        self.assertIn("详情首页", result["excluded_items"][0]["follow_up_question"])

    def test_multi_product_aggregate_exposes_stair_storage_mode_for_child_bed_watch_hint(self) -> None:
        result = PRICING_COMPARE.build_multi_product_aggregate_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "20560元"},
                    "list_price_total": {"value": "20560元"},
                    "discounted_total": {"value": "20560元"},
                }
            },
            product_split_payload={
                "items": [
                    {
                        "product_name": "其他儿童床",
                        "product_code": "20260391004004",
                        "line_total": "20560元",
                        "split_status": "manual_confirmation_required",
                        "formal_quote": {"reason": "formal_quote_not_ready"},
                        "pricing_compare": {},
                        "pricing_precheck": {
                            "blocked_fields": ["stair_depth"],
                            "child_bed_analysis": {
                                "is_child_bed": True,
                                "stair_storage_mode": "open_grid",
                                "stair_storage_signals": ["开放格", "无抽屉"],
                                "stair_storage_evidence_snippets": ["图下注：左侧开放格梯柜，无抽屉，层板可调"],
                            },
                            "route_evidence": {
                                "recommended_route": "modular_child_bed",
                                "candidates": [
                                    {
                                        "route": "modular_child_bed",
                                        "signals": ["上下床", "梯柜"],
                                        "inferred_overrides": {
                                            "bed_form": "上下床",
                                            "access_style": "梯柜",
                                            "stair_storage_mode": "open_grid",
                                        },
                                        "evidence_snippets": ["图下注：左侧开放格梯柜，无抽屉，层板可调"],
                                    }
                                ],
                            },
                            "precheck_result": {"next_question": "这个梯柜我还需要确认进深，请问大概做多深？"},
                        },
                        "normalized_fields": {
                            "child_bed_analysis": {
                                "is_child_bed": True,
                                "stair_storage_mode": "open_grid",
                            }
                        },
                    }
                ]
            },
        )

        self.assertEqual(result["excluded_item_count"], 1)
        self.assertEqual(result["excluded_items"][0]["stair_storage_mode"], "open_grid")
        self.assertTrue(
            any("左侧开放格梯柜" in item for item in result["excluded_items"][0]["stair_storage_evidence_snippets"])
        )


if __name__ == "__main__":
    unittest.main()
