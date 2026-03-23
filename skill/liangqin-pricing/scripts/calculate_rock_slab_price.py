#!/usr/bin/env python3
"""Deterministic calculator for rock slab pricing scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from material_names import formalize_material_name, normalize_material_for_query


ROCK_SLAB_UNIT_PRICES = {
    "rock_slab_countertop": 1460.0,
    "rock_slab_backboard": 1460.0,
    "rock_slab_aluminum_frame_door": 1860.0,
}

SIDE_PANEL_UNIT_PRICES = {
    "玫瑰木": 1500.0,
    "樱桃木": 1538.0,
    "白蜡木": 1538.0,
    "白橡木": 1748.0,
    "黑胡桃": 2028.0,
}

SCENARIOS = tuple(ROCK_SLAB_UNIT_PRICES)


def parse_dimension_to_meters(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("dimension is required")
    text = (
        text.replace("平方米", "")
        .replace("平米", "")
        .replace("平方", "")
        .replace("m²", "")
        .replace("m2", "")
        .replace("㎡", "")
        .replace("毫米", "")
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


def parse_area_to_square_meters(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("side panel area is required")
    text = (
        text.replace("平方米", "")
        .replace("平米", "")
        .replace("平方", "")
        .replace("m²", "")
        .replace("m2", "")
        .replace("㎡", "")
    )
    return float(text)


def calculate_rock_slab_price(
    *,
    scenario: str,
    slab_length: Any,
    base_subtotal: float = 0.0,
    opening_height: Any | None = None,
    cabinet_material: str | None = None,
    side_panel_area: Any | None = None,
) -> dict[str, object]:
    if scenario not in ROCK_SLAB_UNIT_PRICES:
        raise ValueError(f"unsupported scenario: {scenario}")

    slab_length_m = parse_dimension_to_meters(slab_length)
    base_subtotal_value = round(float(base_subtotal), 2)
    rock_slab_addition = round(ROCK_SLAB_UNIT_PRICES[scenario] * slab_length_m, 2)
    side_panel_addition = 0.0
    normalized_material = normalize_material_for_query(cabinet_material)

    calculation_steps: list[str] = []
    if scenario == "rock_slab_aluminum_frame_door":
        calculation_steps.append(f"无门柜体基础价格 = {base_subtotal_value}")
    else:
        calculation_steps.append(f"基础柜体价格 = {base_subtotal_value}")

    if scenario == "rock_slab_countertop":
        calculation_steps.append(
            f"岩板台面加价 = {ROCK_SLAB_UNIT_PRICES[scenario]} × {slab_length_m} = {rock_slab_addition}"
        )
    elif scenario == "rock_slab_aluminum_frame_door":
        calculation_steps.append(
            f"铝框岩板门板加价 = {ROCK_SLAB_UNIT_PRICES[scenario]} × {slab_length_m} = {rock_slab_addition}"
        )
    else:
        calculation_steps.append(
            f"岩板背板加价 = {ROCK_SLAB_UNIT_PRICES[scenario]} × {slab_length_m} = {rock_slab_addition}"
        )
        if opening_height is None:
            raise ValueError("opening height is required for rock slab backboard")
        opening_height_m = parse_dimension_to_meters(opening_height)
        if opening_height_m >= 0.55:
            if not normalized_material:
                raise ValueError("cabinet material is required for rock slab backboard side panel pricing")
            if normalized_material not in SIDE_PANEL_UNIT_PRICES:
                raise ValueError(f"unsupported cabinet material: {cabinet_material}")
            if side_panel_area is None:
                raise ValueError("side panel area is required when opening height is at or above 55cm")
            side_panel_area_value = round(parse_area_to_square_meters(side_panel_area), 4)
            side_panel_unit_price = SIDE_PANEL_UNIT_PRICES[normalized_material]
            side_panel_addition = round(side_panel_area_value * side_panel_unit_price, 2)
            calculation_steps.append(
                f"超出侧板加价 = {side_panel_area_value} × {side_panel_unit_price} = {side_panel_addition}"
            )

    final_subtotal = round(base_subtotal_value + rock_slab_addition + side_panel_addition, 2)
    calculation_steps.append(
        f"小计 = {base_subtotal_value} + {rock_slab_addition} + {side_panel_addition} = {final_subtotal}"
    )

    return {
        "scenario": scenario,
        "base_subtotal": base_subtotal_value,
        "slab_length": slab_length_m,
        "rock_slab_addition": rock_slab_addition,
        "side_panel_addition": side_panel_addition,
        "final_subtotal": final_subtotal,
        "cabinet_material": formalize_material_name(normalized_material),
        "calculation_steps": calculation_steps,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate rock slab pricing scenarios.")
    parser.add_argument("--scenario", required=True, choices=SCENARIOS, help="Rock slab pricing scenario.")
    parser.add_argument("--slab-length", required=True, help="Rock slab length.")
    parser.add_argument("--base-subtotal", default=0, type=float, help="Base cabinet subtotal before rock slab additions.")
    parser.add_argument("--opening-height", help="Opening height for rock slab backboard.")
    parser.add_argument("--cabinet-material", help="Cabinet material for rock slab backboard side panel pricing.")
    parser.add_argument("--side-panel-area", help="Extra side panel area when opening height is at or above 55cm.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = calculate_rock_slab_price(
        scenario=args.scenario,
        slab_length=args.slab_length,
        base_subtotal=args.base_subtotal,
        opening_height=args.opening_height,
        cabinet_material=args.cabinet_material,
        side_panel_area=args.side_panel_area,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
