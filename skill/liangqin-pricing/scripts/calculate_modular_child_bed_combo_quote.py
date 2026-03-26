#!/usr/bin/env python3
"""Deterministic calculator for modular child-bed combos with under-bed cabinets."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from calculate_modular_child_bed_quote import (
    CURRENT_DATA_PATH as MODULAR_CHILD_BED_DATA_PATH,
    calculate_modular_child_bed_quote,
    format_decimal,
    material_key,
    parse_dimension,
    quantize_money,
    round_formal_total,
)
from material_names import formalize_material_name


PRICE_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "current" / "price-index.json"
MIN_PROJECTION_AREA = Decimal("1.6")
SUPPORTED_UNDERBED_CABINET_MODES = {"无门无背板", "有门无背板", "无门有背板"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate modular child-bed combo pricing deterministically.")
    parser.add_argument("--material", required=True, help="材质。")
    parser.add_argument("--bed-form", required=True, help="当前先支持半高床、高架床。")
    parser.add_argument("--width", required=True, help="床垫宽度。")
    parser.add_argument("--length", required=True, help="床垫长度。")
    parser.add_argument("--access-style", required=True, help="上层出入方式：直梯、斜梯、梯柜。")
    parser.add_argument("--access-height", help="直梯/斜梯垂直高度。")
    parser.add_argument("--guardrail-style", required=True, help="围栏样式。")
    parser.add_argument("--guardrail-length", required=True, help="围栏长度。")
    parser.add_argument("--guardrail-height", required=True, help="围栏高度。")
    parser.add_argument("--stair-width", help="梯柜踏步宽度。")
    parser.add_argument("--stair-depth", help="梯柜进深。")
    parser.add_argument("--front-cabinet-length", help="前排柜体长度。")
    parser.add_argument("--front-cabinet-height", help="前排柜体高度。")
    parser.add_argument("--front-cabinet-depth", help="前排柜体进深。")
    parser.add_argument("--front-cabinet-mode", help="前排柜体模式：无门无背板、有门无背板、无门有背板。")
    parser.add_argument("--rear-cabinet-length", help="后排柜体长度。")
    parser.add_argument("--rear-cabinet-height", help="后排柜体高度。")
    parser.add_argument("--rear-cabinet-depth", help="后排柜体进深。")
    parser.add_argument("--rear-cabinet-mode", help="后排柜体模式：无门无背板、有门无背板、无门有背板。")
    parser.add_argument("--interconnected-rows", action="store_true", help="前后双排柜体是否互通。")
    parser.add_argument("--price-index", default=str(PRICE_INDEX_PATH), help="Path to price-index.json.")
    parser.add_argument("--bed-data", default=str(MODULAR_CHILD_BED_DATA_PATH), help="Path to modular-child-bed-price.json.")
    return parser.parse_args()


def load_price_records(data_path: str | Path) -> list[dict[str, Any]]:
    path = Path(data_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload.get("records") or [])


def find_projection_area_record(records: list[dict[str, Any]], *, name: str, remark: str | None = None) -> dict[str, Any]:
    for record in records:
        if record.get("record_kind") != "price":
            continue
        if record.get("pricing_mode") != "projection_area":
            continue
        if str(record.get("name") or "").strip() != name:
            continue
        if remark is not None and str(record.get("remark") or "").strip() != remark:
            continue
        return record
    detail = f"name={name!r}" if remark is None else f"name={name!r}, remark={remark!r}"
    raise ValueError(f"price-index.json 缺少对应记录：{detail}")


def component_unit_price(record: dict[str, Any], material: str) -> Decimal:
    value = (record.get("materials") or {}).get(material)
    if value is None:
        raise ValueError(f"缺少柜体材质单价：{material}")
    return quantize_money(Decimal(str(value)))


def projection_area(length: Decimal, height: Decimal) -> tuple[Decimal, Decimal]:
    raw_area = quantize_money(length * height)
    charged_area = raw_area if raw_area >= MIN_PROJECTION_AREA else MIN_PROJECTION_AREA
    return raw_area, charged_area


def parse_underbed_row(
    *,
    label: str,
    length: str | None,
    height: str | None,
    depth: str | None,
    mode: str | None,
) -> dict[str, Any] | None:
    values = [length, height, depth, mode]
    if not any(str(value or "").strip() for value in values):
        return None
    if not all(str(value or "").strip() for value in values):
        raise ValueError(f"{label}柜体需要同时提供长度、高度、进深和结构模式")

    normalized_mode = str(mode or "").strip()
    if normalized_mode not in SUPPORTED_UNDERBED_CABINET_MODES:
        raise ValueError(f"{label}柜体当前只支持：{', '.join(sorted(SUPPORTED_UNDERBED_CABINET_MODES))}")

    parsed_depth = parse_dimension(depth)
    if parsed_depth > Decimal("0.45"):
        raise ValueError(f"{label}柜体当前只支持单排进深不大于 450mm 的组合报价")

    return {
        "label": label,
        "length": parse_dimension(length),
        "height": parse_dimension(height),
        "depth": parsed_depth,
        "mode": normalized_mode,
    }


def calculate_underbed_row_total(
    *,
    row: dict[str, Any],
    material: str,
    base_record: dict[str, Any],
    door_record: dict[str, Any],
) -> tuple[Decimal, list[str], str]:
    label = str(row["label"])
    row_label = f"{label}排衣柜（{row['mode']}）"
    length = row["length"]
    height = row["height"]
    raw_area, charged_area = projection_area(length, height)
    base_unit_price = component_unit_price(base_record, material)
    door_unit_price = component_unit_price(door_record, material)
    steps: list[str] = [
        f"{row_label}投影面积：{format_decimal(length)} × {format_decimal(height)} = {format_decimal(raw_area)}㎡"
    ]
    if charged_area != raw_area:
        steps.append(f"{row_label}投影面积不足 1.6㎡，按 1.6㎡ 计")

    base_amount = quantize_money(charged_area * base_unit_price)
    subtotal = base_amount
    expression = f"{format_decimal(charged_area)} × {format_decimal(base_unit_price)}"
    description = f"{row_label}基础价（无门无背板）"
    steps.append(f"{description}：{expression} = {format_decimal(base_amount)} 元")

    if row["mode"] == "有门无背板":
        door_amount = quantize_money(charged_area * door_unit_price)
        subtotal += door_amount
        steps.append(
            f"{row_label}门板加价：{format_decimal(charged_area)} × {format_decimal(door_unit_price)} = {format_decimal(door_amount)} 元"
        )
    elif row["mode"] == "无门有背板":
        backboard_addition = quantize_money(base_amount * Decimal("0.1"))
        subtotal += backboard_addition
        steps.append(f"{row_label}背板外露加价：{format_decimal(base_amount)} × 10% = {format_decimal(backboard_addition)} 元")

    subtotal = quantize_money(subtotal)
    steps.append(f"{row_label}小计：{format_decimal(subtotal)} 元")
    return subtotal, steps, row_label


def confirmed_text(
    *,
    bed_quote: dict[str, Any],
    rows: list[dict[str, Any]],
    interconnected_rows: bool,
) -> str:
    parts = [str(bed_quote["confirmed"])]
    if rows:
        row_parts = [
            f"{row['label']}排衣柜：长 {format_decimal(row['length'])} 米 × 高 {format_decimal(row['height'])} 米 × 深 {format_decimal(row['depth'])} 米，{row['mode']}"
            for row in rows
        ]
        parts.extend(row_parts)
        if len(rows) == 2:
            parts.append("床下前后双排柜体互通" if interconnected_rows else "床下前后双排柜体不互通")
    return "；".join(parts)


def calculate_modular_child_bed_combo_quote(
    *,
    material: str,
    bed_form: str,
    width: str,
    length: str,
    access_style: str,
    access_height: str | None = None,
    guardrail_style: str,
    guardrail_length: str,
    guardrail_height: str,
    stair_width: str | None = None,
    stair_depth: str | None = None,
    front_cabinet_length: str | None = None,
    front_cabinet_height: str | None = None,
    front_cabinet_depth: str | None = None,
    front_cabinet_mode: str | None = None,
    rear_cabinet_length: str | None = None,
    rear_cabinet_height: str | None = None,
    rear_cabinet_depth: str | None = None,
    rear_cabinet_mode: str | None = None,
    interconnected_rows: bool = False,
    price_index_path: str | Path = PRICE_INDEX_PATH,
    bed_data_path: str | Path = MODULAR_CHILD_BED_DATA_PATH,
) -> dict[str, Any]:
    if bed_form not in {"半高床", "高架床"}:
        raise ValueError("当前组合报价只支持半高床/高架床 + 床下柜体")

    normalized_material = material_key(material)
    records = load_price_records(price_index_path)
    base_record = find_projection_area_record(records, name="无门无背板书柜")
    door_record = find_projection_area_record(records, name="像素格撞色书柜", remark="带门无背板（门板单价）")

    bed_quote = calculate_modular_child_bed_quote(
        bed_form=bed_form,
        material=material,
        width=width,
        length=length,
        access_style=access_style,
        access_height=access_height,
        guardrail_style=guardrail_style,
        guardrail_length=guardrail_length,
        guardrail_height=guardrail_height,
        stair_width=stair_width,
        stair_depth=stair_depth,
        data_path=bed_data_path,
    )

    rows = [
        row
        for row in [
            parse_underbed_row(
                label="前",
                length=front_cabinet_length,
                height=front_cabinet_height,
                depth=front_cabinet_depth,
                mode=front_cabinet_mode,
            ),
            parse_underbed_row(
                label="后",
                length=rear_cabinet_length,
                height=rear_cabinet_height,
                depth=rear_cabinet_depth,
                mode=rear_cabinet_mode,
            ),
        ]
        if row is not None
    ]
    if not rows:
        raise ValueError("至少需要一排床下柜体参数")

    total = quantize_money(Decimal(str(bed_quote["final_price"])))
    steps = [f"床体小计：{format_decimal(total)} 元"]
    steps.extend(f"床体 - {step}" for step in bed_quote["calculation_steps"])

    for row in rows:
        row_total, row_steps, _ = calculate_underbed_row_total(
            row=row,
            material=normalized_material,
            base_record=base_record,
            door_record=door_record,
        )
        total += row_total
        steps.extend(row_steps)

    total = quantize_money(total)
    formal_material = formalize_material_name(normalized_material) or normalized_material
    product = f"{formal_material}模块化儿童{bed_form}+床下组合柜"
    return {
        "product": product,
        "confirmed": confirmed_text(
            bed_quote=bed_quote,
            rows=rows,
            interconnected_rows=interconnected_rows,
        ),
        "pricing_method": "模块化儿童床+床下柜组合计价",
        "calculation_steps": [
            *steps,
            f"组合小计：{format_decimal(total)} 元",
        ],
        "subtotal": f"{round_formal_total(total)}元",
        "final_price": float(total),
        "formal_total": round_formal_total(total),
        "pricing_route": "modular_child_bed_combo",
    }


def main() -> int:
    args = parse_args()
    payload = calculate_modular_child_bed_combo_quote(
        material=args.material,
        bed_form=args.bed_form,
        width=args.width,
        length=args.length,
        access_style=args.access_style,
        access_height=args.access_height,
        guardrail_style=args.guardrail_style,
        guardrail_length=args.guardrail_length,
        guardrail_height=args.guardrail_height,
        stair_width=args.stair_width,
        stair_depth=args.stair_depth,
        front_cabinet_length=args.front_cabinet_length,
        front_cabinet_height=args.front_cabinet_height,
        front_cabinet_depth=args.front_cabinet_depth,
        front_cabinet_mode=args.front_cabinet_mode,
        rear_cabinet_length=args.rear_cabinet_length,
        rear_cabinet_height=args.rear_cabinet_height,
        rear_cabinet_depth=args.rear_cabinet_depth,
        rear_cabinet_mode=args.rear_cabinet_mode,
        interconnected_rows=args.interconnected_rows,
        price_index_path=args.price_index,
        bed_data_path=args.bed_data,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
