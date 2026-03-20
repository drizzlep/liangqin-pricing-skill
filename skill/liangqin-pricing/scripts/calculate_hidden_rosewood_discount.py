#!/usr/bin/env python3
"""Calculate deterministic whole-cabinet discount for hidden rosewood surfaces."""

from __future__ import annotations

import argparse
import json
import sys

from material_names import formalize_material_name, normalize_material_for_query


DISCOUNT_RATES = {
    "黑胡桃": 0.15,
    "白橡木": 0.10,
    "樱桃木": 0.05,
    "白蜡木": 0.05,
}


def calculate_discount(*, exposed_material: str, base_unit_price: float) -> dict[str, object]:
    normalized_material = normalize_material_for_query(exposed_material)
    if normalized_material not in DISCOUNT_RATES:
        raise ValueError(f"Unsupported exposed material for hidden-rosewood discount: {exposed_material}")

    discount_rate = DISCOUNT_RATES[normalized_material]
    discount_factor = 1 - discount_rate
    adjusted_unit_price = float(base_unit_price) * discount_factor
    return {
        "exposed_material": formalize_material_name(normalized_material),
        "base_unit_price": float(base_unit_price),
        "discount_rate": discount_rate,
        "discount_factor": discount_factor,
        "adjusted_unit_price": adjusted_unit_price,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate hidden-rosewood whole-cabinet discount.")
    parser.add_argument("--exposed-material", required=True, help="Visible/exposed cabinet material.")
    parser.add_argument("--base-unit-price", required=True, type=float, help="Base cabinet unit price before discount.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = calculate_discount(
        exposed_material=args.exposed_material,
        base_unit_price=args.base_unit_price,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
