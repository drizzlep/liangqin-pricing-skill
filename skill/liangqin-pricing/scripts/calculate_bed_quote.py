#!/usr/bin/env python3
"""Deterministic calculator for adult bed pricing rules."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from material_names import formalize_material_name, normalize_material_for_query


CURRENT_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "current" / "price-index.json"
TOLERANCE = Decimal("0.015")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate Liangqin adult bed pricing rules deterministically.")
    parser.add_argument("--name-exact", required=True, help="Exact bed product name.")
    parser.add_argument("--material", required=True, help="Target material.")
    parser.add_argument("--width", required=True, help="Bed width or mattress width.")
    parser.add_argument("--length", required=True, help="Bed length.")
    parser.add_argument("--raise-height", action="store_true", help="Whether the bed height should be increased.")
    parser.add_argument(
        "--index",
        default=str(CURRENT_INDEX_PATH),
        help="Path to price-index.json.",
    )
    return parser.parse_args()


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_formal_total(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_dimension(value: Any) -> Decimal:
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
    number = Decimal(text)
    if number > 10:
        return quantize_money(number / Decimal("1000"))
    return quantize_money(number)


def load_payload(index_path: str | Path) -> dict[str, Any]:
    path = Path(index_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def decimal_close(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= TOLERANCE


def load_bed_records(index_path: str | Path, name_exact: str) -> list[dict[str, Any]]:
    payload = load_payload(index_path)
    records = []
    for record in payload.get("records", []):
        if not record.get("is_queryable", False):
            continue
        if record.get("record_kind") != "price":
            continue
        if record.get("pricing_mode") != "unit_price":
            continue
        if str(record.get("name") or "").strip() != name_exact:
            continue
        records.append(record)
    if not records:
        raise ValueError(f"未找到产品：{name_exact}")
    return records


def record_price(record: dict[str, Any], material: str) -> Decimal:
    materials = record.get("materials") or {}
    value = materials.get(material)
    if value is None:
        raise ValueError(f"产品缺少材质价格：{material}")
    return quantize_money(Decimal(str(value)))


def width_value(record: dict[str, Any]) -> Decimal | None:
    width = (record.get("dimensions") or {}).get("width")
    if width is None:
        return None
    return parse_dimension(width)


def find_record_by_width(records: list[dict[str, Any]], target_width: Decimal) -> dict[str, Any] | None:
    for record in records:
        current_width = width_value(record)
        if decimal_close(current_width, target_width):
            return record
    return None


def normalize_length(length: Decimal) -> tuple[Decimal, str | None]:
    if decimal_close(length, Decimal("1.9")):
        return Decimal("2.00"), "床垫长度 1.9 米按 2 米标准尺寸处理"
    return length, None


def calculate_bed_quote(
    *,
    name_exact: str,
    material: str,
    width: str,
    length: str,
    raise_height: bool = False,
    index_path: str | Path = CURRENT_INDEX_PATH,
) -> dict[str, Any]:
    internal_material = normalize_material_for_query(material)
    if not internal_material:
        raise ValueError("material is required")

    parsed_width = parse_dimension(width)
    parsed_length = parse_dimension(length)
    normalized_length, length_note = normalize_length(parsed_length)
    records = load_bed_records(index_path, name_exact)

    record_15 = find_record_by_width(records, Decimal("1.50"))
    record_18 = find_record_by_width(records, Decimal("1.80"))
    if record_15 is None:
        raise ValueError(f"{name_exact} 缺少 1.5 米标准价，无法按床类规则计算")

    base_price_15 = record_price(record_15, internal_material)
    base_price_18 = record_price(record_18, internal_material) if record_18 else None

    steps: list[str] = []
    if length_note:
        steps.append(length_note)

    if normalized_length > Decimal("2.00") + TOLERANCE or parsed_width > Decimal("1.80") + TOLERANCE:
        long_side = max(parsed_width, normalized_length)
        final_price = quantize_money((base_price_15 / Decimal("1.5")) * long_side)
        steps.extend(
            [
                f"超大床按 1.5 米标准价按比例计算",
                f"1.5 米基础价：{base_price_15} 元",
                f"按比例价格：{base_price_15} ÷ 1.5 × {quantize_money(long_side)} = {final_price} 元",
            ]
        )
        pricing_rule = "oversize_proportion"
        base_price = base_price_15
    elif parsed_width <= Decimal("1.20") + TOLERANCE:
        record_12 = find_record_by_width(records, Decimal("1.20"))
        if record_12 is not None:
            final_price = record_price(record_12, internal_material)
            steps.append(f"1.2 米及以下按 1.2 米标准价：{final_price} 元")
        else:
            if base_price_18 is None:
                raise ValueError(f"{name_exact} 缺少 1.8 米标准价，无法反推 1.2 米价格")
            gap = quantize_money(base_price_18 - base_price_15)
            final_price = quantize_money(base_price_15 - gap)
            steps.extend(
                [
                    "目录无 1.2 米标准价，按规则用 1.5 米价减去 1.8 米与 1.5 米价差",
                    f"1.2 米价格：{base_price_15} - ({base_price_18} - {base_price_15}) = {final_price} 元",
                ]
            )
        pricing_rule = "standard_width_1_2"
        base_price = final_price
    elif parsed_width <= Decimal("1.50") + TOLERANCE:
        final_price = base_price_15
        pricing_rule = "standard_width_1_5"
        base_price = base_price_15
        steps.append(f"床宽按 1.5 米标准价：{final_price} 元")
    else:
        if base_price_18 is None:
            raise ValueError(f"{name_exact} 缺少 1.8 米标准价，无法按 1.8 米标准尺寸计算")
        final_price = base_price_18
        pricing_rule = "standard_width_1_8"
        base_price = base_price_18
        steps.append(f"床宽按 1.8 米标准价：{final_price} 元")

    height_markup_amount = Decimal("0.00")
    if raise_height:
        height_markup_amount = quantize_money(final_price * Decimal("0.15"))
        steps.extend(
            [
                "床体加高按整床价格加收 15%",
                f"加高金额：{final_price} × 15% = {height_markup_amount} 元",
            ]
        )
        final_price = quantize_money(final_price + height_markup_amount)

    formal_product = f"{formalize_material_name(internal_material)}{name_exact}"
    return {
        "product": formal_product,
        "name": name_exact,
        "material": formalize_material_name(internal_material),
        "pricing_rule": pricing_rule,
        "normalized_width": float(parsed_width),
        "normalized_length": float(normalized_length),
        "base_price": float(base_price),
        "height_markup_amount": float(height_markup_amount),
        "final_price": float(final_price),
        "formal_total": round_formal_total(final_price),
        "calculation_steps": steps,
    }


def main() -> int:
    args = parse_args()
    payload = calculate_bed_quote(
        name_exact=args.name_exact,
        material=args.material,
        width=args.width,
        length=args.length,
        raise_height=args.raise_height,
        index_path=args.index,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
