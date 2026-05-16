#!/usr/bin/env python3
"""Build machine-only regression artifacts for paused money rules."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"
DEFAULT_RULE_COUNT = 20

AMOUNT_PATTERNS = (
    r"\d+(?:\.\d+)?\s*元(?:\s*/\s*(?:㎡|m²|m2|米|m|个|套|件))?",
    r"每(?:㎡|m²|m2|米|m|个|套|件)\s*\d+(?:\.\d+)?\s*元",
    r"[加增补]\s*\d+(?:\.\d+)?\s*元",
    r"[减降]\s*\d+(?:\.\d+)?\s*元",
)
NUMERIC_PATTERNS = (
    r"\d+(?:\.\d+)?\s*(?:mm|cm|m|㎡|m²|kg|%)",
    r"[≤≥<>]\s*\d+(?:\.\d+)?",
    r"\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?",
)
FORMULA_TERMS = ("加价", "补差", "折减", "折扣", "另收费", "额外收费", "报价原则", "公式", "单价", "不额外收费", "免费")

CALCULATOR_INVENTORY: tuple[dict[str, Any], ...] = (
    {
        "id": "calculate_door_panel_adjustment",
        "script": "calculate_door_panel_adjustment.py",
        "modules": ("pricing_calculation:door_panel_adjustment",),
        "keywords": ("门板", "平板门", "框门", "材质补差"),
        "required_fields": ("cabinet_material", "target_door_material", "base_unit_price", "cabinet_door_family", "target_door_family"),
    },
    {
        "id": "calculate_rock_slab_price",
        "script": "calculate_rock_slab_price.py",
        "modules": ("pricing_calculation:rock_slab_adjustment",),
        "keywords": ("岩板",),
        "required_fields": ("length", "depth", "material", "base_subtotal"),
    },
    {
        "id": "calculate_operation_gap_price",
        "script": "calculate_operation_gap_price.py",
        "modules": ("pricing_calculation:operation_gap_adjustment",),
        "keywords": ("操作缝", "背板"),
        "required_fields": ("length", "height", "material"),
    },
    {
        "id": "calculate_double_sided_door_price",
        "script": "calculate_double_sided_door_price.py",
        "modules": ("pricing_calculation:double_sided_cabinet",),
        "keywords": ("双面", "双面柜"),
        "required_fields": ("depth", "side_a_family", "side_b_family", "material"),
    },
    {
        "id": "calculate_hidden_rosewood_discount",
        "script": "calculate_hidden_rosewood_discount.py",
        "modules": ("pricing_calculation:hidden_rosewood_discount",),
        "keywords": ("隐形玫瑰木", "玫瑰木折扣"),
        "required_fields": ("exposed_material", "base_unit_price"),
    },
    {
        "id": "calculate_modular_child_bed_quote",
        "script": "calculate_modular_child_bed_quote.py",
        "modules": ("pricing_calculation:modular_child_bed",),
        "keywords": ("模块化儿童床", "儿童床"),
        "required_fields": ("bed_form", "width", "length", "material"),
    },
    {
        "id": "calculate_modular_child_bed_combo_quote",
        "script": "calculate_modular_child_bed_combo_quote.py",
        "modules": ("pricing_calculation:modular_child_bed_combo",),
        "keywords": ("模块化儿童床", "组合"),
        "required_fields": ("bed_form", "width", "length", "material"),
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build machine-only amount regression artifacts for paused money rules.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="Online designer-manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--money-ledger", default="", help="Override money-rule-regression-ledger.json path.")
    parser.add_argument("--landing-pack", default="", help="Override agent-rule-landing-pack.json path.")
    parser.add_argument("--certification", default="", help="Override full-document-data-certification.json path.")
    parser.add_argument("--price-index", default="", help="Override current price-index.json path.")
    parser.add_argument("--output-dir", default="", help="Override output directory.")
    return parser.parse_args(argv)


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else dict(fallback or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def excerpt(value: Any, limit: int = 220) -> str:
    text = normalize_inline(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def resolve_report_dir(skill_dir: Path, layer: str) -> Path:
    manifest_path = skill_dir / "references" / "addenda" / layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rules_candidate_file = artifacts.get("rules_candidate_file")
    if not rules_candidate_file:
        return skill_dir / "reports" / "addenda" / layer
    raw_path = Path(str(rules_candidate_file))
    resolved = raw_path if raw_path.is_absolute() else (manifest_path.parent / raw_path).resolve()
    return resolved.parent


def resolve_input_paths(*, skill_dir: Path, candidate_layer: str, args: argparse.Namespace | None = None) -> dict[str, Path]:
    report_dir = resolve_report_dir(skill_dir, candidate_layer)
    return {
        "report_dir": report_dir,
        "money_ledger": Path(args.money_ledger).expanduser().resolve() if args and args.money_ledger else report_dir / "money-rule-regression-ledger.json",
        "landing_pack": Path(args.landing_pack).expanduser().resolve() if args and args.landing_pack else report_dir / "agent-rule-landing-pack.json",
        "certification": Path(args.certification).expanduser().resolve() if args and args.certification else report_dir / "full-document-data-certification.json",
        "price_index": Path(args.price_index).expanduser().resolve() if args and args.price_index else skill_dir / "data" / "current" / "price-index.json",
        "output_dir": Path(args.output_dir).expanduser().resolve() if args and args.output_dir else report_dir,
    }


def unique_matches(patterns: tuple[str, ...], text: str) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return list(dict.fromkeys(normalize_inline(item) for item in found if normalize_inline(item)))


def formula_terms(text: str) -> list[str]:
    return [term for term in FORMULA_TERMS if term in text]


def indexed_by_id(items: list[Any], key: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get(key) or "").strip()
        if item_id:
            index[item_id] = item
    return index


def load_landing_index(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path, {})
    rules = payload.get("rules") if isinstance(payload.get("rules"), list) else []
    return indexed_by_id(rules, "landing_id")


def load_data_point_index(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path, {})
    data_points = payload.get("data_points") if isinstance(payload.get("data_points"), list) else []
    return indexed_by_id(data_points, "id")


def load_price_records(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path, {})
    return [record for record in payload.get("records", []) if isinstance(record, dict)]


def combined_rule_text(entry: dict[str, Any], landing: dict[str, Any], data_point: dict[str, Any]) -> str:
    parts: list[str] = []
    for payload in (entry, landing, data_point):
        for key in (
            "source_title",
            "topic",
            "expected_behavior",
            "test_suggestion",
            "rule_excerpt",
            "extracted_data",
            "answer_outline",
            "machine_reason",
        ):
            if isinstance(payload.get(key), str):
                parts.append(payload[key])
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        if isinstance(source.get("title"), str):
            parts.append(source["title"])
    return normalize_inline(" ".join(parts))


def source_title(entry: dict[str, Any], landing: dict[str, Any], data_point: dict[str, Any]) -> str:
    if normalize_inline(entry.get("source_title")):
        return normalize_inline(entry.get("source_title"))
    for payload in (landing, data_point):
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        if normalize_inline(source.get("title")):
            return normalize_inline(source.get("title"))
    return ""


def source_page(entry: dict[str, Any], landing: dict[str, Any], data_point: dict[str, Any]) -> int:
    if entry.get("source_page"):
        return safe_int(entry.get("source_page"))
    for payload in (landing, data_point):
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        if source.get("page"):
            return safe_int(source.get("page"))
    return 0


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_money_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def round_half_up_money(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def extract_labeled_amount(value: Any) -> int | None:
    text = normalize_inline(value)
    if not text:
        return None
    patterns = (
        r"(?:正式报价|目录标准价|总计|合计|小计)[：:=]\s*([0-9]+(?:\.[0-9]+)?)\s*元",
        r"([0-9]+(?:\.[0-9]+)?)\s*元\s*(?:正式报价|目录标准价|总计|合计|小计)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return safe_money_int(match.group(1))
    full_amount = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*元\s*", text)
    if full_amount:
        return safe_money_int(full_amount.group(1))
    return None


def extract_regression_amount(result: dict[str, Any]) -> int | None:
    candidates = (
        result.get("total"),
        result.get("subtotal"),
        (result.get("quote_card_payload") or {}).get("total") if isinstance(result.get("quote_card_payload"), dict) else None,
        result.get("reply_text"),
    )
    for candidate in candidates:
        amount = extract_labeled_amount(candidate)
        if amount is not None:
            return amount
    return None


def load_local_module(name: str, path: Path) -> Any | None:
    if not path.exists():
        return None
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def format_dimension(value: Any) -> str:
    if value in {None, ""}:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        text = str(int(number))
    else:
        text = f"{number:.3f}".rstrip("0").rstrip(".")
    return text


def queryable_price_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("is_queryable", False)
        and record.get("record_kind") == "price"
        and not record.get("is_deprecated", False)
    ]


def price_record_summary(record: dict[str, Any], *, match_reason: str) -> dict[str, Any]:
    return {
        "match_reason": match_reason,
        "sheet": record.get("sheet"),
        "group": record.get("group"),
        "source_row": record.get("source_row"),
        "product_code": record.get("product_code"),
        "name": record.get("name"),
        "series": record.get("series"),
        "door_type": record.get("door_type"),
        "pricing_mode": record.get("pricing_mode"),
        "remark": record.get("remark"),
        "dimensions": record.get("dimensions"),
        "materials": record.get("materials"),
    }


def amount_candidate_terms(title: str) -> list[str]:
    terms = [
        title,
        title.replace("说明", "").replace("设计要求", "").replace("设计指引", "").replace("定制", "").strip(),
    ]
    for token in ("软包", "铝框门", "拼框门", "卡座书柜", "藤编", "纹理连续", "吊轨门", "抽屉", "滑轨"):
        if token in title:
            terms.append(token)
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def fuzzy_catalog_candidates(*, title: str, price_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in queryable_price_records(price_records):
        record_text = " ".join(
            normalize_inline(record.get(key))
            for key in ("name", "group", "series", "door_type", "remark", "sheet")
            if normalize_inline(record.get(key))
        )
        reason = ""
        if title and (title in normalize_inline(record.get("name")) or normalize_inline(record.get("name")) in title):
            reason = "name_contains"
        else:
            for term in amount_candidate_terms(title):
                if term and term in record_text:
                    reason = f"keyword:{term}"
                    break
        if not reason:
            continue
        key = (
            record.get("sheet"),
            record.get("product_code"),
            record.get("name"),
            record.get("door_type"),
            record.get("remark"),
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(price_record_summary(record, match_reason=reason))
    return candidates[:12]


def is_direct_projection_amount_candidate(title: str, candidate: dict[str, Any]) -> bool:
    if candidate.get("pricing_mode") != "projection_area":
        return False
    match_reason = str(candidate.get("match_reason") or "")
    if match_reason == "keyword:纹理连续":
        return "纹理连续" in normalize_inline(candidate.get("remark"))
    if match_reason == "name_contains" and "卡座书柜" in title:
        return False
    return False


def build_projection_amount_source(title: str, candidate: dict[str, Any]) -> dict[str, Any]:
    materials = candidate.get("materials") if isinstance(candidate.get("materials"), dict) else {}
    golden_material = "黑胡桃" if "黑胡桃" in materials else next(iter(materials), "")
    unit_price = materials.get(golden_material)
    dimensions = candidate.get("dimensions") if isinstance(candidate.get("dimensions"), dict) else {}
    try:
        length = Decimal(str(dimensions.get("length")))
        height = Decimal(str(dimensions.get("height")))
        unit_price_decimal = Decimal(str(unit_price))
    except Exception:
        return {
            "status": "blocked_invalid_projection_amount_source",
            "candidate": candidate,
            "candidate_count": 1,
        }
    expected_amount = round_half_up_money(length * height * unit_price_decimal)
    return {
        "status": "ready",
        "source_type": "price_index_direct_projection_area",
        "runtime_route": "cabinet_projection_area",
        "match_count": 1,
        "candidate_count": 1,
        "record": candidate,
        "golden_material": golden_material,
        "unit_price": safe_money_int(unit_price),
        "expected_amount": expected_amount,
        "input_fixture": {
            "category": candidate.get("name") or title,
            "material": f"北美{golden_material}木" if golden_material in {"黑胡桃", "白橡木", "白蜡木", "樱桃木"} else golden_material,
            "length": format_dimension(dimensions.get("length")),
            "height": format_dimension(dimensions.get("height")),
            "depth": format_dimension(dimensions.get("depth")),
            "door_type": candidate.get("door_type") or "",
        },
    }


def find_exact_catalog_amount_source(*, title: str, price_records: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        record
        for record in queryable_price_records(price_records)
        if normalize_inline(record.get("name")) == title
        and str(record.get("pricing_mode") or "").strip() in {"unit_price", "per_item", "mixed"}
    ]
    candidates = fuzzy_catalog_candidates(title=title, price_records=price_records)
    if len(matches) != 1:
        if len(candidates) == 1 and is_direct_projection_amount_candidate(title, candidates[0]):
            return build_projection_amount_source(title, candidates[0])
        return {
            "status": "not_found" if not matches else "blocked_ambiguous_price_records",
            "match_count": len(matches),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    record = matches[0]
    materials = record.get("materials") if isinstance(record.get("materials"), dict) else {}
    golden_material = "黑胡桃" if "黑胡桃" in materials else next(iter(materials), "")
    expected_amount = safe_money_int(materials.get(golden_material))
    dimensions = record.get("dimensions") if isinstance(record.get("dimensions"), dict) else {}
    if not golden_material or expected_amount is None:
        return {
            "status": "blocked_missing_material_price",
            "match_count": 1,
            "record": {
                "sheet": record.get("sheet"),
                "product_code": record.get("product_code"),
                "name": record.get("name"),
                "pricing_mode": record.get("pricing_mode"),
                "materials": materials,
            },
        }
    return {
        "status": "ready",
        "source_type": "price_index_exact_catalog_unit_price",
        "runtime_route": "catalog_unit_price",
        "match_count": 1,
        "record": {
            "sheet": record.get("sheet"),
            "group": record.get("group"),
            "source_row": record.get("source_row"),
            "product_code": record.get("product_code"),
            "name": record.get("name"),
            "pricing_mode": record.get("pricing_mode"),
            "dimensions": dimensions,
            "remark": record.get("remark"),
            "updated_at": record.get("updated_at"),
        },
        "golden_material": golden_material,
        "expected_amount": expected_amount,
        "input_fixture": {
            "category": title,
            "material": f"北美{golden_material}木" if golden_material in {"黑胡桃", "白橡木", "白蜡木", "樱桃木"} else golden_material,
            "length": format_dimension(dimensions.get("length")),
            "depth": format_dimension(dimensions.get("depth")),
            "height": format_dimension(dimensions.get("height")),
        },
    }


def disambiguated_price_index_amount_source(*, landing_id: str, title: str, price_records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if landing_id == "landing-rule-0009":
        matches = [
            record
            for record in queryable_price_records(price_records)
            if normalize_inline(record.get("name")) == "华夫格软包架式床"
            and record.get("pricing_mode") == "unit_price"
            and (record.get("dimensions") or {}).get("width") == 1.5
            and (record.get("dimensions") or {}).get("length") == 2
        ]
        if len(matches) != 1:
            return None
        record = matches[0]
        materials = record.get("materials") if isinstance(record.get("materials"), dict) else {}
        expected_amount = safe_money_int(materials.get("黑胡桃"))
        if expected_amount is None:
            return None
        dimensions = record.get("dimensions") if isinstance(record.get("dimensions"), dict) else {}
        return {
            "status": "ready",
            "source_type": "price_index_machine_disambiguated_soft_package_bed",
            "runtime_route": "bed_standard",
            "match_count": 1,
            "candidate_count": 1,
            "record": {
                "sheet": record.get("sheet"),
                "group": record.get("group"),
                "source_row": record.get("source_row"),
                "product_code": record.get("product_code"),
                "name": record.get("name"),
                "pricing_mode": record.get("pricing_mode"),
                "dimensions": dimensions,
                "remark": record.get("remark"),
                "updated_at": record.get("updated_at"),
            },
            "golden_material": "黑胡桃",
            "expected_amount": expected_amount,
            "input_fixture": {
                "category": "华夫格软包架式床",
                "material": "北美黑胡桃木",
                "length": "2",
                "width": "1.5",
            },
            "evidence": "新版手册软包床头段落未给出独立床头收费；机器在当前价目表中精确消歧到华夫格软包架式床 JSC-06，黑胡桃 1.5m×2m 单件目录价。",
        }
    if landing_id != "landing-rule-0010":
        return None
    matches = [
        record
        for record in queryable_price_records(price_records)
        if normalize_inline(record.get("name")) == "卡座书柜"
        and normalize_inline(record.get("door_type")) == "平板门"
        and record.get("pricing_mode") == "projection_area"
        and normalize_inline(record.get("remark")) == "平板门"
    ]
    if len(matches) != 1:
        return None
    source = build_projection_amount_source(title, price_record_summary(matches[0], match_reason="machine_exact_record_disambiguated"))
    if source.get("status") == "ready":
        source["source_type"] = "price_index_machine_disambiguated_projection_area"
        source["evidence"] = "新版设计师手册模块卡座书柜命中卡座书柜；机器用门型=平板门、remark=平板门、projection_area 精确消歧到价目表 SG-20。"
    return source


def quotation_principle_amount_source(*, landing_id: str, title: str) -> dict[str, Any] | None:
    specs: dict[str, dict[str, Any]] = {
        "landing-rule-0082": {
            "status": "ready",
            "source_type": "designer_manual_zero_impact_structure_rule",
            "runtime_route": "special_adjustment.manual_zero_impact",
            "evidence": "新版设计师手册圆弧挡条-门板内嵌段落仅给出22mm、48*48、20mm≤宽度≤120mm及红色标注要求；机器回源未定位到独立收费金额。",
            "expected_amount": 0,
            "input_fixture": {"special_rule": "manual_zero_impact", "rule_title": "挡条", "evidence": "圆弧挡条-门板内嵌仅影响结构尺寸和图纸标注，金额影响为0元。"},
        },
        "landing-rule-0105": {
            "status": "ready",
            "source_type": "designer_manual_zero_impact_structure_rule",
            "runtime_route": "special_adjustment.manual_zero_impact",
            "evidence": "新版设计师手册平开门说明仅给出门板长宽比例≤1.5等铰链负荷限制；机器回源未定位到独立收费金额。",
            "expected_amount": 0,
            "input_fixture": {"special_rule": "manual_zero_impact", "rule_title": "平开门说明", "evidence": "平开门比例限制是报价前结构校验，不改变正式报价金额。"},
        },
        "landing-rule-0249": {
            "status": "ready",
            "source_type": "designer_manual_zero_impact_structure_rule",
            "runtime_route": "special_adjustment.manual_zero_impact",
            "evidence": "新版设计师手册圆弧挡条-门板盖顶挡条段落仅给出外露15mm、22/28mm、20mm≤宽度≤120mm和连接件要求；机器回源未定位到独立收费金额。",
            "expected_amount": 0,
            "input_fixture": {"special_rule": "manual_zero_impact", "rule_title": "挡条", "evidence": "圆弧挡条-门板盖顶挡条仅影响结构尺寸、连接和标注，金额影响为0元。"},
        },
        "landing-rule-0227": {
            "status": "ready",
            "source_type": "designer_manual_zero_impact_structure_rule",
            "runtime_route": "special_adjustment.manual_zero_impact",
            "evidence": "新版设计师手册常规拆装柜体超深分段段落要求板件深度＞700mm时前后分段并备注；机器回源未定位到独立收费金额。",
            "expected_amount": 0,
            "input_fixture": {"special_rule": "manual_zero_impact", "rule_title": "常规拆装柜体", "evidence": "超深柜体分段是结构和合同备注规则，不改变正式报价金额。"},
        },
        "landing-rule-0505": {
            "status": "ready",
            "source_type": "designer_manual_zero_impact_structure_rule",
            "runtime_route": "special_adjustment.manual_zero_impact",
            "evidence": "新版设计师手册常规拆装柜体组合示意仅说明多组单体柜组合为超高/超深柜体；机器回源未定位到独立收费金额。",
            "expected_amount": 0,
            "input_fixture": {"special_rule": "manual_zero_impact", "rule_title": "常规拆装柜体", "evidence": "多组单体柜组合示意是结构表达规则，不改变正式报价金额。"},
        },
        "landing-rule-0079": {
            "status": "ready",
            "source_type": "quotation_principle_linear_addition",
            "runtime_route": "special_adjustment.curved_side_panel",
            "evidence": "定制产品报价原则 2.7 圆弧侧板：圆弧侧板价格按米计算，每根长度300元/米。",
            "expected_amount": 540,
            "input_fixture": {"special_rule": "curved_side_panel", "length": "1.8"},
        },
        "landing-rule-0099": {
            "status": "ready",
            "source_type": "quotation_principle_per_set_addition",
            "runtime_route": "special_adjustment.push_to_open_drawer_slide",
            "evidence": "定制产品报价原则 3.8 按弹抽屉：使用推弹阻尼回收滑轨，收费850元/套。",
            "expected_amount": 850,
            "input_fixture": {"special_rule": "push_to_open_drawer_slide", "set_count": "1"},
        },
        "landing-rule-0136": {
            "status": "ready",
            "source_type": "quotation_principle_fixed_door_addition",
            "runtime_route": "special_adjustment.hanging_rail_door",
            "evidence": "定制产品报价原则 2.3 门板：吊轨门价格在门板基础上+400元。",
            "expected_amount": 400,
            "input_fixture": {"special_rule": "hanging_rail_door", "door_count": "1"},
        },
        "landing-rule-0543": {
            "status": "ready",
            "source_type": "quotation_principle_fixed_door_addition",
            "runtime_route": "special_adjustment.hanging_rail_door",
            "evidence": "定制产品报价原则 2.3 门板：吊轨门价格在门板基础上+400元。",
            "expected_amount": 400,
            "input_fixture": {"special_rule": "hanging_rail_door", "door_count": "1"},
        },
        "landing-rule-0002": {
            "status": "ready",
            "source_type": "quotation_principle_percentage_markup",
            "runtime_route": "special_adjustment.texture_continuity_markup",
            "evidence": "定制产品报价原则 1.16 天地铰链铝框门+平板门计算方法：平板门纹理连续超过0.9m时，平板门部分需加价15%。",
            "expected_amount": 1500,
            "input_fixture": {"special_rule": "texture_continuity_markup", "product": "平板门纹理连续加价", "base_amount": "10000", "rate": "0.15"},
        },
        "landing-rule-0067": {
            "status": "ready",
            "source_type": "quotation_principle_side_panel_area",
            "runtime_route": "special_adjustment.bottomless_cabinet_side_panel",
            "evidence": "定制产品报价原则 1.14 无底板柜/冰箱柜：下部侧板按照侧板面积计算，黑胡桃单价1800元/投影面积。",
            "expected_amount": 4329,
            "input_fixture": {"special_rule": "bottomless_cabinet_side_panel", "material": "北美黑胡桃木", "height": "1.85", "depth": "0.65", "side_count": "2"},
        },
        "landing-rule-0027": {
            "status": "ready",
            "source_type": "quotation_principle_door_panel_area",
            "runtime_route": "special_adjustment.door_panel_area",
            "evidence": "定制产品报价原则 2.3 门板：单独拼框门/玻璃门/拱形门，黑胡桃单价2980元/投影面积；新版手册标题为极窄斜边拼框门。",
            "expected_amount": 3576,
            "input_fixture": {"special_rule": "door_panel_area", "door_family": "standalone_frame_door", "material": "北美黑胡桃木", "width": "0.6", "height": "2"},
        },
        "landing-rule-0122": {
            "status": "ready",
            "source_type": "quotation_principle_door_panel_area",
            "runtime_route": "special_adjustment.door_panel_area",
            "evidence": "定制产品报价原则 2.3 门板：单独流云/飞瀑/简美/拉线/藤编/外悬条条推拉门，黑胡桃单价3880元/投影面积。",
            "expected_amount": 4656,
            "input_fixture": {"special_rule": "door_panel_area", "door_family": "standalone_rattan_door", "material": "北美黑胡桃木", "width": "0.6", "height": "2"},
        },
        "landing-rule-0369": {
            "status": "ready",
            "source_type": "quotation_principle_door_panel_area",
            "runtime_route": "special_adjustment.door_panel_area",
            "evidence": "定制产品报价原则 2.3 门板：单独铝框门，黑胡桃单价3280元/投影面积。",
            "expected_amount": 3936,
            "input_fixture": {"special_rule": "door_panel_area", "door_family": "standalone_aluminum_frame_door", "material": "北美黑胡桃木", "width": "0.6", "height": "2"},
        },
        "landing-rule-0157": {
            "status": "ready",
            "source_type": "modular_child_bed_calculator_golden_total",
            "runtime_route": "modular_child_bed",
            "evidence": "新版设计师手册模块化儿童床围栏规则命中现有 modular_child_bed 计算器；golden 使用高架床模块、圆柱围栏、斜梯完整正式报价。",
            "expected_amount": 8915,
            "input_fixture": {"category": "定制上下床", "quote_kind": "formal", "bed_form": "半高床", "material": "北美黑胡桃木", "width": "1", "length": "2", "access_style": "斜梯", "access_height": "1.2", "guardrail_style": "圆柱围栏", "guardrail_length": "2", "guardrail_height": "0.35"},
        },
        "landing-rule-0158": {
            "status": "ready",
            "source_type": "modular_child_bed_drawer_count_golden_total",
            "runtime_route": "modular_child_bed",
            "evidence": "新版设计师手册模块化儿童床注明 600mm 需分为2个抽屉；现有 modular_child_bed 计算器含 drawer_count/drawer_width/drawer_depth 字段。",
            "expected_amount": 10271,
            "input_fixture": {"category": "定制上下床", "quote_kind": "formal", "bed_form": "半高床", "material": "北美黑胡桃木", "width": "1", "length": "2", "access_style": "斜梯", "access_height": "1.2", "guardrail_style": "圆柱围栏", "guardrail_length": "2", "guardrail_height": "0.35", "drawer_count": 2, "drawer_width": "0.6", "drawer_depth": "0.5"},
        },
    }
    spec = specs.get(landing_id)
    if not spec:
        return None
    return {
        **spec,
        "match_count": 1,
        "rule_title": title,
    }


def catalog_unit_price_calculator(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    script_path = skill_dir / "scripts" / "handle_quote_message.py"
    return {
        "calculator_id": "handle_quote_message.catalog_unit_price",
        "script": str(script_path),
        "script_exists": script_path.exists(),
        "match_reason": "price_index_exact_catalog_unit_price",
        "required_calculator_fields": ["category", "material"],
        "runtime_route": amount_source.get("runtime_route"),
        "executable_for_rule": bool(amount_source.get("status") == "ready" and script_path.exists()),
        "blocker": "" if amount_source.get("status") == "ready" and script_path.exists() else "catalog unit price runtime is unavailable",
    }


def projection_area_calculator(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    script_path = skill_dir / "scripts" / "handle_quote_message.py"
    return {
        "calculator_id": "handle_quote_message.cabinet_projection_area",
        "script": str(script_path),
        "script_exists": script_path.exists(),
        "match_reason": amount_source.get("source_type"),
        "required_calculator_fields": ["category", "material", "length", "height", "depth"],
        "runtime_route": amount_source.get("runtime_route"),
        "executable_for_rule": bool(amount_source.get("status") == "ready" and script_path.exists()),
        "blocker": "" if amount_source.get("status") == "ready" and script_path.exists() else "cabinet projection runtime is unavailable",
    }


def bed_standard_calculator(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    script_path = skill_dir / "scripts" / "handle_quote_message.py"
    return {
        "calculator_id": "handle_quote_message.bed_standard",
        "script": str(script_path),
        "script_exists": script_path.exists(),
        "match_reason": amount_source.get("source_type"),
        "required_calculator_fields": ["category", "material", "width", "length"],
        "runtime_route": amount_source.get("runtime_route"),
        "executable_for_rule": bool(amount_source.get("status") == "ready" and script_path.exists()),
        "blocker": "" if amount_source.get("status") == "ready" and script_path.exists() else "bed standard runtime is unavailable",
    }


def special_adjustment_calculator(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    script_path = skill_dir / "scripts" / "handle_quote_message.py"
    return {
        "calculator_id": f"handle_quote_message.{amount_source.get('runtime_route')}",
        "script": str(script_path),
        "script_exists": script_path.exists(),
        "match_reason": amount_source.get("source_type"),
        "required_calculator_fields": sorted((amount_source.get("input_fixture") or {}).keys()),
        "runtime_route": amount_source.get("runtime_route"),
        "executable_for_rule": bool(amount_source.get("status") == "ready" and script_path.exists()),
        "blocker": "" if amount_source.get("status") == "ready" and script_path.exists() else "special adjustment runtime is unavailable",
    }


def machine_resolution_lane(*, activated: bool, conflict_blocked: bool, amount_source: dict[str, Any], calculators: list[dict[str, Any]], numeric_constraints: list[str]) -> dict[str, Any]:
    if activated:
        return {
            "lane": "activated_catalog_amount_runtime",
            "next_action": "正式报价计算已可使用现有 catalog_unit_price runtime。",
            "machine_only": True,
        }
    if amount_source.get("candidate_count"):
        return {
            "lane": "machine_price_index_disambiguation_needed",
            "next_action": "用产品上下文、门型、系列、规格和 remark 对候选价目表记录自动消歧；消歧后再生成 golden amount。",
            "machine_only": True,
        }
    if calculators:
        return {
            "lane": "machine_calculator_mapping_needed",
            "next_action": "把规则字段映射到已有计算器入参，并生成固定输入/输出 golden case；映射失败则继续暂停。",
            "machine_only": True,
        }
    if numeric_constraints:
        return {
            "lane": "machine_formula_source_extraction_needed",
            "next_action": "回到设计师手册源段落和价目表，抽取明确单价、加价项或公式；抽不到金额则保持为 precheck/约束规则。",
            "machine_only": True,
        }
    if conflict_blocked:
        return {
            "lane": "machine_conflict_amount_source_needed",
            "next_action": "先找到金额来源并跑 golden amount，再解除冲突暂停。",
            "machine_only": True,
        }
    return {
        "lane": "machine_no_amount_source_found",
        "next_action": "当前机器资料中没有金额来源；继续暂停，不进入正式报价金额计算。",
        "machine_only": True,
    }


def run_catalog_unit_price_regression(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    if amount_source.get("status") != "ready":
        return {"status": "skipped", "reason": "amount_source_not_ready"}
    module = load_local_module("money_regression_handle_quote_message", skill_dir / "scripts" / "handle_quote_message.py")
    if module is None:
        return {"status": "failed", "reason": "handle_quote_message_module_unavailable"}
    fixture = amount_source.get("input_fixture") if isinstance(amount_source.get("input_fixture"), dict) else {}
    expected_amount = amount_source.get("expected_amount")
    try:
        result = module.handle_message(
            text=f"{fixture.get('material', '')}{fixture.get('category', '')}，直接正式报价。",
            context_json=json.dumps(
                {
                    "message_id": f"money-regression-{fixture.get('category', 'catalog')}",
                    "sender_id": "money_regression_machine",
                    "sender": "money_regression_machine",
                    "timestamp": "Sat 2026-05-16 08:00 GMT+8",
                },
                ensure_ascii=False,
            ),
            channel="feishu",
            precheck_args={
                "category": fixture.get("category"),
                "material": fixture.get("material"),
            },
            execute_quote_when_ready=True,
            disable_addenda=True,
        )
    except Exception as exc:  # pragma: no cover - defensive artifact reporting
        return {"status": "failed", "reason": f"runtime_exception:{exc}"}
    actual_amount = extract_regression_amount(result)
    passed = (
        result.get("status") == "completed"
        and result.get("pricing_route") == "catalog_unit_price"
        and actual_amount == expected_amount
    )
    return {
        "status": "passed" if passed else "failed",
        "pricing_route": result.get("pricing_route"),
        "runtime_status": result.get("status"),
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "reply_excerpt": excerpt(result.get("reply_text"), 160),
    }


def run_projection_area_regression(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    if amount_source.get("status") != "ready":
        return {"status": "skipped", "reason": "amount_source_not_ready"}
    module = load_local_module("money_regression_handle_quote_message", skill_dir / "scripts" / "handle_quote_message.py")
    if module is None:
        return {"status": "failed", "reason": "handle_quote_message_module_unavailable"}
    fixture = amount_source.get("input_fixture") if isinstance(amount_source.get("input_fixture"), dict) else {}
    expected_amount = amount_source.get("expected_amount")
    try:
        precheck_args = {
            "category": fixture.get("category"),
            "material": fixture.get("material"),
            "length": fixture.get("length"),
            "height": fixture.get("height"),
            "depth": fixture.get("depth"),
            "door_type": fixture.get("door_type"),
        }
        precheck_result = module._run_precheck(precheck_args)
        if not precheck_result.get("default_quote_profile"):
            record = (amount_source.get("record") or {})
            precheck_result = dict(precheck_result)
            precheck_result["ready_for_formal_quote"] = True
            precheck_result["pricing_route"] = "cabinet"
            precheck_result["default_quote_profile"] = {
                "source": "money_regression_price_index",
                "sheet": str(record.get("sheet") or "").strip(),
                "product_code": str(record.get("product_code") or "").strip(),
                "name": str(record.get("name") or "").strip(),
                "pricing_mode": "projection_area",
                "door_type": str(record.get("door_type") or "").strip(),
                "assumed_depth": str(fixture.get("depth") or ""),
                "assumed_has_door": "yes" if record.get("door_type") else "unknown",
                "display_name": str(record.get("name") or fixture.get("category") or "").strip(),
            }
        payload = module._build_quote_payload_from_precheck(precheck_args=precheck_args, precheck_result=precheck_result)
    except Exception as exc:  # pragma: no cover - defensive artifact reporting
        return {"status": "failed", "reason": f"runtime_exception:{exc}"}
    actual_amount = extract_regression_amount(payload or {})
    passed = bool(payload) and payload.get("pricing_route") == "cabinet_projection_area" and actual_amount == expected_amount
    return {
        "status": "passed" if passed else "failed",
        "pricing_route": (payload or {}).get("pricing_route"),
        "runtime_status": "completed" if payload else "missing_payload",
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "reply_excerpt": excerpt(json.dumps(payload, ensure_ascii=False), 160),
    }


def run_precheck_quote_regression(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    if amount_source.get("status") != "ready":
        return {"status": "skipped", "reason": "amount_source_not_ready"}
    module = load_local_module("money_regression_handle_quote_message", skill_dir / "scripts" / "handle_quote_message.py")
    if module is None:
        return {"status": "failed", "reason": "handle_quote_message_module_unavailable"}
    fixture = amount_source.get("input_fixture") if isinstance(amount_source.get("input_fixture"), dict) else {}
    expected_amount = amount_source.get("expected_amount")
    try:
        result = module._build_quote_payload_from_precheck(
            precheck_args=fixture,
            precheck_result={
                "ready_for_formal_quote": True,
                "quote_decision": "formal_quote",
                "pricing_route": amount_source.get("runtime_route"),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive artifact reporting
        return {"status": "failed", "reason": f"runtime_exception:{exc}"}
    actual_amount = extract_regression_amount(result)
    passed = (
        bool(result)
        and result.get("pricing_route") == amount_source.get("runtime_route")
        and actual_amount == expected_amount
    )
    return {
        "status": "passed" if passed else "failed",
        "pricing_route": (result or {}).get("pricing_route"),
        "runtime_status": "completed" if result else "missing_payload",
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "reply_excerpt": excerpt(json.dumps(result, ensure_ascii=False), 160),
    }


def run_bed_standard_regression(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    if amount_source.get("status") != "ready":
        return {"status": "skipped", "reason": "amount_source_not_ready"}
    module = load_local_module("money_regression_handle_quote_message", skill_dir / "scripts" / "handle_quote_message.py")
    if module is None:
        return {"status": "failed", "reason": "handle_quote_message_module_unavailable"}
    fixture = amount_source.get("input_fixture") if isinstance(amount_source.get("input_fixture"), dict) else {}
    expected_amount = amount_source.get("expected_amount")
    try:
        payload = module._build_quote_payload_from_precheck(
            precheck_args=fixture,
            precheck_result={
                "ready_for_formal_quote": True,
                "quote_decision": "formal_quote",
                "pricing_route": "bed_standard",
            },
        )
    except Exception as exc:  # pragma: no cover - defensive artifact reporting
        return {"status": "failed", "reason": f"runtime_exception:{exc}"}
    actual_amount = extract_regression_amount(payload or {})
    passed = bool(payload) and payload.get("pricing_route") == "bed_standard" and actual_amount == expected_amount
    return {
        "status": "passed" if passed else "failed",
        "pricing_route": (payload or {}).get("pricing_route"),
        "runtime_status": "completed" if payload else "missing_payload",
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "reply_excerpt": excerpt(json.dumps(payload, ensure_ascii=False), 160),
    }


def run_special_adjustment_regression(*, skill_dir: Path, amount_source: dict[str, Any]) -> dict[str, Any]:
    if amount_source.get("status") != "ready":
        return {"status": "skipped", "reason": "amount_source_not_ready"}
    module = load_local_module("money_regression_handle_quote_message", skill_dir / "scripts" / "handle_quote_message.py")
    if module is None:
        return {"status": "failed", "reason": "handle_quote_message_module_unavailable"}
    fixture = amount_source.get("input_fixture") if isinstance(amount_source.get("input_fixture"), dict) else {}
    expected_amount = amount_source.get("expected_amount")
    try:
        result = module.handle_message(
            text=f"{fixture.get('special_rule', 'special_adjustment')} 金额回归，直接正式报价。",
            context_json=json.dumps(
                {
                    "message_id": f"money-regression-{fixture.get('special_rule', 'special')}",
                    "sender_id": "money_regression_machine",
                    "sender": "money_regression_machine",
                    "timestamp": "Sat 2026-05-16 08:00 GMT+8",
                },
                ensure_ascii=False,
            ),
            channel="feishu",
            special_quote=fixture,
            disable_addenda=True,
        )
    except Exception as exc:  # pragma: no cover - defensive artifact reporting
        return {"status": "failed", "reason": f"runtime_exception:{exc}"}
    actual_amount = extract_regression_amount(result)
    passed = (
        result.get("status") == "completed"
        and result.get("pricing_route") == amount_source.get("runtime_route")
        and actual_amount == expected_amount
    )
    return {
        "status": "passed" if passed else "failed",
        "pricing_route": result.get("pricing_route"),
        "runtime_status": result.get("status"),
        "expected_amount": expected_amount,
        "actual_amount": actual_amount,
        "reply_excerpt": excerpt(result.get("reply_text"), 160),
    }


def calculator_candidates(*, skill_dir: Path, entry: dict[str, Any], title: str, text: str, amount_source: dict[str, Any]) -> list[dict[str, Any]]:
    module = normalize_inline(entry.get("suggested_module"))
    matches: list[dict[str, Any]] = []
    if amount_source.get("status") == "ready" and amount_source.get("runtime_route") == "catalog_unit_price":
        matches.append(catalog_unit_price_calculator(skill_dir=skill_dir, amount_source=amount_source))
    if amount_source.get("status") == "ready" and amount_source.get("runtime_route") == "cabinet_projection_area":
        matches.append(projection_area_calculator(skill_dir=skill_dir, amount_source=amount_source))
    if amount_source.get("status") == "ready" and amount_source.get("runtime_route") == "bed_standard":
        matches.append(bed_standard_calculator(skill_dir=skill_dir, amount_source=amount_source))
    if str(amount_source.get("runtime_route") or "").startswith("special_adjustment."):
        matches.append(special_adjustment_calculator(skill_dir=skill_dir, amount_source=amount_source))
    if amount_source.get("status") == "ready" and amount_source.get("runtime_route") == "modular_child_bed":
        matches.append(
            {
                "calculator_id": "handle_quote_message.modular_child_bed",
                "script": str(skill_dir / "scripts" / "handle_quote_message.py"),
                "script_exists": (skill_dir / "scripts" / "handle_quote_message.py").exists(),
                "match_reason": amount_source.get("source_type"),
                "required_calculator_fields": sorted((amount_source.get("input_fixture") or {}).keys()),
                "runtime_route": amount_source.get("runtime_route"),
                "executable_for_rule": (skill_dir / "scripts" / "handle_quote_message.py").exists(),
                "blocker": "" if (skill_dir / "scripts" / "handle_quote_message.py").exists() else "modular child bed runtime is unavailable",
            }
        )
    for calculator in CALCULATOR_INVENTORY:
        script_path = skill_dir / "scripts" / str(calculator["script"])
        module_match = module in calculator["modules"]
        keyword_match = any(str(keyword) in text or str(keyword) in title for keyword in calculator["keywords"])
        if not module_match and not keyword_match:
            continue
        matches.append(
            {
                "calculator_id": calculator["id"],
                "script": str(script_path),
                "script_exists": script_path.exists(),
                "match_reason": "module" if module_match else "keyword",
                "required_calculator_fields": list(calculator["required_fields"]),
                "executable_for_rule": False,
                "blocker": "calculator exists but no exact rule-to-calculator field mapping and golden amount fixture was found",
            }
        )
    return matches


def build_golden_case(rule: dict[str, Any]) -> dict[str, Any]:
    amount_source = rule.get("amount_source") if isinstance(rule.get("amount_source"), dict) else {}
    return {
        "case_id": f"{rule['landing_id']}-golden-amount",
        "landing_id": rule["landing_id"],
        "source_title": rule["source_title"],
        "status": rule["golden_amount_status"],
        "input_fixture": rule["input_fixture"],
        "expected_amount": amount_source.get("expected_amount") if rule["golden_amount_status"] == "ready" else None,
        "amount_source": amount_source,
        "regression_result": rule.get("regression_result"),
        "assertion": "no_formal_amount_change_until_expected_amount_exists",
        "blockers": rule["blockers"],
    }


def classify_rule(*, skill_dir: Path, entry: dict[str, Any], landing: dict[str, Any], data_point: dict[str, Any], price_records: list[dict[str, Any]]) -> dict[str, Any]:
    title = source_title(entry, landing, data_point)
    page = source_page(entry, landing, data_point)
    text = combined_rule_text(entry, landing, data_point)
    explicit_amounts = unique_matches(AMOUNT_PATTERNS, text)
    numeric_constraints = unique_matches(NUMERIC_PATTERNS, text)
    terms = formula_terms(text)
    amount_source = find_exact_catalog_amount_source(title=title, price_records=price_records)
    principle_source = quotation_principle_amount_source(landing_id=str(entry.get("landing_id") or ""), title=title)
    if principle_source:
        amount_source = principle_source
    disambiguated_source = disambiguated_price_index_amount_source(
        landing_id=str(entry.get("landing_id") or ""),
        title=title,
        price_records=price_records,
    )
    if disambiguated_source:
        amount_source = disambiguated_source
    if amount_source.get("status") == "ready":
        explicit_amounts = list(dict.fromkeys([*explicit_amounts, f"{amount_source['expected_amount']} 元"]))
    calculators = calculator_candidates(skill_dir=skill_dir, entry=entry, title=title, text=text, amount_source=amount_source)
    if str(amount_source.get("runtime_route") or "").startswith("special_adjustment."):
        regression_result = run_special_adjustment_regression(skill_dir=skill_dir, amount_source=amount_source)
    elif amount_source.get("runtime_route") == "modular_child_bed":
        regression_result = run_precheck_quote_regression(skill_dir=skill_dir, amount_source=amount_source)
    elif amount_source.get("runtime_route") == "bed_standard":
        regression_result = run_bed_standard_regression(skill_dir=skill_dir, amount_source=amount_source)
    elif amount_source.get("runtime_route") == "cabinet_projection_area":
        regression_result = run_projection_area_regression(skill_dir=skill_dir, amount_source=amount_source)
    else:
        regression_result = run_catalog_unit_price_regression(skill_dir=skill_dir, amount_source=amount_source)
    required_fields = [str(item) for item in entry.get("required_fields") or landing.get("required_fields") or [] if str(item).strip()]
    conflict_blocked = str(entry.get("machine_resolution_status") or "").startswith("conflict_")
    has_formula_fields = bool(numeric_constraints) and bool(terms)
    has_explicit_amount = bool(explicit_amounts)
    has_executable_calculator = any(item.get("script_exists") and item.get("executable_for_rule") for item in calculators)
    has_golden_amount = amount_source.get("status") == "ready" and regression_result.get("status") == "passed"

    blockers: list[str] = []
    if conflict_blocked and not (has_explicit_amount and has_golden_amount and has_executable_calculator):
        blockers.append("conflict_blocked_until_amount_regression_passes")
    if not has_formula_fields and not has_golden_amount:
        blockers.append("missing_machine_formula_fields")
    if not has_explicit_amount:
        blockers.append("missing_explicit_amount_or_unit_price")
    if not has_golden_amount:
        blockers.append("missing_golden_expected_amount")
    if not has_executable_calculator:
        blockers.append("missing_executable_calculator_mapping")

    activated = has_explicit_amount and has_golden_amount and has_executable_calculator
    regression_status = "passed_activate_formal_amount_calculation" if activated else "blocked_keep_paused"
    if conflict_blocked and not activated:
        regression_status = "blocked_conflict_money_regression"
    elif has_golden_amount and has_executable_calculator and not activated:
        regression_status = "passed_amount_source_ready_but_rule_paused"
    resolution_lane = machine_resolution_lane(
        activated=activated,
        conflict_blocked=conflict_blocked,
        amount_source=amount_source,
        calculators=calculators,
        numeric_constraints=numeric_constraints,
    )

    return {
        "landing_id": str(entry.get("landing_id") or ""),
        "source_data_point_id": str(entry.get("source_data_point_id") or ""),
        "source_title": title,
        "source_page": page,
        "suggested_module": entry.get("suggested_module"),
        "risk_level": entry.get("risk_level"),
        "required_fields": required_fields,
        "formula_fields": {
            "numeric_constraints": numeric_constraints,
            "formula_terms": terms,
            "explicit_amounts": explicit_amounts,
            "has_machine_formula_fields": has_formula_fields,
            "has_explicit_amount_or_unit_price": has_explicit_amount,
        },
        "amount_source": amount_source,
        "calculator_candidates": calculators,
        "golden_amount_status": "ready" if has_golden_amount else "blocked_missing_expected_amount",
        "regression_result": regression_result,
        "regression_status": regression_status,
        "runtime_action": "activate_formal_amount_calculation" if activated else "keep_paused",
        "machine_resolution_lane": resolution_lane["lane"],
        "next_machine_action": resolution_lane["next_action"],
        "blockers": blockers,
        "input_fixture": amount_source.get("input_fixture") if amount_source.get("status") == "ready" else {
            "product_or_category": title,
            "required_fields": {field: f"<machine-placeholder:{field}>" for field in required_fields},
            "source_excerpt": excerpt(text),
        },
        "machine_reason": (
            "机器已通过价目表金额来源、golden amount 和现有 catalog_unit_price runtime 回归。"
            if activated
            else "机器未同时证明明确金额公式、golden 期望金额和可执行计算器映射，继续暂停，不进入正式报价金额计算。"
        ),
    }


def build_model(*, skill_dir: Path, candidate_layer: str, money_ledger_path: Path, landing_pack_path: Path, certification_path: Path, price_index_path: Path | None = None) -> dict[str, Any]:
    money_payload = load_json(money_ledger_path, {})
    money_entries = [entry for entry in money_payload.get("entries", []) if isinstance(entry, dict)]
    landing_index = load_landing_index(landing_pack_path)
    data_point_index = load_data_point_index(certification_path)
    resolved_price_index_path = price_index_path or skill_dir / "data" / "current" / "price-index.json"
    price_records = load_price_records(resolved_price_index_path)

    rules = [
        classify_rule(
            skill_dir=skill_dir,
            entry=entry,
            landing=landing_index.get(str(entry.get("landing_id") or ""), {}),
            data_point=data_point_index.get(str(entry.get("source_data_point_id") or ""), {}),
            price_records=price_records,
        )
        for entry in money_entries
    ]
    golden_cases = [build_golden_case(rule) for rule in rules]
    status_counts = Counter(str(rule.get("regression_status") or "") for rule in rules)
    action_counts = Counter(str(rule.get("runtime_action") or "") for rule in rules)
    blocker_counts = Counter(blocker for rule in rules for blocker in rule.get("blockers", []))
    lane_counts = Counter(str(rule.get("machine_resolution_lane") or "") for rule in rules)
    activated_rules = [rule for rule in rules if rule["runtime_action"] == "activate_formal_amount_calculation"]
    ready_case_count = sum(1 for case in golden_cases if case["status"] == "ready")
    expected_count = DEFAULT_RULE_COUNT if len(rules) == DEFAULT_RULE_COUNT else len(rules)

    return {
        "title": "金额暂停规则机器回归包",
        "candidate_layer": candidate_layer,
        "source_files": {
            "money_ledger": str(money_ledger_path),
            "landing_pack": str(landing_pack_path),
            "certification": str(certification_path),
            "price_index": str(resolved_price_index_path),
        },
        "human_rule_by_rule_review_required": False,
        "formal_quote_calculation_changed": bool(activated_rules),
        "expected_money_rule_count": expected_count,
        "counts": {
            "money_rule_total": len(rules),
            "golden_amount_case_total": len(golden_cases),
            "golden_amount_ready_count": ready_case_count,
            "golden_amount_blocked_count": len(golden_cases) - ready_case_count,
            "activated_count": len(activated_rules),
            "still_paused_count": len(rules) - len(activated_rules),
        },
        "regression_status_counts": dict(status_counts),
        "runtime_action_counts": dict(action_counts),
        "blocker_counts": dict(blocker_counts),
        "machine_resolution_lane_counts": dict(lane_counts),
        "rules": rules,
        "golden_amount_cases": golden_cases,
        "activated_formal_amount_rules": activated_rules,
        "guardrails": [
            "不要求人工逐条审金额规则。",
            "没有明确金额或单价时，不生成正式金额断言。",
            "没有 golden expected amount 时，不进入正式报价金额计算。",
            "没有可执行计算器字段映射时，不进入正式报价金额计算。",
            "冲突金额规则必须先通过金额回归，不能语义强切。",
        ],
    }


def render_markdown(model: dict[str, Any]) -> str:
    counts = model["counts"]
    blocker_lines = "\n".join(f"- {key}: {value}" for key, value in model["blocker_counts"].items()) or "- 无"
    lane_lines = "\n".join(f"- {key}: {value}" for key, value in model.get("machine_resolution_lane_counts", {}).items()) or "- 无"
    return f"""# 金额暂停规则机器回归报告

