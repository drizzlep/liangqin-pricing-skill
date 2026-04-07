#!/usr/bin/env python3
"""Deterministic intake helpers for non-quote customer inquiries."""

from __future__ import annotations

import re
from decimal import Decimal
from math import isclose
from typing import Any

import precheck_quote


SIZE_SPEC_PATTERN = re.compile(
    r"(这款(?:没有)?尺寸吗|这款.*尺寸|什么尺寸(?:的[^，。！？]*)?|尺寸是多少|什么规格|规格是多少|长宽高(?:是多少|多少|吗)?|多大|多高|多宽|多深|多长(?!时间))"
)
MEASUREMENT_INSTALLATION_PATTERN = re.compile(r"(怎么量|量尺寸|量尺|怎么测|如何量|怎么留尺寸|量哪里|怎么预留)")
LEAD_TIME_SERVICE_PATTERN = re.compile(r"(多久|周期|交期|发货|什么时候用|多长时间|要多久|大概要多久)")
MATERIAL_CONFIG_PATTERN = re.compile(r"(纯实木|全实木|木蜡油|甲醛|环保|五金|BLUM|百隆|海蒂诗|DTC|进口五金|国产五金)")
PURCHASE_MODE_PATTERN = re.compile(r"(定制|订制|订做|成品|现货|现成|做好|标准品|标品)")
QUOTE_HINT_PATTERN = re.compile(r"(多少钱|报价|报个价|价格|费用|预算|正式报价|参考价)")
RULE_CONSULTATION_PATTERN = re.compile(r"(规则|工艺|结构|节点|默认做|允许范围|专项|加价|顶盖侧|侧盖顶|牙称)")
PRODUCT_CATEGORY_PATTERN = re.compile(r"(衣柜|书柜|玄关柜|电视柜|餐边柜|床|上下床|高架床|半高床|榻榻米|书桌)")
MATERIAL_NAME_PATTERN = re.compile(r"(北美黑胡桃木|北美樱桃木|北美白橡木|北美白蜡木|乌拉圭玫瑰木)")
LABELED_DIMENSION_PATTERN = re.compile(r"(长|高|深|宽)\s*[:：]?\s*\d")
DIMENSION_VALUE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mm|毫米|cm|厘米|m|米)|(\d+(?:\.\d+)?)\s*[*xX×乘]\s*(\d+(?:\.\d+)?)"
)


def _normalize_product_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("sheet") or "").strip(),
        str(record.get("product_code") or "").strip(),
        str(record.get("name") or "").strip(),
    )


def _dimensions_signature(dimensions: dict[str, Any] | None) -> tuple[str, str, str, str]:
    payload = dimensions or {}
    return (
        str(payload.get("length") or "").strip(),
        str(payload.get("depth") or "").strip(),
        str(payload.get("height") or "").strip(),
        str(payload.get("width") or "").strip(),
    )


