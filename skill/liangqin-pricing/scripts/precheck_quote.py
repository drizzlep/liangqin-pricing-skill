#!/usr/bin/env python3
"""Deterministic precheck for Liangqin quote intake."""

from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from math import isclose
from pathlib import Path
from typing import Any


CABINET_CATEGORIES = {
    "衣柜",
    "书柜",
    "玄关柜",
    "电视柜",
    "电视背景柜",
    "组合电视柜",
    "餐边柜",
    "酒柜",
    "整体酒柜",
    "组合柜",
}

BED_CATEGORIES = {
    "床",
    "床榻",
    "架式床",
    "箱体床",
    "抽屉床",
    "儿童床",
    "儿童上下床",
    "上下床",
    "子母床",
    "高架床",
    "儿童高架床",
    "半高床",
    "错层床",
    "伴床",
    "儿童床书柜伴床",
    "ins儿童床",
    "糖果儿童床",
    "积木上下床",
}
TATAMI_CATEGORIES = {"榻榻米", "榻榻米+超大抽屉", "榻榻米加超大抽屉"}
TABLE_CATEGORIES = {"餐桌", "书桌", "桌", "茶几", "边几", "书桌柜", "转角书桌", "转角书桌柜", "儿童多屉书桌"}
CHILD_BED_STYLE_KEYWORDS = {"经典", "城堡", "挂梯", "梯柜", "直梯", "伴床", "ins", "糖果", "积木", "组合"}
ADULT_BED_STYLE_QUESTIONS = {
    "架式床": "架式床我还需要先确认具体款式，比如抛物线架式床、悬浮架式床、支腿架式床；你也可以直接告诉我正式产品名。",
    "箱体床": "箱体床我还需要先确认具体款式，比如经典箱体床、悬浮箱体床、支腿箱体床；你也可以直接告诉我正式产品名。",
}
MIXED_QUOTE_KIND_CATEGORY_KEYWORDS = {
    "衣柜",
    "书柜",
    "玄关柜",
    "电视柜",
    "餐边柜",
    "床",
    "儿童床",
    "上下床",
    "高架床",
    "书桌",
    "书桌柜",
    "转角书桌",
}
STANDARD_PRICING_MODES = {"unit_price", "per_item", "mixed"}
CUSTOM_INTENT_PATTERN = re.compile(r"(定制|订制|定做|订做|订个|订一|来订|想订)")
STANDARD_INTENT_KEYWORDS = ["成品", "标品", "标准品", "现成"]
CURRENT_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "current" / "price-index.json"
MODULAR_CHILD_BED_KEYWORDS = {"儿童床", "上下床", "子母床", "高架床", "半高床", "错层床"}
MODULAR_CHILD_BED_FORMS = {"上下床", "半高床", "高架床", "错层床"}

DEFAULT_CABINET_PROFILES = {
    "书柜": {
        "product_code": "SG-01",
        "name": "飘飘家开放书柜",
        "sheet": "书柜",
        "pricing_mode": "projection_area",
        "assumed_depth": 0.35,
        "assumed_has_door": "no",
        "assumed_door_type": "",
        "display_name": "常规开放书柜",
    },
    "衣柜": {
        "product_code": "YG-22",
        "name": "升级经典门衣柜",
        "sheet": "衣柜",
        "pricing_mode": "projection_area",
        "assumed_depth": 0.6,
        "assumed_has_door": "yes",
        "assumed_door_type": "带门",
        "display_name": "常规带门衣柜",
    },
    "玄关柜": {
        "product_code": "XGG-02",
        "name": "经典玄关柜",
        "sheet": "玄关柜",
        "pricing_mode": "projection_area",
        "assumed_depth": 0.4,
        "assumed_has_door": "yes",
        "assumed_door_type": "带门",
        "display_name": "常规带门玄关柜",
    },
    "电视柜": {
        "product_code": "DSG-05",
        "name": "简美电视柜及配柜",
        "sheet": "电视柜",
        "pricing_mode": "projection_area",
        "assumed_depth": 0.45,
        "assumed_has_door": "unknown",
        "assumed_door_type": "",
        "display_name": "常规电视柜",
    },
    "餐边柜": {
        "product_code": "CBG-14",
        "name": "简美餐边柜高柜",
        "sheet": "餐边柜",
        "pricing_mode": "projection_area",
        "assumed_depth": 0.45,
        "assumed_has_door": "unknown",
        "assumed_door_type": "",
        "display_name": "常规餐边柜",
    },
}

