from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

import pricing_compare


ABS_DIFF_HIGH = Decimal("300.00")
RATIO_DIFF_HIGH = Decimal("0.03")
AMOUNT_MATCH_TOLERANCE = Decimal("20.00")
PERCENT_STEP = Decimal("100.00")
PRIORITY_ORDER = {"normal": 0, "p2": 1, "p1": 2, "p0": 3}
SEVERITY_TO_PRIORITY = {
    "critical": "p0",
    "high": "p1",
    "medium": "p2",
    "low": "normal",
}

FIELD_LABELS = {
    "depth": "进深",
    "length": "长度",
    "height": "高度",
    "width": "宽度",
    "material": "材质",
    "category": "类目",
    "door_type": "门型",
}


def build_review_analysis(
    *,
    contract_audit_payload: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
    single_product_line_item: dict[str, Any] | None = None,
    unresolved_ocr_assets: int = 0,
) -> dict[str, Any]:
    financials = contract_audit_payload.get("financials") or {}
    issues: list[dict[str, Any]] = []
    issues.extend(_build_field_conflict_issues(contract_audit_payload))
    issues.extend(_build_missing_field_issues(pricing_bridge_payload))
    issues.extend(_build_arithmetic_issues(financials))
    issues.extend(
        _build_quantity_mismatch_issues(
            single_product_line_item=single_product_line_item,
            formal_quote_payload=formal_quote_payload,
            pricing_compare_payload=pricing_compare_payload,
        )
    )
    issues.extend(
        _build_discount_mismatch_issues(
            financials=financials,
            pricing_compare_payload=pricing_compare_payload,
        )
    )
    issues.extend(
        _build_add_on_mismatch_issues(
            financials=financials,
            pricing_compare_payload=pricing_compare_payload,
        )
    )
    issues.extend(
        _build_quote_conflict_issues(
            financials=financials,
            pricing_compare_payload=pricing_compare_payload,
        )
    )
    issues.extend(
        _build_ocr_issues(
            pricing_bridge_payload=pricing_bridge_payload,
            unresolved_ocr_assets=unresolved_ocr_assets,
        )
    )

    deduped_issues = _dedupe_issues(issues)
    priority = _derive_priority(deduped_issues)
    verdict = _derive_verdict(priority=priority, issues=deduped_issues)
    next_actions = _collect_next_actions(deduped_issues)
    top_issue_titles = [str(item.get("title") or "").strip() for item in deduped_issues[:3] if str(item.get("title") or "").strip()]
    issue_summary = "；".join(top_issue_titles) if top_issue_titles else "当前未发现高风险差异。"
    next_question = _build_next_question(deduped_issues)

    review_card = {
        "verdict": verdict,
        "priority": priority,
        "contract_total": str((financials.get("contract_total") or {}).get("value") or "").strip(),
        "pricing_total": str(
            pricing_compare_payload.get("pricing_total")
            or formal_quote_payload.get("pricing_total")
            or ""
        ).strip(),
        "best_match_target": str(pricing_compare_payload.get("best_match_target") or "").strip(),
        "issue_summary": issue_summary,
        "next_actions": next_actions[:3],
    }

    return {
        "issues": deduped_issues,
        "issue_count": len(deduped_issues),
        "issue_codes": [str(item.get("issue_code") or "").strip() for item in deduped_issues if str(item.get("issue_code") or "").strip()],
        "root_cause_breakdown": _build_root_cause_breakdown(deduped_issues),
        "review_card": review_card,
        "next_question": next_question,
    }