def _extract_price_mentions(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for raw in re.findall(r"(?<!\d)(\d{3,6})(?!\d)", str(text or "")):
        try:
            values.append(Decimal(raw))
        except Exception:
            continue
    return values


def _candidate_price_matches(text: str, record: dict[str, Any]) -> bool:
    price_mentions = _extract_price_mentions(text)
    if not price_mentions:
        return False
    materials = record.get("materials") or {}
    for value in materials.values():
        if value is None:
            continue
        try:
            record_price = Decimal(str(value))
        except Exception:
            continue
        for mentioned in price_mentions:
            if record_price == mentioned:
                return True
    return False


def _build_queryable_candidates(product_context: dict[str, Any]) -> list[dict[str, Any]]:
    context = product_context or {}
    recent_candidates = context.get("recent_catalog_candidates") or []
    normalized_recent = [candidate for candidate in recent_candidates if isinstance(candidate, dict)]
    if normalized_recent:
        return normalized_recent

    product_code = str(context.get("product_code") or "").strip()
    product_name = str(context.get("product_name") or "").strip()
    queryable_records = precheck_quote.load_queryable_price_records()

    if product_code:
        matched = [
            record
            for record in queryable_records
            if str(record.get("product_code") or "").strip() == product_code
        ]
        if matched:
            return matched

    if product_name:
        matched = [
            record
            for record in queryable_records
            if str(record.get("name") or "").strip() == product_name
        ]
        if matched:
            return matched

    return []


def resolve_product_context(product_context: dict[str, Any] | None, *, text: str = "") -> dict[str, Any] | None:
    context = product_context or {}
    candidates = _build_queryable_candidates(context)
    if not candidates:
        return None

    if len(candidates) == 1:
        record = dict(candidates[0])
        record["resolved_from"] = "single_candidate"
        return record

    price_matches = [candidate for candidate in candidates if _candidate_price_matches(text, candidate)]
    if len(price_matches) == 1:
        record = dict(price_matches[0])
        record["resolved_from"] = "price_match"
        return record

    product_keys = {_normalize_product_key(candidate) for candidate in candidates}
    dimension_signatures = {_dimensions_signature(candidate.get("dimensions") or {}) for candidate in candidates}
    if len(product_keys) == 1 and len(dimension_signatures) == 1:
        merged = dict(candidates[0])
        merged_materials: dict[str, Any] = {}
        for candidate in candidates:
            merged_materials.update(candidate.get("materials") or {})
        merged["materials"] = merged_materials
        merged["resolved_from"] = "unique_product_dimensions"
        return merged

    return None


def format_dimension_value(value: Any) -> str:
    if value in {None, ""}:
        return ""
    if isinstance(value, (int, float)):
        decimal_value = Decimal(str(value))
        if decimal_value == decimal_value.to_integral():
            return str(int(decimal_value))
        return f"{decimal_value.normalize():f}".rstrip("0").rstrip(".")
    text = str(value).strip()
    return text


def format_dimension_pairs(dimensions: dict[str, Any] | None) -> list[str]:
    pairs = []
    for field_name, label in (("length", "长"), ("depth", "深"), ("height", "高"), ("width", "宽")):
        value = format_dimension_value((dimensions or {}).get(field_name))
        if value:
            pairs.append(f"{label}{value}米")
    return pairs


def _contains_purchase_mode_question(text: str) -> bool:
    normalized = str(text or "").strip()
    if not PURCHASE_MODE_PATTERN.search(normalized):
        return False
    return any(keyword in normalized for keyword in ("还是", "能定制吗", "有成品吗", "有现货吗", "可以挑", "做好"))


def _contains_size_spec_question(text: str) -> bool:
    return SIZE_SPEC_PATTERN.search(str(text or "").strip()) is not None


def _contains_measurement_question(text: str) -> bool:
    return MEASUREMENT_INSTALLATION_PATTERN.search(str(text or "").strip()) is not None


def _contains_lead_time_question(text: str) -> bool:
    return LEAD_TIME_SERVICE_PATTERN.search(str(text or "").strip()) is not None


def _contains_material_question(text: str) -> bool:
    return MATERIAL_CONFIG_PATTERN.search(str(text or "").strip()) is not None


def _looks_like_rule_consultation(text: str) -> bool:
    return RULE_CONSULTATION_PATTERN.search(str(text or "").strip()) is not None


def _has_structured_dimensions(text: str) -> bool:
    normalized = str(text or "").strip()
    return LABELED_DIMENSION_PATTERN.search(normalized) is not None or DIMENSION_VALUE_PATTERN.search(normalized) is not None


def _looks_like_structured_quote_flow(text: str) -> bool:
    normalized = str(text or "").strip()
    has_quote_hint = QUOTE_HINT_PATTERN.search(normalized) is not None
    if not has_quote_hint:
        return False

    has_product_signal = PRODUCT_CATEGORY_PATTERN.search(normalized) is not None
    has_material_signal = MATERIAL_NAME_PATTERN.search(normalized) is not None
    has_dimension_signal = _has_structured_dimensions(normalized) or "床垫尺寸" in normalized
    return has_product_signal or has_material_signal or has_dimension_signal


def classify_inquiry(
    text: str,
    *,
    product_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = str(text or "").strip()
    resolved_product = resolve_product_context(product_context, text=normalized)
    if _looks_like_rule_consultation(normalized):
        return {
            "inquiry_family": "quote_flow",
            "inquiry_confidence": 0.92,
            "can_answer_directly": False,
            "needs_product_context": False,
            "resolved_product_context": resolved_product,
        }

    if _contains_material_question(normalized) and not _looks_like_structured_quote_flow(normalized):
        return {
            "inquiry_family": "material_config",
            "inquiry_confidence": 0.94,
            "can_answer_directly": True,
            "needs_product_context": False,
            "resolved_product_context": resolved_product,
        }

    if _contains_lead_time_question(normalized):
        return {
            "inquiry_family": "lead_time_service",
            "inquiry_confidence": 0.9,
            "can_answer_directly": True,
            "needs_product_context": False,
            "resolved_product_context": resolved_product,
        }

    if _contains_measurement_question(normalized):
        return {
            "inquiry_family": "measurement_installation",
            "inquiry_confidence": 0.92,
            "can_answer_directly": True,
            "needs_product_context": False,
            "resolved_product_context": resolved_product,
        }

    if _looks_like_structured_quote_flow(normalized):
        return {
            "inquiry_family": "quote_flow",
            "inquiry_confidence": 0.93,
            "can_answer_directly": False,
            "needs_product_context": False,
            "resolved_product_context": resolved_product,
        }

    if _contains_purchase_mode_question(normalized):
        return {
            "inquiry_family": "purchase_mode",
            "inquiry_confidence": 0.88,
            "can_answer_directly": True,
            "needs_product_context": False,
            "resolved_product_context": resolved_product,
        }

    if _contains_size_spec_question(normalized):
        can_answer_directly = resolved_product is not None and bool(format_dimension_pairs(resolved_product.get("dimensions") or {}))
        return {
            "inquiry_family": "size_spec",
            "inquiry_confidence": 0.9,
            "can_answer_directly": can_answer_directly,
            "needs_product_context": not can_answer_directly,
            "resolved_product_context": resolved_product,
        }

    has_quote_hint = QUOTE_HINT_PATTERN.search(normalized) is not None
    return {
        "inquiry_family": "quote_flow",
        "inquiry_confidence": 0.7 if has_quote_hint else 0.55,
        "can_answer_directly": False,
        "needs_product_context": False,
        "resolved_product_context": resolved_product,
    }


def dimension_matches(record: dict[str, Any], expected_dimensions: dict[str, Any]) -> bool:
    record_dimensions = record.get("dimensions") or {}
    for field_name, expected in expected_dimensions.items():
        expected_value = precheck_quote.parse_dimension_to_meters(expected)
        if expected_value is None:
            continue
        actual_value = precheck_quote.parse_dimension_to_meters(record_dimensions.get(field_name))
        if actual_value is None or not isclose(actual_value, expected_value, abs_tol=0.015):
            return False
    return True
