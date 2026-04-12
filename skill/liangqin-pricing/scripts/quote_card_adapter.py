#!/usr/bin/env python3
"""Adapt Liangqin quote payloads into quote-card view models."""

from __future__ import annotations

import re
from typing import Any

from material_names import formalize_text


MAX_ITEM_ROWS = 6
MAX_MULTI_DETAIL_CARDS = 4
MAX_SINGLE_BASIS_LINES = 4
MAX_MULTI_BASIS_LINES = 5
MAX_MULTI_HIGHLIGHTS_PER_CARD = 3
MAX_NOTES = 3
MAX_OPTION_CARDS = 3
MAX_ACTION_QUEUE_CARDS = 5
MAX_OBJECTION_CARDS = 3
MAX_QUICK_ACTION_CARDS = 6
MAX_RISK_POINTS = 3
INTERNAL_NOTE_PATTERNS = [
    re.compile(r"^按当前规则可正式报价[。.]?$"),
    re.compile(r"^已套用设计师追加规则[:：]"),
]
FINAL_TOTAL_PATTERN = re.compile(r"(最终|合计|总价|总计|报价)")
SUMMARY_STEP_PATTERN = re.compile(r"(小计|合计|总价|总计|报价|最终)")
CHILD_SPACE_KEYWORDS = (
    "儿童房",
    "儿童空间",
    "儿童床",
    "半高床",
    "高架床",
    "错层床",
    "子母床",
    "上下床",
)


def _normalize_text(value: Any) -> str:
    return formalize_text(str(value or "").strip()).strip()


def _ensure_string(record: dict[str, Any], key: str) -> str:
    value = _normalize_text(record.get(key, ""))
    if not value:
        raise ValueError(f"缺少必填字段: {key}")
    return value