def _build_field_conflict_issues(contract_audit_payload: dict[str, Any]) -> list[dict[str, Any]]:
    suggestions = {
        str(item.get("field_name") or "").strip(): item
        for item in contract_audit_payload.get("conflict_resolution_suggestions") or []
        if str(item.get("field_name") or "").strip()
    }
    issues: list[dict[str, Any]] = []
    for item in contract_audit_payload.get("field_conflicts") or []:
        field_name = str(item.get("field_name") or "").strip()
        if not field_name:
            continue
        detected_values = list(item.get("detected_values") or [])
        suggestion = suggestions.get(field_name) or {}
        recommendation = str(suggestion.get("rationale") or "").strip()
        if not recommendation:
            recommendation = f"请先核对 `{field_name}` 的最终取值，再决定是否继续正式报价。"
        issues.append(
            _build_issue(
                issue_code="field_conflict",
                severity=_normalize_severity(str(item.get("severity") or "medium").strip()),
                confidence=0.95,
                title=f"{field_name} 存在冲突",
                contract_value=" / ".join(detected_values),
                pricing_value="",
                delta_value="",
                delta_percent="",
                evidence_refs=list(item.get("evidence_refs") or []),
                suspected_causes=[
                    "合同正文、OCR 图纸或附件表格里出现了多个不一致取值。",
                    f"当前字段：{field_name}。",
                ],
                recommended_check=recommendation,
            )
        )
    return issues


def _build_missing_field_issues(pricing_bridge_payload: dict[str, Any]) -> list[dict[str, Any]]:
    status = str(pricing_bridge_payload.get("status") or "").strip()
    if status not in {"needs_input", "manual_confirmation_required"}:
        return []

    blocked_fields = list(pricing_bridge_payload.get("blocked_fields") or [])
    next_required_field = str((pricing_bridge_payload.get("precheck_result") or {}).get("next_required_field") or "").strip()
    if not next_required_field and blocked_fields:
        next_required_field = blocked_fields[0]

    if not next_required_field:
        return []

    field_label = FIELD_LABELS.get(next_required_field, next_required_field)
    severity = "high" if status == "needs_input" else "medium"
    return [
        _build_issue(
            issue_code="missing_required_field",
            severity=severity,
            confidence=0.92,
            title=f"正式报价还缺 {field_label}",
            contract_value=field_label,
            pricing_value="",
            delta_value="",
            delta_percent="",
            evidence_refs=[],
            suspected_causes=[
                "合同关键字段未抽到，或抽到了但置信度不足。",
                "当前正式报价还不能稳定继续。",
            ],
            recommended_check=f"请先核对这份合同的{field_label}（{next_required_field}）。",
        )
    ]


def _build_arithmetic_issues(financials: dict[str, Any]) -> list[dict[str, Any]]:
    list_total = pricing_compare.parse_amount((financials.get("list_price_total") or {}).get("value"))
    discounted_total = pricing_compare.parse_amount((financials.get("discounted_total") or {}).get("value"))
    contract_total = pricing_compare.parse_amount((financials.get("contract_total") or {}).get("value"))
    discount_text = str((financials.get("discount_rate") or {}).get("value") or "").strip()
    add_on_items = list(financials.get("add_on_items") or [])
    add_on_total = sum((pricing_compare.parse_amount(item.get("amount")) or Decimal("0")) for item in add_on_items)
    issues: list[dict[str, Any]] = []

    if list_total is not None and discounted_total is not None:
        expected_discounted = _calculate_discounted_total(list_total, discount_text)
        if expected_discounted is not None and abs(expected_discounted - discounted_total) > Decimal("1.00"):
            issues.append(
                _build_issue(
                    issue_code="calculation_error",
                    severity="critical",
                    confidence=0.97,
                    title="合同折扣计算不自洽",
                    contract_value=pricing_compare.format_amount(discounted_total),
                    pricing_value=pricing_compare.format_amount(expected_discounted),
                    delta_value=pricing_compare.format_amount(abs(discounted_total - expected_discounted)),
                    delta_percent=_format_delta_percent(abs(discounted_total - expected_discounted), discounted_total),
                    evidence_refs=[],
                    suspected_causes=["折前合计、折扣和折后合计之间存在算术不一致。"],
                    recommended_check="请先核对折前合计、折扣和折后合计三者是否一致，再继续审单。",
                )
            )

    if discounted_total is not None and contract_total is not None and add_on_total:
        expected_contract_total = discounted_total + add_on_total
        if abs(expected_contract_total - contract_total) > Decimal("1.00"):
            issues.append(
                _build_issue(
                    issue_code="calculation_error",
                    severity="high",
                    confidence=0.9,
                    title="合同总价与折后价/增项合计不一致",
                    contract_value=pricing_compare.format_amount(contract_total),
                    pricing_value=pricing_compare.format_amount(expected_contract_total),
                    delta_value=pricing_compare.format_amount(abs(contract_total - expected_contract_total)),
                    delta_percent=_format_delta_percent(abs(contract_total - expected_contract_total), contract_total),
                    evidence_refs=[],
                    suspected_causes=["合同总价可能漏算或重复计算了增项。"],
                    recommended_check="请核对折后合计、增项金额和合同总价三者的加总关系。",
                )
            )
    return issues


