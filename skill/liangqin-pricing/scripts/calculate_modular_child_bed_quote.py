#!/usr/bin/env python3
"""Deterministic calculator for modular child-bed pricing."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from material_names import formalize_material_name, normalize_material_for_query


CURRENT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "current" / "modular-child-bed-price.json"
UPPER_BED_LIMIT = Decimal("1.2")
TOLERANCE = Decimal("0.015")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate modular child-bed pricing deterministically.")
    parser.add_argument("--bed-form", required=True, help="儿童床形态：上下床、半高床、高架床、错层床。")
    parser.add_argument("--material", required=True, help="材质。")
    parser.add_argument("--width", required=True, help="床垫宽度。")
    parser.add_argument("--length", required=True, help="床垫长度。")
    parser.add_argument("--access-style", required=True, help="上层出入方式：直梯、斜梯、梯柜。")
    parser.add_argument("--access-height", help="直梯/斜梯垂直高度。")
    parser.add_argument("--lower-bed-type", help="下层结构：架式床、箱体床。")
    parser.add_argument("--guardrail-style", help="围栏样式。")
    parser.add_argument("--guardrail-length", help="围栏长度。")
    parser.add_argument("--guardrail-height", help="围栏高度。")
    parser.add_argument("--stair-width", help="梯柜踏步宽度。")
    parser.add_argument("--stair-depth", help="梯柜进深。")
    parser.add_argument("--add-underframe-board", action="store_true", help="是否增加下框板。")
    parser.add_argument("--drawer-count", type=int, default=0, help="拖抽数量。")
    parser.add_argument("--drawer-width", help="拖抽宽度。")
    parser.add_argument("--drawer-depth", help="拖抽进深。")
    parser.add_argument("--leg-brace-length", help="腿称长度。")
    parser.add_argument("--data", default=str(CURRENT_DATA_PATH), help="Path to modular-child-bed-price.json.")
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


def format_decimal(value: Decimal) -> str:
    return f"{value.normalize():f}".rstrip("0").rstrip(".") if value != value.to_integral() else str(int(value))


def load_payload(data_path: str | Path) -> dict[str, Any]:
    path = Path(data_path).expanduser().resolve()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def material_key(material: str) -> str:
    normalized = normalize_material_for_query(material)
    if not normalized:
        raise ValueError("material is required")
    return normalized


def size_key(width: Decimal, length: Decimal) -> str:
    return f"{format_decimal(width)}x{format_decimal(length)}"


def stair_width_band(width: Decimal) -> str:
    if Decimal("0.45") <= width <= Decimal("0.5"):
        return "450-500"
    if Decimal("0.5") < width <= Decimal("0.6"):
        return "500-600"
    raise ValueError("梯柜踏步宽度需在 450mm-600mm 之间")


def component_unit_price(component: dict[str, Any], material: str) -> Decimal:
    value = (component.get("unit_prices") or {}).get(material)
    if value is None:
        raise ValueError(f"缺少材质单价：{material}")
    return quantize_money(Decimal(str(value)))


def ensure_upper_width_limit(bed_form: str, width: Decimal) -> None:
    if bed_form in {"上下床", "半高床", "高架床", "错层床"} and width > UPPER_BED_LIMIT + TOLERANCE:
        raise ValueError("上铺/高架床床垫宽度需不大于 1.2 米")


def modular_confirmed_text(
    *,
    bed_form: str,
    width: Decimal,
    length: Decimal,
    access_style: str,
    lower_bed_type: str | None,
    guardrail_style: str | None,
    material: str,
) -> str:
    parts = [
        f"床形态：{bed_form}",
        f"床垫尺寸：{format_decimal(width)}m×{format_decimal(length)}m",
        f"上层出入方式：{access_style}",
        f"材质：{formalize_material_name(material)}",
    ]
    if lower_bed_type:
        parts.append(f"下层结构：{lower_bed_type}")
    if guardrail_style:
        parts.append(f"围栏：{guardrail_style}")
    return "；".join(parts)


def add_area_component(
    *,
    steps: list[str],
    title: str,
    unit_label: str,
    unit_price: Decimal,
    length: Decimal,
    width: Decimal,
) -> Decimal:
    amount = quantize_money(length * width * unit_price)
    steps.append(
        f"{title}：{format_decimal(length)} × {format_decimal(width)} × {format_decimal(unit_price)} = {format_decimal(amount)} 元"
    )
    return amount


def add_linear_component(
    *,
    steps: list[str],
    title: str,
    unit_price: Decimal,
    length: Decimal,
) -> Decimal:
    amount = quantize_money(length * unit_price)
    steps.append(f"{title}：{format_decimal(length)} × {format_decimal(unit_price)} = {format_decimal(amount)} 元")
    return amount


def calculate_modular_child_bed_quote(
    *,
    bed_form: str,
    material: str,
    width: str,
    length: str,
    access_style: str,
    access_height: str | None = None,
    lower_bed_type: str | None = None,
    guardrail_style: str | None = None,
    guardrail_length: str | None = None,
    guardrail_height: str | None = None,
    stair_width: str | None = None,
    stair_depth: str | None = None,
    add_underframe_board: bool = False,
    drawer_count: int = 0,
    drawer_width: str | None = None,
    drawer_depth: str | None = None,
    leg_brace_length: str | None = None,
    data_path: str | Path = CURRENT_DATA_PATH,
) -> dict[str, Any]:
    payload = load_payload(data_path)
    data = payload["general_components"]
    specials = payload["rosewood_specials"]

    internal_material = material_key(material)
    parsed_width = parse_dimension(width)
    parsed_length = parse_dimension(length)
    ensure_upper_width_limit(bed_form, parsed_width)

    if bed_form in {"上下床", "错层床"} and not lower_bed_type:
        raise ValueError("上下床/错层床需要明确下层结构")
    if not guardrail_style:
        raise ValueError("guardrail_style is required")

    steps: list[str] = []
    total = Decimal("0.00")
    rosewood_size_key = size_key(parsed_width, parsed_length)
    rosewood_bunk_special = specials.get("bunk_modules", {}).get(rosewood_size_key) if internal_material == "玫瑰木" else None
    rosewood_castle_special = specials.get("castle_modules", {}).get(rosewood_size_key) if internal_material == "玫瑰木" else None
    upper_includes_guardrail = False

    if bed_form in {"半高床", "高架床"}:
        if bed_form == "半高床":
            steps.append("半高床按高架床单层模块组合")
        component = data["bed_frames"]["高架床"]
        total += add_area_component(
            steps=steps,
            title="高架床模块",
            unit_label="㎡",
            unit_price=component_unit_price(component, internal_material),
            length=parsed_length,
            width=parsed_width,
        )
    elif bed_form == "上下床":
        if (
            rosewood_bunk_special
            and guardrail_style == rosewood_bunk_special.get("supported_guardrail_style")
            and access_style in {"直梯", "斜梯", "梯柜"}
        ):
            special_name = "梯柜上床" if access_style == "梯柜" else "挂梯上床"
            special_upper = rosewood_bunk_special.get("upper_modules", {}).get(special_name)
            if special_upper is not None:
                amount = quantize_money(Decimal(str(special_upper)))
                steps.append(f"玫瑰木特价上床模块（{special_name}）：{format_decimal(amount)} 元")
                total += amount
                upper_includes_guardrail = True
        if not upper_includes_guardrail:
            component = data["bed_frames"]["高架床"]
            total += add_area_component(
                steps=steps,
                title="高架床模块",
                unit_label="㎡",
                unit_price=component_unit_price(component, internal_material),
                length=parsed_length,
                width=parsed_width,
            )

        if lower_bed_type == "架式床" and rosewood_bunk_special and "下床" in rosewood_bunk_special.get("lower_modules", {}):
            amount = quantize_money(Decimal(str(rosewood_bunk_special["lower_modules"]["下床"])))
            steps.append(f"玫瑰木特价下床模块：{format_decimal(amount)} 元")
            total += amount
        elif lower_bed_type == "箱体床" and rosewood_bunk_special and "箱体床" in rosewood_bunk_special.get("lower_modules", {}):
            amount = quantize_money(Decimal(str(rosewood_bunk_special["lower_modules"]["箱体床"])))
            steps.append(f"玫瑰木特价箱体下床模块：{format_decimal(amount)} 元")
            total += amount
        else:
            component = data["bed_frames"][lower_bed_type]
            total += add_area_component(
                steps=steps,
                title=f"{lower_bed_type}模块",
                unit_label="㎡",
                unit_price=component_unit_price(component, internal_material),
                length=parsed_length,
                width=parsed_width,
            )
    elif bed_form == "错层床":
        if rosewood_castle_special and guardrail_style == rosewood_castle_special.get("supported_guardrail_style"):
            upper = rosewood_castle_special["upper_modules"].get("错层床上床")
            lower = rosewood_castle_special["lower_modules"].get("错层床下床")
            if upper is not None:
                amount = quantize_money(Decimal(str(upper)))
                steps.append(f"玫瑰木特价上床模块（错层床上床）：{format_decimal(amount)} 元")
                total += amount
                upper_includes_guardrail = True
            if lower is not None:
                amount = quantize_money(Decimal(str(lower)))
                steps.append(f"玫瑰木特价下床模块（错层床下床）：{format_decimal(amount)} 元")
                total += amount
        else:
            steps.append("错层床当前按高架床上层 + 下层床架模块组合")
            component = data["bed_frames"]["高架床"]
            total += add_area_component(
                steps=steps,
                title="高架床模块",
                unit_label="㎡",
                unit_price=component_unit_price(component, internal_material),
                length=parsed_length,
                width=parsed_width,
            )
            component = data["bed_frames"][lower_bed_type]
            total += add_area_component(
                steps=steps,
                title=f"{lower_bed_type}模块",
                unit_label="㎡",
                unit_price=component_unit_price(component, internal_material),
                length=parsed_length,
                width=parsed_width,
            )
    else:
        raise ValueError(f"unsupported bed_form: {bed_form}")

    if not upper_includes_guardrail:
        if not guardrail_length or not guardrail_height:
            raise ValueError("围栏长度和围栏高度是必填项")
        railing_component = data["railings"][guardrail_style]
        railing_length = parse_dimension(guardrail_length)
        railing_height = parse_dimension(guardrail_height)
        amount = quantize_money(
            railing_length * railing_height * component_unit_price(railing_component, internal_material)
        )
        steps.append(
            f"{guardrail_style}：{format_decimal(railing_length)} × {format_decimal(railing_height)} × "
            f"{format_decimal(component_unit_price(railing_component, internal_material))} = {format_decimal(amount)} 元"
        )
        total += amount

    if access_style in {"直梯", "斜梯"}:
        if rosewood_bunk_special and access_style in rosewood_bunk_special.get("access_modules", {}):
            amount = quantize_money(Decimal(str(rosewood_bunk_special["access_modules"][access_style])))
            steps.append(f"玫瑰木特价{access_style}：{format_decimal(amount)} 元")
            total += amount
        else:
            if not access_height:
                raise ValueError(f"{access_style}需要提供 access_height")
            amount = add_linear_component(
                steps=steps,
                title=access_style,
                unit_price=component_unit_price(data["access"][access_style], internal_material),
                length=parse_dimension(access_height),
            )
            total += amount
    elif access_style == "梯柜":
        if rosewood_bunk_special and guardrail_style == rosewood_bunk_special.get("supported_guardrail_style"):
            special_key = "含篱笆围栏" if guardrail_style == "篱笆围栏" else "不含后围栏"
            special_amount = rosewood_bunk_special.get("stair_cabinet", {}).get(special_key)
            if special_amount is not None:
                amount = quantize_money(Decimal(str(special_amount)))
                steps.append(f"玫瑰木特价梯柜（{special_key}）：{format_decimal(amount)} 元")
                total += amount
            else:
                raise ValueError("缺少匹配的玫瑰木特价梯柜")
        else:
            if not stair_width or not stair_depth:
                raise ValueError("梯柜需要提供 stair_width 和 stair_depth")
            band = stair_width_band(parse_dimension(stair_width))
            band_component = data["access"]["梯柜"]["width_bands"][band]
            amount = add_linear_component(
                steps=steps,
                title=f"梯柜（{band}）",
                unit_price=component_unit_price(band_component, internal_material),
                length=parse_dimension(stair_depth),
            )
            total += amount
    else:
        raise ValueError(f"unsupported access_style: {access_style}")

    if add_underframe_board:
        component = data["addons"]["下框板"]
        total += add_linear_component(
            steps=steps,
            title="下框板",
            unit_price=component_unit_price(component, internal_material),
            length=parsed_width,
        )

    if drawer_count:
        if not drawer_width or not drawer_depth:
            raise ValueError("拖抽需要提供 drawer_width 和 drawer_depth")
        component = data["addons"]["拖抽"]
        parsed_drawer_width = parse_dimension(drawer_width)
        parsed_drawer_depth = parse_dimension(drawer_depth)
        unit_price = component_unit_price(component, internal_material)
        amount = quantize_money(parsed_drawer_width * parsed_drawer_depth * Decimal(drawer_count) * unit_price)
        steps.append(
            f"拖抽：{format_decimal(parsed_drawer_width)} × {format_decimal(parsed_drawer_depth)} × "
            f"{drawer_count} × {format_decimal(unit_price)} = {format_decimal(amount)} 元"
        )
        total += amount

    if leg_brace_length:
        component = data["addons"]["腿称"]
        total += add_linear_component(
            steps=steps,
            title="腿称",
            unit_price=component_unit_price(component, internal_material),
            length=parse_dimension(leg_brace_length),
        )

    total = quantize_money(total)
    formal_material = formalize_material_name(internal_material) or internal_material
    product = f"{formal_material}模块化儿童{bed_form}"
    return {
        "product": product,
        "confirmed": modular_confirmed_text(
            bed_form=bed_form,
            width=parsed_width,
            length=parsed_length,
            access_style=access_style,
            lower_bed_type=lower_bed_type,
            guardrail_style=guardrail_style,
            material=internal_material,
        ),
        "pricing_method": "模块化儿童床组合计价",
        "calculation_steps": steps,
        "subtotal": f"{round_formal_total(total)}元",
        "final_price": float(total),
        "formal_total": round_formal_total(total),
        "pricing_route": "modular_child_bed",
    }


def main() -> int:
    args = parse_args()
    payload = calculate_modular_child_bed_quote(
        bed_form=args.bed_form,
        material=args.material,
        width=args.width,
        length=args.length,
        access_style=args.access_style,
        access_height=args.access_height,
        lower_bed_type=args.lower_bed_type,
        guardrail_style=args.guardrail_style,
        guardrail_length=args.guardrail_length,
        guardrail_height=args.guardrail_height,
        stair_width=args.stair_width,
        stair_depth=args.stair_depth,
        add_underframe_board=args.add_underframe_board,
        drawer_count=args.drawer_count,
        drawer_width=args.drawer_width,
        drawer_depth=args.drawer_depth,
        leg_brace_length=args.leg_brace_length,
        data_path=args.data,
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
