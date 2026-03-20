#!/usr/bin/env python3
"""Query the normalized Liangqin price index."""

from __future__ import annotations

import argparse
import json
import sys
from math import isclose
from pathlib import Path
from typing import Any

from material_names import formalize_material_name, formalize_materials, formalize_text, normalize_material_for_query


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Liangqin price index records.")
    parser.add_argument(
        "--index",
        default=str(Path(__file__).resolve().parent.parent / "data" / "current" / "price-index.json"),
        help="Path to price-index.json.",
    )
    parser.add_argument("--sheet", help="Exact sheet/category name.")
    parser.add_argument("--product-code", help="Exact product code.")
    parser.add_argument("--name-exact", help="Exact match on product name.")
    parser.add_argument("--name-contains", help="Substring match on product name.")
    parser.add_argument("--group-contains", help="Substring match on group/series label.")
    parser.add_argument("--remark-contains", help="Substring match on remark.")
    parser.add_argument("--series", help="Substring match on normalized series name.")
    parser.add_argument("--door-type", help="Substring match on normalized door type.")
    parser.add_argument("--has-door", choices=["yes", "no", "unknown"], help="Filter by normalized has_door flag.")
    parser.add_argument("--pricing-mode", help="Exact pricing mode such as projection_area or unit_price.")
    parser.add_argument(
        "--quote-kind",
        choices=["standard", "custom"],
        help="Convenience filter. standard prefers unit-price style records; custom prefers projection-area style records.",
    )
    parser.add_argument("--record-kind", help="Exact record kind such as price, guidance_note, status_note.")
    parser.add_argument("--variant-tag", action="append", default=[], help="Require a variant tag. Can be passed multiple times.")
    parser.add_argument("--length", help="Match a specific length dimension.")
    parser.add_argument("--depth", help="Match a specific depth dimension.")
    parser.add_argument("--height", help="Match a specific height dimension.")
    parser.add_argument("--width", help="Match a specific width dimension.")
    parser.add_argument("--material", help="Material column to display.")
    parser.add_argument("--include-dimensions", action="store_true", help="Include catalog/sample dimensions in the output.")
    parser.add_argument("--include-non-queryable", action="store_true", help="Include non-queryable rows such as notes or deprecated items.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of records to return.")
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def contains(value: str | None, needle: str | None) -> bool:
    if not needle:
        return True
    if not value:
        return False
    return needle.lower() in value.lower()


def exact_match(value: str | None, target: str | None) -> bool:
    if not target:
        return True
    if not value:
        return False
    return value.strip().lower() == target.strip().lower()


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


def record_matches(record: dict[str, Any], args: argparse.Namespace) -> bool:
    if not args.include_non_queryable and not record.get("is_queryable", False):
        return False
    if args.sheet and record.get("sheet") != args.sheet:
        return False
    if args.product_code and record.get("product_code") != args.product_code:
        return False
    if args.pricing_mode and record.get("pricing_mode") != args.pricing_mode:
        return False
    if args.quote_kind == "standard" and record.get("pricing_mode") not in {"unit_price", "per_item", "mixed"}:
        return False
    if args.quote_kind == "custom" and record.get("pricing_mode") not in {"projection_area"}:
        return False
    if args.record_kind and record.get("record_kind") != args.record_kind:
        return False
    if args.has_door and record.get("has_door") != args.has_door:
        return False
    if not exact_match(record.get("name"), args.name_exact):
        return False
    if not contains(record.get("name"), args.name_contains):
        return False
    if not contains(record.get("group"), args.group_contains):
        return False
    if not contains(record.get("remark"), args.remark_contains):
        return False
    if not contains(record.get("series"), args.series):
        return False
    if not contains(record.get("door_type"), args.door_type):
        return False
    variant_tags = record.get("variant_tags", [])
    for required_tag in args.variant_tag:
        if required_tag not in variant_tags:
            return False
    dimensions = record.get("dimensions") or {}
    for field_name in ["length", "depth", "height", "width"]:
        expected = parse_dimension_to_meters(getattr(args, field_name, None))
        if expected is None:
            continue
        actual = parse_dimension_to_meters(dimensions.get(field_name))
        if actual is None or not isclose(actual, expected, abs_tol=0.015):
            return False
    return True


def project_record(record: dict[str, Any], material: str | None) -> dict[str, Any]:
    base = {
        "sheet": record.get("sheet"),
        "group": record.get("group"),
        "product_code": record.get("product_code"),
        "name": record.get("name"),
        "series": record.get("series"),
        "variant_tags": record.get("variant_tags"),
        "door_type": record.get("door_type"),
        "has_door": record.get("has_door"),
        "remark": formalize_text(record.get("remark")),
        "pricing_mode": record.get("pricing_mode"),
        "record_kind": record.get("record_kind"),
        "is_queryable": record.get("is_queryable"),
        "is_deprecated": record.get("is_deprecated"),
        "notes": record.get("notes"),
    }
    if material:
        internal_material = normalize_material_for_query(material)
        base["material"] = formalize_material_name(internal_material)
        base["value"] = record.get("materials", {}).get(internal_material)
        return base
    base["materials"] = formalize_materials(record.get("materials"))
    return base


def main() -> int:
    args = parse_args()
    args.material = normalize_material_for_query(args.material)
    index_path = Path(args.index).expanduser().resolve()
    payload = load_payload(index_path)
    records = payload.get("records", [])
    matched = [record for record in records if record_matches(record, args)]
    output = [project_record(record, args.material) for record in matched[: args.limit]]
    if args.include_dimensions:
        for projected, source in zip(output, matched[: args.limit], strict=False):
            projected["dimensions"] = source.get("dimensions")

    response = {
        "count": len(output),
        "matched_total": len(matched),
        "filters": {
            "sheet": args.sheet,
            "product_code": args.product_code,
        "name_contains": args.name_contains,
        "name_exact": args.name_exact,
        "group_contains": args.group_contains,
            "remark_contains": args.remark_contains,
            "series": args.series,
            "door_type": args.door_type,
            "has_door": args.has_door,
            "pricing_mode": args.pricing_mode,
            "quote_kind": args.quote_kind,
            "record_kind": args.record_kind,
        "variant_tag": args.variant_tag,
        "length": args.length,
        "depth": args.depth,
        "height": args.height,
        "width": args.width,
        "include_dimensions": args.include_dimensions,
            "include_non_queryable": args.include_non_queryable,
            "material": formalize_material_name(args.material),
        },
        "records": output,
    }
    json.dump(response, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
