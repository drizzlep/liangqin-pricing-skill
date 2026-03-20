#!/usr/bin/env python3
"""Extract a normalized price index from the Liangqin Excel workbook."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile
import xml.etree.ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}

IGNORE_SHEETS = {"WpsReserved_CellImgList"}
MATERIALS = ["玫瑰木", "樱桃木", "白蜡木", "白橡木", "黑胡桃"]
SERIES_KEYWORDS = [
    "流云",
    "飞瀑",
    "真格栅",
    "简美",
    "海棠",
    "遇见",
    "新古典",
    "经典",
    "佳偶",
    "儿童",
    "藤编",
    "拱形门",
    "丹霞",
    "辛巴",
    "卡座",
    "金属玻璃门",
]
VARIANT_PATTERNS = [
    "不带门",
    "带门",
    "无门无背板",
    "带门无背板",
    "平板门",
    "拼框门",
    "铝框门",
    "金属门",
    "金属玻璃门",
    "格栅门",
    "真格栅门",
    "真格栅",
    "推拉门",
    "下柜",
    "上柜",
    "带腿",
    "开放",
    "转角",
    "左长",
    "右长",
    "单件价格",
    "梯子单价",
    "金属支腿",
    "架式",
    "箱体",
    "抽屉款",
]
TEXT_NOTE_KEYWORDS = [
    "按",
    "计算",
    "注意",
    "默认",
    "功率",
    "纹理连续",
    "单价",
    "配",
    "上限",
    "可选",
    "单加",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract normalized price records from Liangqin xlsx.")
    parser.add_argument("--input", required=True, help="Path to the source xlsx file.")
    parser.add_argument("--output", required=True, help="Path to write normalized JSON.")
    parser.add_argument("--pretty", action="store_true", help="Write indented JSON.")
    return parser.parse_args()


def load_shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("a:si", NS):
        strings.append("".join(t.text or "" for t in item.iterfind(".//a:t", NS)))
    return strings


def cell_value(cell: ET.Element, shared: list[str]) -> str:
    value = ""
    inline = cell.find("a:is", NS)
    if inline is not None:
        value = "".join(t.text or "" for t in inline.iterfind(".//a:t", NS))
    else:
        raw = cell.find("a:v", NS)
        if raw is not None and raw.text is not None:
            if cell.attrib.get("t") == "s":
                idx = int(raw.text)
                value = shared[idx] if idx < len(shared) else raw.text
            else:
                value = raw.text
    return value.replace("\r", " ").replace("\n", " ").strip()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def find_column_index(cells: list[str], candidates: list[str]) -> int | None:
    normalized = [normalize_text(cell) for cell in cells]
    for candidate in candidates:
        target = normalize_text(candidate)
        for index, value in enumerate(normalized):
            if value == target:
                return index
    for candidate in candidates:
        target = normalize_text(candidate)
        for index, value in enumerate(normalized):
            if target and target in value:
                return index
    return None


def infer_pricing_mode(sheet_header: str, remark: str) -> str:
    header = normalize_text(sheet_header)
    note = normalize_text(remark)
    joined = f"{header} {note}"
    if "单件价格" in note or "价格为单件" in note or ("单价（元）" in note and "投影面积" not in note):
        return "unit_price"
    if "按米" in note or "价格（元/米）" in joined:
        return "per_meter"
    if "按个" in note or "个" in note and "单加" in note:
        return "per_item"
    if "投影面积" in note and "单价" in note:
        return "projection_area"
    if "体积" in joined:
        return "volume"
    if "比例" in joined:
        return "ratio"
    if "投影面积" in header and "单价（元）" in header:
        return "mixed"
    if "投影面积" in joined and "单价" in joined:
        return "projection_area"
    if "单价（元）" in header or "单件价格" in joined:
        return "unit_price"
    return "unknown"


def numeric_or_text(value: str) -> Any:
    if value == "":
        return None
    if value == "/":
        return "/"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        if "." in value:
            return float(value)
        return int(value)
    return value


def parse_bool_text(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def is_product_code(value: str) -> bool:
    compact = normalize_text(value)
    return bool(compact) and bool(re.fullmatch(r"[A-Z]+[A-Z0-9-]*", compact))


def infer_series(group: str, name: str, remark: str) -> str:
    text = " ".join(part for part in [group, name, remark] if part)
    for keyword in SERIES_KEYWORDS:
        if keyword in text:
            return keyword
    group_text = (group or "").replace("系列", "").strip()
    if group_text and not is_product_code(group_text):
        return group_text
    return ""


def infer_variant_tags(*parts: str) -> list[str]:
    text = " ".join(part for part in parts if part)
    tags: list[str] = []
    for pattern in VARIANT_PATTERNS:
        if pattern not in text:
            continue
        if pattern == "带门" and ("不带门" in text or "带门无背板" in text):
            continue
        if pattern == "金属门" and "金属玻璃门" in text:
            continue
        if pattern == "格栅门" and "真格栅门" in text:
            continue
        if pattern == "真格栅" and "真格栅门" in text:
            continue
        tags.append(pattern)
    if "旧款升级" in text:
        tags.append("旧款升级")
    if "纹理连续" in text:
        tags.append("纹理连续")
    return sorted(set(tags))


def infer_door_type(*parts: str) -> str:
    text = " ".join(part for part in parts if part)
    if "不带门" in text or "无门" in text:
        return "无门"
    if "真格栅门" in text:
        return "真格栅门"
    if "格栅门" in text:
        return "格栅门"
    if "金属玻璃门" in text:
        return "金属玻璃门"
    if "金属门" in text:
        return "金属门"
    if "铝框门" in text:
        return "铝框门"
    if "拼框门" in text:
        return "拼框门"
    if "平板门" in text:
        return "平板门"
    if "带门" in text or ("门" in text and "单价" not in text):
        return "带门"
    return ""


def infer_has_door(*parts: str) -> bool | None:
    text = " ".join(part for part in parts if part)
    if "不带门" in text or "无门" in text:
        return False
    if any(keyword in text for keyword in ["平板门", "拼框门", "铝框门", "格栅门", "真格栅门", "金属门", "带门"]):
        return True
    if "门" in text and "单价" not in text:
        return True
    return None


def build_column_map(header1: list[str], header2: list[str]) -> dict[str, Any]:
    merged_headers = [
        (header1[index] if index < len(header1) else "") + " " + (header2[index] if index < len(header2) else "")
        for index in range(max(len(header1), len(header2)))
    ]
    materials = {material: find_column_index(header2, [material]) for material in MATERIALS}
    return {
        "product_code": find_column_index(header1, ["产品编号"]),
        "name": find_column_index(header1, ["名称"]),
        "image": find_column_index(header1, ["图片"]),
        "bed_position": find_column_index(header1, ["床位"]),
        "edge": find_column_index(header1, ["边角"]),
        "remark": find_column_index(header1, ["备注"]),
        "updated_at": find_column_index(header1, ["最后更新日期"]),
        "status_miniprogram": find_column_index(header1, ["小程序商品状态"]),
        "status_parabola": find_column_index(header1, ["抛物线商品状态"]),
        "pricing_header": find_column_index(header1, ["投影面积单价（元/㎡）", "投影面积单价（元/㎡）、单价（元）", "单价（元）", "价格（元/米）"]),
        "dimensions": {
            "length": find_column_index(header2, ["长度"]),
            "depth": find_column_index(header2, ["进深"]),
            "height": find_column_index(header2, ["高度"]),
            "width": find_column_index(header2, ["宽度"]),
            "mattress_height": find_column_index(merged_headers, ["建议床垫高度（mm)", "建议床垫高度（mm）"]),
        },
        "materials": {key: value for key, value in materials.items() if value is not None},
    }


def value_at(values: list[str], index: int | None) -> str:
    if index is None or index >= len(values):
        return ""
    return values[index]


def sanitize_note_text(value: str) -> str:
    if value.startswith("=DISPIMG("):
        return ""
    return value


def child_bed_variant_tag(bed_position: str) -> str:
    text = (bed_position or "").strip()
    if text == "下床（抽屉）":
        return "下床抽屉款"
    if text == "下床（架式）":
        return "下床架式款"
    if text == "下床（箱体）":
        return "下床箱体款"
    return ""


def extract_dimensions(values: list[str], column_map: dict[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    for key, index in column_map["dimensions"].items():
        if index is None:
            continue
        dimensions[key] = numeric_or_text(value_at(values, index))
    return dimensions


def extract_materials(values: list[str], column_map: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for material, index in column_map["materials"].items():
        result[material] = numeric_or_text(value_at(values, index))
    return result


def row_is_group(values: list[str], column_map: dict[str, Any]) -> bool:
    non_empty = [(index, value) for index, value in enumerate(values) if value]
    if not non_empty:
        return False
    if len(non_empty) > 2:
        return False
    if any(index in column_map["materials"].values() for index, _ in non_empty):
        return False
    if any(index in [value for value in column_map["dimensions"].values() if value is not None] for index, _ in non_empty):
        return False
    first_text = non_empty[0][1]
    if is_product_code(first_text):
        return False
    return all(index in {0, 1} for index, _ in non_empty)


def clean_material_texts(materials: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    cleaned: dict[str, Any] = {}
    notes: list[str] = []
    for material, value in materials.items():
        if isinstance(value, str) and value not in {"", "/"}:
            notes.append(value)
            cleaned[material] = None
        else:
            cleaned[material] = value
    return cleaned, sorted(set(notes))


def classify_record(
    *,
    has_numeric_price: bool,
    notes: list[str],
    remark: str,
    updated_at: str,
    statuses: dict[str, str],
) -> tuple[str, bool, bool, bool]:
    combined = " ".join([remark, updated_at, *notes, *statuses.values()]).strip()
    deprecated = "下架" in combined
    is_reference_note_row = any(keyword in combined for keyword in TEXT_NOTE_KEYWORDS) and not has_numeric_price
    is_guidance_row = bool(notes) and not has_numeric_price
    if has_numeric_price:
        return "price", deprecated, is_reference_note_row, is_guidance_row
    if deprecated:
        return "status_note", deprecated, is_reference_note_row, is_guidance_row
    if is_guidance_row or remark:
        return "guidance_note", deprecated, is_reference_note_row, True
    return "status_note", deprecated, is_reference_note_row, is_guidance_row


def summarize_records(records: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {
        "record_count": len(records),
        "queryable_record_count": 0,
        "price_record_count": 0,
        "guidance_note_count": 0,
        "status_note_count": 0,
        "deprecated_record_count": 0,
    }
    for record in records:
        if record.get("is_queryable"):
            summary["queryable_record_count"] += 1
        record_kind = record.get("record_kind")
        if record_kind == "price":
            summary["price_record_count"] += 1
        elif record_kind == "guidance_note":
            summary["guidance_note_count"] += 1
        elif record_kind == "status_note":
            summary["status_note_count"] += 1
        if record.get("is_deprecated"):
            summary["deprecated_record_count"] += 1
    return summary


def parse_workbook(path: Path) -> dict[str, Any]:
    with ZipFile(path) as zf:
        shared = load_shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("p:Relationship", NS)
        }
        sheets: list[tuple[str, str]] = []
        for sheet in workbook.find("a:sheets", NS):
            name = sheet.attrib["name"]
            if name in IGNORE_SHEETS:
                continue
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            sheets.append((name, "xl/" + rel_map[rel_id]))

        records: list[dict[str, Any]] = []
        for sheet_name, target in sheets:
            root = ET.fromstring(zf.read(target))
            rows = root.findall(".//a:sheetData/a:row", NS)
            if len(rows) < 2:
                continue

            row_values = []
            for row in rows:
                row_values.append([cell_value(cell, shared) for cell in row.findall("a:c", NS)])

            header1 = row_values[0]
            header2 = row_values[1] if len(row_values) > 1 else []
            column_map = build_column_map(header1, header2)
            pricing_header = value_at(header1, column_map["pricing_header"])

            current_group = ""
            previous_record: dict[str, Any] | None = None
            for index, values in enumerate(row_values[2:], start=3):
                if not any(values):
                    continue

                if row_is_group(values, column_map):
                    current_group = " ".join(value for _, value in [(i, v) for i, v in enumerate(values) if v]).strip()
                    continue

                product_code = value_at(values, column_map["product_code"])
                name = value_at(values, column_map["name"])
                image = value_at(values, column_map["image"])
                edge = value_at(values, column_map["edge"])
                bed_position = value_at(values, column_map["bed_position"])
                remark = sanitize_note_text(value_at(values, column_map["remark"]))
                updated_at = sanitize_note_text(value_at(values, column_map["updated_at"]))
                statuses = {
                    "mini_program": sanitize_note_text(value_at(values, column_map["status_miniprogram"])),
                    "parabola": sanitize_note_text(value_at(values, column_map["status_parabola"])),
                }
                dimensions = extract_dimensions(values, column_map)
                materials_raw = extract_materials(values, column_map)
                materials, embedded_notes = clean_material_texts(materials_raw)

                has_any_material_value = any(value not in {"", None} for value in materials_raw.values())
                has_numeric_price = any(isinstance(value, (int, float)) for value in materials.values())
                has_dimensions = any(value not in {"", None} for value in dimensions.values())

                continuation = (
                    not product_code
                    and not name
                    and previous_record is not None
                    and (has_any_material_value or remark or updated_at or any(statuses.values()) or image)
                )

                if continuation and previous_record:
                    product_code = previous_record.get("product_code", "")
                    name = previous_record.get("name", "")
                    edge = edge or previous_record.get("edge", "")
                    image = image or previous_record.get("image_formula", "")
                    if not has_dimensions:
                        dimensions = previous_record.get("dimensions", {})
                    if not current_group:
                        current_group = previous_record.get("group", "")

                if not any([product_code, name, has_any_material_value, remark, updated_at, image, *statuses.values()]):
                    continue

                notes = sorted(set(filter(None, [*embedded_notes])))
                record_kind, is_deprecated, is_reference_note_row, is_guidance_row = classify_record(
                    has_numeric_price=has_numeric_price,
                    notes=notes,
                    remark=remark,
                    updated_at=updated_at,
                    statuses=statuses,
                )

                variant_tags = infer_variant_tags(name, remark, current_group, " ".join(notes))
                door_type = infer_door_type(name, remark, current_group, " ".join(notes))
                has_door = infer_has_door(name, remark, current_group, " ".join(notes))
                pricing_mode = infer_pricing_mode(pricing_header, remark or " ".join(notes))
                is_queryable = record_kind == "price" and has_numeric_price and not is_deprecated

                record = {
                    "sheet": sheet_name,
                    "group": current_group,
                    "source_row": index,
                    "pricing_mode": pricing_mode,
                    "record_kind": record_kind,
                    "is_queryable": is_queryable,
                    "is_deprecated": is_deprecated,
                    "is_reference_note_row": is_reference_note_row,
                    "is_guidance_row": is_guidance_row,
                    "product_code": product_code,
                    "name": name,
                    "series": infer_series(current_group, name, remark),
                    "variant_tags": variant_tags,
                    "door_type": door_type,
                    "has_door": parse_bool_text(has_door),
                    "image_formula": image,
                    "bed_position": bed_position,
                    "edge": edge,
                    "dimensions": dimensions,
                    "materials": materials,
                    "remark": remark,
                    "updated_at": updated_at,
                    "notes": notes,
                    "status": statuses,
                    "continuation": continuation,
                }

                records.append(record)

                if (
                    sheet_name == "儿童床"
                    and continuation
                    and bed_position.startswith("下床")
                    and previous_record is not None
                    and previous_record.get("sheet") == "儿童床"
                    and previous_record.get("pricing_mode") == "unit_price"
                    and previous_record.get("record_kind") == "price"
                ):
                    tag = child_bed_variant_tag(bed_position)
                    if tag:
                        previous_tags = set(previous_record.get("variant_tags", []))
                        previous_tags.add(tag)
                        previous_record["variant_tags"] = sorted(previous_tags)
                    lower_width = dimensions.get("width")
                    lower_length = dimensions.get("length")
                    structure_note = bed_position
                    if lower_width not in {"", None}:
                        structure_note += f" 下床宽{lower_width}m"
                    if lower_length not in {"", None}:
                        structure_note += f" 下床长{lower_length}m"
                    previous_notes = set(previous_record.get("notes", []))
                    previous_notes.add(structure_note)
                    previous_record["notes"] = sorted(previous_notes)

                previous_record = record

        summary = summarize_records(records)
        return {
            "source_file": str(path),
            "sheet_count": len(sheets),
            **summary,
            "records": records,
        }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = parse_workbook(input_path)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2 if args.pretty else None)
        handle.write("\n")
    os.replace(temp_path, output_path)

    print(
        "Wrote "
        f"{data['record_count']} records "
        f"({data['queryable_record_count']} queryable price rows) "
        f"to {output_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
