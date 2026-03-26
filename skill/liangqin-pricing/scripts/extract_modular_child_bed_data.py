#!/usr/bin/env python3
"""Extract modular child-bed pricing data from the dedicated xls workbook."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import xlrd


GENERAL_SHEET = "部件单价 "
ROSEWOOD_SHEET = "玫瑰木特价部件"
MATERIAL_COLUMNS = ["玫瑰木", "樱桃木", "白蜡木", "白橡木", "黑胡桃"]
SHARED_MATERIAL_LABEL = "樱桃/白蜡"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract modular child-bed pricing data from xls.")
    parser.add_argument("--input", required=True, help="Path to 模块儿童上下床报价.xls")
    parser.add_argument("--output", required=True, help="Path to write normalized JSON data.")
    parser.add_argument("--pretty", action="store_true", help="Write indented JSON output.")
    return parser.parse_args()


def cell_text(sheet: xlrd.sheet.Sheet, row: int, col: int) -> str:
    return str(sheet.cell_value(row, col)).strip()


def numeric_value(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_size_label(value: str) -> str:
    compact = re.sub(r"\s+", "", str(value or ""))
    compact = compact.replace("米", "").replace("*", "x")
    compact = compact.lower()
    return compact


def material_prices_from_general_row(values: list[str]) -> dict[str, float]:
    if len(values) != 4:
        raise ValueError("general material row requires four price cells")
    rosewood, cherry_ash, oak, walnut = values
    return {
        "玫瑰木": float(rosewood),
        "樱桃木": float(cherry_ash),
        "白蜡木": float(cherry_ash),
        "白橡木": float(oak),
        "黑胡桃": float(walnut),
    }


def stair_width_band(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("stair width is required")
    if "450" in text and "500" in text:
        return "450-500"
    if "500" in text and "600" in text:
        return "500-600"
    number = float(text)
    if number > 10:
        number = number / 1000
    if 0.45 <= number <= 0.5:
        return "450-500"
    if 0.5 < number <= 0.6:
        return "500-600"
    raise ValueError("stair width must be within 450mm-600mm")


def normalized_formula(value: str) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def extract_general_components(sheet: xlrd.sheet.Sheet) -> dict[str, Any]:
    railings: dict[str, Any] = {}
    bed_frames: dict[str, Any] = {}
    access: dict[str, Any] = {}
    addons: dict[str, Any] = {}
    current_group = ""

    for row in range(2, sheet.nrows):
        group = cell_text(sheet, row, 0) or current_group
        name = cell_text(sheet, row, 1).replace("\n", " ").strip()
        prices = [cell_text(sheet, row, col) for col in range(2, 6)]
        formula = normalized_formula(cell_text(sheet, row, 6))
        current_group = group

        if not name:
            continue
        if not any(numeric_value(value) is not None for value in prices):
            continue

        price_map = material_prices_from_general_row(prices)
        payload = {
            "group": group,
            "name": name,
            "formula": formula,
            "unit_prices": price_map,
        }

        if group in {"围栏", "特殊围栏"}:
            railings[name] = payload
            continue
        if group == "床架":
            bed_frames[name] = payload
            continue
        if group == "梯子":
            if "梯柜" in name:
                access.setdefault("梯柜", {"group": group, "name": "梯柜", "formula": formula, "width_bands": {}})
                access["梯柜"]["width_bands"][stair_width_band(name)] = {
                    "name": name,
                    "unit_prices": price_map,
                }
            else:
                access[name] = payload
            continue
        if group == "部件":
            addons[name] = payload

    return {
        "railings": railings,
        "bed_frames": bed_frames,
        "access": access,
        "addons": addons,
    }


def extract_rosewood_specials(sheet: xlrd.sheet.Sheet) -> dict[str, Any]:
    bunk_modules: dict[str, Any] = {}
    castle_modules: dict[str, Any] = {}

    current_size = ""
    for row in range(2, 9):
        size = normalize_size_label(cell_text(sheet, row, 0)) or current_size
        component = cell_text(sheet, row, 1)
        component_price = numeric_value(cell_text(sheet, row, 3))
        single_bed_price = numeric_value(cell_text(sheet, row, 5))
        access_component = cell_text(sheet, row, 7).replace("\n", " ").strip()
        access_price = numeric_value(cell_text(sheet, row, 9))
        if size:
            current_size = size
        if not current_size:
            continue

        entry = bunk_modules.setdefault(
            current_size,
            {
                "supported_guardrail_style": "篱笆围栏",
                "upper_modules": {},
                "lower_modules": {},
                "access_modules": {},
                "stair_cabinet": {},
            },
        )
        if single_bed_price is not None:
            entry["single_bed_frame"] = single_bed_price
        if component_price is not None and component:
            if component in {"梯柜上床", "挂梯上床"}:
                entry["upper_modules"][component] = component_price
            else:
                entry["lower_modules"][component] = component_price
        if access_price is not None and access_component:
            if access_component.startswith("梯柜"):
                label = "含篱笆围栏" if "含篱笆围栏" in access_component else "不含后围栏"
                entry["stair_cabinet"][label] = access_price
            else:
                entry["access_modules"][access_component] = access_price

    current_size = ""
    for row in range(11, 13):
        size = normalize_size_label(cell_text(sheet, row, 0)) or current_size
        component = cell_text(sheet, row, 1)
        component_price = numeric_value(cell_text(sheet, row, 3))
        single_bed_price = numeric_value(cell_text(sheet, row, 5))
        if size:
            current_size = size
        if not current_size or component_price is None or not component:
            continue
        entry = castle_modules.setdefault(
            current_size,
            {
                "supported_guardrail_style": "城堡围栏",
                "upper_modules": {},
                "lower_modules": {},
            },
        )
        if "上床" in component:
            entry["upper_modules"][component] = component_price
        else:
            entry["lower_modules"][component] = component_price
        if single_bed_price is not None:
            entry["single_bed_frame"] = single_bed_price

    return {
        "bunk_modules": bunk_modules,
        "castle_modules": castle_modules,
    }


def extract_payload(input_path: str | Path) -> dict[str, Any]:
    workbook = xlrd.open_workbook(str(Path(input_path).expanduser().resolve()))
    general_sheet = workbook.sheet_by_name(GENERAL_SHEET)
    rosewood_sheet = workbook.sheet_by_name(ROSEWOOD_SHEET)
    return {
        "source_file": str(Path(input_path).expanduser().resolve()),
        "general_components": extract_general_components(general_sheet),
        "rosewood_specials": extract_rosewood_specials(rosewood_sheet),
    }


def main() -> int:
    args = parse_args()
    payload = extract_payload(args.input)
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2 if args.pretty else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
