#!/usr/bin/env python3
"""Deterministic lookup for double-sided cabinet pricing (table 5)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from material_names import formalize_material_name, normalize_material_for_query


FAMILY_ORDER = {"frame": 0, "grid": 1, "flat": 2}
FAMILY_LABELS = {
    "frame": "拼框",
    "grid": "格栅",
    "flat": "平板",
}

DOUBLE_SIDED_PRICES = {
    "depth_lte_450": {
        "frame/grid": {"玫瑰木": 5860, "樱桃木": 6400, "白蜡木": 6400, "白橡木": 7400, "黑胡桃": 9110},
        "frame/flat": {"玫瑰木": 6260, "樱桃木": 6800, "白蜡木": 6800, "白橡木": 7960, "黑胡桃": 9710},
        "grid/flat": {"玫瑰木": 6460, "樱桃木": 7000, "白蜡木": 7000, "白橡木": 8180, "黑胡桃": 10110},
        "frame/frame": {"玫瑰木": 5660, "樱桃木": 6200, "白蜡木": 6200, "白橡木": 7180, "黑胡桃": 8810},
        "grid/grid": {"玫瑰木": 6060, "樱桃木": 6600, "白蜡木": 6600, "白橡木": 7660, "黑胡桃": 9510},
        "flat/flat": {"玫瑰木": 6660, "樱桃木": 7200, "白蜡木": 7200, "白橡木": 8500, "黑胡桃": 11010},
    },
    "450_lt_depth_lte_600": {
        "frame/grid": {"玫瑰木": 6360, "樱桃木": 6900, "白蜡木": 6900, "白橡木": 7960, "黑胡桃": 9810},
        "frame/flat": {"玫瑰木": 6760, "樱桃木": 7300, "白蜡木": 7300, "白橡木": 8500, "黑胡桃": 10410},
        "grid/flat": {"玫瑰木": 6960, "樱桃木": 7500, "白蜡木": 7500, "白橡木": 8760, "黑胡桃": 10810},
        "frame/frame": {"玫瑰木": 6160, "樱桃木": 6700, "白蜡木": 6700, "白橡木": 7760, "黑胡桃": 9510},
        "grid/grid": {"玫瑰木": 6560, "樱桃木": 7100, "白蜡木": 7100, "白橡木": 8180, "黑胡桃": 10210},
        "flat/flat": {"玫瑰木": 7160, "樱桃木": 7700, "白蜡木": 7700, "白橡木": 9060, "黑胡桃": 11710},
    },
}


def parse_dimension_to_meters(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("depth is required")
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


def normalize_combo(side_a_family: str, side_b_family: str) -> str:
    if side_a_family not in FAMILY_ORDER:
        raise ValueError(f"Unknown side_a_family: {side_a_family}")
    if side_b_family not in FAMILY_ORDER:
        raise ValueError(f"Unknown side_b_family: {side_b_family}")
    ordered = sorted([side_a_family, side_b_family], key=FAMILY_ORDER.get)
    return "/".join(ordered)


def resolve_depth_band(depth: str) -> str:
    value = parse_dimension_to_meters(depth)
    if value <= 0.45:
        return "depth_lte_450"
    if value <= 0.6:
        return "450_lt_depth_lte_600"
    raise ValueError("double-sided cabinet table 5 currently only covers depth up to 600mm")


def calculate_double_sided_price(
    *,
    material: str,
    depth: str,
    side_a_family: str,
    side_b_family: str,
) -> dict[str, object]:
    normalized_material = normalize_material_for_query(material)
    if not normalized_material:
        raise ValueError("material is required")

    depth_band = resolve_depth_band(depth)
    combo = normalize_combo(side_a_family, side_b_family)
    band_prices = DOUBLE_SIDED_PRICES[depth_band]
    combo_prices = band_prices.get(combo)
    if combo_prices is None:
        raise ValueError(f"Unsupported double-sided combo: {combo}")
    if normalized_material not in combo_prices:
        raise ValueError(f"Unsupported material: {material}")

    return {
        "material": formalize_material_name(normalized_material),
        "depth_band": depth_band,
        "door_combo": combo,
        "door_combo_label": f"{FAMILY_LABELS[combo.split('/')[0]]}/{FAMILY_LABELS[combo.split('/')[1]]}",
        "unit_price": combo_prices[normalized_material],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lookup double-sided cabinet unit price from table 5.")
    parser.add_argument("--material", required=True, help="Cabinet material.")
    parser.add_argument("--depth", required=True, help="Cabinet depth.")
    parser.add_argument("--side-a-family", required=True, choices=sorted(FAMILY_ORDER), help="Door family for side A.")
    parser.add_argument("--side-b-family", required=True, choices=sorted(FAMILY_ORDER), help="Door family for side B.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = calculate_double_sided_price(
        material=args.material,
        depth=args.depth,
        side_a_family=args.side_a_family,
        side_b_family=args.side_b_family,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
