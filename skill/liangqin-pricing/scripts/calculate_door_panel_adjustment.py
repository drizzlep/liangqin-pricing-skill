#!/usr/bin/env python3
"""Calculate deterministic door-panel price adjustments for cabinet quotes."""

from __future__ import annotations

import argparse
import json
import sys

from material_names import formalize_material_name, normalize_material_for_query


DOOR_PANEL_UNIT_PRICES = {
    "frame": {
        "樱桃木": 1780,
        "白蜡木": 1780,
        "白橡木": 2080,
        "玫瑰木": 2280,
        "黑胡桃": 2980,
    },
    "flat": {
        "樱桃木": 2380,
        "白蜡木": 2380,
        "白橡木": 2980,
        "玫瑰木": 2280,
        "黑胡桃": 3880,
    },
}


def calculate_adjustment(
    *,
    cabinet_material: str,
    target_door_material: str,
    base_unit_price: float,
    cabinet_door_family: str,
    target_door_family: str,
) -> dict[str, object]:
    normalized_cabinet_material = normalize_material_for_query(cabinet_material)
    normalized_target_door_material = normalize_material_for_query(target_door_material)
    cabinet_prices = DOOR_PANEL_UNIT_PRICES.get(cabinet_door_family)
    target_prices = DOOR_PANEL_UNIT_PRICES.get(target_door_family)

    if not cabinet_prices:
        raise ValueError(f"Unknown cabinet door family: {cabinet_door_family}")
    if not target_prices:
        raise ValueError(f"Unknown target door family: {target_door_family}")
    if normalized_cabinet_material not in cabinet_prices:
        raise ValueError(f"Unknown cabinet material: {cabinet_material}")
    if normalized_target_door_material not in target_prices:
        raise ValueError(f"Unknown target door material: {target_door_material}")

    cabinet_door_unit_price = cabinet_prices[normalized_cabinet_material]
    target_door_unit_price = target_prices[normalized_target_door_material]
    door_unit_diff = target_door_unit_price - cabinet_door_unit_price
    adjusted_base_unit = float(base_unit_price) + door_unit_diff

    return {
        "cabinet_material": formalize_material_name(normalized_cabinet_material),
        "target_door_material": formalize_material_name(normalized_target_door_material),
        "base_unit_price": float(base_unit_price),
        "cabinet_door_family": cabinet_door_family,
        "target_door_family": target_door_family,
        "cabinet_door_unit_price": cabinet_door_unit_price,
        "target_door_unit_price": target_door_unit_price,
        "door_unit_diff": door_unit_diff,
        "adjusted_base_unit": adjusted_base_unit,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate cabinet door-panel price adjustment.")
    parser.add_argument("--cabinet-material", required=True, help="Cabinet/base material.")
    parser.add_argument("--target-door-material", required=True, help="Target door material.")
    parser.add_argument("--base-unit-price", required=True, type=float, help="Base cabinet unit price.")
    parser.add_argument("--cabinet-door-family", required=True, choices=sorted(DOOR_PANEL_UNIT_PRICES), help="Base door family.")
    parser.add_argument("--target-door-family", required=True, choices=sorted(DOOR_PANEL_UNIT_PRICES), help="Target door family.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = calculate_adjustment(
        cabinet_material=args.cabinet_material,
        target_door_material=args.target_door_material,
        base_unit_price=args.base_unit_price,
        cabinet_door_family=args.cabinet_door_family,
        target_door_family=args.target_door_family,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