DEFAULT_BLOCKING_CABINET_KEYWORDS = {
    "抽屉",
    "灯带",
    "异形",
    "双面门",
    "岩板",
    "门板",
    "玫瑰木",
    "非见光",
    "超深",
    "改深",
    "无背板",
    "有背板",
    "背板",
    "双排",
    "互通",
    "前后",
}
MODULAR_CHILD_BED_GUARDRAIL_STYLES = {"胶囊围栏", "蘑菇围栏", "田园围栏", "篱笆围栏", "圆柱围栏", "方圆围栏", "城堡围栏"}
UNDERBED_CABINET_MODES = {"无门无背板", "有门无背板", "无门有背板"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check which quote parameter should be asked next.")
    parser.add_argument("--category", required=True, help="Product category, such as 书柜、衣柜、床、餐桌.")
    parser.add_argument("--length", help="Known length.")
    parser.add_argument("--depth", help="Known depth.")
    parser.add_argument("--height", help="Known height.")
    parser.add_argument("--width", help="Known width for beds/tables.")
    parser.add_argument("--material", help="Known material.")
    parser.add_argument(
        "--quote-kind",
        choices=["standard", "custom", "unknown"],
        default="unknown",
        help="Whether this should follow catalog standard-product pricing or custom pricing.",
    )
    parser.add_argument("--has-door", choices=["yes", "no", "unknown"], default="unknown", help="Whether the product has doors.")
    parser.add_argument("--door-type", default="", help="Known door type.")
    parser.add_argument("--series", default="", help="Known series or style.")
    parser.add_argument("--shape", default="", help="Known special shape info.")
    parser.add_argument("--bed-form", default="", help="Modular child-bed form such as 上下床、半高床、高架床、错层床.")
    parser.add_argument("--access-style", default="", help="Upper-bed access style such as 直梯、斜梯、梯柜.")
    parser.add_argument("--lower-bed-type", default="", help="Lower-bed structure such as 架式床、箱体床.")
    parser.add_argument("--guardrail-style", default="", help="Guardrail style for modular child-bed quotes.")
    parser.add_argument("--guardrail-length", default="", help="Guardrail run length for modular child-bed quotes.")
    parser.add_argument("--guardrail-height", default="", help="Guardrail height for modular child-bed quotes.")
    parser.add_argument("--access-height", default="", help="Vertical ladder height for modular child-bed quotes.")
    parser.add_argument("--stair-width", default="", help="Stair-cabinet tread width for modular child-bed quotes.")
    parser.add_argument("--stair-depth", default="", help="Stair-cabinet depth for modular child-bed quotes.")
    parser.add_argument("--underbed-cabinet-mode", default="", help="Whether the child bed includes under-bed cabinets.")
    parser.add_argument("--front-cabinet-length", default="", help="Front under-bed cabinet length.")
    parser.add_argument("--front-cabinet-height", default="", help="Front under-bed cabinet height.")
    parser.add_argument("--front-cabinet-depth", default="", help="Front under-bed cabinet depth.")
    parser.add_argument("--front-cabinet-mode", default="", help="Front under-bed cabinet mode.")
    parser.add_argument("--rear-cabinet-length", default="", help="Rear under-bed cabinet length.")
    parser.add_argument("--rear-cabinet-height", default="", help="Rear under-bed cabinet height.")
    parser.add_argument("--rear-cabinet-depth", default="", help="Rear under-bed cabinet depth.")
    parser.add_argument("--rear-cabinet-mode", default="", help="Rear under-bed cabinet mode.")
    parser.add_argument("--interconnected-rows", action="store_true", help="Whether front/rear cabinet rows are interconnected.")
    parser.add_argument("--approximate-only", action="store_true", help="Whether the user only wants a reference quote.")
    return parser.parse_args()


def normalize_category_label(category: str) -> str:
    if category in TATAMI_CATEGORIES:
        return "tatami"
    if category in CABINET_CATEGORIES:
        return "cabinet"
    if category in BED_CATEGORIES:
        return "bed"
    if category in TABLE_CATEGORIES:
        return "table"
    if "榻榻米" in category:
        return "tatami"
    if "书桌柜" in category or "转角书桌" in category:
        return "table"
    if "儿童床" in category or "上下床" in category or "子母床" in category or "高架床" in category or "半高床" in category or "错层床" in category:
        return "bed"
    return "generic"


@lru_cache(maxsize=1)
def load_queryable_product_lookup() -> list[dict[str, Any]]:
    with CURRENT_INDEX_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    products: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in payload.get("records", []):
        if not record.get("is_queryable", False):
            continue
        if record.get("record_kind") != "price":
            continue
        sheet = str(record.get("sheet") or "").strip()
        product_code = str(record.get("product_code") or "").strip()
        name = str(record.get("name") or "").strip()
        if not sheet or (not product_code and not name):
            continue
        key = (sheet, product_code, name)
        product = products.setdefault(
            key,
            {
                "sheet": sheet,
                "product_code": product_code,
                "name": name,
                "series": str(record.get("series") or "").strip(),
                "dimensions": record.get("dimensions") or {},
                "pricing_modes": set(),
            },
        )
        pricing_mode = str(record.get("pricing_mode") or "").strip()
        if pricing_mode:
            product["pricing_modes"].add(pricing_mode)

    normalized_products = []
    for product in products.values():
        normalized_products.append(
            {
                "sheet": product["sheet"],
                "product_code": product["product_code"],
                "name": product["name"],
                "series": product["series"],
                "dimensions": product["dimensions"],
                "pricing_modes": sorted(product["pricing_modes"]),
            }
        )
    return sorted(
        normalized_products,
        key=lambda item: (
            len(item["product_code"]),
            len(item["name"]),
        ),
        reverse=True,
    )


@lru_cache(maxsize=1)
def load_queryable_price_records() -> list[dict[str, Any]]:
    with CURRENT_INDEX_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records: list[dict[str, Any]] = []
    for record in payload.get("records", []):
        if not record.get("is_queryable", False):
            continue
        if record.get("record_kind") != "price":
            continue
        records.append(record)
    return records


def is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def format_meter_value(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def collect_source_text(args: argparse.Namespace) -> str:
    return " ".join(
        [
            str(args.category or ""),
            str(args.series or ""),
            str(args.shape or ""),
            str(getattr(args, "bed_form", "") or ""),
            str(getattr(args, "access_style", "") or ""),
            str(getattr(args, "lower_bed_type", "") or ""),
            str(getattr(args, "guardrail_style", "") or ""),
        ]
    ).strip()


def normalize_text_for_match(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def parse_dimension_to_meters(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    text = (
        text.replace("毫米", "")
        .replace("mm", "")
        .replace("厘米", "")
        .replace("cm", "")
        .replace("米", "")
        .replace("m", "")
    )
    try:
        number = float(text)
    except ValueError:
        return None
    if number > 10:
        return number / 1000
    return number


def identity_match_score(
    *,
    source_text: str,
    normalized_source_text: str,
    normalized_category: str,
    normalized_series: str,
    product_code: str,
    name: str,
    sheet: str,
    series: str,
) -> int:
    score = 0
    product_name = normalize_text_for_match(name)
    product_sheet = normalize_text_for_match(sheet)
    product_series = normalize_text_for_match(series)
    upper_source_text = source_text.upper()

    if product_code and product_code.upper() in upper_source_text:
        score = max(score, 200 + len(product_code))
    if name and name in source_text:
        score = max(score, 100 + len(name))
    if product_name and product_name in normalized_source_text:
        score = max(score, 100 + len(product_name))
    if product_series and product_sheet and normalized_series and normalized_category:
        if product_series == normalized_series and product_sheet == normalized_category:
            score = max(score, 90 + len(product_series) + len(product_sheet))
            if product_name in {
                f"{normalized_series}{normalized_category}",
                f"{normalized_category}{normalized_series}",
            }:
                score = max(score, 150 + len(product_name))
    if product_series and product_sheet and product_series in normalized_source_text and product_sheet in normalized_source_text:
        score = max(score, 80 + len(product_series) + len(product_sheet))
    return score


def infer_explicit_product_match(args: argparse.Namespace) -> dict[str, Any] | None:
    source_text = collect_source_text(args)
    if not source_text:
        return None

    normalized_source_text = normalize_text_for_match(source_text)
    normalized_category = normalize_text_for_match(args.category)
    normalized_series = normalize_text_for_match(args.series)
    matched_products: list[tuple[int, dict[str, Any]]] = []
    for product in load_queryable_product_lookup():
        product_code = str(product.get("product_code") or "").strip()
        name = str(product.get("name") or "").strip()
        score = identity_match_score(
            source_text=source_text,
            normalized_source_text=normalized_source_text,
            normalized_category=normalized_category,
            normalized_series=normalized_series,
            product_code=product_code,
            name=name,
            sheet=str(product.get("sheet") or ""),
            series=str(product.get("series") or ""),
        )
        if score:
            matched_products.append((score, product))

    if not matched_products:
        return None

    matched_products.sort(key=lambda item: item[0], reverse=True)
    best_score = matched_products[0][0]
    best_matches = [product for score, product in matched_products if score == best_score]
    if len(best_matches) > 1:
        return None

    return best_matches[0]


def find_matching_catalog_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    source_text = collect_source_text(args)
    provided_dimension_fields = [
        field_name
        for field_name in ["length", "depth", "height", "width"]
        if parse_dimension_to_meters(getattr(args, field_name, None)) is not None
    ]
    if not source_text and len(provided_dimension_fields) < 2:
        return []

    normalized_source_text = normalize_text_for_match(source_text)
    normalized_category = normalize_text_for_match(args.category)
    normalized_series = normalize_text_for_match(args.series)
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in load_queryable_price_records():
        score = identity_match_score(
            source_text=source_text,
            normalized_source_text=normalized_source_text,
            normalized_category=normalized_category,
            normalized_series=normalized_series,
            product_code=str(record.get("product_code") or "").strip(),
            name=str(record.get("name") or "").strip(),
            sheet=str(record.get("sheet") or "").strip(),
            series=str(record.get("series") or "").strip(),
        )
        if not score:
            continue

        dimensions = record.get("dimensions") or {}
        dimension_match = True
        for field_name in ["length", "depth", "height", "width"]:
            expected = parse_dimension_to_meters(getattr(args, field_name, None))
            if expected is None:
                continue
            actual = parse_dimension_to_meters(dimensions.get(field_name))
            if actual is None or not isclose(actual, expected, abs_tol=0.015):
                dimension_match = False
                break
        if dimension_match:
            scored.append((score, record))

    if not scored:
        category = str(args.category or "").strip()
        if len(provided_dimension_fields) < 2 or not category:
            return []

        dimension_candidates: list[dict[str, Any]] = []
        for record in load_queryable_price_records():
            if str(record.get("sheet") or "").strip() != category:
                continue

            dimensions = record.get("dimensions") or {}
            dimension_match = True
            for field_name in ["length", "depth", "height", "width"]:
                expected = parse_dimension_to_meters(getattr(args, field_name, None))
                if expected is None:
                    continue
                actual = parse_dimension_to_meters(dimensions.get(field_name))
                if actual is None or not isclose(actual, expected, abs_tol=0.015):
                    dimension_match = False
                    break
            if dimension_match:
                dimension_candidates.append(record)

        if not dimension_candidates:
            return []

        product_keys = {
            (
                str(record.get("sheet") or "").strip(),
                str(record.get("product_code") or "").strip(),
                str(record.get("name") or "").strip(),
            )
            for record in dimension_candidates
        }
        if len(product_keys) != 1:
            return []
        return dimension_candidates

    best_score = max(score for score, _ in scored)
    return [record for score, record in scored if score == best_score]


def dimensions_indicate_custom(args: argparse.Namespace, matched_product: dict[str, Any] | None) -> bool:
    if not matched_product:
        return False
    sample_dimensions = matched_product.get("dimensions") or {}
    if not sample_dimensions:
        return False
    for field_name in ["length", "depth", "height", "width"]:
        sample_value = parse_dimension_to_meters(sample_dimensions.get(field_name))
        input_value = parse_dimension_to_meters(getattr(args, field_name, None))
        if sample_value is None or input_value is None:
            continue
        if not isclose(sample_value, input_value, abs_tol=0.015):
            return True
    return False


def find_matching_catalog_variant(args: argparse.Namespace, matched_product: dict[str, Any] | None) -> dict[str, Any] | None:
    if not matched_product:
        return None

    candidates: list[dict[str, Any]] = []
    for record in load_queryable_price_records():
        if record.get("sheet") != matched_product.get("sheet"):
            continue
        if record.get("product_code") != matched_product.get("product_code"):
            continue
        if record.get("name") != matched_product.get("name"):
            continue
        if record.get("pricing_mode") not in STANDARD_PRICING_MODES:
            continue

        dimensions = record.get("dimensions") or {}
        matches = True
        for field_name in ["length", "depth", "height", "width"]:
            input_value = parse_dimension_to_meters(getattr(args, field_name, None))
            if input_value is None:
                continue
            sample_value = parse_dimension_to_meters(dimensions.get(field_name))
            if sample_value is None or not isclose(sample_value, input_value, abs_tol=0.015):
                matches = False
                break
        if matches:
            candidates.append(record)

    if len(candidates) == 1:
        return candidates[0]
    return None


def infer_quote_kind_from_product_match(args: argparse.Namespace) -> str:
    matched_records = find_matching_catalog_records(args)
    if matched_records:
        pricing_modes = {str(record.get("pricing_mode") or "").strip() for record in matched_records}
        pricing_modes.discard("")
        if pricing_modes and pricing_modes <= STANDARD_PRICING_MODES:
            return "standard"
        if pricing_modes == {"projection_area"}:
            return "custom"

    matched_product = infer_explicit_product_match(args)
    if not matched_product:
        return "unknown"
    matched_variant = find_matching_catalog_variant(args, matched_product)
    if matched_variant and matched_variant.get("pricing_mode") in STANDARD_PRICING_MODES:
        return "standard"
    if dimensions_indicate_custom(args, matched_product):
        return "custom"
    pricing_modes = set(matched_product.get("pricing_modes", []))
    if not pricing_modes:
        return "unknown"
    if pricing_modes <= STANDARD_PRICING_MODES:
        return "standard"
    if pricing_modes == {"projection_area"}:
        return "custom"
    return "unknown"


def has_explicit_product_identity(args: argparse.Namespace) -> bool:
    return infer_explicit_product_match(args) is not None or bool(find_matching_catalog_records(args))


def has_matching_standard_catalog_variant(args: argparse.Namespace) -> bool:
    matched_product = infer_explicit_product_match(args)
    matched_variant = find_matching_catalog_variant(args, matched_product)
    return matched_variant is not None


def has_unique_standard_catalog_variant(args: argparse.Namespace) -> bool:
    matched_product = infer_explicit_product_match(args)
    if not matched_product:
        return False

    candidates = []
    for record in load_queryable_price_records():
        if record.get("sheet") != matched_product.get("sheet"):
            continue
        if record.get("product_code") != matched_product.get("product_code"):
            continue
        if record.get("name") != matched_product.get("name"):
            continue
        if record.get("pricing_mode") not in STANDARD_PRICING_MODES:
            continue
        candidates.append(record)
    return len(candidates) == 1


def generic_cabinet_dimensions_indicate_custom(args: argparse.Namespace) -> bool:
    if has_explicit_product_identity(args):
        return False

    category = str(args.category or "").strip()
    if normalize_category_label(category) != "cabinet":
        return False

    expected_dimensions = {
        field_name: parse_dimension_to_meters(getattr(args, field_name, None))
        for field_name in ["length", "depth", "height"]
    }
    if any(value is None for value in expected_dimensions.values()):
        return False

    standard_matches = 0
    for record in load_queryable_price_records():
        if str(record.get("sheet") or "").strip() != category:
            continue
        if record.get("pricing_mode") not in STANDARD_PRICING_MODES:
            continue

        dimensions = record.get("dimensions") or {}
        matches = True
        for field_name, expected in expected_dimensions.items():
            actual = parse_dimension_to_meters(dimensions.get(field_name))
            if actual is None or not isclose(actual, expected, abs_tol=0.015):
                matches = False
                break
        if matches:
            standard_matches += 1

    return standard_matches == 0


def child_bed_variant_is_ambiguous(args: argparse.Namespace) -> bool:
    records = find_matching_catalog_records(args)
    if len(records) <= 1:
        return False
    return any(str(record.get("sheet") or "") == "儿童床" for record in records)


def explicit_cabinet_variant_requires_door_type(args: argparse.Namespace) -> bool:
    records = find_matching_catalog_records(args)
    if len(records) <= 1:
        return False
    door_types = {str(record.get("door_type") or "").strip() for record in records}
    door_types.discard("")
    return len(door_types) > 1


def is_diamond_cabinet_request(args: argparse.Namespace) -> bool:
    source_text = collect_source_text(args)
    return "钻石柜" in source_text


def normalize_category(args: argparse.Namespace) -> str:
    matched_product = infer_explicit_product_match(args)
    if matched_product:
        return normalize_category_label(str(matched_product.get("sheet") or ""))
    return normalize_category_label(str(args.category or ""))


def infer_quote_kind(args: argparse.Namespace) -> str:
    if getattr(args, "quote_kind", "unknown") != "unknown":
        return args.quote_kind
    source_text = collect_source_text(args)
    if any(keyword in source_text for keyword in ["定制", "非标", "改尺寸", "改大", "改小"]):
        return "custom"
    if CUSTOM_INTENT_PATTERN.search(source_text):
        return "custom"
    if any(keyword in source_text for keyword in STANDARD_INTENT_KEYWORDS):
        return "standard"
    if generic_cabinet_dimensions_indicate_custom(args):
        return "custom"
    product_quote_kind = infer_quote_kind_from_product_match(args)
    if product_quote_kind != "unknown":
        return product_quote_kind
    return "unknown"


def needs_quote_kind_confirmation(args: argparse.Namespace, category_type: str) -> bool:
    if category_type == "tatami":
        return False
    quote_kind = infer_quote_kind(args)
    if quote_kind != "unknown":
        return False
    category = str(args.category or "").strip()
    if category_type in {"bed", "table"}:
        return True
    if category_type == "cabinet":
        if has_cabinet_core_quote_fields(args):
            return False
        return any(keyword in category for keyword in MIXED_QUOTE_KIND_CATEGORY_KEYWORDS)
    return False


def has_cabinet_core_quote_fields(args: argparse.Namespace) -> bool:
    category = str(args.category or "").strip()
    if category not in DEFAULT_CABINET_PROFILES:
        return False
    return not any(is_blank(getattr(args, field_name, None)) for field_name in ["length", "height", "material"])


def cabinet_has_default_blocker(args: argparse.Namespace) -> bool:
    source_text = collect_source_text(args)
    return any(keyword in source_text for keyword in DEFAULT_BLOCKING_CABINET_KEYWORDS)


def load_default_cabinet_anchor(profile: dict[str, Any]) -> dict[str, Any] | None:
    for record in load_queryable_price_records():
        if record.get("record_kind") != "price":
            continue
        if record.get("sheet") != profile["sheet"]:
            continue
        if record.get("product_code") != profile["product_code"]:
            continue
        if record.get("name") != profile["name"]:
            continue
        if record.get("pricing_mode") != profile["pricing_mode"]:
            continue
        door_type = str(record.get("door_type") or "").strip()
        expected_door_type = str(profile.get("assumed_door_type") or "").strip()
        if expected_door_type and door_type != expected_door_type:
            continue
        return record
    return None


def build_default_quote_profile(
    *,
    source: str,
    anchor_record: dict[str, Any],
    assumed_depth: float,
    assumed_has_door: str,
    assumed_door_type: str,
    display_name: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "sheet": str(anchor_record.get("sheet") or "").strip(),
        "product_code": str(anchor_record.get("product_code") or "").strip(),
        "name": str(anchor_record.get("name") or "").strip(),
        "pricing_mode": str(anchor_record.get("pricing_mode") or "").strip(),
        "door_type": assumed_door_type,
        "assumed_depth": format_meter_value(assumed_depth),
        "assumed_has_door": assumed_has_door,
        "display_name": display_name,
    }


def explicit_cabinet_default_context(args: argparse.Namespace) -> dict[str, Any] | None:
    matched_product = infer_explicit_product_match(args)
    if not matched_product:
        return None
    if "projection_area" not in set(matched_product.get("pricing_modes", [])):
        return None

    sample_dimensions = matched_product.get("dimensions") or {}
    sample_depth = parse_dimension_to_meters(sample_dimensions.get("depth"))
    if sample_depth is None:
        return None

    provided_depth = parse_dimension_to_meters(args.depth)
    if provided_depth is not None:
        if provided_depth > 0.7:
            return None
        return None

    assumed_defaults = []
    if provided_depth is None:
        assumed_defaults.append(
            {
                "field": "depth",
                "value": format_meter_value(sample_depth),
                "reason": "explicit cabinet product uses catalog standard depth",
            }
        )

    return {
        "mode": "explicit_product",
        "assumed_defaults": assumed_defaults,
        "default_quote_profile": build_default_quote_profile(
            source="explicit_product",
            anchor_record={
                "sheet": matched_product.get("sheet"),
                "product_code": matched_product.get("product_code"),
                "name": matched_product.get("name"),
                "pricing_mode": "projection_area",
            },
            assumed_depth=provided_depth if provided_depth is not None else sample_depth,
            assumed_has_door="unknown",
            assumed_door_type="",
            display_name=str(matched_product.get("name") or "").strip(),
        ),
    }


def generic_cabinet_default_context(args: argparse.Namespace) -> dict[str, Any] | None:
    category = str(args.category or "").strip()
    profile = DEFAULT_CABINET_PROFILES.get(category)
    if not profile:
        return None
    if infer_explicit_product_match(args) is not None:
        return None
    if not has_cabinet_core_quote_fields(args):
        return None
    if cabinet_has_default_blocker(args):
        return None

    provided_depth = parse_dimension_to_meters(args.depth)
    if provided_depth is not None and provided_depth > 0.7:
        return None

    anchor_record = load_default_cabinet_anchor(profile)
    if not anchor_record:
        return None

    assumed_defaults = []
    effective_depth = provided_depth
    if effective_depth is None:
        effective_depth = float(profile["assumed_depth"])
        assumed_defaults.append(
            {
                "field": "depth",
                "value": format_meter_value(effective_depth),
                "reason": "generic cabinet quote uses the category standard depth",
            }
        )

    assumed_has_door = str(profile["assumed_has_door"])
    if args.has_door == "unknown" and assumed_has_door != "unknown":
        assumed_defaults.append(
            {
                "field": "has_door",
                "value": assumed_has_door,
                "reason": "generic cabinet quote uses the category default structure",
            }
        )

    assumed_door_type = str(profile["assumed_door_type"])
    if is_blank(args.door_type) and assumed_door_type:
        assumed_defaults.append(
            {
                "field": "door_type",
                "value": assumed_door_type,
                "reason": "generic cabinet quote uses the category default door path",
            }
        )

    return {
        "mode": "generic_profile",
        "assumed_defaults": assumed_defaults,
        "default_quote_profile": build_default_quote_profile(
            source="generic_category",
            anchor_record=anchor_record,
            assumed_depth=effective_depth,
            assumed_has_door=assumed_has_door,
            assumed_door_type=assumed_door_type,
            display_name=str(profile["display_name"]),
        ),
    }


def resolve_cabinet_default_context(args: argparse.Namespace) -> dict[str, Any] | None:
    return explicit_cabinet_default_context(args) or generic_cabinet_default_context(args)


def quote_kind_question(category_type: str) -> str:
    if category_type == "bed":
        return "这类床品我先需要确认一下，你这是按目录成品/标准品报价，还是按定制报价？先不用选款，定制和成品的算法不一样。"
    if category_type == "table":
        return "这类桌品我先需要确认一下，你这是按目录成品/标准品报价，还是按定制报价？先不用选款，定制和成品的算法不一样。"
    return "这类产品我先需要确认一下，你这是按目录成品/标准品报价，还是按定制报价？先不用选款，定制和成品的算法不一样。"


def needs_child_bed_style(args: argparse.Namespace) -> bool:
    if has_explicit_product_identity(args):
        return False
    category = str(args.category or "").strip()
    if not category:
        return False
    if not (
        "儿童床" in category
        or "上下床" in category
        or "子母床" in category
        or "高架床" in category
    ):
        return False
    if not is_blank(args.series):
        return False
    return not any(keyword in category for keyword in CHILD_BED_STYLE_KEYWORDS)


def adult_bed_style_question(args: argparse.Namespace) -> str | None:
    if has_explicit_product_identity(args):
        return None
    category = str(args.category or "").strip()
    return ADULT_BED_STYLE_QUESTIONS.get(category)


def response(
    *,
    ready: bool,
    category_type: str,
    next_required_field: str | None,
    next_question: str | None,
    reason: str,
    assumed_defaults: list[dict[str, str]] | None = None,
    default_quote_profile: dict[str, Any] | None = None,
    approximate_only: bool = False,
    hard_block: bool = False,
) -> dict[str, Any]:
    if ready:
        quote_decision = "reference_quote" if approximate_only else "formal_quote"
    else:
        quote_decision = "hard_block" if hard_block else "ask_follow_up"
    payload = {
        "ready_for_formal_quote": ready,
        "category_type": category_type,
        "next_required_field": next_required_field,
        "next_question": next_question,
        "reason": reason,
        "quote_decision": quote_decision,
    }
    if assumed_defaults:
        payload["assumed_defaults"] = assumed_defaults
    if default_quote_profile:
        payload["default_quote_profile"] = default_quote_profile
    if not ready:
        payload["ask_only_this_question"] = True
        payload["do_not_list_style_options"] = True
        payload["do_not_list_prices"] = True
    return payload


def is_modular_child_bed_request(args: argparse.Namespace) -> bool:
    category = str(args.category or "").strip()
    if normalize_category_label(category) != "bed":
        return False
    if has_explicit_product_identity(args) and infer_quote_kind(args) != "custom":
        return False
    if any(keyword in category for keyword in {"半高床", "错层床"}):
        return True
    return infer_quote_kind(args) == "custom" and any(keyword in category for keyword in MODULAR_CHILD_BED_KEYWORDS)


def has_underbed_cabinet_request(args: argparse.Namespace) -> bool:
    fields = [
        "underbed_cabinet_mode",
        "front_cabinet_length",
        "front_cabinet_height",
        "front_cabinet_depth",
        "front_cabinet_mode",
        "rear_cabinet_length",
        "rear_cabinet_height",
        "rear_cabinet_depth",
        "rear_cabinet_mode",
    ]
    if any(not is_blank(str(getattr(args, field, "") or "").strip()) for field in fields):
        return True
    return bool(getattr(args, "interconnected_rows", False))


def bed_pricing_route(args: argparse.Namespace) -> str:
    if is_modular_child_bed_request(args):
        if has_underbed_cabinet_request(args):
            return "modular_child_bed_combo"
        return "modular_child_bed"
    category = str(args.category or "").strip()
    if any(keyword in category for keyword in MODULAR_CHILD_BED_KEYWORDS) and has_explicit_product_identity(args):
        return "catalog_child_bed"
    return "bed_standard"


def modular_child_bed_special_guardrail_included(args: argparse.Namespace) -> bool:
    bed_form = str(getattr(args, "bed_form", "") or "").strip()
    access_style = str(getattr(args, "access_style", "") or "").strip()
    guardrail_style = str(getattr(args, "guardrail_style", "") or "").strip()
    material = str(args.material or "").strip()
    width = parse_dimension_to_meters(args.width)
    length = parse_dimension_to_meters(args.length)
    if not all([bed_form, access_style, guardrail_style, material, width, length]):
        return False
    if material not in {"玫瑰木", "乌拉圭玫瑰木"}:
        return False
    if abs(length - 2.0) > 0.015 or all(abs(width - candidate) > 0.015 for candidate in (0.9, 1.2)):
        return False
    if bed_form == "上下床" and guardrail_style == "篱笆围栏" and access_style in {"直梯", "斜梯", "梯柜"}:
        return True
    if bed_form == "错层床" and guardrail_style == "城堡围栏":
        return True
    return False


def modular_child_bed_access_dimensions_required(args: argparse.Namespace) -> bool:
    return not modular_child_bed_special_guardrail_included(args)


def modular_child_bed_guardrail_dimensions_required(args: argparse.Namespace) -> bool:
    return not modular_child_bed_special_guardrail_included(args)


def modular_child_bed_guardrail_style_is_known(args: argparse.Namespace) -> bool:
    guardrail_style = str(getattr(args, "guardrail_style", "") or "").strip()
    if not guardrail_style:
        return False
    return guardrail_style in MODULAR_CHILD_BED_GUARDRAIL_STYLES


def precheck_modular_child_bed_combo(args: argparse.Namespace, responder) -> dict[str, Any]:
    for field_name, field_label in (
        ("front_cabinet_depth", "前排柜体进深"),
        ("rear_cabinet_depth", "后排柜体进深"),
    ):
        raw_value = str(getattr(args, field_name, "") or "").strip()
        parsed_depth = parse_dimension_to_meters(raw_value)
        if parsed_depth is not None and parsed_depth > 0.45:
            row_label = "前排" if field_name.startswith("front_") else "后排"
            return responder(
                ready=False,
                next_required_field=field_name,
                next_question=f"{row_label}柜体当前只支持单排进深不大于 450mm 的组合报价；你这个进深已经超出范围，当前不能直接正式报价。如果要继续，我建议先把{row_label}进深调整到 450mm 以内。",
                reason=f"{field_label} exceeds the supported 450mm combo limit",
                hard_block=True,
            )

    base_result = precheck_modular_child_bed(args, responder)
    if not base_result.get("ready_for_formal_quote"):
        return base_result

    bed_form = str(getattr(args, "bed_form", "") or "").strip()
    if bed_form not in {"半高床", "高架床"}:
        return responder(
            ready=False,
            next_required_field="bed_form",
            next_question="床下组合柜体这条路径当前只支持半高床或高架床，请先确认这次具体是半高床还是高架床。",
            reason="under-bed combo pricing currently supports half loft and loft beds only",
        )

    row_specs = [
        ("front_cabinet_length", "前排柜体长度", "床下前排柜体我还需要确认长度，请问大概做多长？"),
        ("front_cabinet_height", "前排柜体高度", "床下前排柜体我还需要确认高度，请问大概做多高？"),
        ("front_cabinet_mode", "前排柜体结构", "床下前排柜体我还需要确认结构，请问是无门无背板、有门无背板，还是无门有背板？"),
        ("front_cabinet_depth", "前排柜体进深", "床下前排柜体我还需要确认进深，请问前排大概做多深？"),
        ("rear_cabinet_length", "后排柜体长度", "床下后排柜体我还需要确认长度，请问大概做多长？"),
        ("rear_cabinet_height", "后排柜体高度", "床下后排柜体我还需要确认高度，请问大概做多高？"),
        ("rear_cabinet_mode", "后排柜体结构", "床下后排柜体我还需要确认结构，请问是无门无背板、有门无背板，还是无门有背板？"),
        ("rear_cabinet_depth", "后排柜体进深", "床下后排柜体我还需要确认进深，请问后排大概做多深？"),
    ]

    has_front = any(
        not is_blank(str(getattr(args, field, "") or "").strip())
        for field in ("front_cabinet_length", "front_cabinet_height", "front_cabinet_depth", "front_cabinet_mode")
    )
    has_rear = any(
        not is_blank(str(getattr(args, field, "") or "").strip())
        for field in ("rear_cabinet_length", "rear_cabinet_height", "rear_cabinet_depth", "rear_cabinet_mode")
    )
    if not has_front and not has_rear:
        return responder(
            ready=False,
            next_required_field="front_cabinet_length",
            next_question="如果床下要一起按组合柜体报价，我还需要先确认前排柜体尺寸和结构。请先告诉我前排衣柜的长度、高度、进深，以及是无门无背板、有门无背板还是无门有背板。",
            reason="under-bed combo pricing requires at least one cabinet row",
        )

    for field_name, field_label, question in row_specs:
        value = str(getattr(args, field_name, "") or "").strip()
        row_prefix = field_name.split("_", 1)[0]
        if row_prefix == "rear" and not has_rear:
            continue
        if not value:
            return responder(
                ready=False,
                next_required_field=field_name,
                next_question=question,
                reason=f"{field_label} is required for under-bed combo pricing",
            )

    front_mode = str(getattr(args, "front_cabinet_mode", "") or "").strip()
    rear_mode = str(getattr(args, "rear_cabinet_mode", "") or "").strip()
    if front_mode and front_mode not in UNDERBED_CABINET_MODES:
        return responder(
            ready=False,
            next_required_field="front_cabinet_mode",
            next_question="床下前排柜体当前请先对应成标准结构名称：无门无背板、有门无背板，或无门有背板。",
            reason="front under-bed cabinet mode must map to a supported structure",
        )
    if has_rear and rear_mode and rear_mode not in UNDERBED_CABINET_MODES:
        return responder(
            ready=False,
            next_required_field="rear_cabinet_mode",
            next_question="床下后排柜体当前请先对应成标准结构名称：无门无背板、有门无背板，或无门有背板。",
            reason="rear under-bed cabinet mode must map to a supported structure",
        )

    return responder(
        ready=True,
        next_required_field=None,
        next_question=None,
        reason="modular child bed combo intake has the required fields for a formal quote",
    )


def precheck_modular_child_bed(args: argparse.Namespace, responder) -> dict[str, Any]:
    bed_form = str(getattr(args, "bed_form", "") or "").strip()
    access_style = str(getattr(args, "access_style", "") or "").strip()
    lower_bed_type = str(getattr(args, "lower_bed_type", "") or "").strip()
    guardrail_style = str(getattr(args, "guardrail_style", "") or "").strip()
    guardrail_length = str(getattr(args, "guardrail_length", "") or "").strip()
    guardrail_height = str(getattr(args, "guardrail_height", "") or "").strip()
    access_height = str(getattr(args, "access_height", "") or "").strip()
    stair_width = str(getattr(args, "stair_width", "") or "").strip()
    stair_depth = str(getattr(args, "stair_depth", "") or "").strip()

    if not bed_form:
        return responder(
            ready=False,
            next_required_field="bed_form",
            next_question="这次如果按模块化儿童床报价，我还需要先确认床形态：上下床、半高床、高架床还是错层床？",
            reason="modular child bed requires bed form before pricing",
        )
    if not access_style:
        return responder(
            ready=False,
            next_required_field="access_style",
            next_question="模块化儿童床我还需要确认上层出入方式，你想做直梯、斜梯还是梯柜？",
            reason="modular child bed requires access style before size confirmation",
        )
    if is_blank(args.width):
        return responder(
            ready=False,
            next_required_field="width",
            next_question="模块化儿童床我先需要确认床垫宽度，请问是多宽？",
            reason="modular child bed requires mattress width",
        )
    if is_blank(args.length):
        return responder(
            ready=False,
            next_required_field="length",
            next_question="模块化儿童床我还需要确认床垫长度，请问是多长？",
            reason="modular child bed requires mattress length",
        )
    width_value = parse_dimension_to_meters(args.width)
    if bed_form in {"半高床", "高架床"} and width_value is not None and width_value > 1.2:
        return responder(
            ready=False,
            next_required_field="width",
            next_question="这类上铺或高架床当前只支持床垫宽度不大于 1.2 米；你这个宽度已经超出范围，所以现在不能直接正式报价。如果要继续，我建议先确认是否能调整到 1.2 米以内。",
            reason="upper-bed width exceeds the supported 1.2m limit",
            hard_block=True,
        )
    if bed_form in {"上下床", "错层床"} and not lower_bed_type:
        return responder(
            ready=False,
            next_required_field="lower_bed_type",
            next_question="这次模块化儿童床我还需要确认下层结构，你想做架式床还是箱体床？",
            reason="modular bunk-style beds require lower bed structure",
        )
    if is_blank(args.material):
        return responder(
            ready=False,
            next_required_field="material",
            next_question="模块化儿童床我还需要确认材质，你想用哪种木材？",
            reason="modular child bed requires material",
        )
    if not guardrail_style:
        return responder(
            ready=False,
            next_required_field="guardrail_style",
            next_question="模块化儿童床我还需要确认围栏样式，你想做哪种围栏？例如篱笆围栏、胶囊围栏、城堡围栏。",
            reason="modular child bed requires guardrail style",
        )
    if not modular_child_bed_guardrail_style_is_known(args):
        return responder(
            ready=False,
            next_required_field="guardrail_style",
            next_question="你说的这个护栏款式我这边还需要先对应到标准围栏名称。请确认是胶囊围栏、蘑菇围栏、田园围栏、篱笆围栏、圆柱围栏、方圆围栏还是城堡围栏。",
            reason="modular child bed requires a supported standard guardrail style before pricing",
        )
    if modular_child_bed_guardrail_dimensions_required(args):
        if not guardrail_length:
            return responder(
                ready=False,
                next_required_field="guardrail_length",
                next_question="这个围栏我还需要确认长度，请问围栏总长度大概多少？",
                reason="generic modular guardrail requires length",
            )
        if not guardrail_height:
            return responder(
                ready=False,
                next_required_field="guardrail_height",
                next_question="这个围栏我还需要确认高度，请问围栏高度大概多少？",
                reason="generic modular guardrail requires height",
            )
    if access_style in {"直梯", "斜梯"} and modular_child_bed_access_dimensions_required(args) and not access_height:
        return responder(
            ready=False,
            next_required_field="access_height",
            next_question="这个梯子我还需要确认垂直高度，请问上下床间距或实际垂直高度大概多少？",
            reason="generic ladder pricing requires vertical height",
        )
    if access_style == "梯柜" and modular_child_bed_access_dimensions_required(args):
        if not stair_width:
            return responder(
                ready=False,
                next_required_field="stair_width",
                next_question="这个梯柜我还需要确认踏步宽度，请问大概是 450-500mm，还是 500-600mm 这一档？",
                reason="generic stair cabinet pricing requires width band",
            )
        if not stair_depth:
            return responder(
                ready=False,
                next_required_field="stair_depth",
                next_question="这个梯柜我还需要确认进深，请问大概做多深？",
                reason="generic stair cabinet pricing requires depth",
            )
    return responder(
        ready=True,
        next_required_field=None,
        next_question=None,
        reason="modular child bed intake has the required fields for a formal quote",
    )


def precheck_cabinet(args: argparse.Namespace) -> dict[str, Any]:
    default_context = resolve_cabinet_default_context(args)
    explicit_product = has_explicit_product_identity(args)
    if needs_quote_kind_confirmation(args, "cabinet"):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="quote_kind",
            next_question=quote_kind_question("cabinet"),
            reason="cabinet requires standard-vs-custom path before final pricing path",
        )
    if explicit_product and has_unique_standard_catalog_variant(args):
        if is_blank(args.material):
            return response(
                ready=False,
                category_type="cabinet",
                next_required_field="material",
                next_question="这类柜体我还需要确认材质，你想用哪种木材？",
                reason="standard single-variant cabinet still requires material before formal quote",
            )
        return response(
            ready=True,
            category_type="cabinet",
            next_required_field=None,
            next_question=None,
            reason="cabinet explicit product matches a unique standard catalog variant",
            approximate_only=bool(getattr(args, "approximate_only", False)),
        )
    if is_blank(args.length):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="length",
            next_question="这类柜体我先需要确认长度，请问大概做多长？",
            reason="cabinet requires length before formal quote",
        )
    if is_blank(args.depth) and not (default_context and default_context["mode"] == "explicit_product"):
        if default_context and default_context["mode"] == "generic_profile":
            return response(
                ready=True,
                category_type="cabinet",
                next_required_field=None,
                next_question=None,
                reason="generic cabinet quote can use the category default baseline profile",
                assumed_defaults=default_context["assumed_defaults"],
                default_quote_profile=default_context["default_quote_profile"],
                approximate_only=bool(getattr(args, "approximate_only", False)),
            )
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="depth",
            next_question="这类柜体我先需要确认进深，请问大概做多深？",
            reason="cabinet requires depth before formal quote and before asking style",
        )
    if is_blank(args.height):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="height",
            next_question="这类柜体我还需要确认高度，请问大概做多高？",
            reason="cabinet requires height before formal quote",
        )
    if is_blank(args.material):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="material",
            next_question="这类柜体我还需要确认材质，你想用哪种木材？",
            reason="cabinet requires material before formal quote",
        )
    if default_context and default_context["mode"] == "generic_profile":
        return response(
            ready=True,
            category_type="cabinet",
            next_required_field=None,
            next_question=None,
            reason="generic cabinet quote can use the category default baseline profile",
            assumed_defaults=default_context["assumed_defaults"],
            default_quote_profile=default_context["default_quote_profile"],
            approximate_only=bool(getattr(args, "approximate_only", False)),
        )
    if is_diamond_cabinet_request(args) and is_blank(args.shape):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="shape",
            next_question="这个钻石柜我还需要确认一下结构关系：钻石柜这部分和旁边柜体是同类型吗？比如都开放，或都带门；如果不是，请直接告诉我是钻石柜开放、旁边带门，还是相反。",
            reason="diamond cabinet requires structure relationship before formal quote",
        )
    if explicit_cabinet_variant_requires_door_type(args) and is_blank(args.door_type):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="door_type",
            next_question="这款玄关柜我还需要确认门型，你想做平板门、真格栅门，还是其他明确门型？",
            reason="explicit cabinet product still has multiple door-type variants",
        )
    if not explicit_product and args.has_door == "unknown" and is_blank(args.door_type):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="has_door",
            next_question="这组柜体你是做带门还是不带门？",
            reason="cabinet requires door path before asking series",
        )
    if not explicit_product and args.has_door == "yes" and is_blank(args.door_type):
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="door_type",
            next_question="门型我还需要确认一下，你想做平板门、拼框门、铝框门还是其他门型？",
            reason="cabinet requires door type before asking series",
        )
    if is_blank(args.series) and not explicit_product:
        return response(
            ready=False,
            category_type="cabinet",
            next_required_field="series",
            next_question="在进深和门型确认后，如果你已经有目标款式，可以告诉我系列或款式名；没有的话我也可以按常规路径先给你参考报价。",
            reason="series is asked only after cabinet dimensions and door path are known",
        )
    return response(
        ready=True,
        category_type="cabinet",
        next_required_field=None,
        next_question=None,
        reason="cabinet intake has the required fields for a formal quote",
        assumed_defaults=default_context["assumed_defaults"] if default_context else None,
        default_quote_profile=default_context["default_quote_profile"] if default_context else None,
        approximate_only=bool(getattr(args, "approximate_only", False)),
    )


