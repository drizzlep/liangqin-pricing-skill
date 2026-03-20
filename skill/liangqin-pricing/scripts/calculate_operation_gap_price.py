#!/usr/bin/env python3
"""Deterministic calculator for operation-gap/backboard area pricing (table 6)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from material_names import formalize_material_name, normalize_material_for_query


TABLE_SIX_PRICES = {
    "玫瑰木": 1235,
    "樱桃木": 1326,
    "白蜡木": 1326,
    "白橡木": 1630,
    "黑胡桃": 2002,
}


def parse_dimension_to_meters(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("dimension is required")
    text = (
        text.replace("毫米", "")
        .replace("mm", "")
        .replace("厘米", "")
        .replace("cm", "")
        .replace("米", "")
        .replace("m", "")
    )
    number = float(text)
    if number > 10:
        return number / 1000
    return number


def calculate_operation_gap_price(
    *,
    material: str,
    width: str,
    height: str,
    luminous_backboard: bool = False,
    custom_pattern: bool = False,
) -> dict[str, object]:
    normalized_material = normalize_material_for_query(material)
    if not normalized_material:
        raise ValueError("material is required")
    if normalized_material not in TABLE_SIX_PRICES:
        raise ValueError(f"unsupported material: {material}")

    area = round(parse_dimension_to_meters(width) * parse_dimension_to_meters(height), 4)
    unit_price = TABLE_SIX_PRICES["白橡木"] if luminous_backboard else TABLE_SIX_PRICES[normalized_material]
    pattern_addition = 200 if custom_pattern else 0
    adjusted_unit_price = unit_price + pattern_addition
    subtotal = round(area * adjusted_unit_price, 2)

    return {
        "material": formalize_material_name(normalized_material),
        "area": area,
        "unit_price": unit_price,
        "pattern_addition": pattern_addition,
        "adjusted_unit_price": adjusted_unit_price,
        "subtotal": subtotal,
        "luminous_backboard": luminous_backboard,
        "custom_pattern": custom_pattern,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate operation-gap/backboard area pricing.")
    parser.add_argument("--material", required=True, help="Gap/backboard material.")
    parser.add_argument("--width", required=True, help="Gap width.")
    parser.add_argument("--height", required=True, help="Gap height.")
    parser.add_argument("--luminous-backboard", action="store_true", help="Whether this is a luminous backboard.")
    parser.add_argument("--custom-pattern", action="store_true", help="Whether a custom pattern adds 200/m².")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = calculate_operation_gap_price(
        material=args.material,
        width=args.width,
        height=args.height,
        luminous_backboard=args.luminous_backboard,
        custom_pattern=args.custom_pattern,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