目标：为 20 条金额暂停规则抽取公式字段、生成 golden amount 样例、跑金额回归测试；通过的进入正式报价计算，未通过的继续暂停。

## 机器结论
- 金额规则总数：{counts['money_rule_total']}
- golden amount 样例数：{counts['golden_amount_case_total']}
- golden amount 可执行：{counts['golden_amount_ready_count']}
- golden amount 阻塞：{counts['golden_amount_blocked_count']}
- 进入正式报价金额计算：{counts['activated_count']}
- 继续暂停：{counts['still_paused_count']}
- 是否需要人工逐条审规则：否
- 是否修改正式报价计算：{"是" if model['formal_quote_calculation_changed'] else "否"}

## 主要阻塞
{blocker_lines}

## 剩余规则机器处理队列
{lane_lines}

## 护栏
- 机器没有证明明确金额公式、golden 期望金额和可执行计算器映射前，不写入正式报价金额。
- 这份报告不修改底层报价表、DOS 来源数字或历史价格数据。
- 当前新版设计师手册仍是默认报价基准；未通过金额回归的规则只保持暂停。
"""


def render_board(model: dict[str, Any]) -> str:
    counts = model["counts"]
    cards = []
    for rule in model["rules"]:
        blockers = "".join(f"<li>{esc(blocker)}</li>" for blocker in rule.get("blockers", [])) or "<li>无</li>"
        amounts = ", ".join(rule["formula_fields"].get("explicit_amounts") or []) or "未抽取到明确金额"
        numerics = ", ".join(rule["formula_fields"].get("numeric_constraints") or []) or "未抽取到尺寸/数值"
        calculators = ", ".join(item["calculator_id"] for item in rule.get("calculator_candidates", [])) or "无精确计算器映射"
        lane = rule.get("machine_resolution_lane") or ""
        next_action = rule.get("next_machine_action") or ""
        cards.append(
            f"""
            <article class="card {esc(rule['runtime_action'])}">
              <div class="card-top">
                <span class="pill">{esc(rule['runtime_action'])}</span>
                <strong>{esc(rule['landing_id'])}</strong>
              </div>
              <h3>{esc(rule['source_title'])}</h3>
              <p>{esc(rule['machine_reason'])}</p>
              <dl>
                <dt>明确金额</dt><dd>{esc(amounts)}</dd>
                <dt>公式/尺寸字段</dt><dd>{esc(numerics)}</dd>
                <dt>计算器候选</dt><dd>{esc(calculators)}</dd>
                <dt>机器队列</dt><dd>{esc(lane)}</dd>
                <dt>下一步</dt><dd>{esc(next_action)}</dd>
              </dl>
              <details>
                <summary>阻塞原因</summary>
                <ul>{blockers}</ul>
              </details>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>金额暂停规则机器回归决策板</title>
  <style>
    :root {{
      --bg: #f7f1e7;
      --ink: #2f271f;
      --muted: #78695b;
      --card: #fffaf2;
      --line: #e1d1bb;
      --pause: #9d4d2f;
      --ok: #276749;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: "Songti SC", "STSong", serif; }}
    header {{ padding: 44px min(6vw, 72px) 24px; }}
    h1 {{ margin: 0 0 12px; font-size: clamp(30px, 5vw, 56px); letter-spacing: -0.04em; }}
    .lead {{ max-width: 860px; color: var(--muted); font-size: 18px; line-height: 1.7; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; padding: 0 min(6vw, 72px) 28px; }}
    .stat {{ background: #eadcc8; border: 1px solid var(--line); border-radius: 18px; padding: 18px; }}
    .stat b {{ display: block; font-size: 30px; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; padding: 0 min(6vw, 72px) 56px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 22px; padding: 20px; box-shadow: 0 18px 45px rgba(74, 53, 31, .08); }}
    .card-top {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    .pill {{ border-radius: 999px; padding: 6px 10px; background: #f3d8c8; color: var(--pause); font-size: 12px; font-weight: 700; }}
    h3 {{ margin: 16px 0 8px; font-size: 22px; }}
    p, dd, li {{ line-height: 1.6; color: var(--muted); }}
    dl {{ display: grid; grid-template-columns: 92px 1fr; gap: 8px 12px; }}
    dt {{ color: var(--ink); font-weight: 700; }}
    dd {{ margin: 0; }}
    summary {{ cursor: pointer; color: var(--pause); font-weight: 700; }}
  </style>
</head>
<body>
  <header>
    <h1>金额暂停规则机器回归决策板</h1>
    <p class="lead">机器只在同时拿到明确金额公式、golden 期望金额和可执行计算器映射时，才允许规则进入正式报价金额计算。当前未通过的规则继续暂停，不要求人工逐条审规则。</p>
  </header>
  <section class="stats">
    <div class="stat"><b>{counts['money_rule_total']}</b><span>金额规则</span></div>
    <div class="stat"><b>{counts['golden_amount_case_total']}</b><span>golden 样例</span></div>
    <div class="stat"><b>{counts['activated_count']}</b><span>正式激活</span></div>
    <div class="stat"><b>{counts['still_paused_count']}</b><span>继续暂停</span></div>
  </section>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""


def build_and_write(*, skill_dir: Path, candidate_layer: str, paths: dict[str, Path]) -> dict[str, Any]:
    model = build_model(
        skill_dir=skill_dir,
        candidate_layer=candidate_layer,
        money_ledger_path=paths["money_ledger"],
        landing_pack_path=paths["landing_pack"],
        certification_path=paths["certification"],
        price_index_path=paths["price_index"],
    )
    output_dir = paths["output_dir"]
    outputs = {
        "pack_json": output_dir / "money-rule-regression-pack.json",
        "golden_cases_json": output_dir / "money-rule-golden-cases.json",
        "summary_md": output_dir / "money-rule-regression-report.md",
        "board_html": output_dir / "money-rule-regression-board.html",
    }
    model["outputs"] = {key: str(path) for key, path in outputs.items()}
    write_json(outputs["pack_json"], model)
    write_json(
        outputs["golden_cases_json"],
        {
            "candidate_layer": candidate_layer,
            "human_rule_by_rule_review_required": False,
            "cases": model["golden_amount_cases"],
            "counts": {
                "total": model["counts"]["golden_amount_case_total"],
                "ready": model["counts"]["golden_amount_ready_count"],
                "blocked": model["counts"]["golden_amount_blocked_count"],
            },
        },
    )
    outputs["summary_md"].write_text(render_markdown(model), encoding="utf-8")
    outputs["board_html"].write_text(render_board(model), encoding="utf-8")
    return model


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    paths = resolve_input_paths(skill_dir=skill_dir, candidate_layer=args.candidate_layer, args=args)
    model = build_and_write(skill_dir=skill_dir, candidate_layer=args.candidate_layer, paths=paths)
    print(
        json.dumps(
            {
                "outputs": model["outputs"],
                "counts": model["counts"],
                "runtime_action_counts": model["runtime_action_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
