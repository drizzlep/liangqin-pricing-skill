from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


AUTO_PASS_DIFF = Decimal("100.00")
REVIEW_DIFF = Decimal("500.00")

DECISION_LABELS = {
    "auto_pass": "可自动通过",
    "review_recommended": "建议人工复核",
    "manual_required": "必须人工确认",
}
ITEM_STATUS_LABELS = {
    "compared": "已核对",
    "review_recommended": "建议复核",
    "manual_required": "必须人工确认",
}
BASIS_LABELS = {
    "contract_total": "合同总金额",
    "list_price_total": "折前合计",
    "discounted_total": "折后合计",
}


def build_reviewer_card(
    *,
    contract_audit_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
    review_analysis_payload: dict[str, Any],
) -> dict[str, Any]:
    financials = contract_audit_payload.get("financials") or {}
    best_match_target = str(pricing_compare_payload.get("best_match_target") or "").strip()
    difference = str(pricing_compare_payload.get("best_match_diff") or "").strip()
    difference_value = _to_decimal(pricing_compare_payload.get("best_match_diff_value"))
    pricing_amount = str(pricing_compare_payload.get("pricing_total") or "").strip()
    contract_amount = _pick_contract_amount(financials=financials, basis=best_match_target)
    item_ledger = _extract_item_ledger(
        financials=financials,
        pricing_compare_payload=pricing_compare_payload,
    )
    line_items = [_build_line_item(item) for item in item_ledger]
    pending_items = [item for item in line_items if item["review_status"] == "manual_required"]
    compared_items = [item for item in line_items if item["review_status"] != "manual_required"]
    pending_amount = sum(
        (_parse_amount(item.get("contract_amount")) or Decimal("0"))
        for item in pending_items
    )

    difference_sources = _build_difference_sources(
        pending_items=pending_items,
        compared_items=compared_items,
        pending_amount=pending_amount,
        best_match_target=best_match_target,
        pricing_compare_payload=pricing_compare_payload,
    )
    decision = _derive_decision(
        pending_items=pending_items,
        difference_value=difference_value,
        best_match_target=best_match_target,
        pricing_amount=pricing_amount,
        line_items=line_items,
    )
    primary_reason = _build_primary_reason(
        decision=decision,
        pending_items=pending_items,
        difference=difference,
        difference_value=difference_value,
        best_match_target=best_match_target,
        pricing_amount=pricing_amount,
    )
    next_actions = _build_next_actions(
        decision=decision,
        pending_items=pending_items,
        best_match_target=best_match_target,
        review_analysis_payload=review_analysis_payload,
    )

    return {
        "status": "ready",
        "decision": decision,
        "decision_label": DECISION_LABELS[decision],
        "primary_reason": primary_reason,
        "amounts": {
            "contract_amount": contract_amount,
            "pricing_amount": pricing_amount,
            "difference": difference,
            "difference_value": _decimal_to_float(difference_value),
            "comparison_basis": best_match_target,
            "comparison_basis_label": BASIS_LABELS.get(best_match_target, best_match_target or "未识别"),
        },
        "difference_sources": difference_sources,
        "line_items": line_items,
        "next_actions": next_actions[:3],
    }


def render_reviewer_card_markdown(card: dict[str, Any]) -> str:
    amounts = card.get("amounts") or {}
    lines = [
        "# 审核员决策卡",
        "",
        f"- 审核结论：{card.get('decision_label') or '待判断'}",
        f"- 主要原因：{card.get('primary_reason') or '暂无'}",
        f"- 对比口径：{amounts.get('comparison_basis_label') or '未识别'}",
        f"- 合同金额：{amounts.get('contract_amount') or '未识别'}",
        f"- 系统报价：{amounts.get('pricing_amount') or '未形成报价'}",
        f"- 差额：{amounts.get('difference') or '无法对比'}",
        "",
        "## 逐品项",
        "",
    ]
    for index, item in enumerate(list(card.get("line_items") or []), start=1):
        lines.append(
            f"{index}. {item.get('product_name') or '未命名品项'}："
            f"合同 {item.get('contract_amount') or '未识别'}，"
            f"报价 {item.get('pricing_amount') or '未形成报价'}，"
            f"差额 {item.get('difference') or '无法对比'}，"
            f"状态 {item.get('review_status_label') or '待判断'}。"
        )
        manual_hint = str(item.get("manual_hint") or "").strip()
        if manual_hint:
            lines.append(f"   提示：{manual_hint}")
    next_actions = [str(item).strip() for item in list(card.get("next_actions") or []) if str(item).strip()]
    if next_actions:
        lines.extend(["", "## 建议动作", ""])
        for index, action in enumerate(next_actions, start=1):
            lines.append(f"{index}. {action}")
    return "\n".join(lines).strip() + "\n"