def precheck_bed(args: argparse.Namespace) -> dict[str, Any]:
    pricing_route = bed_pricing_route(args)

    def bed_response(
        *,
        ready: bool,
        next_required_field: str | None,
        next_question: str | None,
        reason: str,
        hard_block: bool = False,
    ) -> dict[str, Any]:
        payload = response(
            ready=ready,
            category_type="bed",
            next_required_field=next_required_field,
            next_question=next_question,
            reason=reason,
            approximate_only=bool(getattr(args, "approximate_only", False)),
            hard_block=hard_block,
        )
        payload["pricing_route"] = pricing_route
        return payload

    if pricing_route == "modular_child_bed":
        return precheck_modular_child_bed(args, bed_response)
    if pricing_route == "modular_child_bed_combo":
        return precheck_modular_child_bed_combo(args, bed_response)

    adult_style_question = adult_bed_style_question(args)
    if adult_style_question:
        return bed_response(
            ready=False,
            next_required_field="series",
            next_question=adult_style_question,
            reason="generic adult bed requires explicit style before formal quote",
        )
    if needs_quote_kind_confirmation(args, "bed"):
        return bed_response(
            ready=False,
            next_required_field="quote_kind",
            next_question=quote_kind_question("bed"),
            reason="bed requires standard-vs-custom path before size-based pricing",
        )
    if needs_child_bed_style(args):
        return bed_response(
            ready=False,
            next_required_field="series",
            next_question="儿童床我还需要先确认床型，先不用看价格。若是上下床，请明确是挂梯款还是梯柜款（梯柜下可储物）；也可以直接告诉我具体正式款式名，例如经典挂梯上下床、经典梯柜上下床、城堡挂梯上下床（落地直梯）等。",
            reason="child bed requires style before formal quote",
        )
    if child_bed_variant_is_ambiguous(args):
        return bed_response(
            ready=False,
            next_required_field="shape",
            next_question="这款上下床我还需要确认下床结构，你想做抽屉款、架式款还是箱体款？",
            reason="explicit child bunk bed still has multiple lower-bed structure variants",
        )
    if is_blank(args.width):
        return bed_response(
            ready=False,
            next_required_field="width",
            next_question="床类我先需要确认床垫宽度或床宽，请问是多宽？",
            reason="bed requires width",
        )
    if is_blank(args.length):
        return bed_response(
            ready=False,
            next_required_field="length",
            next_question="床类我还需要确认长度，请问是多长？",
            reason="bed requires length",
        )
    if is_blank(args.material):
        return bed_response(
            ready=False,
            next_required_field="material",
            next_question="床类我还需要确认材质，你想用哪种木材？",
            reason="bed requires material",
        )
    return bed_response(
        ready=True,
        next_required_field=None,
        next_question=None,
        reason="bed intake has the required fields for a formal quote",
    )


