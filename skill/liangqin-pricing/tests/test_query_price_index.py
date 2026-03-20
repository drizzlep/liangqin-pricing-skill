import argparse
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "query_price_index.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("query_price_index", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QueryPriceIndexTests(unittest.TestCase):
    def make_args(self, **overrides):
        defaults = dict(
            include_non_queryable=False,
            sheet=None,
            product_code=None,
            pricing_mode=None,
            quote_kind=None,
            record_kind=None,
            has_door=None,
            name_contains=None,
            name_exact=None,
            group_contains=None,
            remark_contains=None,
            series=None,
            door_type=None,
            variant_tag=[],
            length=None,
            depth=None,
            height=None,
            width=None,
            material=None,
            include_dimensions=False,
            limit=10,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_name_exact_does_not_match_similar_names(self) -> None:
        args = self.make_args(sheet="椅", name_exact="罗胖椅")
        exact_record = {"sheet": "椅", "name": "罗胖椅", "is_queryable": True, "record_kind": "price", "pricing_mode": "unit_price", "variant_tags": []}
        similar_record = {"sheet": "椅", "name": "高背罗胖椅", "is_queryable": True, "record_kind": "price", "pricing_mode": "unit_price", "variant_tags": []}
        self.assertTrue(MODULE.record_matches(exact_record, args))
        self.assertFalse(MODULE.record_matches(similar_record, args))

    def test_dimension_filters_match_specific_variant(self) -> None:
        args = self.make_args(sheet="书桌", name_exact="升降桌", length="1.6", depth="0.7")
        matched_record = {
            "sheet": "书桌",
            "name": "升降桌",
            "is_queryable": True,
            "record_kind": "price",
            "pricing_mode": "unit_price",
            "variant_tags": [],
            "dimensions": {"length": 1.6, "depth": 0.7},
        }
        other_record = {
            "sheet": "书桌",
            "name": "升降桌",
            "is_queryable": True,
            "record_kind": "price",
            "pricing_mode": "unit_price",
            "variant_tags": [],
            "dimensions": {"length": 1.8, "depth": 0.8},
        }
        self.assertTrue(MODULE.record_matches(matched_record, args))
        self.assertFalse(MODULE.record_matches(other_record, args))


if __name__ == "__main__":
    unittest.main()
