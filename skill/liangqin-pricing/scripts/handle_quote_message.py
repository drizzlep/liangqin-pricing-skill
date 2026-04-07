#!/usr/bin/env python3
"""Unified message orchestrator for Liangqin quote conversations."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import calculate_bed_quote
import calculate_double_sided_door_price
import calculate_hidden_rosewood_discount
import calculate_modular_child_bed_combo_quote
import calculate_modular_child_bed_quote
import calculate_operation_gap_price
import calculate_rock_slab_price
import customer_guidance_templates
import detect_special_cabinet_rule
import format_quote_reply
import generate_quote_card_reply
import inquiry_intake
from material_names import formalize_material_name, formalize_text, normalize_material_for_query
import precheck_quote
import query_addendum_guidance
import query_bed_weight_guidance
import query_price_index
import quote_flow_state
import quote_result_bundle
import route_quote_request


DEFAULT_ADDENDA_ROOT = Path(__file__).resolve().parent.parent / "references" / "addenda"
FORMAL_MATERIAL_NAMES = ("北美黑胡桃木", "北美樱桃木", "北美白橡木", "北美白蜡木", "乌拉圭玫瑰木")
DIMENSION_UNIT_PATTERN = r"(mm|毫米|cm|厘米|m|米)?"
ROLE_SWITCH_KEYWORDS = (
    "发客户话术",
    "发客户",
    "客户版",
    "转给客户",
    "帮我回客户",
    "内部版",
    "内部口径",
    "顾问模式",
    "设计师模式",
    "普通客户模式",
    "切成顾问",
    "切到顾问",
    "切成设计师",
    "切到设计师",
    "切成客户",
    "切到客户",
)
CUSTOM_QUOTE_KEYWORDS = ("定制", "订制", "定做", "订做", "非标")
BED_FORM_KEYWORDS = ("上下床", "半高床", "高架床", "错层床")
BED_FORM_ALIASES = (
    ("上下床", ("上下床",)),
    ("半高床", ("半高床", "半高", "半高上铺床", "半高梯柜上铺床")),
    ("高架床", ("高架床", "高架", "高架上铺床", "高架梯柜上铺床")),
    ("错层床", ("错层床", "错层")),
)
ACCESS_STYLE_ALIASES = (
    ("梯柜", ("梯柜", "梯柜款")),
    ("斜梯", ("斜梯",)),
    ("直梯", ("直梯",)),
)
UNDERBED_CABINET_MODES = ("有门无背板", "无门有背板", "无门无背板")
CUSTOMER_GUIDED_ENTRY_MODES = {
    "customer_guided_discovery",
}
CUSTOMER_PRODUCT_HINTS = (
    "书柜",
    "衣柜",
    "玄关柜",
    "餐边柜",
    "电视柜",
    "书桌",
    "床",
    "柜子",
    "家具",
)
CUSTOMER_SPACE_HINTS = ("儿童房", "次卧", "主卧", "书房", "玄关", "客厅", "阳台", "角落")
CUSTOMER_GOAL_HINTS = ("收纳", "睡觉", "学习", "展示", "空间利用", "利用起来", "陪睡")
CUSTOMER_USER_HINTS = ("一个孩子", "两个孩子", "小朋友", "孩子", "大人", "全家")
CUSTOMER_REFERENCE_HINTS = ("照片", "户型图", "草图", "现场图")
CUSTOMER_BUDGET_HINTS = ("预算", "先看看价格", "先看价格", "大概多少钱", "先估个大概")

PRECHECK_DEFAULTS = {
    "category": "",
    "length": None,
    "depth": None,
    "height": None,
    "width": None,
    "material": None,
    "quote_kind": "unknown",
    "has_door": "unknown",
    "door_type": "",
    "series": "",
    "shape": "",
    "bed_form": "",
    "access_style": "",
    "lower_bed_type": "",
    "guardrail_style": "",
    "guardrail_length": "",
    "guardrail_height": "",
    "access_height": "",
    "stair_width": "",
    "stair_depth": "",
    "underbed_cabinet_mode": "",
    "front_cabinet_length": "",
    "front_cabinet_height": "",
    "front_cabinet_depth": "",
    "front_cabinet_mode": "",
    "rear_cabinet_length": "",
    "rear_cabinet_height": "",
    "rear_cabinet_depth": "",
    "rear_cabinet_mode": "",
    "interconnected_rows": False,
    "approximate_only": False,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Handle Liangqin quote messages through the role-aware orchestrator.")
    parser.add_argument("--text", required=True, help="Current user message.")
    parser.add_argument("--context-json", help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", help="Current channel id, such as feishu or dingtalk-connector.")
    parser.add_argument("--product-context-json", help="Optional product context JSON for inquiry intake.")
    parser.add_argument(
        "--output-mode",
        choices=["json", "reply_text", "openclaw_reply"],
        default="json",
        help="CLI output mode. Use openclaw_reply to print only the final user-facing reply text.",
    )
    parser.add_argument(
        "--role-override",
        choices=["customer", "designer", "consultant", "auto"],
        help="Optional manual audience-role override.",
    )
    parser.add_argument("--precheck-args-json", help="Structured precheck input JSON.")
    parser.add_argument("--quote-payload-json", help="Ready-to-format quote payload JSON.")
    parser.add_argument("--special-quote-json", help="Structured special quote / special adjustment JSON.")
    parser.add_argument(
        "--execute-quote-when-ready",
        action="store_true",
        help="When structured precheck args are present and precheck is ready, continue into quote calculation automatically.",
    )
    parser.add_argument(
        "--state-root",
        default=str(quote_flow_state.DEFAULT_FLOW_STATE_ROOT),
        help="Directory containing quote flow state files.",
    )
    parser.add_argument(
        "--bundle-root",
        default=str(quote_result_bundle.DEFAULT_BUNDLE_ROOT),
        help="Directory containing cached quote-result bundles.",
    )
    parser.add_argument(
        "--addenda-root",
        default=str(DEFAULT_ADDENDA_ROOT),
        help="Directory containing active addendum layers.",
    )
    parser.add_argument("--disable-addenda", action="store_true", help="Skip applying addendum layers before formatting.")
    parser.add_argument("--apply-context-reset", action="store_true", help="Clear prior state and bundle for a new quote topic.")
    parser.add_argument(
        "--media-root",
        default=str(generate_quote_card_reply.quote_card_renderer.DEFAULT_MEDIA_ROOT),
        help="Output directory for rendered quote-card media.",
    )
    parser.add_argument("--hero-image", help="Optional local hero image path for the quote card.")
    return parser.parse_args(argv)


def _parse_json_object(raw: str | None, *, field_name: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{field_name} must be a JSON object")
    return payload


def _pick_cli_reply_text(payload: dict[str, Any]) -> str:
    for field_name in ("reply_text", "customer_forward_text", "internal_summary", "next_best_question"):
        value = str(payload.get(field_name) or "").strip()
        if value:
            return value
    return ""


def _emit_cli_payload(payload: dict[str, Any], *, output_mode: str) -> None:
    if output_mode == "json":
        json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    reply_text = _pick_cli_reply_text(payload)
    if reply_text:
        sys.stdout.write(reply_text)
        if not reply_text.endswith("\n"):
            sys.stdout.write("\n")
        return

    json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _parse_amount(value: Any) -> Decimal:
    if isinstance(value, (int, float)):
        return _quantize_money(Decimal(str(value)))
    text = str(value or "").strip()
    if not text:
        raise ValueError("amount is required")
    normalized = (
        text.replace("元/㎡", "")
        .replace("元/米", "")
        .replace("元", "")
        .replace(",", "")
        .strip()
    )
    return _quantize_money(Decimal(normalized))


def _amount_to_text(value: Decimal) -> str:
    quantized = _quantize_money(value)
    if quantized == quantized.to_integral():
        return str(int(quantized))
    return f"{quantized.normalize():f}".rstrip("0").rstrip(".")


def _find_first_match(text: str, patterns: tuple[str, ...]) -> str:
    normalized = str(text or "").strip()
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return str(match.group(1)).strip()
    return ""


@lru_cache(maxsize=1)
def _queryable_product_names() -> tuple[str, ...]:
    names = {
        str(item.get("name") or "").strip()
        for item in precheck_quote.load_queryable_product_lookup()
        if str(item.get("name") or "").strip()
    }
    return tuple(sorted(names, key=len, reverse=True))


@lru_cache(maxsize=1)
def _category_candidates() -> tuple[str, ...]:
    candidates = {
        *precheck_quote.CABINET_CATEGORIES,
        *precheck_quote.BED_CATEGORIES,
        *precheck_quote.TATAMI_CATEGORIES,
        *precheck_quote.TABLE_CATEGORIES,
        "定制上下床",
    }
    return tuple(sorted((item for item in candidates if item), key=len, reverse=True))


def _normalize_metric_value(number_text: str | None, unit_text: str | None = None) -> str:
    raw = str(number_text or "").strip()
    if not raw:
        return ""

    value = Decimal(raw)
    unit = str(unit_text or "").strip().lower()
    if unit in {"mm", "毫米"}:
        value = value / Decimal("1000")
    elif unit in {"cm", "厘米"}:
        value = value / Decimal("100")
    elif unit in {"m", "米"}:
        value = value
    elif value >= 10:
        value = value / Decimal("1000")
    return _format_decimal(_quantize_money(value))


def _extract_labeled_metric(text: str, labels: tuple[str, ...]) -> str:
    joined = "|".join(re.escape(label) for label in labels)
    patterns = (
        rf"(?:{joined})\s*[:：]?\s*(\d+(?:\.\d+)?)\s*{DIMENSION_UNIT_PATTERN}",
        rf"(\d+(?:\.\d+)?)\s*{DIMENSION_UNIT_PATTERN}\s*(?:{joined})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _normalize_metric_value(match.group(1), match.group(2))
    return ""


def _extract_adjusted_metric(text: str, labels: tuple[str, ...]) -> str:
    joined = "|".join(re.escape(label) for label in labels)
    pattern = rf"(?:实际)?(?:{joined})(?:改成|改为|做到|做成|做到大概|做大概)?\s*(\d+(?:\.\d+)?)\s*{DIMENSION_UNIT_PATTERN}"
    match = re.search(pattern, text)
    if match:
        return _normalize_metric_value(match.group(1), match.group(2))
    return ""


def _extract_contextual_metric(text: str, *, context_terms: tuple[str, ...], field_terms: tuple[str, ...]) -> str:
    context_pattern = "|".join(re.escape(term) for term in context_terms)
    field_pattern = "|".join(re.escape(term) for term in field_terms)
    pattern = rf"(?:{context_pattern})[^。；,\n]{{0,30}}?(?:{field_pattern})\s*[:：]?\s*(\d+(?:\.\d+)?)\s*{DIMENSION_UNIT_PATTERN}"
    match = re.search(pattern, text)
    if not match:
        return ""
    return _normalize_metric_value(match.group(1), match.group(2))


def _extract_bed_pair_dimensions(text: str) -> tuple[str, str]:
    for match in re.finditer(
        rf"(\d+(?:\.\d+)?)\s*{DIMENSION_UNIT_PATTERN}\s*[*xX×乘]\s*(\d+(?:\.\d+)?)\s*{DIMENSION_UNIT_PATTERN}",
        text,
    ):
        first = _normalize_metric_value(match.group(1), match.group(2))
        second = _normalize_metric_value(match.group(3), match.group(4))
        if not first or not second:
            continue

        first_value = Decimal(first)
        second_value = Decimal(second)
        width = min(first_value, second_value)
        length = max(first_value, second_value)
        if Decimal("0.7") <= width <= Decimal("2.0") and Decimal("1.7") <= length <= Decimal("2.5"):
            return _format_decimal(width), _format_decimal(length)
    return "", ""


def _infer_bed_form_from_text(text: str) -> str:
    for normalized, keywords in BED_FORM_ALIASES:
        if any(keyword in text for keyword in keywords):
            return normalized
    return ""


def _looks_like_bed_combo_request(text: str) -> bool:
    has_bed_signal = "床" in text or any(keyword in text for keyword in ("上铺床", "床下"))
    has_combo_signal = any(keyword in text for keyword in ("床下", "前排", "后排", "前面", "后面", "前方", "后方", "前后双排", "互通"))
    return has_bed_signal and has_combo_signal


def _extract_row_segment(text: str, *, prefixes: tuple[str, ...], stop_prefixes: tuple[str, ...] = ()) -> str:
    prefix_pattern = "|".join(re.escape(item) for item in prefixes)
    stop_pattern = "|".join(re.escape(item) for item in stop_prefixes)
    lookahead = rf"(?:(?:{stop_pattern})|[。；\n]|$)" if stop_pattern else r"(?=[。；\n]|$)"
    pattern = rf"((?:{prefix_pattern})[^。；\n]*?){lookahead}"
    match = re.search(pattern, text)
    if not match:
        return ""
    return str(match.group(1)).strip("，, ")


def _extract_underbed_cabinet_mode(text: str) -> str:
    for mode in UNDERBED_CABINET_MODES:
        if mode in text:
            return mode
    return ""


def _extract_customer_guided_signals(text: str) -> dict[str, list[str]]:
    normalized = str(text or "").strip()
    return {
        "product": [keyword for keyword in CUSTOMER_PRODUCT_HINTS if keyword in normalized],
        "space": [keyword for keyword in CUSTOMER_SPACE_HINTS if keyword in normalized],
        "goal": [keyword for keyword in CUSTOMER_GOAL_HINTS if keyword in normalized],
        "user": [keyword for keyword in CUSTOMER_USER_HINTS if keyword in normalized],
        "reference": [keyword for keyword in CUSTOMER_REFERENCE_HINTS if keyword in normalized],
        "budget": [keyword for keyword in CUSTOMER_BUDGET_HINTS if keyword in normalized],
        "size": [
            label
            for label, value in {
                "length": _extract_labeled_metric(normalized, ("长度", "长")),
                "height": _extract_labeled_metric(normalized, ("高度", "高")),
                "depth": _extract_labeled_metric(normalized, ("进深", "深度", "深")),
                "width": _extract_labeled_metric(normalized, ("宽度", "宽")),
                "area": "面积" if "面积" in normalized else "",
            }.items()
            if value
        ],
    }


def _merge_customer_guided_signals(
    previous: dict[str, list[str]] | None,
    current: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for key in ("product", "space", "goal", "user", "reference", "budget", "size"):
        seen: list[str] = []
        for source in (previous or {}, current or {}):
            for value in source.get(key, []) or []:
                normalized = str(value or "").strip()
                if normalized and normalized not in seen:
                    seen.append(normalized)
        merged[key] = seen
    return merged


def _customer_guided_context_from_state(state: dict[str, Any] | None) -> tuple[dict[str, list[str]] | None, int]:
    if not state:
        return None, 1
    if str(state.get("active_route") or "").strip() != "customer_guided_discovery":
        return None, 1
    missing_fields = [str(item).strip() for item in (state.get("missing_fields") or []) if str(item).strip()]
    if "customer_guided_answer" not in missing_fields:
        return None, 1
    confirmed_fields = state.get("confirmed_fields") or {}
    signal_summary = confirmed_fields.get("signal_summary")
    if not isinstance(signal_summary, dict):
        return None, 1
    guided_turn_count = int(confirmed_fields.get("guided_turn_count") or 1)
    normalized_summary: dict[str, list[str]] = {}
    for key, values in signal_summary.items():
        normalized_summary[str(key)] = [str(value).strip() for value in (values or []) if str(value).strip()]
    return normalized_summary, max(guided_turn_count, 1)


def _customer_response_stage(customer_strategy: str, signals: dict[str, list[str]]) -> str:
    signal_count = sum(1 for values in signals.values() if values)
    if signals.get("size") and (signals.get("product") or signals.get("goal")):
        return "reference_quote"
    if signal_count >= 2:
        return "proposal_range"
    if customer_strategy in {"precise_need", "renovation_browse", "guided_discovery"}:
        return "direction_confirm"
    return "direction_confirm"


def _customer_guided_text(
    text: str,
    *,
    customer_strategy: str,
    previous_signals: dict[str, list[str]] | None = None,
    turn_index: int = 1,
) -> dict[str, Any]:
    signals = _merge_customer_guided_signals(previous_signals, _extract_customer_guided_signals(text))
    response_stage = _customer_response_stage(customer_strategy, signals)
    template_summary = customer_guidance_templates.summarize_customer_guidance_template(
        customer_strategy=customer_strategy,
        response_stage=response_stage,
        signals=signals,
        turn_index=turn_index,
    )
    question_code = str(template_summary["question_code"])
    next_question = str(template_summary["next_question"])
    customer_text = str(template_summary["reply_text"])
    text_bundle = _shape_role_output(
        audience_role="customer",
        professional_text=customer_text,
        customer_text=customer_text,
    )
    return {
        **text_bundle,
        "question_code": question_code,
        "constraint_code": None,
        "detail_level_hint": "solution_plus_range" if response_stage != "direction_confirm" else "solution_direction",
        "response_stage": response_stage,
        "signal_summary": signals,
        "next_best_question": next_question,
        "missing_fields": ["customer_guided_answer"],
        "pricing_route": "",
        "guided_turn_count": turn_index,
    }


def _customer_guided_category_from_signals(signals: dict[str, list[str]] | None) -> str:
    if not signals:
        return ""
    preferred_products = ("书柜", "衣柜", "玄关柜", "餐边柜", "电视柜", "书桌", "床")
    signal_products = [str(item).strip() for item in (signals.get("product") or []) if str(item).strip()]
    for product in preferred_products:
        if product in signal_products:
            return product
    return ""


def _augment_precheck_args_from_customer_guided_context(
    precheck_args: dict[str, Any] | None,
    *,
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if precheck_args is None:
        return None
    previous_signals, _ = _customer_guided_context_from_state(state)
    category = str(precheck_args.get("category") or "").strip()
    if category:
        return precheck_args
    inferred_category = _customer_guided_category_from_signals(previous_signals)
    if not inferred_category:
        return precheck_args
    augmented = dict(precheck_args)
    augmented["category"] = inferred_category
    return augmented


def _augment_precheck_args_from_product_context(
    precheck_args: dict[str, Any] | None,
    *,
    product_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if precheck_args is None and not product_context:
        return None
    resolved_product = inquiry_intake.resolve_product_context(product_context, text="")
    if not resolved_product:
        return precheck_args

    augmented = dict(precheck_args or {})
    if not str(augmented.get("category") or "").strip():
        augmented["category"] = str(resolved_product.get("name") or resolved_product.get("sheet") or "").strip()
    dimensions = resolved_product.get("dimensions") or {}
    for field_name in ("length", "depth", "height", "width"):
        if str(augmented.get(field_name) or "").strip():
            continue
        value = dimensions.get(field_name)
        if value in {None, ""}:
            continue
        augmented[field_name] = inquiry_intake.format_dimension_value(value)
    return augmented


def _should_use_customer_guidance(*, customer_strategy: str, precheck_args: dict[str, Any] | None) -> bool:
    if customer_strategy in {"renovation_browse", "guided_discovery"}:
        return True
    normalized = precheck_args or {}
    has_core_quote_signal = any(
        str(normalized.get(field) or "").strip()
        for field in ("length", "height", "width", "depth", "material")
    )
    if customer_strategy == "default":
        return not has_core_quote_signal
    if customer_strategy != "precise_need":
        return False
    return not has_core_quote_signal


def _infer_cabinet_category_from_payload(payload: dict[str, Any]) -> str:
    product_text = " ".join(
        str(part).strip()
        for part in [
            ((payload.get("items") or [{}])[0] or {}).get("product", ""),
            ((payload.get("items") or [{}])[0] or {}).get("confirmed", ""),
        ]
        if str(part).strip()
    )
    for category in sorted(precheck_quote.CABINET_CATEGORIES, key=len, reverse=True):
        if category in product_text:
            return category
    return ""


def _infer_cabinet_precheck_args_from_formal_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if str(payload.get("pricing_route") or "").strip() != "cabinet_projection_area":
        return None
    items = payload.get("items") or []
    if not items or not isinstance(items[0], dict):
        return None

    confirmed = str(items[0].get("confirmed") or "").strip()
    base_args: dict[str, Any] = {}
    category = _infer_cabinet_category_from_payload(payload)
    material = _infer_material_from_text_or_payload(confirmed, payload)
    length = _extract_labeled_metric(confirmed, ("长度", "长"))
    height = _extract_labeled_metric(confirmed, ("高度", "高"))
    depth = _extract_labeled_metric(confirmed, ("进深", "深度", "深"))

    if category:
        base_args["category"] = category
    if material:
        base_args["material"] = material
    if length:
        base_args["length"] = length
    if height:
        base_args["height"] = height
    if depth:
        base_args["depth"] = depth
    if "不带门" in confirmed:
        base_args["has_door"] = "no"
    elif "带门" in confirmed:
        base_args["has_door"] = "yes"
        base_args["door_type"] = "带门"
    return base_args or None


def _extract_combo_row_follow_up_fields(
    text: str,
    *,
    row_prefix: str,
) -> dict[str, Any]:
    if row_prefix not in {"front", "rear"}:
        return {}

    explicit_terms = ("前排", "前面", "前方") if row_prefix == "front" else ("后排", "后面", "后方")
    other_terms = ("后排", "后面", "后方") if row_prefix == "front" else ("前排", "前面", "前方")
    segment = _extract_row_segment(text, prefixes=explicit_terms, stop_prefixes=other_terms) or text

    updates: dict[str, Any] = {}
    field_map = {
        f"{row_prefix}_cabinet_length": _extract_labeled_metric(segment, ("长度", "长")),
        f"{row_prefix}_cabinet_height": _extract_labeled_metric(segment, ("高度", "高")),
        f"{row_prefix}_cabinet_depth": _extract_labeled_metric(segment, ("进深", "深度", "深")),
        f"{row_prefix}_cabinet_mode": _extract_underbed_cabinet_mode(segment),
    }
    for field_name, value in field_map.items():
        if value:
            updates[field_name] = value
    return updates


def _infer_category_from_text(text: str) -> str:
    bed_form = _infer_bed_form_from_text(text)
    if _looks_like_bed_combo_request(text):
        return bed_form or "半高床"
    if bed_form:
        return "定制上下床" if bed_form == "上下床" and any(keyword in text for keyword in CUSTOM_QUOTE_KEYWORDS) else bed_form
    for product_name in _queryable_product_names():
        if product_name in text:
            return product_name
    if "上下床" in text and any(keyword in text for keyword in CUSTOM_QUOTE_KEYWORDS):
        return "定制上下床"
    for candidate in _category_candidates():
        if candidate in text:
            return candidate
    return ""


def _infer_material_from_text(text: str) -> str:
    normalized_text = formalize_text(text) or text
    for material_name in FORMAL_MATERIAL_NAMES:
        if material_name in normalized_text:
            return material_name
    return ""


def _infer_quote_kind_from_text(text: str) -> str:
    if any(keyword in text for keyword in CUSTOM_QUOTE_KEYWORDS):
        return "custom"
    if any(keyword in text for keyword in precheck_quote.STANDARD_INTENT_KEYWORDS):
        return "standard"
    return ""


def _infer_access_style(text: str) -> str:
    for normalized, keywords in ACCESS_STYLE_ALIASES:
        if any(keyword in text for keyword in keywords):
            return normalized
    return ""


def _infer_precheck_args_from_text(text: str) -> dict[str, Any]:
    normalized_text = str(text or "").strip()
    if not normalized_text:
        return {}

    inferred: dict[str, Any] = {}
    bed_form = _infer_bed_form_from_text(normalized_text)
    category = _infer_category_from_text(normalized_text)
    if category:
        inferred["category"] = category

    material = _infer_material_from_text(normalized_text)
    if material:
        inferred["material"] = material

    quote_kind = _infer_quote_kind_from_text(normalized_text)
    if quote_kind:
        inferred["quote_kind"] = quote_kind

    length = _extract_labeled_metric(normalized_text, ("长度", "长"))
    depth = _extract_labeled_metric(normalized_text, ("进深", "深度", "深"))
    height = _extract_labeled_metric(normalized_text, ("高度", "高"))
    width = _extract_labeled_metric(normalized_text, ("宽度", "宽"))

    bed_pair_width, bed_pair_length = _extract_bed_pair_dimensions(normalized_text)
    category_type = precheck_quote.normalize_category_label(category)
    is_bed_like_text = category_type == "bed" or "床" in normalized_text
    if bed_pair_width and is_bed_like_text:
        width = bed_pair_width
    elif not width and bed_pair_width:
        width = bed_pair_width
    if bed_pair_length and is_bed_like_text:
        length = bed_pair_length
    elif not length and bed_pair_length:
        length = bed_pair_length

    if length:
        inferred["length"] = length
    if depth:
        inferred["depth"] = depth
    if height:
        inferred["height"] = height
    if width:
        inferred["width"] = width

    if bed_form:
        inferred["bed_form"] = bed_form

    access_style = _infer_access_style(normalized_text)
    if access_style:
        inferred["access_style"] = access_style

    bed_form = str(inferred.get("bed_form") or "")
    if "下层箱体床" in normalized_text or ("箱体床" in normalized_text and bed_form in {"上下床", "错层床"}):
        inferred["lower_bed_type"] = "箱体床"
    elif "下层架式床" in normalized_text or ("架式床" in normalized_text and bed_form in {"上下床", "错层床"}):
        inferred["lower_bed_type"] = "架式床"

    for style_name in sorted(precheck_quote.MODULAR_CHILD_BED_GUARDRAIL_STYLES, key=len, reverse=True):
        if style_name in normalized_text:
            inferred["guardrail_style"] = style_name
            break

    guardrail_length = _extract_contextual_metric(
        normalized_text,
        context_terms=("围栏",),
        field_terms=("总长度", "长度", "长"),
    )
    guardrail_height = _extract_contextual_metric(
        normalized_text,
        context_terms=("围栏",),
        field_terms=("高度", "高"),
    )
    access_height = _extract_contextual_metric(
        normalized_text,
        context_terms=("梯子", "直梯", "斜梯", "上下床间距", "垂直高度"),
        field_terms=("高度", "高"),
    )
    stair_width = _extract_contextual_metric(
        normalized_text,
        context_terms=("梯柜", "踏步"),
        field_terms=("踏步宽度", "踏步宽", "宽度", "宽"),
    )
    stair_depth = _extract_contextual_metric(
        normalized_text,
        context_terms=("梯柜", "踏步"),
        field_terms=("进深", "深度", "深"),
    )

    if guardrail_length:
        inferred["guardrail_length"] = guardrail_length
    if guardrail_height:
        inferred["guardrail_height"] = guardrail_height
    if access_height:
        inferred["access_height"] = access_height
    if stair_width:
        inferred["stair_width"] = stair_width
    if stair_depth:
        inferred["stair_depth"] = stair_depth
    if (
        stair_width
        and not bed_pair_width
        and inferred.get("width") == stair_width
        and "梯柜" in normalized_text
    ):
        inferred.pop("width", None)

    if _looks_like_bed_combo_request(normalized_text):
        inferred["quote_kind"] = "custom"

        front_segment = _extract_row_segment(
            normalized_text,
            prefixes=("前排", "前面", "前方"),
            stop_prefixes=("后排", "后面", "后方"),
        )
        rear_segment = _extract_row_segment(
            normalized_text,
            prefixes=("后排", "后面", "后方"),
        )

        if "互通" in normalized_text:
            inferred["interconnected_rows"] = True

        if front_segment:
            front_length = _extract_labeled_metric(front_segment, ("长度", "长"))
            front_height = _extract_labeled_metric(front_segment, ("高度", "高"))
            front_depth = _extract_labeled_metric(front_segment, ("进深", "深度", "深"))
            front_mode = _extract_underbed_cabinet_mode(front_segment)
            if front_length:
                inferred["front_cabinet_length"] = front_length
            if front_height:
                inferred["front_cabinet_height"] = front_height
            if front_depth:
                inferred["front_cabinet_depth"] = front_depth
            if front_mode:
                inferred["front_cabinet_mode"] = front_mode

        if rear_segment:
            rear_length = _extract_labeled_metric(rear_segment, ("长度", "长"))
            rear_height = _extract_labeled_metric(rear_segment, ("高度", "高"))
            rear_depth = _extract_labeled_metric(rear_segment, ("进深", "深度", "深"))
            rear_mode = _extract_underbed_cabinet_mode(rear_segment)
            if rear_length:
                inferred["rear_cabinet_length"] = rear_length
            if rear_height:
                inferred["rear_cabinet_height"] = rear_height
            if rear_depth:
                inferred["rear_cabinet_depth"] = rear_depth
            if rear_mode:
                inferred["rear_cabinet_mode"] = rear_mode

    return inferred


def _infer_precheck_follow_up_from_state(
    *,
    text: str,
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not state:
        return None

    confirmed_fields = state.get("confirmed_fields")
    missing_fields = [str(item).strip() for item in (state.get("missing_fields") or []) if str(item).strip()]
    active_route = str(state.get("active_route") or "").strip()
    if not isinstance(confirmed_fields, dict) or not confirmed_fields or not missing_fields:
        return None

    updates: dict[str, Any] = {}
    if active_route == "modular_child_bed_combo":
        for row_prefix in ("front", "rear"):
            row_missing_fields = [field for field in missing_fields if field.startswith(f"{row_prefix}_")]
            if row_missing_fields:
                updates.update(
                    _extract_combo_row_follow_up_fields(
                        text,
                        row_prefix=row_prefix,
                    )
                )
    else:
        inferred = _infer_precheck_args_from_text(text)
        for field_name, value in inferred.items():
            if value not in (None, "", []):
                updates[field_name] = value

    if not updates:
        return None

    merged = dict(confirmed_fields)
    merged.update(updates)
    if merged == confirmed_fields:
        return None
    return merged


def _infer_formal_quote_adjustment_from_state(
    *,
    text: str,
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not state:
        return None
    if str(state.get("last_quote_kind") or "").strip() != "formal":
        return None

    active_route = str(state.get("active_route") or "").strip()
    last_formal_payload = state.get("last_formal_payload")
    if not isinstance(last_formal_payload, dict) or not last_formal_payload:
        return None

    if active_route == "cabinet_projection_area":
        base_args = _infer_cabinet_precheck_args_from_formal_payload(last_formal_payload)
        if not base_args:
            return None
        updates = {}
        depth = _extract_adjusted_metric(text, ("进深", "深度", "深")) or _extract_labeled_metric(text, ("进深", "深度", "深"))
        if depth:
            updates["depth"] = depth
        has_door = ""
        if "不带门" in text or "不要门" in text or "无门" in text:
            has_door = "no"
        elif "带门" in text or "加门" in text:
            has_door = "yes"
        if has_door:
            updates["has_door"] = has_door
            updates["door_type"] = "带门" if has_door == "yes" else ""
        if not updates:
            return None
        merged = dict(base_args)
        merged.update(updates)
        if merged == base_args:
            return None
        return merged

    return None


def _infer_material_from_text_or_payload(text: str, payload: dict[str, Any] | None) -> str:
    normalized_text = str(text or "").strip()
    for material_name in FORMAL_MATERIAL_NAMES:
        if material_name in normalized_text:
            return material_name
    if not payload:
        return ""
    for item in payload.get("items") or []:
        combined = f"{item.get('product', '')} {item.get('confirmed', '')}"
        for material_name in FORMAL_MATERIAL_NAMES:
            if material_name in combined:
                return material_name
    return ""


def _infer_base_payload(state: dict[str, Any] | None, bundle: dict[str, Any] | None) -> dict[str, Any] | None:
    if state and isinstance(state.get("last_formal_payload"), dict) and state.get("last_formal_payload"):
        return state["last_formal_payload"]
    if bundle and isinstance(bundle.get("prepared_payload"), dict):
        return bundle["prepared_payload"]
    return None


def _has_explicit_new_quote_signal(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in route_quote_request.NEW_QUOTE_TOPIC_KEYWORDS)


def _route_family(route: str) -> str:
    normalized = str(route or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("special_adjustment."):
        return "special_adjustment"
    if normalized in {"cabinet_projection_area", "cabinet"}:
        return "cabinet"
    if normalized == "modular_child_bed_combo":
        return "modular_child_bed_combo"
    if normalized == "modular_child_bed":
        return "modular_child_bed"
    if normalized in {"bed_standard", "bed"}:
        return "bed"
    if normalized in {"catalog_unit_price", "table"}:
        return "table"
    return normalized


def _existing_route_family(state: dict[str, Any] | None, bundle: dict[str, Any] | None) -> str:
    active_route = str((state or {}).get("active_route") or "").strip()
    if active_route:
        return _route_family(active_route)
    bundle_payload = (bundle or {}).get("prepared_payload") or {}
    bundle_route = str(bundle_payload.get("pricing_route") or "").strip()
    return _route_family(bundle_route)


def _inferred_route_family_from_text(text: str) -> str:
    inferred_args = _infer_precheck_args_from_text(text)
    if not inferred_args:
        return ""
    signal_count = sum(
        1
        for key in ("category", "material", "length", "height", "width", "depth")
        if str(inferred_args.get(key) or "").strip()
    )
    if signal_count < 3:
        return ""
    precheck_result = _run_precheck(inferred_args)
    inferred_route = str(precheck_result.get("pricing_route") or precheck_result.get("normalized_category_type") or "").strip()
    return _route_family(inferred_route)


def _has_conflicting_new_quote_route_signal(
    *,
    text: str,
    state: dict[str, Any] | None,
    bundle: dict[str, Any] | None,
) -> bool:
    existing_family = _existing_route_family(state, bundle)
    inferred_family = _inferred_route_family_from_text(text)
    return bool(existing_family and inferred_family and existing_family != inferred_family)


def _has_cached_quote_to_reformat(state: dict[str, Any] | None, bundle: dict[str, Any] | None) -> bool:
    state_quote_kind = str((state or {}).get("last_quote_kind") or "").strip()
    bundle_quote_kind = str((bundle or {}).get("quote_kind") or "").strip()
    return state_quote_kind in {"formal", "reference"} or bundle_quote_kind in {"formal", "reference"}


def _is_role_output_switch_request(text: str, *, role_override: str | None) -> bool:
    normalized_override = str(role_override or "").strip()
    if normalized_override in {"customer", "designer", "consultant", "auto"}:
        return True
    normalized_text = str(text or "").strip()
    return any(keyword in normalized_text for keyword in ROLE_SWITCH_KEYWORDS)


def _extract_base_unit_price_from_payload(payload: dict[str, Any] | None) -> float | None:
    if not payload:
        return None
    for item in payload.get("items") or []:
        for step in item.get("calculation_steps") or []:
            match = re.search(r"基础单价[：:=]?\s*([0-9]+(?:\.[0-9]+)?)", str(step))
            if match:
                return float(match.group(1))
    return None


def _shape_role_output(
    *,
    audience_role: str,
    professional_text: str,
    customer_text: str | None = None,
) -> dict[str, str]:
    normalized_professional = str(professional_text or "").strip()
    normalized_customer = str(customer_text or normalized_professional).strip()

    if audience_role == "designer":
        return {
            "reply_text": normalized_professional,
            "internal_summary": normalized_professional,
            "customer_forward_text": normalized_customer if normalized_customer != normalized_professional else "",
        }
    if audience_role == "consultant":
        return {
            "reply_text": normalized_customer,
            "internal_summary": normalized_professional,
            "customer_forward_text": normalized_customer,
        }
    return {
        "reply_text": normalized_customer,
        "internal_summary": "",
        "customer_forward_text": normalized_customer,
    }


def _resolve_context(
    context_json: str | None,
    channel: str | None,
) -> dict[str, Any] | None:
    if not context_json or not channel:
        return None
    return quote_result_bundle.resolve_conversation_context(context_json, channel=channel)


def _load_existing_quote_context(
    *,
    context_json: str | None,
    channel: str | None,
    state_root: Path,
    bundle_root: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    context = _resolve_context(context_json, channel)
    if not context:
        return None, None
    conversation_id = context["conversation_id"]
    return (
        quote_flow_state.load_quote_flow_state(conversation_id, cache_root=state_root),
        quote_result_bundle.load_latest_quote_result_bundle(conversation_id, cache_root=bundle_root),
    )


def _effective_product_context(
    product_context: dict[str, Any] | None,
    *,
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if isinstance(product_context, dict) and product_context:
        return product_context
    existing_context = (state or {}).get("captured_product_context")
    if isinstance(existing_context, dict) and existing_context:
        return existing_context
    return None


def _build_inquiry_text_bundle(
    *,
    audience_role: str,
    reply_text: str,
) -> dict[str, str]:
    return _shape_role_output(
        audience_role=audience_role,
        professional_text=reply_text,
        customer_text=reply_text,
    )


def _size_spec_inquiry_result(
    text: str,
    *,
    audience_role: str,
    product_context: dict[str, Any] | None,
) -> dict[str, Any]:
    resolved_product = inquiry_intake.resolve_product_context(product_context, text=text)
    if resolved_product:
        dimension_pairs = inquiry_intake.format_dimension_pairs(resolved_product.get("dimensions") or {})
        if dimension_pairs:
            product_label = str(resolved_product.get("name") or resolved_product.get("product_code") or "这款").strip() or "这款"
            price_mentions = re.findall(r"(?<!\d)(\d{3,6})(?!\d)", str(text or ""))
            if price_mentions:
                price_hint = price_mentions[0]
                reply_text = (
                    f"如果你说的是当前这条 {price_hint} 这档，我这边先对到的目录规格是"
                    f"{'、'.join(dimension_pairs)}。如果你还想继续往下收价格，我再帮你确认材质或是否改尺寸。"
                )
            else:
                reply_text = (
                    f"{product_label}目前对到的目录尺寸是{'、'.join(dimension_pairs)}。"
                    "如果你还想继续往下收价格，我再帮你确认材质或是否改尺寸。"
                )
            text_bundle = _build_inquiry_text_bundle(audience_role=audience_role, reply_text=reply_text)
            return {
                **text_bundle,
                "source_basis": "catalog_dimensions",
                "can_answer_directly": True,
                "next_question": "",
                "safe_boundary_reason": "",
                "handoff_needed": False,
                "missing_fields": [],
                "resolved_product_context": resolved_product,
            }

    next_question = "你先发我产品名、产品编号或者当前链接，我就能直接帮你对这款的目录尺寸。"
    reply_text = f"可以，我先帮你对尺寸。{next_question}"
    text_bundle = _build_inquiry_text_bundle(audience_role=audience_role, reply_text=reply_text)
    return {
        **text_bundle,
        "source_basis": "product_identity_required",
        "can_answer_directly": False,
        "next_question": next_question,
        "safe_boundary_reason": "",
        "handoff_needed": False,
        "missing_fields": ["product_context"],
        "resolved_product_context": resolved_product or {},
    }


def _inquiry_category_hint(
    text: str,
    *,
    product_context: dict[str, Any] | None,
) -> str:
    resolved_product = inquiry_intake.resolve_product_context(product_context, text=text)
    if resolved_product:
        sheet = str(resolved_product.get("sheet") or "").strip()
        if sheet:
            return sheet
    inferred_precheck_args = _infer_precheck_args_from_text(text) or {}
    return str(inferred_precheck_args.get("category") or "").strip()


def _measurement_installation_inquiry_result(
    text: str,
    *,
    audience_role: str,
    product_context: dict[str, Any] | None,
) -> dict[str, Any]:
    category_hint = _inquiry_category_hint(text, product_context=product_context)
    if any(keyword in category_hint for keyword in ("床", "半高床", "高架床", "上下床", "错层床")):
        next_question = "如果你想让我继续往下收，我先只确认一个问题：床垫宽和床垫长分别是多少？"
        reply_text = (
            "如果你现在先量床类，优先记床垫宽、床垫长，再补可做总高和关键结构位置。"
            f"{next_question}"
        )
    elif any(keyword in category_hint for keyword in ("书桌", "桌")):
        next_question = "如果你想继续往下收，我先只确认一个问题：桌面总长大概是多少？"
        reply_text = (
            "如果你现在先量桌类，通常先记总长、总高和可做进深；如果旁边带柜体，再补柜体长度。"
            f"{next_question}"
        )
    elif category_hint:
        next_question = "如果你想继续往下收，我先只确认一个问题：这组大概要做多长？"
        reply_text = (
            "如果你现在先量柜体，通常先记 3 个数：总长、总高、可做进深。"
            f"{next_question}"
        )
    else:
        next_question = "你这次主要是在量柜体、床，还是书桌？"
        reply_text = (
            "如果你现在只是先量尺寸，通常先记总长、总高、可做进深；床类再补床垫宽和床垫长。"
            f"下一步我先只确认一个问题：{next_question}"
        )
    text_bundle = _build_inquiry_text_bundle(audience_role=audience_role, reply_text=reply_text)
    return {
        **text_bundle,
        "source_basis": "generic_measurement_guidance",
        "can_answer_directly": True,
        "next_question": next_question,
        "safe_boundary_reason": "service_scope_not_committed",
        "handoff_needed": False,
        "missing_fields": ["measurement_anchor"],
        "resolved_product_context": inquiry_intake.resolve_product_context(product_context, text=text) or {},
    }


def _lead_time_service_inquiry_result(
    text: str,
    *,
    audience_role: str,
    product_context: dict[str, Any] | None,
) -> dict[str, Any]:
    boundary_text = "这类定制的测量、设计、排产和安装时间，当前不能直接按固定天数给你承诺，一般都要结合城市、排产和设计确认。"
    inferred_precheck_args = _infer_precheck_args_from_text(text) or {}
    inferred_precheck_args = _augment_precheck_args_from_product_context(
        inferred_precheck_args if inferred_precheck_args else None,
        product_context=product_context,
    ) or {}
    next_question = "如果你想先把价格往下收，我先只确认一个关键条件：你这次具体想做哪一类产品？"
    missing_fields = ["quote_anchor"]
    if inferred_precheck_args:
        precheck_result = _run_precheck(inferred_precheck_args)
        candidate_question = str(precheck_result.get("next_question") or "").strip()
        candidate_missing = [str(item).strip() for item in (precheck_result.get("missing_fields") or []) if str(item).strip()]
        if candidate_question:
            next_question = candidate_question
            missing_fields = candidate_missing or missing_fields
    reply_text = f"{boundary_text}如果你想先把价格往下收，我先只确认一个问题：{next_question}"
    text_bundle = _build_inquiry_text_bundle(audience_role=audience_role, reply_text=reply_text)
    return {
        **text_bundle,
        "source_basis": "safe_service_boundary",
        "can_answer_directly": True,
        "next_question": next_question,
        "safe_boundary_reason": "service_facts_not_loaded",
        "handoff_needed": False,
        "missing_fields": missing_fields,
        "resolved_product_context": inquiry_intake.resolve_product_context(product_context, text=text) or {},
    }


def _purchase_mode_inquiry_result(
    *,
    audience_role: str,
    product_context: dict[str, Any] | None,
) -> dict[str, Any]:
    next_question = "你这次更想先看成品，还是按尺寸定制？"
    reply_text = "这边两条都能走：目录成品/标准品和按尺寸定制，后面的报价路径不一样。下一步我先只确认一个问题：" + next_question
    text_bundle = _build_inquiry_text_bundle(audience_role=audience_role, reply_text=reply_text)
    return {
        **text_bundle,
        "source_basis": "purchase_mode_overview",
        "can_answer_directly": True,
        "next_question": next_question,
        "safe_boundary_reason": "",
        "handoff_needed": False,
        "missing_fields": ["purchase_mode"],
        "resolved_product_context": inquiry_intake.resolve_product_context(product_context, text=next_question) or {},
    }


def _build_inquiry_reply_result(
    text: str,
    *,
    audience_role: str,
    inquiry_family: str,
    product_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if inquiry_family == "size_spec":
        return _size_spec_inquiry_result(text, audience_role=audience_role, product_context=product_context)
    if inquiry_family == "measurement_installation":
        return _measurement_installation_inquiry_result(text, audience_role=audience_role, product_context=product_context)
    if inquiry_family == "lead_time_service":
        return _lead_time_service_inquiry_result(text, audience_role=audience_role, product_context=product_context)
    if inquiry_family == "purchase_mode":
        return _purchase_mode_inquiry_result(audience_role=audience_role, product_context=product_context)
    return {
        **_build_inquiry_text_bundle(audience_role=audience_role, reply_text=""),
        "source_basis": "unsupported_inquiry_family",
        "can_answer_directly": False,
        "next_question": "",
        "safe_boundary_reason": "",
        "handoff_needed": True,
        "missing_fields": [],
        "resolved_product_context": inquiry_intake.resolve_product_context(product_context, text=text) or {},
    }


def _store_flow_state(
    *,
    context_json: str | None,
    channel: str | None,
    state_root: Path,
    audience_role: str,
    customer_strategy: str,
    active_route: str,
    missing_fields: list[str],
    internal_summary: str,
    customer_forward_text: str,
    confirmed_fields: dict[str, Any] | None = None,
    handoff_summary: str = "",
    active_inquiry_family: str = "",
    captured_product_context: dict[str, Any] | None = None,
    last_non_quote_reply: str = "",
    last_safe_boundary_reason: str = "",
) -> str:
    context = _resolve_context(context_json, channel)
    if not context:
        return ""

    quote_flow_state.merge_quote_flow_state(
        context["conversation_id"],
        updates={
            "audience_role": audience_role,
            "customer_strategy": customer_strategy,
            "confirmed_fields": confirmed_fields or {},
            "missing_fields": missing_fields,
            "active_route": active_route,
            "internal_summary": internal_summary,
            "customer_forward_text": customer_forward_text,
            "handoff_summary": handoff_summary,
            "active_inquiry_family": active_inquiry_family,
            "captured_product_context": captured_product_context or {},
            "last_non_quote_reply": last_non_quote_reply,
            "last_safe_boundary_reason": last_safe_boundary_reason,
        },
        cache_root=state_root,
    )
    return context["conversation_id"]


def _run_precheck(precheck_args: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(PRECHECK_DEFAULTS)
    normalized.update(precheck_args)
    args = argparse.Namespace(**normalized)
    category_type = precheck_quote.normalize_category(args)
    if category_type == "cabinet":
        result = precheck_quote.precheck_cabinet(args)
    elif category_type == "bed":
        result = precheck_quote.precheck_bed(args)
    elif category_type == "tatami":
        result = precheck_quote.precheck_tatami(args)
    elif category_type == "table":
        result = precheck_quote.precheck_table(args)
    else:
        result = precheck_quote.precheck_generic(args)
    result["normalized_category_type"] = category_type
    if not str(result.get("pricing_route", "") or "").strip():
        result["pricing_route"] = str(result.get("route", "") or category_type).strip()
    return result


def _precheck_text(result: dict[str, Any], *, audience_role: str) -> dict[str, str]:
    next_question = str(result.get("next_question", "") or "").strip()
    pricing_route = str(result.get("pricing_route", "") or result.get("route", "") or "").strip()
    if result.get("ready_for_formal_quote"):
        professional = f"预检通过，可直接进入正式报价。当前路径：{pricing_route or 'standard'}。"
        customer = "现在条件已经够了，可以进入正式报价。"
        if result.get("quote_decision") == "reference_quote":
            professional = f"预检通过，可先给参考报价。当前路径：{pricing_route or 'standard'}。"
            customer = "现在条件已经够了，可以先给你参考报价。"
    else:
        professional = next_question
        customer = next_question
    return _shape_role_output(
        audience_role=audience_role,
        professional_text=professional,
        customer_text=customer,
    )


def _guidance_text(
    result: dict[str, Any],
    *,
    audience_role: str,
) -> dict[str, str]:
    professional = str(
        result.get("suggested_reply")
        or result.get("answer_summary")
        or result.get("next_question")
        or ""
    ).strip()
    customer = professional
    follow_ups = result.get("follow_up_questions") or []
    if follow_ups:
        first_question = str((follow_ups[0] or {}).get("question", "")).strip()
        if first_question:
            customer = first_question
            if not professional:
                professional = first_question
    if not professional:
        professional = customer
    return _shape_role_output(
        audience_role=audience_role,
        professional_text=professional,
        customer_text=customer,
    )


def _special_rule_text(
    result: dict[str, Any],
    *,
    audience_role: str,
) -> dict[str, str]:
    next_question = str(result.get("next_question", "") or "").strip()
    special_rule = str(result.get("special_rule", "") or "").strip()
    professional = next_question
    customer = next_question
    if not professional and special_rule:
        professional = f"当前命中特殊柜体规则：{special_rule}。"
        customer = "这个情况需要按特殊规则继续确认，我按这条规则往下处理。"
    return _shape_role_output(
        audience_role=audience_role,
        professional_text=professional,
        customer_text=customer,
    )


def _build_status(downstream_result: dict[str, Any], *, preferred_next_tool: str) -> str:
    if preferred_next_tool == "precheck_quote":
        if downstream_result.get("ready_for_formal_quote"):
            return "ready_for_quote"
        if downstream_result.get("quote_decision") == "hard_block":
            return "blocked"
        return "needs_input"
    if downstream_result.get("missing_fields"):
        return "needs_input"
    return "completed"


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_formal_total(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _format_decimal(value: Decimal) -> str:
    return f"{value.normalize():f}".rstrip("0").rstrip(".") if value != value.to_integral() else str(int(value))


def _load_price_records() -> list[dict[str, Any]]:
    payload = query_price_index.load_payload(Path(__file__).resolve().parent.parent / "data" / "current" / "price-index.json")
    return list(payload.get("records") or [])


def _find_projection_area_record(default_quote_profile: dict[str, Any]) -> dict[str, Any]:
    for record in _load_price_records():
        if not record.get("is_queryable", False):
            continue
        if record.get("record_kind") != "price":
            continue
        if str(record.get("sheet") or "").strip() != str(default_quote_profile.get("sheet") or "").strip():
            continue
        if str(record.get("product_code") or "").strip() != str(default_quote_profile.get("product_code") or "").strip():
            continue
        if str(record.get("name") or "").strip() != str(default_quote_profile.get("name") or "").strip():
            continue
        if str(record.get("pricing_mode") or "").strip() != "projection_area":
            continue
        expected_door_type = str(default_quote_profile.get("door_type") or "").strip()
        if expected_door_type and str(record.get("door_type") or "").strip() != expected_door_type:
            continue
        return record
    raise ValueError("未找到可用于投影面积报价的目录记录")


def _build_default_assumption_note(
    precheck_result: dict[str, Any],
    *,
    explicit_overrides: dict[str, Any] | None = None,
) -> str:
    assumptions = []
    overrides = explicit_overrides or {}
    for item in precheck_result.get("assumed_defaults") or []:
        field = str((item or {}).get("field", "")).strip()
        value = str((item or {}).get("value", "")).strip()
        if field in overrides:
            override_value = overrides.get(field)
            if override_value is None:
                pass
            elif str(override_value).strip() != value:
                continue
        if field and value:
            assumptions.append(f"{field}={value}")
    if not assumptions:
        return ""
    return f"本次先按默认条件计算：{'，'.join(assumptions)}。"


def _build_cabinet_projection_quote_payload(
    *,
    precheck_args: dict[str, Any],
    precheck_result: dict[str, Any],
) -> dict[str, Any]:
    default_quote_profile = precheck_result.get("default_quote_profile") or {}
    if not default_quote_profile:
        raise ValueError("当前柜体路径缺少 default_quote_profile，无法自动执行正式报价")

    record = _find_projection_area_record(default_quote_profile)
    internal_material = normalize_material_for_query(str(precheck_args.get("material") or ""))
    if not internal_material:
        raise ValueError("material is required for cabinet projection quote")
    unit_price = (record.get("materials") or {}).get(internal_material)
    if unit_price is None:
        raise ValueError("目录记录缺少对应材质单价")

    length = calculate_modular_child_bed_quote.parse_dimension(precheck_args.get("length"))
    height = calculate_modular_child_bed_quote.parse_dimension(precheck_args.get("height"))
    depth_value = precheck_args.get("depth") or default_quote_profile.get("assumed_depth")
    depth = calculate_modular_child_bed_quote.parse_dimension(depth_value)
    area = _quantize_money(length * height)
    unit_price_decimal = _quantize_money(Decimal(str(unit_price)))
    subtotal = _quantize_money(area * unit_price_decimal)
    formal_total = _round_formal_total(subtotal)

    material_label = formalize_material_name(internal_material) or internal_material
    display_name = str(default_quote_profile.get("display_name") or default_quote_profile.get("name") or "柜体").strip()
    explicit_has_door = str(precheck_args.get("has_door") or "").strip()
    explicit_door_type = str(precheck_args.get("door_type") or "").strip()
    has_door = explicit_has_door or str(default_quote_profile.get("assumed_has_door") or "").strip()
    if explicit_has_door == "no":
        door_type = ""
    else:
        door_type = explicit_door_type or str(default_quote_profile.get("door_type") or "").strip()
    confirmed_parts = [
        material_label,
        f"长{_format_decimal(length)}米",
        f"高{_format_decimal(height)}米",
        f"深{_format_decimal(depth)}米",
    ]
    if door_type:
        confirmed_parts.append(door_type)
    elif has_door == "yes":
        confirmed_parts.append("带门")
    elif has_door == "no":
        confirmed_parts.append("不带门")

    payload: dict[str, Any] = {
        "items": [
            {
                "product": f"{material_label}{display_name}",
                "confirmed": "，".join(confirmed_parts),
                "pricing_method": "投影面积计价",
                "calculation_steps": [
                    f"投影面积：{_format_decimal(length)} × {_format_decimal(height)} = {_format_decimal(area)}㎡",
                    f"基础单价：{_format_decimal(unit_price_decimal)} 元/㎡",
                    f"基础价格：{_format_decimal(area)} × {_format_decimal(unit_price_decimal)} = {_format_decimal(subtotal)} 元",
                ],
                "subtotal": f"{formal_total}元",
            }
        ],
        "total": f"{formal_total}元",
        "pricing_route": "cabinet_projection_area",
    }
    explicit_overrides = {
        key: precheck_args.get(key)
        for key in ("depth", "has_door", "door_type")
        if key in precheck_args
    }
    assumption_note = _build_default_assumption_note(precheck_result, explicit_overrides=explicit_overrides)
    if assumption_note:
        payload["note"] = assumption_note
    if precheck_result.get("quote_decision") == "reference_quote":
        payload["reference"] = True
    return payload


def _build_modular_child_bed_quote_payload(
    *,
    precheck_args: dict[str, Any],
    precheck_result: dict[str, Any],
) -> dict[str, Any]:
    pricing_route = str(precheck_result.get("pricing_route") or "").strip()
    if pricing_route == "modular_child_bed":
        item = calculate_modular_child_bed_quote.calculate_modular_child_bed_quote(
            bed_form=str(precheck_args.get("bed_form") or ""),
            material=str(precheck_args.get("material") or ""),
            width=str(precheck_args.get("width") or ""),
            length=str(precheck_args.get("length") or ""),
            access_style=str(precheck_args.get("access_style") or ""),
            access_height=precheck_args.get("access_height"),
            lower_bed_type=precheck_args.get("lower_bed_type"),
            guardrail_style=precheck_args.get("guardrail_style"),
            guardrail_length=precheck_args.get("guardrail_length"),
            guardrail_height=precheck_args.get("guardrail_height"),
            stair_width=precheck_args.get("stair_width"),
            stair_depth=precheck_args.get("stair_depth"),
            add_underframe_board=bool(precheck_args.get("add_underframe_board")),
            drawer_count=int(precheck_args.get("drawer_count") or 0),
            drawer_width=precheck_args.get("drawer_width"),
            drawer_depth=precheck_args.get("drawer_depth"),
            leg_brace_length=precheck_args.get("leg_brace_length"),
        )
    elif pricing_route == "modular_child_bed_combo":
        item = calculate_modular_child_bed_combo_quote.calculate_modular_child_bed_combo_quote(
            material=str(precheck_args.get("material") or ""),
            bed_form=str(precheck_args.get("bed_form") or ""),
            width=str(precheck_args.get("width") or ""),
            length=str(precheck_args.get("length") or ""),
            access_style=str(precheck_args.get("access_style") or ""),
            access_height=precheck_args.get("access_height"),
            guardrail_style=str(precheck_args.get("guardrail_style") or ""),
            guardrail_length=str(precheck_args.get("guardrail_length") or ""),
            guardrail_height=str(precheck_args.get("guardrail_height") or ""),
            stair_width=precheck_args.get("stair_width"),
            stair_depth=precheck_args.get("stair_depth"),
            front_cabinet_length=precheck_args.get("front_cabinet_length"),
            front_cabinet_height=precheck_args.get("front_cabinet_height"),
            front_cabinet_depth=precheck_args.get("front_cabinet_depth"),
            front_cabinet_mode=precheck_args.get("front_cabinet_mode"),
            rear_cabinet_length=precheck_args.get("rear_cabinet_length"),
            rear_cabinet_height=precheck_args.get("rear_cabinet_height"),
            rear_cabinet_depth=precheck_args.get("rear_cabinet_depth"),
            rear_cabinet_mode=precheck_args.get("rear_cabinet_mode"),
            interconnected_rows=bool(precheck_args.get("interconnected_rows")),
        )
    else:
        raise ValueError("当前不是模块化儿童床报价路径")

    payload: dict[str, Any] = {
        "items": [item],
        "total": f"{item['formal_total']}元",
        "pricing_route": pricing_route,
    }
    if precheck_result.get("quote_decision") == "reference_quote":
        payload["reference"] = True
    return payload


def _build_bed_standard_quote_payload(
    *,
    precheck_args: dict[str, Any],
    precheck_result: dict[str, Any],
) -> dict[str, Any]:
    result = calculate_bed_quote.calculate_bed_quote(
        name_exact=str(precheck_args.get("category") or ""),
        material=str(precheck_args.get("material") or ""),
        width=str(precheck_args.get("width") or ""),
        length=str(precheck_args.get("length") or ""),
        raise_height=bool(precheck_args.get("raise_height")),
    )
    material_label = str(result.get("material") or str(precheck_args.get("material") or "")).strip()
    confirmed_parts = [
        material_label,
        f"床宽{precheck_args.get('width')}米",
        f"床长{precheck_args.get('length')}米",
    ]
    if precheck_args.get("raise_height"):
        confirmed_parts.append("床体加高")

    item = {
        "product": str(result.get("product") or precheck_args.get("category") or "").strip(),
        "confirmed": "，".join(part for part in confirmed_parts if part),
        "pricing_method": "床类标准规则计价",
        "calculation_steps": [
            *[str(step).strip() for step in (result.get("calculation_steps") or []) if str(step).strip()],
            f"床体小计：{result['formal_total']} 元",
        ],
        "subtotal": f"{result['formal_total']}元",
    }
    payload: dict[str, Any] = {
        "items": [item],
        "total": f"{result['formal_total']}元",
        "pricing_route": "bed_standard",
    }
    if precheck_result.get("quote_decision") == "reference_quote":
        payload["reference"] = True
    return payload


def _find_standard_catalog_record(precheck_args: dict[str, Any]) -> dict[str, Any] | None:
    normalized = dict(PRECHECK_DEFAULTS)
    normalized.update(precheck_args)
    args = argparse.Namespace(**normalized)

    matched_product = precheck_quote.infer_explicit_product_match(args)
    matched_variant = precheck_quote.find_matching_catalog_variant(args, matched_product)
    if matched_variant and str(matched_variant.get("pricing_mode") or "").strip() in precheck_quote.STANDARD_PRICING_MODES:
        return matched_variant

    matched_records = precheck_quote.find_matching_catalog_records(args)
    standard_records = [
        record
        for record in matched_records
        if str(record.get("pricing_mode") or "").strip() in precheck_quote.STANDARD_PRICING_MODES
    ]
    if len(standard_records) == 1:
        return standard_records[0]

    if matched_product:
        candidates = [
            record
            for record in precheck_quote.load_queryable_price_records()
            if record.get("sheet") == matched_product.get("sheet")
            and record.get("product_code") == matched_product.get("product_code")
            and record.get("name") == matched_product.get("name")
            and str(record.get("pricing_mode") or "").strip() in precheck_quote.STANDARD_PRICING_MODES
        ]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _dimension_pairs_from_record(record: dict[str, Any]) -> list[str]:
    dimensions = record.get("dimensions") or {}
    pairs = []
    for field_name, label in [("length", "长"), ("depth", "深"), ("height", "高"), ("width", "宽")]:
        value = dimensions.get(field_name)
        if value in {None, ""}:
            continue
        if isinstance(value, (int, float)):
            pairs.append(f"{label}{_format_decimal(_quantize_money(Decimal(str(value))))}米")
        else:
            pairs.append(f"{label}{value}")
    return pairs


def _build_catalog_unit_price_quote_payload(
    *,
    precheck_args: dict[str, Any],
    precheck_result: dict[str, Any],
) -> dict[str, Any]:
    record = _find_standard_catalog_record(precheck_args)
    if record is None:
        raise ValueError("当前标准目录品未命中唯一目录记录，无法自动执行正式报价")

    internal_material = normalize_material_for_query(str(precheck_args.get("material") or ""))
    if not internal_material:
        raise ValueError("material is required for catalog unit-price quote")
    material_price = (record.get("materials") or {}).get(internal_material)
    if material_price is None:
        raise ValueError("目录记录缺少对应材质价格")

    material_label = formalize_material_name(internal_material) or internal_material
    formal_total = _round_formal_total(_quantize_money(Decimal(str(material_price))))
    dimension_pairs = _dimension_pairs_from_record(record)
    confirmed_parts = [material_label, *dimension_pairs]
    remark = str(record.get("remark") or "").strip()

    item = {
        "product": f"{material_label}{str(record.get('name') or '').strip()}",
        "confirmed": "，".join(part for part in confirmed_parts if part),
        "pricing_method": "目录标准单价计价",
        "calculation_steps": [
            *( [f"目录规格：{'，'.join(dimension_pairs)}"] if dimension_pairs else [] ),
            f"目录标准价：{formal_total} 元",
        ],
        "subtotal": f"{formal_total}元",
    }
    payload: dict[str, Any] = {
        "items": [item],
        "total": f"{formal_total}元",
        "pricing_route": "catalog_unit_price",
    }
    if remark:
        payload["note"] = remark
    if precheck_result.get("quote_decision") == "reference_quote":
        payload["reference"] = True
    return payload


def _build_rock_slab_special_payload(
    *,
    special_quote: dict[str, Any],
    quote_payload: dict[str, Any],
) -> dict[str, Any]:
    items = list(quote_payload.get("items") or [])
    if len(items) != 1:
        raise ValueError("岩板专项价当前需要单个基础报价 item")
    base_item = items[0]
    base_subtotal = _parse_amount(base_item.get("subtotal") or quote_payload.get("total"))
    special_rule = str(special_quote.get("special_rule") or "").strip()
    result = calculate_rock_slab_price.calculate_rock_slab_price(
        scenario=special_rule,
        slab_length=special_quote.get("slab_length"),
        base_subtotal=float(base_subtotal),
        opening_height=special_quote.get("opening_height"),
        cabinet_material=special_quote.get("cabinet_material"),
        side_panel_area=special_quote.get("side_panel_area"),
    )

    confirmed_parts = [str(base_item.get("confirmed") or "").strip()]
    if special_quote.get("slab_length"):
        confirmed_parts.append(f"岩板长度{special_quote.get('slab_length')}m")
    if special_quote.get("opening_height") is not None:
        confirmed_parts.append(f"空区高度{special_quote.get('opening_height')}m")
    if special_quote.get("side_panel_area") is not None:
        confirmed_parts.append(f"超出侧板面积{special_quote.get('side_panel_area')}㎡")

    final_subtotal = _quantize_money(Decimal(str(result["final_subtotal"])))
    pricing_method = str(base_item.get("pricing_method") or "").strip() or "专项计价"
    return {
        "items": [
            {
                "product": str(base_item.get("product") or "").strip(),
                "confirmed": "，".join(part for part in confirmed_parts if part),
                "pricing_method": f"{pricing_method}+岩板加价",
                "calculation_steps": [str(step).strip() for step in result.get("calculation_steps") or [] if str(step).strip()],
                "subtotal": f"{_amount_to_text(final_subtotal)}元",
            }
        ],
        "total": f"{_amount_to_text(final_subtotal)}元",
        "pricing_route": f"special_adjustment.{special_rule}",
    }


def _build_double_sided_door_special_payload(special_quote: dict[str, Any]) -> dict[str, Any]:
    result = calculate_double_sided_door_price.calculate_double_sided_price(
        material=str(special_quote.get("material") or ""),
        depth=str(special_quote.get("depth") or ""),
        side_a_family=str(special_quote.get("side_a_family") or ""),
        side_b_family=str(special_quote.get("side_b_family") or ""),
    )
    unit_price = Decimal(str(result["unit_price"]))
    material_label = str(result.get("material") or special_quote.get("material") or "").strip()
    return {
        "items": [
            {
                "product": f"{material_label}双面门柜体",
                "confirmed": f"{material_label}，进深{special_quote.get('depth')}m，门型组合{result['door_combo_label']}",
                "pricing_method": "双面门专项单价计价",
                "calculation_steps": [
                    f"深度分档：{result['depth_band']}",
                    f"门型组合：{result['door_combo_label']}",
                    f"目录单价：{_amount_to_text(unit_price)} 元",
                ],
                "subtotal": f"{_amount_to_text(unit_price)}元",
            }
        ],
        "total": f"{_amount_to_text(unit_price)}元",
        "pricing_route": "special_adjustment.double_sided_door",
    }


def _build_operation_gap_special_payload(special_quote: dict[str, Any]) -> dict[str, Any]:
    result = calculate_operation_gap_price.calculate_operation_gap_price(
        material=str(special_quote.get("material") or ""),
        width=str(special_quote.get("width") or ""),
        height=str(special_quote.get("height") or ""),
        luminous_backboard=bool(special_quote.get("luminous_backboard")),
        custom_pattern=bool(special_quote.get("custom_pattern")),
    )
    subtotal = Decimal(str(result["subtotal"]))
    material_label = str(result.get("material") or special_quote.get("material") or "").strip()
    confirmed_parts = [material_label, f"宽{special_quote.get('width')}m", f"高{special_quote.get('height')}m"]
    if result.get("luminous_backboard"):
        confirmed_parts.append("发光背板")
    if result.get("custom_pattern"):
        confirmed_parts.append("定制图案")
    return {
        "items": [
            {
                "product": "操作空区背板",
                "confirmed": "，".join(part for part in confirmed_parts if part),
                "pricing_method": "操作空区专项面积计价",
                "calculation_steps": [
                    f"面积：{result['area']}㎡",
                    f"专项单价：{_amount_to_text(Decimal(str(result['adjusted_unit_price'])))} 元/㎡",
                    f"小计：{result['area']} × {_amount_to_text(Decimal(str(result['adjusted_unit_price'])))} = {_amount_to_text(subtotal)} 元",
                ],
                "subtotal": f"{_amount_to_text(subtotal)}元",
            }
        ],
        "total": f"{_amount_to_text(subtotal)}元",
        "pricing_route": "special_adjustment.operation_gap",
    }


def _build_hidden_rosewood_special_payload(special_quote: dict[str, Any]) -> dict[str, Any]:
    result = calculate_hidden_rosewood_discount.calculate_discount(
        exposed_material=str(special_quote.get("exposed_material") or ""),
        base_unit_price=float(special_quote.get("base_unit_price") or 0),
    )
    adjusted_unit_price = Decimal(str(result["adjusted_unit_price"]))
    base_unit_price = Decimal(str(result["base_unit_price"]))
    discount_rate = Decimal(str(result["discount_rate"])) * Decimal("100")
    exposed_material = str(result.get("exposed_material") or special_quote.get("exposed_material") or "").strip()
    return {
        "items": [
            {
                "product": "非见光玫瑰木柜体",
                "confirmed": f"外露材质：{exposed_material}",
                "pricing_method": "非见光玫瑰木折减计价",
                "calculation_steps": [
                    f"基础单价：{_amount_to_text(base_unit_price)} 元/㎡",
                    f"折减比例：{_amount_to_text(discount_rate)}%",
                    f"折后单价：{_amount_to_text(base_unit_price)} × (1 - {result['discount_rate']}) = {_amount_to_text(adjusted_unit_price)} 元/㎡",
                ],
                "subtotal": f"{_amount_to_text(adjusted_unit_price)}元/㎡",
            }
        ],
        "total": f"{_amount_to_text(adjusted_unit_price)}元/㎡",
        "pricing_route": "special_adjustment.hidden_rosewood_discount",
    }


def _build_special_quote_payload(
    *,
    special_quote: dict[str, Any],
    quote_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    special_rule = str(special_quote.get("special_rule") or "").strip()
    if special_rule in calculate_rock_slab_price.SCENARIOS:
        if quote_payload is None:
            raise ValueError("岩板专项价需要提供基础 quote_payload")
        return _build_rock_slab_special_payload(
            special_quote=special_quote,
            quote_payload=quote_payload,
        )
    if special_rule == "double_sided_door":
        return _build_double_sided_door_special_payload(special_quote)
    if special_rule == "operation_gap":
        return _build_operation_gap_special_payload(special_quote)
    if special_rule == "hidden_rosewood_discount":
        return _build_hidden_rosewood_special_payload(special_quote)
    raise ValueError(f"unsupported special_rule: {special_rule}")


def _infer_special_quote_from_context(
    *,
    text: str,
    state: dict[str, Any] | None,
    bundle: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    normalized_text = str(text or "").strip()
    base_payload = _infer_base_payload(state, bundle)
    if not base_payload:
        return None, None

    material = _infer_material_from_text_or_payload(normalized_text, base_payload)

    if "岩板台面" in normalized_text:
        slab_length = _find_first_match(
            normalized_text,
            (
                r"岩板长度\s*([0-9]+(?:\.[0-9]+)?)",
                r"长度\s*([0-9]+(?:\.[0-9]+)?)",
            ),
        )
        if slab_length:
            return (
                {
                    "special_rule": "rock_slab_countertop",
                    "slab_length": slab_length,
                },
                base_payload,
            )

    if ("操作空区" in normalized_text or "空区" in normalized_text) and "报价" in normalized_text:
        width = _find_first_match(normalized_text, (r"宽\s*([0-9]+(?:\.[0-9]+)?)",))
        height = _find_first_match(normalized_text, (r"高\s*([0-9]+(?:\.[0-9]+)?)",))
        if width and height and material:
            return (
                {
                    "special_rule": "operation_gap",
                    "material": material,
                    "width": width,
                    "height": height,
                },
                None,
            )

    if "非见光" in normalized_text and "玫瑰木" in normalized_text:
        base_unit_price = _extract_base_unit_price_from_payload(base_payload)
        if material and base_unit_price is not None:
            return (
                {
                    "special_rule": "hidden_rosewood_discount",
                    "exposed_material": material,
                    "base_unit_price": base_unit_price,
                },
                None,
            )

    if "双面门" in normalized_text:
        side_a_family = ""
        side_b_family = ""
        if "拼框/平板" in normalized_text or "平板/拼框" in normalized_text:
            side_a_family, side_b_family = "frame", "flat"
        elif "拼框/格栅" in normalized_text or "格栅/拼框" in normalized_text:
            side_a_family, side_b_family = "frame", "grid"
        elif "格栅/平板" in normalized_text or "平板/格栅" in normalized_text:
            side_a_family, side_b_family = "grid", "flat"
        elif "平板/平板" in normalized_text:
            side_a_family, side_b_family = "flat", "flat"
        elif "拼框/拼框" in normalized_text:
            side_a_family, side_b_family = "frame", "frame"
        elif "格栅/格栅" in normalized_text:
            side_a_family, side_b_family = "grid", "grid"
        depth = _find_first_match(normalized_text, (r"深\s*([0-9]+(?:\.[0-9]+)?)", r"进深\s*([0-9]+(?:\.[0-9]+)?)"))
        if side_a_family and side_b_family and depth and material:
            return (
                {
                    "special_rule": "double_sided_door",
                    "material": material,
                    "depth": depth,
                    "side_a_family": side_a_family,
                    "side_b_family": side_b_family,
                },
                None,
            )

    return None, None


def _build_quote_payload_from_precheck(
    *,
    precheck_args: dict[str, Any],
    precheck_result: dict[str, Any],
) -> dict[str, Any] | None:
    pricing_route = str(precheck_result.get("pricing_route") or "").strip()
    if pricing_route in {"modular_child_bed", "modular_child_bed_combo"}:
        return _build_modular_child_bed_quote_payload(
            precheck_args=precheck_args,
            precheck_result=precheck_result,
        )
    if pricing_route == "bed_standard" and precheck_result.get("ready_for_formal_quote"):
        return _build_bed_standard_quote_payload(
            precheck_args=precheck_args,
            precheck_result=precheck_result,
        )
    if (
        pricing_route == "cabinet"
        and precheck_result.get("ready_for_formal_quote")
        and precheck_result.get("default_quote_profile")
    ):
        return _build_cabinet_projection_quote_payload(
            precheck_args=precheck_args,
            precheck_result=precheck_result,
        )
    if pricing_route in {"table", "catalog_child_bed", "cabinet", "bed"} and precheck_result.get("ready_for_formal_quote"):
        return _build_catalog_unit_price_quote_payload(
            precheck_args=precheck_args,
            precheck_result=precheck_result,
        )
    return None


def _format_quote_payload_result(
    *,
    quote_payload: dict[str, Any],
    audience_role: str,
    output_profile: str,
    context_json: str | None,
    channel: str | None,
    bundle_root: Path,
    state_root: Path,
    addenda_root: Path,
    disable_addenda: bool,
    route_result: dict[str, Any],
) -> dict[str, Any]:
    prepared_payload = format_quote_reply.prepare_payload(
        quote_payload,
        addenda_root=addenda_root,
        disable_addenda=disable_addenda,
    )
    render_bundle = format_quote_reply.render_for_output_profile(
        prepared_payload,
        audience_role=audience_role,
        output_profile=output_profile,
    )
    reply_text = format_quote_reply.render_with_quote_card_follow_up(
        prepared_payload,
        context_json=context_json,
        channel=channel,
        bundle_root=bundle_root,
        audience_role=audience_role,
        output_profile=output_profile,
        flow_state_root=state_root,
    )
    return {
        "status": "completed",
        "handled_by": "format_quote_reply",
        "audience_role": audience_role,
        "output_profile": output_profile,
        "reply_text": reply_text,
        "internal_summary": render_bundle["internal_summary"],
        "customer_forward_text": render_bundle["customer_forward_text"],
        "missing_fields": list(render_bundle["prepared_payload"].get("missing_fields", [])),
        "pricing_route": str(render_bundle["prepared_payload"].get("pricing_route", "")).strip(),
        "route_result": route_result,
        "downstream_result": render_bundle,
        "conversation_id": str(route_result.get("conversation_id", "")).strip(),
    }


def handle_message(
    *,
    text: str,
    context_json: str | None = None,
    channel: str | None = None,
    product_context: dict[str, Any] | None = None,
    role_override: str | None = None,
    precheck_args: dict[str, Any] | None = None,
    quote_payload: dict[str, Any] | None = None,
    special_quote: dict[str, Any] | None = None,
    state_root: Path = quote_flow_state.DEFAULT_FLOW_STATE_ROOT,
    bundle_root: Path = quote_result_bundle.DEFAULT_BUNDLE_ROOT,
    addenda_root: Path = DEFAULT_ADDENDA_ROOT,
    disable_addenda: bool = False,
    execute_quote_when_ready: bool = False,
    apply_context_reset: bool = False,
    media_root: Path = generate_quote_card_reply.quote_card_renderer.DEFAULT_MEDIA_ROOT,
    hero_image: str | None = None,
    renderer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    existing_state, existing_bundle = _load_existing_quote_context(
        context_json=context_json,
        channel=channel,
        state_root=state_root,
        bundle_root=bundle_root,
    )
    effective_product_context = _effective_product_context(product_context, state=existing_state)
    route_result = route_quote_request.route_message(
        text=text,
        context_json=context_json,
        channel=channel,
        product_context=effective_product_context,
        role_override=role_override,
        state_root=state_root,
        bundle_root=bundle_root,
        addenda_root=addenda_root,
        apply_context_reset=apply_context_reset,
    )
    if (
        not apply_context_reset
        and route_result.get("should_clear_previous_context")
        and not route_result.get("context_reset_applied")
        and (
            _has_explicit_new_quote_signal(text)
            or _has_conflicting_new_quote_route_signal(text=text, state=existing_state, bundle=existing_bundle)
        )
    ):
        route_result = route_quote_request.route_message(
            text=text,
            context_json=context_json,
            channel=channel,
            role_override=role_override,
            state_root=state_root,
            bundle_root=bundle_root,
            addenda_root=addenda_root,
            apply_context_reset=True,
    )
    audience_role = str(route_result.get("audience_role", "customer") or "customer").strip() or "customer"
    output_profile = str(route_result.get("output_profile", "customer_simple") or "customer_simple").strip()
    entry_mode = str(((route_result.get("role_result") or {}).get("entry_mode") or "")).strip()
    customer_strategy = str(((route_result.get("role_result") or {}).get("customer_strategy") or "")).strip()
    previous_guided_signals, previous_guided_turn_count = _customer_guided_context_from_state(existing_state)
    previous_customer_strategy = str((existing_state or {}).get("customer_strategy") or "").strip()
    if (
        audience_role == "customer"
        and entry_mode in CUSTOMER_GUIDED_ENTRY_MODES
        and previous_guided_signals
        and previous_customer_strategy
        and customer_strategy in {"", "default"}
    ):
        customer_strategy = previous_customer_strategy
    existing_state, existing_bundle = _load_existing_quote_context(
        context_json=context_json,
        channel=channel,
        state_root=state_root,
        bundle_root=bundle_root,
    )
    effective_product_context = _effective_product_context(product_context, state=existing_state)
    resumed_precheck_args = None
    if precheck_args is None and quote_payload is None and special_quote is None:
        resumed_precheck_args = _infer_precheck_follow_up_from_state(
            text=text,
            state=existing_state,
        )
        if resumed_precheck_args is None:
            resumed_precheck_args = _infer_formal_quote_adjustment_from_state(
                text=text,
                state=existing_state,
            )
    if route_result.get("should_generate_quote_card"):
        card_reply = generate_quote_card_reply.generate_quote_card_reply(
            context_json=context_json or "",
            channel=channel or "",
            bundle_root=bundle_root,
            media_root=media_root,
            hero_image=hero_image,
            renderer=renderer,
        )
        return {
            "status": "completed",
            "handled_by": "generate_quote_card_reply",
            "audience_role": audience_role,
            "output_profile": output_profile,
            "reply_text": str(card_reply.get("text", "")).strip(),
            "internal_summary": "",
            "customer_forward_text": str(card_reply.get("text", "")).strip(),
            "media_url": str(card_reply.get("media_url", "")).strip(),
            "route_result": route_result,
            "downstream_result": card_reply,
            "conversation_id": str(route_result.get("conversation_id", "")).strip(),
        }

    if special_quote is None and quote_payload is None:
        inferred_special_quote, inferred_base_payload = _infer_special_quote_from_context(
            text=text,
            state=existing_state,
            bundle=existing_bundle,
        )
        if inferred_special_quote is not None:
            special_quote = inferred_special_quote
            quote_payload = inferred_base_payload

    if (
        precheck_args is None
        and quote_payload is None
        and special_quote is None
        and resumed_precheck_args is None
        and not route_result.get("should_clear_previous_context")
        and _has_cached_quote_to_reformat(existing_state, existing_bundle)
        and _is_role_output_switch_request(text, role_override=role_override)
    ):
        cached_payload = _infer_base_payload(existing_state, existing_bundle)
        if cached_payload is not None:
            return _format_quote_payload_result(
                quote_payload=cached_payload,
                audience_role=audience_role,
                output_profile=output_profile,
                context_json=context_json,
                channel=channel,
                bundle_root=bundle_root,
                state_root=state_root,
                addenda_root=addenda_root,
                disable_addenda=disable_addenda,
                route_result=route_result,
            )

    if special_quote is not None:
        return _format_quote_payload_result(
            quote_payload=_build_special_quote_payload(
                special_quote=special_quote,
                quote_payload=quote_payload,
            ),
            audience_role=audience_role,
            output_profile=output_profile,
            context_json=context_json,
            channel=channel,
            bundle_root=bundle_root,
            state_root=state_root,
            addenda_root=addenda_root,
            disable_addenda=disable_addenda,
            route_result=route_result,
        )

    if quote_payload is not None:
        return _format_quote_payload_result(
            quote_payload=quote_payload,
            audience_role=audience_role,
            output_profile=output_profile,
            context_json=context_json,
            channel=channel,
            bundle_root=bundle_root,
            state_root=state_root,
            addenda_root=addenda_root,
            disable_addenda=disable_addenda,
            route_result=route_result,
        )

    preferred_next_tool = str(route_result.get("preferred_next_tool", "") or "").strip()
    inquiry_family = str(route_result.get("inquiry_family", "quote_flow") or "quote_flow").strip() or "quote_flow"
    if preferred_next_tool == "inquiry_reply":
        inquiry_result = _build_inquiry_reply_result(
            text,
            audience_role=audience_role,
            inquiry_family=inquiry_family,
            product_context=effective_product_context,
        )
        missing_fields = list(inquiry_result.get("missing_fields") or [])
        resolved_product_context = inquiry_result.get("resolved_product_context") or effective_product_context or {}
        conversation_id = _store_flow_state(
            context_json=context_json,
            channel=channel,
            state_root=state_root,
            audience_role=audience_role,
            customer_strategy=customer_strategy,
            active_route=inquiry_family,
            missing_fields=missing_fields,
            internal_summary=inquiry_result["internal_summary"],
            customer_forward_text=inquiry_result["customer_forward_text"],
            confirmed_fields={},
            handoff_summary=inquiry_result["reply_text"],
            active_inquiry_family=inquiry_family,
            captured_product_context=resolved_product_context,
            last_non_quote_reply=inquiry_result["reply_text"],
            last_safe_boundary_reason=str(inquiry_result.get("safe_boundary_reason") or ""),
        )
        return {
            "status": "completed" if inquiry_result.get("can_answer_directly") and not missing_fields else "needs_input",
            "handled_by": "inquiry_reply",
            "audience_role": audience_role,
            "output_profile": output_profile,
            "entry_mode": entry_mode,
            "customer_strategy": customer_strategy,
            "reply_text": inquiry_result["reply_text"],
            "internal_summary": inquiry_result["internal_summary"],
            "customer_forward_text": inquiry_result["customer_forward_text"],
            "missing_fields": missing_fields,
            "question_code": None,
            "constraint_code": None,
            "detail_level_hint": "single_question_follow_up" if missing_fields else "direct_answer",
            "response_stage": "inquiry_reply",
            "signal_summary": {},
            "next_best_question": inquiry_result.get("next_question") or "",
            "pricing_route": "",
            "source_basis": inquiry_result.get("source_basis") or "",
            "safe_boundary_reason": inquiry_result.get("safe_boundary_reason") or "",
            "handoff_needed": bool(inquiry_result.get("handoff_needed")),
            "route_result": route_result,
            "downstream_result": inquiry_result,
            "conversation_id": conversation_id or str(route_result.get("conversation_id", "")).strip(),
        }
    if resumed_precheck_args is not None:
        precheck_args = resumed_precheck_args
        preferred_next_tool = "precheck_quote"
    if preferred_next_tool == "query_bed_weight_guidance":
        downstream_result = query_bed_weight_guidance.query_guidance(text)
        text_bundle = _guidance_text(downstream_result, audience_role=audience_role)
    elif preferred_next_tool == "query_addendum_guidance":
        downstream_result = query_addendum_guidance.query_guidance(text, addenda_root)
        text_bundle = _guidance_text(downstream_result, audience_role=audience_role)
    elif preferred_next_tool == "detect_special_cabinet_rule":
        downstream_result = detect_special_cabinet_rule.detect_rule(text)
        text_bundle = _special_rule_text(downstream_result, audience_role=audience_role)
    elif preferred_next_tool == "precheck_quote":
        if precheck_args is None:
            inferred_precheck_args = _infer_precheck_args_from_text(text)
            if inferred_precheck_args:
                precheck_args = inferred_precheck_args
        precheck_args = _augment_precheck_args_from_customer_guided_context(precheck_args, state=existing_state)
        precheck_args = _augment_precheck_args_from_product_context(precheck_args, product_context=effective_product_context)
        if audience_role == "customer" and entry_mode in CUSTOMER_GUIDED_ENTRY_MODES and _should_use_customer_guidance(
            customer_strategy=customer_strategy,
            precheck_args=precheck_args,
        ):
            if audience_role == "customer" and entry_mode in CUSTOMER_GUIDED_ENTRY_MODES:
                guidance_result = _customer_guided_text(
                    text,
                    customer_strategy=customer_strategy,
                    previous_signals=previous_guided_signals,
                    turn_index=previous_guided_turn_count + 1 if previous_guided_signals else 1,
                )
                conversation_id = _store_flow_state(
                    context_json=context_json,
                    channel=channel,
                    state_root=state_root,
                    audience_role=audience_role,
                    customer_strategy=customer_strategy,
                    active_route=entry_mode,
                    missing_fields=list(guidance_result["missing_fields"]),
                    internal_summary=guidance_result["internal_summary"],
                    customer_forward_text=guidance_result["customer_forward_text"],
                    confirmed_fields={
                        "signal_summary": guidance_result["signal_summary"],
                        "guided_turn_count": guidance_result["guided_turn_count"],
                    },
                    handoff_summary=guidance_result["reply_text"],
                    active_inquiry_family="quote_flow",
                    captured_product_context=effective_product_context or {},
                )
                return {
                    "status": "needs_input",
                    "handled_by": "customer_guided_discovery",
                    "audience_role": audience_role,
                    "output_profile": output_profile,
                    "entry_mode": entry_mode,
                    "customer_strategy": customer_strategy,
                    "reply_text": guidance_result["reply_text"],
                    "internal_summary": guidance_result["internal_summary"],
                    "customer_forward_text": guidance_result["customer_forward_text"],
                    "missing_fields": list(guidance_result["missing_fields"]),
                    "question_code": guidance_result["question_code"],
                    "constraint_code": guidance_result["constraint_code"],
                    "detail_level_hint": guidance_result["detail_level_hint"],
                    "response_stage": guidance_result["response_stage"],
                    "signal_summary": guidance_result["signal_summary"],
                    "next_best_question": guidance_result["next_best_question"],
                    "guided_turn_count": guidance_result["guided_turn_count"],
                    "pricing_route": "",
                    "route_result": route_result,
                    "downstream_result": guidance_result,
                    "conversation_id": conversation_id or str(route_result.get("conversation_id", "")).strip(),
                }
        if precheck_args is None:
            return {
                "status": "needs_precheck_args",
                "handled_by": "route_quote_request",
                "audience_role": audience_role,
                "output_profile": output_profile,
                "entry_mode": entry_mode,
                "customer_strategy": customer_strategy,
                "reply_text": "",
                "internal_summary": "",
                "customer_forward_text": "",
                "missing_fields": [],
                "route_result": route_result,
                "downstream_result": {},
                "conversation_id": str(route_result.get("conversation_id", "")).strip(),
            }
        downstream_result = _run_precheck(precheck_args)
        if execute_quote_when_ready and downstream_result.get("ready_for_formal_quote"):
            calculated_payload = _build_quote_payload_from_precheck(
                precheck_args=precheck_args,
                precheck_result=downstream_result,
            )
            if calculated_payload is not None:
                return _format_quote_payload_result(
                    quote_payload=calculated_payload,
                    audience_role=audience_role,
                    output_profile=output_profile,
                    context_json=context_json,
                    channel=channel,
                    bundle_root=bundle_root,
                    state_root=state_root,
                    addenda_root=addenda_root,
                    disable_addenda=disable_addenda,
                    route_result=route_result,
                )
        text_bundle = _precheck_text(downstream_result, audience_role=audience_role)
    else:
        downstream_result = {}
        text_bundle = _shape_role_output(audience_role=audience_role, professional_text="", customer_text="")

    status = _build_status(downstream_result, preferred_next_tool=preferred_next_tool)
    missing_fields = list(downstream_result.get("missing_fields", []))
    active_route = str(
        downstream_result.get("pricing_route")
        or downstream_result.get("route")
        or preferred_next_tool
    ).strip()
    conversation_id = _store_flow_state(
        context_json=context_json,
        channel=channel,
        state_root=state_root,
        audience_role=audience_role,
        customer_strategy=customer_strategy,
        active_route=active_route,
        missing_fields=missing_fields,
        internal_summary=text_bundle["internal_summary"],
        customer_forward_text=text_bundle["customer_forward_text"],
        confirmed_fields=precheck_args if preferred_next_tool == "precheck_quote" else {},
        handoff_summary=text_bundle["reply_text"],
        active_inquiry_family=inquiry_family,
        captured_product_context=effective_product_context or {},
    )

    return {
        "status": status,
        "handled_by": preferred_next_tool,
        "audience_role": audience_role,
        "output_profile": output_profile,
        "entry_mode": entry_mode,
        "customer_strategy": customer_strategy,
        "reply_text": text_bundle["reply_text"],
        "internal_summary": text_bundle["internal_summary"],
        "customer_forward_text": text_bundle["customer_forward_text"],
        "missing_fields": missing_fields,
        "question_code": downstream_result.get("question_code"),
        "constraint_code": downstream_result.get("constraint_code"),
        "detail_level_hint": downstream_result.get("detail_level_hint"),
        "response_stage": downstream_result.get("response_stage"),
        "signal_summary": downstream_result.get("signal_summary"),
        "next_best_question": downstream_result.get("next_best_question"),
        "pricing_route": str(downstream_result.get("pricing_route", "")).strip(),
        "route_result": route_result,
        "downstream_result": downstream_result,
        "conversation_id": conversation_id or str(route_result.get("conversation_id", "")).strip(),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = handle_message(
        text=args.text,
        context_json=args.context_json,
        channel=args.channel,
        product_context=_parse_json_object(args.product_context_json, field_name="product_context_json"),
        role_override=args.role_override,
        precheck_args=_parse_json_object(args.precheck_args_json, field_name="precheck_args_json"),
        quote_payload=_parse_json_object(args.quote_payload_json, field_name="quote_payload_json"),
        special_quote=_parse_json_object(args.special_quote_json, field_name="special_quote_json"),
        state_root=Path(args.state_root).expanduser().resolve(),
        bundle_root=Path(args.bundle_root).expanduser().resolve(),
        addenda_root=Path(args.addenda_root).expanduser().resolve(),
        disable_addenda=args.disable_addenda,
        execute_quote_when_ready=args.execute_quote_when_ready,
        apply_context_reset=args.apply_context_reset,
        media_root=Path(args.media_root).expanduser().resolve(),
        hero_image=args.hero_image,
    )
    _emit_cli_payload(payload, output_mode=args.output_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
