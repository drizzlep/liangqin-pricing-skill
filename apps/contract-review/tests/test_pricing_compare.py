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


if __name__ == "__main__":
    unittest.main()