def _extract_item_ledger(
    *,
    financials: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    item_ledger = [
        dict(item)
        for item in list(pricing_compare_payload.get("item_ledger") or [])
        if isinstance(item, dict)
    ]
    if item_ledger:
        return item_ledger
    return [
        {
            "product_name": "整单",
            "contract_amount": str(
                ((financials.get("contract_total") or {}).get("value"))
                or ((financials.get("discounted_total") or {}).get("value"))
                or ((financials.get("list_price_total") or {}).get("value"))
                or ""
            ).strip(),
            "pricing_amount": str(pricing_compare_payload.get("pricing_total") or "").strip(),
            "difference": str(pricing_compare_payload.get("best_match_diff") or "").strip(),
            "ledger_status": "compared" if str(pricing_compare_payload.get("pricing_total") or "").strip() else "pending",
            "pricing_route": str(pricing_compare_payload.get("pricing_route") or "").strip(),
        }
    ]


def _build_line_item(item: dict[str, Any]) -> dict[str, Any]:
    ledger_status = str(item.get("ledger_status") or "").strip()
    pricing_amount = str(item.get("pricing_amount") or "").strip()
    difference_value = _parse_amount(item.get("difference"))
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()

    if ledger_status != "compared" or not pricing_amount:
        review_status = "manual_required"
        manual_hint = "该品项未形成报价，请人工确认后再判断整单金额。"
    elif difference_value is not None and difference_value > REVIEW_DIFF:
        review_status = "review_recommended"
        manual_hint = "该品项差额偏大，建议人工复核。"
    elif fallback_strategy:
        review_status = "review_recommended"
        manual_hint = "该品项使用估算路线，金额接近时可低优先级复核。"
    else:
        review_status = "compared"
        manual_hint = ""

    return {
        "product_name": str(item.get("product_name") or "整单").strip() or "整单",
        "product_code": str(item.get("product_code") or "").strip(),
        "contract_amount": str(item.get("contract_amount") or "").strip(),
        "pricing_amount": pricing_amount,
        "difference": str(item.get("difference") or "").strip(),
        "difference_value": _decimal_to_float(difference_value),
        "review_status": review_status,
        "review_status_label": ITEM_STATUS_LABELS[review_status],
        "field_confidence": _derive_field_confidence(item),
        "manual_hint": manual_hint,
        "pricing_route_label": _pricing_route_label(item),
    }


def _derive_field_confidence(item: dict[str, Any]) -> str:
    if str(item.get("ledger_status") or "").strip() != "compared":
        return "low"
    if str(item.get("fallback_strategy") or "").strip():
        return "medium"
    return "high"


def _pricing_route_label(item: dict[str, Any]) -> str:
    fallback_label = str(item.get("fallback_label") or "").strip()
    if fallback_label:
        return fallback_label
    route = str(item.get("pricing_route") or "").strip()
    labels = {
        "catalog_unit_price": "目录价",
        "cabinet_projection_area": "柜类投影面积",
        "cabinet_projection_area_fallback": "柜类投影面积估算",
        "multi_product_aggregate": "多品项汇总",
        "non_billable_accessory": "0元附件",
    }
    return labels.get(route, route)


def _build_difference_sources(
    *,
    pending_items: list[dict[str, Any]],
    compared_items: list[dict[str, Any]],
    pending_amount: Decimal,
    best_match_target: str,
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if pending_items:
        sources.append(
            {
                "source_type": "pending_items",
                "label": "待入账品项",
                "amount": _format_amount(pending_amount),
                "item_count": len(pending_items),
                "item_names": [item["product_name"] for item in pending_items],
            }
        )
    dominant = _pick_largest_compared_diff(compared_items)
    if dominant:
        sources.append(
            {
                "source_type": "largest_compared_item",
                "label": "最大已入账差异品项",
                "amount": dominant.get("difference") or "",
                "item_count": 1,
                "item_names": [dominant["product_name"]],
            }
        )
    if best_match_target == "list_price_total":
        sources.append(
            {
                "source_type": "discount_basis",
                "label": "折扣口径",
                "amount": str(pricing_compare_payload.get("best_match_diff") or "").strip(),
                "item_count": 0,
                "item_names": [],
            }
        )
    return sources


def _pick_largest_compared_diff(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        item for item in items if _to_decimal(item.get("difference_value")) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: _to_decimal(item.get("difference_value")) or Decimal("0"))


def _derive_decision(
    *,
    pending_items: list[dict[str, Any]],
    difference_value: Decimal | None,
    best_match_target: str,
    pricing_amount: str,
    line_items: list[dict[str, Any]],
) -> str:
    if pending_items or not pricing_amount:
        return "manual_required"
    if best_match_target == "list_price_total":
        return "review_recommended"
    if difference_value is None:
        return "manual_required"
    if difference_value <= AUTO_PASS_DIFF and all(item["review_status"] != "manual_required" for item in line_items):
        return "auto_pass"
    if difference_value <= REVIEW_DIFF:
        return "review_recommended"
    return "manual_required"


def _build_primary_reason(
    *,
    decision: str,
    pending_items: list[dict[str, Any]],
    difference: str,
    difference_value: Decimal | None,
    best_match_target: str,
    pricing_amount: str,
) -> str:
    if pending_items:
        return f"存在{len(pending_items)}个品项未入账，不能判断整单金额是否正确。"
    if not pricing_amount:
        return "系统未形成报价，必须人工确认。"
    if best_match_target == "list_price_total":
        return "系统报价更接近折前价，建议人工确认折扣口径。"
    if decision == "auto_pass":
        return f"金额差异在可自动通过范围内（差额{difference or '0元'}）。"
    if decision == "review_recommended":
        return f"金额差异较小但仍建议复核（差额{difference or '未识别'}）。"
    if difference_value is not None:
        return f"金额差异超过自动通过范围（差额{difference or '未识别'}）。"
    return "当前证据不足，必须人工确认。"


def _build_next_actions(
    *,
    decision: str,
    pending_items: list[dict[str, Any]],
    best_match_target: str,
    review_analysis_payload: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    if pending_items:
        names = "、".join(item["product_name"] for item in pending_items[:3])
        actions.append(f"优先确认未入账品项：{names}。")
    if best_match_target == "list_price_total":
        actions.append("系统报价更接近折前价，请确认折扣口径，以及报价系统是否未应用合同折扣。")
    if decision == "auto_pass":
        actions.append("可低风险通过，建议保留本次金额核对记录。")
    legacy_actions = list((review_analysis_payload.get("review_card") or {}).get("next_actions") or [])
    for action in legacy_actions:
        text = str(action or "").strip()
        if text and text not in actions:
            actions.append(text)
    return actions


def _pick_contract_amount(*, financials: dict[str, Any], basis: str) -> str:
    if basis:
        value = str(((financials.get(basis) or {}).get("value")) or "").strip()
        if value:
            return value
    for key in ("contract_total", "discounted_total", "list_price_total"):
        value = str(((financials.get(key) or {}).get("value")) or "").strip()
        if value:
            return value
    return ""


def _parse_amount(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = (
        text.replace(",", "")
        .replace("，", "")
        .replace("人民币", "")
        .replace("元", "")
        .strip()
    )
    if not normalized:
        return None
    try:
        return Decimal(normalized).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _format_amount(value: Decimal | None) -> str:
    if value is None:
        return ""
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized == quantized.to_integral():
        return f"{int(quantized)}元"
    return f"{format(quantized.normalize(), 'f')}元"


def _to_decimal(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