def precheck_tatami(args: argparse.Namespace) -> dict[str, Any]:
    if is_blank(args.width):
        return response(
            ready=False,
            category_type="tatami",
            next_required_field="width",
            next_question="榻榻米我先需要确认宽度，请问大概多宽？",
            reason="tatami requires width",
        )
    if is_blank(args.length):
        return response(
            ready=False,
            category_type="tatami",
            next_required_field="length",
            next_question="榻榻米我还需要确认长度，请问大概多长？",
            reason="tatami requires length",
        )
    if is_blank(args.height):
        return response(
            ready=False,
            category_type="tatami",
            next_required_field="height",
            next_question="榻榻米我还需要确认高度，请问大概多高？",
            reason="tatami requires height for pricing band",
        )
    if is_blank(args.material):
        return response(
            ready=False,
            category_type="tatami",
            next_required_field="material",
            next_question="榻榻米我还需要确认材质，你想用哪种木材？",
            reason="tatami requires material",
        )
    return response(
        ready=True,
        category_type="tatami",
        next_required_field=None,
        next_question=None,
        reason="tatami intake has the required fields for a formal quote",
        approximate_only=bool(getattr(args, "approximate_only", False)),
    )


def precheck_table(args: argparse.Namespace) -> dict[str, Any]:
    if needs_quote_kind_confirmation(args, "table"):
        return response(
            ready=False,
            category_type="table",
            next_required_field="quote_kind",
            next_question=quote_kind_question("table"),
            reason="table requires standard-vs-custom path before size-based pricing",
        )
    if is_blank(args.length):
        return response(
            ready=False,
            category_type="table",
            next_required_field="length",
            next_question="桌类我先需要确认长度，请问大概多长？",
            reason="table requires length",
        )
    if is_blank(args.depth) and not has_matching_standard_catalog_variant(args):
        return response(
            ready=False,
            category_type="table",
            next_required_field="depth",
            next_question="桌类我还需要确认进深或台面宽度，请问大概多深？",
            reason="table requires depth",
        )
    if ("书桌柜" in args.category or "转角书桌柜" in args.category) and is_blank(args.height):
        return response(
            ready=False,
            category_type="table",
            next_required_field="height",
            next_question="书桌柜我还需要确认总高度，请问大概做多高？",
            reason="desk cabinet requires height for cabinet portion",
        )
    if is_blank(args.material):
        return response(
            ready=False,
            category_type="table",
            next_required_field="material",
            next_question="桌类我还需要确认材质，你想用哪种木材？",
            reason="table requires material",
        )
    return response(
        ready=True,
        category_type="table",
        next_required_field=None,
        next_question=None,
        reason="table intake has the required fields for a formal quote",
        approximate_only=bool(getattr(args, "approximate_only", False)),
    )


def precheck_generic(args: argparse.Namespace) -> dict[str, Any]:
    for field, question in [
        ("category", "我先需要确认你做的是哪一类产品。"),
        ("material", "我还需要确认材质，你想用哪种木材？"),
    ]:
        value = args.category if field == "category" else args.material
        if is_blank(value):
            return response(
                ready=False,
                category_type="generic",
                next_required_field=field,
                next_question=question,
                reason=f"generic quote requires {field}",
            )
    return response(
        ready=True,
        category_type="generic",
        next_required_field=None,
        next_question=None,
        reason="generic intake has the required fields for further pricing",
        approximate_only=bool(getattr(args, "approximate_only", False)),
    )


def main() -> int:
    args = parse_args()
    category_type = normalize_category(args)
    if category_type == "cabinet":
        result = precheck_cabinet(args)
    elif category_type == "bed":
        result = precheck_bed(args)
    elif category_type == "tatami":
        result = precheck_tatami(args)
    elif category_type == "table":
        result = precheck_table(args)
    else:
        result = precheck_generic(args)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