def _build_quantity_mismatch_issues(
    *,
    single_product_line_item: dict[str, Any] | None,
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    if not single_product_line_item:
        return []
    qty_text = str(single_product_line_item.get("quantity") or "").strip()
    try:
        contract_qty = int(qty_text)
    except ValueError:
        return []
    quote_qty = int(
        formal_quote_payload.get("quantity_multiplier")
        or (formal_quote_payload.get("prepared_payload") or {}).get("quantity_multiplier")
        or 1
    )
    if contract_qty <= quote_qty:
        return []

    diff_value = pricing_compare.parse_amount(pricing_compare_payload.get("best_match_diff"))
    return [
        _build_issue(
            issue_code="quantity_mismatch",
            severity="high",
            confidence=0.88,
            title="合同数量和报价数量不一致",
            contract_value=str(contract_qty),
            pricing_value=str(quote_qty),
            delta_value=pricing_compare.format_amount(diff_value) if diff_value is not None else "",
            delta_percent="",
            evidence_refs=[],
            suspected_causes=["合同数量大于当前报价倍数，报价很可能少算了件数。"],
            recommended_check="请先核对数量字段，以及报价回放是否按正确数量倍增。",
        )
    ]


def _build_discount_mismatch_issues(
    *,
    financials: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    best_target = str(pricing_compare_payload.get("best_match_target") or "").strip()
    if best_target != "list_price_total":
        return []
    if not str((financials.get("discount_rate") or {}).get("value") or "").strip():
        return []
    diff_value = pricing_compare.parse_amount(pricing_compare_payload.get("best_match_diff"))
    return [
        _build_issue(
            issue_code="discount_mismatch",
            severity="high",
            confidence=0.91,
            title="报价更接近折前价",
            contract_value=str((financials.get("discounted_total") or {}).get("value") or "").strip(),
            pricing_value=str(pricing_compare_payload.get("pricing_total") or "").strip(),
            delta_value=pricing_compare.format_amount(diff_value) if diff_value is not None else "",
            delta_percent=_format_delta_percent(diff_value, pricing_compare.parse_amount((financials.get("discounted_total") or {}).get("value"))),
            evidence_refs=[],
            suspected_causes=[
                "报价回放更接近合同折前合计，折扣口径可能没有进入回放。",
                "合同折扣字段也可能抽取错位。",
            ],
            recommended_check="请先核对合同折扣、折后合计，以及报价系统是否按同一折扣口径计算。",
        )
    ]


def _build_add_on_mismatch_issues(
    *,
    financials: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    add_on_items = list(financials.get("add_on_items") or [])
    if not add_on_items:
        return []
    diff_value = pricing_compare.parse_amount(pricing_compare_payload.get("best_match_diff"))
    if diff_value is None:
        return []
    add_on_total = sum((pricing_compare.parse_amount(item.get("amount")) or Decimal("0")) for item in add_on_items)
    if not add_on_total or abs(add_on_total - diff_value) > AMOUNT_MATCH_TOLERANCE:
        return []
    return [
        _build_issue(
            issue_code="add_on_mismatch",
            severity="high",
            confidence=0.89,
            title="差额与合同增项高度接近",
            contract_value=pricing_compare.format_amount(add_on_total),
            pricing_value=str(pricing_compare_payload.get("pricing_total") or "").strip(),
            delta_value=pricing_compare.format_amount(diff_value),
            delta_percent="",
            evidence_refs=[ref for item in add_on_items for ref in list(item.get("evidence_refs") or [])],
            suspected_causes=["合同里的增项可能没有进入当前报价回放。"],
            recommended_check="请先核对合同增项、另计项或五金/安装加价是否已进入报价系统。",
        )
    ]


def _build_quote_conflict_issues(
    *,
    financials: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    pricing_total = pricing_compare.parse_amount(pricing_compare_payload.get("pricing_total"))
    if pricing_total is None:
        return []
    diff_value = pricing_compare.parse_amount(pricing_compare_payload.get("best_match_diff"))
    if diff_value is None:
        return []
    contract_total = pricing_compare.parse_amount((financials.get("contract_total") or {}).get("value"))
    delta_ratio = _calculate_ratio(diff_value, contract_total or pricing_total)
    best_target = str(pricing_compare_payload.get("best_match_target") or "").strip()
    if diff_value <= ABS_DIFF_HIGH and (delta_ratio is None or delta_ratio <= RATIO_DIFF_HIGH) and best_target == "contract_total":
        return []
    severity = "critical" if diff_value > ABS_DIFF_HIGH or (delta_ratio is not None and delta_ratio > RATIO_DIFF_HIGH) else "medium"
    suspected_causes = _default_quote_conflict_causes(best_target=best_target, financials=financials)
    return [
        _build_issue(
            issue_code="quote_conflict",
            severity=severity,
            confidence=0.87,
            title="合同金额与报价回放存在明显偏差",
            contract_value=str((financials.get("contract_total") or {}).get("value") or "").strip(),
            pricing_value=str(pricing_compare_payload.get("pricing_total") or "").strip(),
            delta_value=pricing_compare.format_amount(diff_value),
            delta_percent=_format_ratio(delta_ratio),
            evidence_refs=[],
            suspected_causes=suspected_causes,
            recommended_check="请优先核对数量、折扣、增项，以及门型/材质等默认条件是否一致。",
        )
    ]


def _build_ocr_issues(
    *,
    pricing_bridge_payload: dict[str, Any],
    unresolved_ocr_assets: int,
) -> list[dict[str, Any]]:
    blocked_fields = list(pricing_bridge_payload.get("blocked_fields") or [])
    withheld_fields = list(pricing_bridge_payload.get("withheld_source_fields") or [])
    strict_ocr_blocked_fields = list(pricing_bridge_payload.get("strict_ocr_blocked_fields") or [])
    child_bed_analysis = pricing_bridge_payload.get("child_bed_analysis") or {}
    if unresolved_ocr_assets <= 0 and not blocked_fields and not withheld_fields:
        return []

    if strict_ocr_blocked_fields:
        strict_labels = [FIELD_LABELS.get(field_name, field_name) for field_name in strict_ocr_blocked_fields]
        primary_drawing_file_name = str(child_bed_analysis.get("primary_drawing_file_name") or "").strip()
        drawing_cause = (
            f"系统已识别主尺寸图：{primary_drawing_file_name}，但主图关键字段仍不够稳定。"
            if primary_drawing_file_name
            else "当前还没稳定锁定儿童床主尺寸图，其他视角图不适合直接驱动报价。"
        )
        return [
            _build_issue(
                issue_code="ocr_low_confidence",
                severity="high",
                confidence=0.9,
                title="儿童床主尺寸图证据还不够稳，暂不建议直接对账",
                contract_value="、".join(strict_labels),
                pricing_value="",
                delta_value="",
                delta_percent="",
                evidence_refs=[],
                suspected_causes=[
                    "儿童床/床下组合柜这类合同对床形态、围栏、梯柜和柜体尺寸特别敏感。",
                    drawing_cause,
                ],
                recommended_check="请先人工核对儿童床主尺寸图上的床形态、长宽、高度、围栏/梯柜参数及床下柜体配置，再决定是否继续报价对账。",
            )
        ]
    return [
        _build_issue(
            issue_code="ocr_low_confidence",
            severity="medium",
            confidence=0.82,
            title="存在 OCR 或低置信字段风险",
            contract_value="、".join(withheld_fields or blocked_fields),
            pricing_value="",
            delta_value="",
            delta_percent="",
            evidence_refs=[],
            suspected_causes=[
                "图纸/扫描件尚未完全转成高置信证据。",
                "关键字段可能需要人工二次确认。",
            ],
            recommended_check="请先核对 OCR 来源字段或图纸证据，再决定是否放行。",
        )
    ]


def _build_issue(
    *,
    issue_code: str,
    severity: str,
    confidence: float,
    title: str,
    contract_value: str,
    pricing_value: str,
    delta_value: str,
    delta_percent: str,
    evidence_refs: list[Any],
    suspected_causes: list[str],
    recommended_check: str,
) -> dict[str, Any]:
    return {
        "issue_code": issue_code,
        "severity": _normalize_severity(severity),
        "confidence": round(float(confidence), 2),
        "title": title,
        "contract_value": contract_value,
        "pricing_value": pricing_value,
        "delta_value": delta_value,
        "delta_percent": delta_percent,
        "evidence_refs": evidence_refs,
        "suspected_causes": suspected_causes,
        "recommended_check": recommended_check,
    }


def _calculate_discounted_total(list_total: Decimal, discount_text: str) -> Decimal | None:
    rate = _parse_discount_rate(discount_text)
    if rate is None:
        return None
    return (list_total * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_discount_rate(value: str) -> Decimal | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*折", str(value or ""))
    if not match:
        return None
    raw = Decimal(match.group(1))
    divisor = Decimal("100") if raw > Decimal("10") else Decimal("10")
    return (raw / divisor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _normalize_severity(value: str) -> str:
    if value in {"critical", "high", "medium", "low"}:
        return value
    return "medium"


def _derive_priority(issues: list[dict[str, Any]]) -> str:
    priority = "normal"
    for item in issues:
        current = SEVERITY_TO_PRIORITY.get(str(item.get("severity") or "").strip(), "normal")
        if PRIORITY_ORDER[current] > PRIORITY_ORDER[priority]:
            priority = current
    return priority


def _derive_verdict(*, priority: str, issues: list[dict[str, Any]]) -> str:
    if priority in {"p0", "p1"}:
        return "manual_review_required"
    if issues:
        return "pass_with_watch"
    return "recommended_release"


def _collect_next_actions(issues: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    actions: list[str] = []
    for item in issues:
        action = str(item.get("recommended_check") or "").strip()
        if not action or action in seen:
            continue
        seen.add(action)
        actions.append(action)
    return actions


def _build_next_question(issues: list[dict[str, Any]]) -> str:
    for item in issues:
        if item.get("issue_code") == "missing_required_field":
            return str(item.get("recommended_check") or "").strip()
    return ""


def _build_root_cause_breakdown(issues: list[dict[str, Any]]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for item in issues:
        code = str(item.get("issue_code") or "").strip()
        if not code:
            continue
        breakdown[code] = breakdown.get(code, 0) + 1
    return breakdown


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in issues:
        key = (
            str(item.get("issue_code") or "").strip(),
            str(item.get("contract_value") or "").strip(),
            str(item.get("pricing_value") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    deduped.sort(key=lambda item: (-PRIORITY_ORDER[SEVERITY_TO_PRIORITY.get(str(item.get("severity") or ""), "normal")], str(item.get("issue_code") or "")))
    return deduped


def _default_quote_conflict_causes(*, best_target: str, financials: dict[str, Any]) -> list[str]:
    causes: list[str] = []
    if best_target == "list_price_total":
        causes.append("报价更接近折前价，折扣口径可能不一致。")
    if list(financials.get("add_on_items") or []):
        causes.append("合同增项或另计项可能没有进入报价回放。")
    causes.extend(
        [
            "数量或默认条件可能与合同不一致。",
            "模板字段位置漂移，导致类目/尺寸/材质映射偏了。",
        ]
    )
    return causes[:3]


def _calculate_ratio(diff: Decimal | None, total: Decimal | None) -> Decimal | None:
    if diff is None or total in {None, Decimal("0")}:
        return None
    return (diff / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _format_delta_percent(diff: Decimal | None, base: Decimal | None) -> str:
    ratio = _calculate_ratio(diff, base)
    return _format_ratio(ratio)


def _format_ratio(value: Decimal | None) -> str:
    if value is None:
        return ""
    percent = (value * PERCENT_STEP).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{percent}%"