def _unique_notes(entries: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        normalized = _normalize_text(entry)
        if not normalized:
            continue
        if any(pattern.search(normalized) for pattern in INTERNAL_NOTE_PATTERNS):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _summarize_confirmed_text(value: str) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    first_chunk = re.split(r"[，。；;]", normalized)[0]
    return first_chunk.strip()


def _looks_like_total_repeat(step: str, quote_total: str) -> bool:
    normalized_step = _normalize_text(step)
    normalized_total = _normalize_text(quote_total)
    return bool(FINAL_TOTAL_PATTERN.search(normalized_step)) and normalized_total and normalized_total in normalized_step


def _select_single_basis_lines(item: dict[str, Any], quote_total: str) -> tuple[list[str], bool]:
    pricing_method = _ensure_string(item, "pricing_method")
    steps = [_normalize_text(step) for step in item.get("calculation_steps") or [] if _normalize_text(step)]
    lines = [f"计价方式：{pricing_method}"]

    for step in steps:
        if _looks_like_total_repeat(step, quote_total):
            continue
        if step not in lines:
            lines.append(step)

    trimmed = lines[:MAX_SINGLE_BASIS_LINES]
    return trimmed, len(lines) > len(trimmed)


def _build_single_item_rows(item: dict[str, Any], quote_total: str) -> list[dict[str, str]]:
    return [
        {
            "name": _ensure_string(item, "product"),
            "amount": _normalize_text(item.get("subtotal") or quote_total),
            "meta": _ensure_string(item, "pricing_method"),
        }
    ]


def _build_option_cards(payload: dict[str, Any]) -> list[dict[str, str]]:
    option_cards: list[dict[str, str]] = []
    for entry in payload.get("option_set") or []:
        if not isinstance(entry, dict):
            continue
        title = _normalize_text(entry.get("title", ""))
        detail = _normalize_text(entry.get("description", ""))
        if not title or not detail:
            continue
        option_cards.append({"title": title, "detail": detail})
    return option_cards[:MAX_OPTION_CARDS]


def _build_version_action_cards(payload: dict[str, Any]) -> list[dict[str, str]]:
    actions = payload.get("quote_version_actions") or {}
    if not isinstance(actions, dict):
        return []
    mapping = (
        ("当前怎么发", "current_send_action"),
        ("下一版怎么接", "next_version_offer_action"),
        ("给客户怎么解释", "customer_transition_line"),
    )
    cards: list[dict[str, str]] = []
    for title, key in mapping:
        detail = _normalize_text(actions.get(key, ""))
        if not detail:
            continue
        cards.append({"title": title, "detail": detail})
    return cards[:3]


def _build_action_queue_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    queue = payload.get("consultant_action_queue") or []
    if not isinstance(queue, list):
        return []
    normalized_entries: list[dict[str, Any]] = []
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        title = _normalize_text(entry.get("title", ""))
        text = _normalize_text(entry.get("text", ""))
        if not title or not text:
            continue
        try:
            rank = int(entry.get("rank"))
        except (TypeError, ValueError):
            rank = len(normalized_entries) + 1
        trigger_hint = _normalize_text(entry.get("trigger_hint", ""))
        normalized_entries.append(
            {
                "title": title,
                "text": text,
                "rank": rank,
                "recommended": bool(entry.get("recommended")),
                "trigger_hint": trigger_hint,
            }
        )

    normalized_entries.sort(key=lambda item: (int(item.get("rank", 9999)), str(item.get("title", "")).strip()))
    cards: list[dict[str, Any]] = []
    for entry in normalized_entries[:MAX_ACTION_QUEUE_CARDS]:
        rank = int(entry.get("rank", len(cards) + 1))
        title = str(entry.get("title", "")).strip()
        prefix = f"建议先做 {rank}" if bool(entry.get("recommended")) else f"第 {rank} 步"
        lines = [f"动作：{str(entry.get('text', '')).strip()}"]
        trigger_hint = str(entry.get("trigger_hint", "")).strip()
        if trigger_hint:
            lines.append(f"时机：{trigger_hint}")
        cards.append({"title": f"{prefix} | {title}", "lines": lines[:2]})
    return cards


def _build_objection_action_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    objection_playbook = payload.get("objection_playbook") or {}
    if not isinstance(objection_playbook, dict):
        return []
    recommended_code = _normalize_text(objection_playbook.get("recommended_first_code", ""))
    ordered_codes: list[str] = []
    if recommended_code:
        ordered_codes.append(recommended_code)
    for code in ("price_high", "why_this_price", "cheaper_option", "need_time"):
        if code not in ordered_codes:
            ordered_codes.append(code)

    cards: list[dict[str, Any]] = []
    for code in ordered_codes:
        entry = objection_playbook.get(code)
        if not isinstance(entry, dict):
            continue
        label = _normalize_text(entry.get("label", ""))
        if not label:
            continue
        lines: list[str] = []
        customer_reply = _normalize_text(entry.get("customer_reply", ""))
        transition_line = _normalize_text(entry.get("transition_line", ""))
        followthrough_line = _normalize_text(entry.get("followthrough_line", ""))
        if customer_reply:
            lines.append(f"怎么回：{customer_reply}")
        if transition_line:
            lines.append(f"怎么接：{transition_line}")
        if followthrough_line:
            lines.append(f"怎么推进：{followthrough_line}")
        if not lines:
            continue
        title = f"优先处理 | {label}" if code == recommended_code else label
        cards.append({"title": title, "lines": lines[:3]})
    return cards[:MAX_OBJECTION_CARDS]


def _build_quick_action_cards(payload: dict[str, Any]) -> list[dict[str, str]]:
    actions = payload.get("consultant_quick_actions") or []
    if not isinstance(actions, list):
        return []
    cards: list[dict[str, str]] = []
    for entry in actions:
        if not isinstance(entry, dict):
            continue
        title = _normalize_text(entry.get("label", ""))
        detail = _normalize_text(entry.get("text", ""))
        if not title or not detail:
            continue
        cards.append({"title": title, "detail": detail})
    return cards[:MAX_QUICK_ACTION_CARDS]


def _build_next_action_text(payload: dict[str, Any]) -> str:
    next_best_action = payload.get("next_best_action") or {}
    if not isinstance(next_best_action, dict):
        return ""
    return _normalize_text(next_best_action.get("card_text", "")) or _normalize_text(next_best_action.get("text", ""))


def _build_followthrough_action(payload: dict[str, Any]) -> dict[str, str]:
    next_best_action = payload.get("next_best_action") or {}
    if not isinstance(next_best_action, dict):
        return {}
    label = _normalize_text(next_best_action.get("followthrough_action_label", ""))
    text = _normalize_text(next_best_action.get("followthrough_text", ""))
    if not label and not text:
        return {}
    return {"label": label, "text": text}


def _build_decision_risk_points(payload: dict[str, Any]) -> list[str]:
    return [
        _normalize_text(entry)
        for entry in (payload.get("decision_risk_points") or [])[:MAX_RISK_POINTS]
        if _normalize_text(entry)
    ]


def _adapt_single(payload: dict[str, Any], item: dict[str, Any], quote_badge: str, quote_total: str) -> dict[str, Any]:
    headline = _ensure_string(item, "product")
    confirmed_text = _ensure_string(item, "confirmed")
    _ensure_string(item, "pricing_method")
    steps = item.get("calculation_steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("缺少必填字段: calculation_steps")

    key_basis_lines, basis_overflow = _select_single_basis_lines(item, quote_total)
    notes = _unique_notes([str(payload.get("note", "")), *[str(entry) for entry in payload.get("addendum_notes") or []]])
    trimmed_notes = notes[:MAX_NOTES]
    overflow = basis_overflow or len(notes) > len(trimmed_notes)

    return {
        "quote_badge": quote_badge,
        "headline": headline,
        "quote_total": quote_total,
        "confirmed_text": confirmed_text,
        "item_rows": _build_single_item_rows(item, quote_total),
        "key_basis_lines": key_basis_lines,
        "notes": trimmed_notes,
        "option_cards": _build_option_cards(payload),
        "version_action_cards": _build_version_action_cards(payload),
        "action_queue_cards": _build_action_queue_cards(payload),
        "quick_action_cards": _build_quick_action_cards(payload),
        "objection_action_cards": _build_objection_action_cards(payload),
        "decision_risk_points": _build_decision_risk_points(payload),
        "next_action_text": _build_next_action_text(payload),
        "followthrough_action": _build_followthrough_action(payload),
        "overflow_hint": "完整计算过程见本条文字报价。" if overflow else "",
    }


def _build_multi_item_rows(items: list[dict[str, Any]]) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    for index, item in enumerate(items):
        name = _normalize_text(item.get("product", "")) or f"产品 {index + 1}"
        amount = _normalize_text(item.get("subtotal", ""))
        meta = _normalize_text(item.get("pricing_method", "")) or _summarize_confirmed_text(str(item.get("confirmed", "")))
        rows.append({"name": name, "amount": amount, "meta": meta})
    trimmed = rows[:MAX_ITEM_ROWS]
    return trimmed, len(rows) > len(trimmed)


def _select_multi_item_highlights(item: dict[str, Any]) -> tuple[list[str], bool]:
    steps = [_normalize_text(step) for step in item.get("calculation_steps") or [] if _normalize_text(step)]
    filtered = [step for step in steps if not SUMMARY_STEP_PATTERN.search(step)]
    preferred = filtered or steps
    trimmed = preferred[:MAX_MULTI_HIGHLIGHTS_PER_CARD]
    return trimmed, len(preferred) > len(trimmed)


def _build_multi_detail_cards(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    cards: list[dict[str, Any]] = []
    overflow = False
    for index, item in enumerate(items):
        highlights, highlight_overflow = _select_multi_item_highlights(item)
        overflow = overflow or highlight_overflow
        cards.append(
            {
                "name": _normalize_text(item.get("product", "")) or f"产品 {index + 1}",
                "amount": _normalize_text(item.get("subtotal", "")),
                "meta": _normalize_text(item.get("pricing_method", "")) or _summarize_confirmed_text(str(item.get("confirmed", ""))),
                "highlights": highlights,
            }
        )
    trimmed = cards[:MAX_MULTI_DETAIL_CARDS]
    return trimmed, overflow or len(cards) > len(trimmed)


def _select_multi_basis_lines(items: list[dict[str, Any]]) -> tuple[list[str], bool]:
    methods = []
    basis_lines = []
    for item in items:
        pricing_method = _normalize_text(item.get("pricing_method", ""))
        if pricing_method and pricing_method not in methods:
            methods.append(pricing_method)
        highlights, highlight_overflow = _select_multi_item_highlights(item)
        basis_lines.extend(f"{_normalize_text(item.get('product', '产品'))}：{highlight}" for highlight in highlights[:2])
        if highlight_overflow:
            basis_lines.append(f"{_normalize_text(item.get('product', '产品'))}：完整细项见文字报价")

    header = f"共 {len(items)} 项，涉及 {' / '.join(methods) if methods else '多种计价方式'}。"
    lines = [header, *basis_lines]
    trimmed = lines[:MAX_MULTI_BASIS_LINES]
    return trimmed, len(lines) > len(trimmed)


def _build_multi_confirmed_text(items: list[dict[str, Any]]) -> str:
    names = [_normalize_text(item.get("product", "")) or f"产品 {index + 1}" for index, item in enumerate(items)]
    if not names:
        return ""
    if len(names) <= 3:
        return f"共 {len(names)} 项，包含{'、'.join(names)}。"
    return f"共 {len(names)} 项，包含{'、'.join(names[:3])}等产品。"


def _build_multi_headline(items: list[dict[str, Any]]) -> str:
    combined = " ".join(
        [
            _normalize_text(item.get("product", "")) + " " + _normalize_text(item.get("confirmed", ""))
            for item in items
        ]
    )
    if any(keyword in combined for keyword in CHILD_SPACE_KEYWORDS):
        return "儿童空间报价"
    return "定制报价汇总"


def _adapt_multi(payload: dict[str, Any], items: list[dict[str, Any]], quote_badge: str, quote_total: str) -> dict[str, Any]:
    item_rows, item_overflow = _build_multi_item_rows(items)
    detail_cards, detail_overflow = _build_multi_detail_cards(items)
    key_basis_lines, basis_overflow = _select_multi_basis_lines(items)
    notes = _unique_notes([str(payload.get("note", "")), *[str(entry) for entry in payload.get("addendum_notes") or []]])
    trimmed_notes = notes[:MAX_NOTES]
    overflow = item_overflow or detail_overflow or basis_overflow or len(notes) > len(trimmed_notes)

    return {
        "quote_badge": quote_badge,
        "headline": _build_multi_headline(items),
        "quote_total": quote_total,
        "confirmed_text": _build_multi_confirmed_text(items),
        "item_rows": item_rows,
        "key_basis_lines": key_basis_lines,
        "detail_cards": detail_cards,
        "notes": trimmed_notes,
        "option_cards": _build_option_cards(payload),
        "version_action_cards": _build_version_action_cards(payload),
        "action_queue_cards": _build_action_queue_cards(payload),
        "quick_action_cards": _build_quick_action_cards(payload),
        "objection_action_cards": _build_objection_action_cards(payload),
        "decision_risk_points": _build_decision_risk_points(payload),
        "next_action_text": _build_next_action_text(payload),
        "followthrough_action": _build_followthrough_action(payload),
        "overflow_hint": "完整计算过程见本条文字报价。" if overflow else "",
    }


def adapt_quote_card_payload(payload: dict[str, Any], *, hero_image: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload 必须是对象。")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("缺少必填字段: items")

    quote_total = _normalize_text(payload.get("total", ""))
    if not quote_total:
        raise ValueError("缺少必填字段: total")

    quote_badge = "参考报价（仅供参考）" if payload.get("reference") else "正式报价"

    result = _adapt_single(payload, items[0], quote_badge, quote_total) if len(items) == 1 else _adapt_multi(
        payload, items, quote_badge, quote_total
    )
    if hero_image:
        result["hero_image"] = hero_image
    return result
