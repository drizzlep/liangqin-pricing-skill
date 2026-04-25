import importlib.util
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

MODULE_PATH = CORE_ROOT / "reviewer_card.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REVIEWER_CARD = load_module("contract_review_reviewer_card", MODULE_PATH)


class ReviewerCardTests(unittest.TestCase):
    def test_auto_pass_when_all_items_compared_and_amount_is_close(self) -> None:
        card = REVIEWER_CARD.build_reviewer_card(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "1279元"},
                    "list_price_total": {"value": "1279元"},
                    "discounted_total": {"value": "1279元"},
                }
            },
            pricing_compare_payload={
                "status": "close_match_contract_total",
                "match_band": "close_match",
                "best_match_target": "contract_total",
                "best_match_diff": "2元",
                "best_match_diff_value": 2.0,
                "pricing_total": "1281元",
                "aggregation_complete": True,
                "item_ledger": [
                    {
                        "product_name": "新罗胖椅",
                        "contract_amount": "1180元",
                        "pricing_amount": "1180元",
                        "difference": "0元",
                        "ledger_status": "compared",
                        "pricing_route": "catalog_unit_price",
                    },
                    {
                        "product_name": "小板凳",
                        "contract_amount": "99元",
                        "pricing_amount": "101元",
                        "difference": "2元",
                        "ledger_status": "compared",
                        "pricing_route": "catalog_stool_candidate",
                    },
                ],
            },
            review_analysis_payload={"review_card": {"next_actions": []}},
        )

        self.assertEqual(card["decision"], "auto_pass")
        self.assertEqual(card["decision_label"], "可自动通过")
        self.assertEqual(card["amounts"]["difference"], "2元")
        self.assertEqual(card["amounts"]["comparison_basis"], "contract_total")
        self.assertEqual(card["line_items"][0]["field_confidence"], "high")
        self.assertIn("金额差异在可自动通过范围", card["primary_reason"])

    def test_manual_required_when_any_item_is_pending(self) -> None:
        card = REVIEWER_CARD.build_reviewer_card(
            contract_audit_payload={
                "financials": {
                    "list_price_total": {"value": "51696元"},
                    "discount_rate": {"value": "98折"},
                    "discounted_total": {"value": "50660元"},
                }
            },
            pricing_compare_payload={
                "status": "mismatch_discounted_total",
                "match_band": "mismatch",
                "best_match_target": "discounted_total",
                "best_match_diff": "13720元",
                "best_match_diff_value": 13720.0,
                "pricing_total": "36940元",
                "aggregation_complete": False,
                "excluded_item_count": 1,
                "item_ledger": [
                    {
                        "product_name": "升级经典无腰线衣柜",
                        "contract_amount": "36936元",
                        "pricing_amount": "36940元",
                        "difference": "4元",
                        "ledger_status": "compared",
                        "pricing_route": "cabinet_projection_area_fallback",
                        "fallback_strategy": "generic_cabinet_projection_profile",
                    },
                    {
                        "product_name": "衣柜组合",
                        "contract_amount": "14760元",
                        "pricing_amount": "",
                        "difference": "",
                        "ledger_status": "pending",
                        "reason": "formal_quote_total_missing",
                    },
                ],
            },
            review_analysis_payload={"review_card": {"next_actions": ["请优先核对是否应按衣柜路线计价。"]}},
        )

        self.assertEqual(card["decision"], "manual_required")
        self.assertEqual(card["decision_label"], "必须人工确认")
        self.assertIn("1个品项未入账", card["primary_reason"])
        pending_source = next(item for item in card["difference_sources"] if item["source_type"] == "pending_items")
        self.assertEqual(pending_source["amount"], "14760元")
        self.assertEqual(pending_source["item_count"], 1)
        pending_item = next(item for item in card["line_items"] if item["product_name"] == "衣柜组合")
        self.assertEqual(pending_item["review_status"], "manual_required")
        self.assertIn("未形成报价", pending_item["manual_hint"])

    def test_discount_basis_match_becomes_review_recommended(self) -> None:
        card = REVIEWER_CARD.build_reviewer_card(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": "41085元"},
                    "list_price_total": {"value": "43708元"},
                    "discount_rate": {"value": "94折"},
                    "discounted_total": {"value": "41085元"},
                }
            },
            pricing_compare_payload={
                "status": "close_match_list_price_total",
                "match_band": "close_match",
                "best_match_target": "list_price_total",
                "best_match_diff": "55元",
                "best_match_diff_value": 55.0,
                "pricing_total": "43763元",
                "item_ledger": [
                    {
                        "product_name": "整单",
                        "contract_amount": "41085元",
                        "pricing_amount": "43763元",
                        "difference": "2678元",
                        "ledger_status": "compared",
                        "pricing_route": "cabinet_projection_area",
                    }
                ],
            },
            review_analysis_payload={"review_card": {"next_actions": []}},
        )

        self.assertEqual(card["decision"], "review_recommended")
        self.assertEqual(card["decision_label"], "建议人工复核")
        self.assertEqual(card["amounts"]["comparison_basis"], "list_price_total")
        self.assertIn("折前价", card["primary_reason"])
        self.assertTrue(any(item["source_type"] == "discount_basis" for item in card["difference_sources"]))
        self.assertTrue(any("折扣口径" in action for action in card["next_actions"]))

    def test_render_reviewer_card_markdown_uses_business_language(self) -> None:
        markdown = REVIEWER_CARD.render_reviewer_card_markdown(
            {
                "decision_label": "必须人工确认",
                "primary_reason": "存在1个品项未入账，不能判断整单金额是否正确。",
                "amounts": {
                    "contract_amount": "50660元",
                    "pricing_amount": "36940元",
                    "difference": "13720元",
                    "comparison_basis_label": "折后合计",
                },
                "line_items": [
                    {
                        "product_name": "衣柜组合",
                        "contract_amount": "14760元",
                        "pricing_amount": "",
                        "difference": "",
                        "review_status_label": "必须人工确认",
                        "manual_hint": "该品项未形成报价，请人工确认。",
                    }
                ],
                "next_actions": ["优先确认衣柜组合应走哪个报价路线。"],
            }
        )

        self.assertIn("审核结论：必须人工确认", markdown)
        self.assertIn("主要原因：存在1个品项未入账", markdown)
        self.assertIn("衣柜组合", markdown)
        self.assertNotIn("fallback_strategy", markdown)


if __name__ == "__main__":
    unittest.main()
