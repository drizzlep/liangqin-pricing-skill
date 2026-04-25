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
    "guardrail_length": "围栏长度",
    "guardrail_height": "围栏高度",
    "access_height": "梯子垂直高度",
    "stair_width": "梯柜踏步宽度",
    "stair_depth": "梯柜进深",
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
    aggregate_follow_up_question = _extract_aggregate_follow_up_question(pricing_compare_payload)
    complete_multi_product_amount_signal = _has_complete_multi_product_amount_signal(pricing_compare_payload)
    soften_aggregate_follow_up = _should_soften_aggregate_follow_up_question(
        aggregate_follow_up_question=aggregate_follow_up_question,
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
    )
    surfaced_aggregate_follow_up_question = "" if soften_aggregate_follow_up else aggregate_follow_up_question
    suppress_mechanical_bridge_issues = bool(aggregate_follow_up_question) or complete_multi_product_amount_signal
    issues: list[dict[str, Any]] = []
    issues.extend(_build_field_conflict_issues(contract_audit_payload))
    if not suppress_mechanical_bridge_issues:
        issues.extend(
            _build_missing_field_issues(
                pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                pricing_compare_payload=pricing_compare_payload,
            )
        )
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
            pricing_bridge_payload=pricing_bridge_payload,
            formal_quote_payload=formal_quote_payload,
            pricing_compare_payload=pricing_compare_payload,
        )
    )
    if not suppress_mechanical_bridge_issues:
        issues.extend(
            _build_ocr_issues(
                pricing_bridge_payload=pricing_bridge_payload,
                unresolved_ocr_assets=unresolved_ocr_assets,
            )
        )

    deduped_issues = _dedupe_issues(issues)
    priority = _derive_priority(deduped_issues)
    verdict = _derive_verdict(priority=priority, issues=deduped_issues, formal_quote_payload=formal_quote_payload)
    next_actions = _build_advisory_actions(
        pricing_bridge_payload=pricing_bridge_payload,
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
        aggregate_follow_up_question=aggregate_follow_up_question,
        soften_aggregate_follow_up=soften_aggregate_follow_up,
    ) + _collect_next_actions(deduped_issues)
    next_actions = _prioritize_aggregate_follow_up_question(
        next_actions,
        follow_up_question=surfaced_aggregate_follow_up_question,
    )
    top_issue_titles = [str(item.get("title") or "").strip() for item in deduped_issues[:3] if str(item.get("title") or "").strip()]
    issue_summary = _build_issue_summary(
        top_issue_titles=top_issue_titles,
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
        aggregate_follow_up_question=surfaced_aggregate_follow_up_question,
    )
    next_question = _build_next_question(
        deduped_issues,
        aggregate_follow_up_question=surfaced_aggregate_follow_up_question,
    )

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


def _build_missing_field_issues(
    pricing_bridge_payload: dict[str, Any],
    *,
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    status = str(pricing_bridge_payload.get("status") or "").strip()
    if status not in {"needs_input", "manual_confirmation_required"}:
        return []
    if _has_lightweight_amount_signal(
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
    ):
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
    is_multi_product_watch = _is_complete_multi_product_list_price_watch(pricing_compare_payload)
    return [
        _build_issue(
            issue_code="discount_mismatch",
            severity="medium" if is_multi_product_watch else "high",
            confidence=0.91,
            title="报价更接近折前价",
            contract_value=str((financials.get("discounted_total") or {}).get("value") or "").strip(),
            pricing_value=str(pricing_compare_payload.get("pricing_total") or "").strip(),
            delta_value=pricing_compare.format_amount(diff_value) if diff_value is not None else "",
            delta_percent=_format_delta_percent(diff_value, pricing_compare.parse_amount((financials.get("discounted_total") or {}).get("value"))),
            evidence_refs=[],
            suspected_causes=[
                (
                    "整单自动汇总金额更接近合同折前合计，折扣口径可能没有进入回放。"
                    if is_multi_product_watch
                    else "报价回放更接近合同折前合计，折扣口径可能没有进入回放。"
                ),
                "合同折扣字段也可能抽取错位。",
            ],
            recommended_check=(
                "整单金额已基本命中折前价，请留意合同折扣和报价系统折扣口径是否一致。"
                if is_multi_product_watch
                else "请先核对合同折扣、折后合计，以及报价系统是否按同一折扣口径计算。"
            ),
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
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
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
    if _is_complete_multi_product_list_price_watch(pricing_compare_payload):
        return []
    if diff_value <= ABS_DIFF_HIGH and (delta_ratio is None or delta_ratio <= RATIO_DIFF_HIGH) and best_target in {"contract_total", "discounted_total"}:
        return []
    severity = "critical" if diff_value > ABS_DIFF_HIGH or (delta_ratio is not None and delta_ratio > RATIO_DIFF_HIGH) else "medium"
    suspected_causes = _default_quote_conflict_causes(
        best_target=best_target,
        financials=financials,
        pricing_bridge_payload=pricing_bridge_payload,
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
    )
    recommended_check = _build_quote_conflict_recommended_check(
        pricing_bridge_payload=pricing_bridge_payload,
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
    )
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
            recommended_check=recommended_check,
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
        route_specific_causes = _build_route_specific_ocr_causes(pricing_bridge_payload)
        recommended_check = _build_route_specific_ocr_recommended_check(pricing_bridge_payload)
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
                    *route_specific_causes,
                ],
                recommended_check=recommended_check or "请先人工核对儿童床主尺寸图上的床形态、长宽、高度、围栏/梯柜参数及床下柜体配置，再决定是否继续报价对账。",
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


def _derive_verdict(*, priority: str, issues: list[dict[str, Any]], formal_quote_payload: dict[str, Any]) -> str:
    if priority in {"p0", "p1"}:
        return "manual_review_required"
    if not issues and _is_approximate_quote_completed(formal_quote_payload):
        return "pass_with_watch"
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


def _build_advisory_actions(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
    aggregate_follow_up_question: str,
    soften_aggregate_follow_up: bool,
) -> list[str]:
    actions: list[str] = []
    if soften_aggregate_follow_up:
        softened_follow_up_hint = _build_softened_child_bed_follow_up_hint(aggregate_follow_up_question)
        if softened_follow_up_hint:
            actions.append(softened_follow_up_hint)
    if _is_approximate_quote_completed(formal_quote_payload):
        assumptions = []
        for item in list(formal_quote_payload.get("assumed_defaults") or []):
            if not isinstance(item, dict):
                continue
            field_name = str(item.get("field") or "").strip()
            field_label = FIELD_LABELS.get(field_name, field_name or "默认项")
            field_value = str(item.get("value") or "").strip()
            if field_label and field_value:
                assumptions.append(f"{field_label}={field_value}")
        if assumptions:
            actions.append("本次金额核对先按轻量试算完成，默认使用：" + "，".join(assumptions[:4]) + "。")
        route_hint = _build_route_evidence_hint(
            pricing_bridge_payload=pricing_bridge_payload,
            formal_quote_payload=formal_quote_payload,
        )
        if route_hint:
            actions.append(route_hint)
        route_uncertainty_hint = _build_route_uncertainty_hint(formal_quote_payload)
        if route_uncertainty_hint:
            actions.append(route_uncertainty_hint)

    child_bed_analysis = pricing_bridge_payload.get("child_bed_analysis") or {}
    precheck_result = pricing_bridge_payload.get("precheck_result") or {}
    precheck_args = pricing_bridge_payload.get("precheck_args") or {}
    route = str(
        precheck_result.get("pricing_route")
        or child_bed_analysis.get("suggested_pricing_route")
        or ""
    ).strip()
    if route != "modular_child_bed_combo":
        stair_cabinet_variant_watch = _build_stair_cabinet_variant_watch_hint(
            pricing_bridge_payload=pricing_bridge_payload,
            pricing_compare_payload=pricing_compare_payload,
        )
        if stair_cabinet_variant_watch:
            actions.append(stair_cabinet_variant_watch)
        return actions

    focus_points: list[str] = []
    combo_signals = [
        str(item).strip()
        for item in list(child_bed_analysis.get("combo_candidate_signals") or [])
        if str(item).strip()
    ]
    if any(
        str(precheck_args.get(field_name) or "").strip()
        for field_name in (
            "front_cabinet_length",
            "front_cabinet_height",
            "front_cabinet_depth",
            "rear_cabinet_length",
            "rear_cabinet_height",
            "rear_cabinet_depth",
        )
    ):
        focus_points.append("床下柜体尺寸")
    if precheck_args.get("interconnected_rows"):
        focus_points.append("前后柜体互通")
    if combo_signals:
        focus_points.append("/".join(combo_signals[:3]))
    if not focus_points:
        focus_points.append("床下柜体配置")

    actions.append(
        "本单更像床体+床下组合柜路线，请优先复核"
        + "、".join(focus_points)
        + "是否与合同一致。"
    )
    return actions


def _should_soften_aggregate_follow_up_question(
    *,
    aggregate_follow_up_question: str,
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> bool:
    if not str(aggregate_follow_up_question or "").strip():
        return False
    if not _find_child_bed_stair_follow_up_item(pricing_compare_payload):
        return False
    pricing_total = str(
        pricing_compare_payload.get("pricing_total")
        or formal_quote_payload.get("pricing_total")
        or ""
    ).strip()
    if not pricing_total:
        return False
    return str(pricing_compare_payload.get("match_band") or "").strip() in {
        "exact_match",
        "close_match",
        "approximate_match",
        "mismatch",
    }


def _build_softened_child_bed_follow_up_hint(aggregate_follow_up_question: str) -> str:
    normalized_follow_up = str(aggregate_follow_up_question or "").strip()
    if not normalized_follow_up:
        return ""

    detail_hint = "围栏样式、梯柜参数和上下床尺寸"
    if "梯柜参数" in normalized_follow_up or "上下床尺寸" in normalized_follow_up:
        detail_hint = "围栏样式、梯柜参数和上下床尺寸"
    elif "踏步宽度" in normalized_follow_up:
        detail_hint = "梯柜踏步宽度"
    elif "进深" in normalized_follow_up:
        detail_hint = "梯柜进深"
    elif "围栏" in normalized_follow_up:
        detail_hint = "围栏参数"

    return (
        "儿童床已先按现有信息试算并用于金额核对；"
        f"如后续还要继续收缩差额，再补充{detail_hint}。"
    )


def _build_stair_cabinet_variant_watch_hint(
    *,
    pricing_bridge_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> str:
    precheck_result = pricing_bridge_payload.get("precheck_result") or {}
    child_bed_analysis = pricing_bridge_payload.get("child_bed_analysis") or {}
    aggregate_child_bed_item = _find_child_bed_stair_follow_up_item(pricing_compare_payload)
    aggregate_child_bed_follow_up = str(aggregate_child_bed_item.get("follow_up_question") or "").strip()
    route = str(
        precheck_result.get("pricing_route")
        or child_bed_analysis.get("suggested_pricing_route")
        or ""
    ).strip()
    if route != "modular_child_bed" and not aggregate_child_bed_follow_up:
        return ""

    precheck_args = pricing_bridge_payload.get("precheck_args") or {}
    access_style = str(precheck_args.get("access_style") or "").strip()
    if access_style != "梯柜":
        if not aggregate_child_bed_follow_up:
            return ""

    stair_storage_mode = str(
        aggregate_child_bed_item.get("stair_storage_mode")
        or child_bed_analysis.get("stair_storage_mode")
        or ""
    ).strip()
    stair_storage_snippets = [
        str(item).strip()
        for item in list(
            aggregate_child_bed_item.get("stair_storage_evidence_snippets")
            or child_bed_analysis.get("stair_storage_evidence_snippets")
            or []
        )
        if str(item).strip()
    ]
    if stair_storage_mode == "open_grid":
        suffix = _format_route_evidence_follow_up(stair_storage_snippets)
        return (
            "图下注释更像开放格/无抽屉梯柜，当前系统仍按标准梯柜模块试算，请人工留意这一步可能带来金额偏差。"
            + suffix
        )
    if stair_storage_mode == "mixed":
        suffix = _format_route_evidence_follow_up(stair_storage_snippets)
        return (
            "图下注释显示梯柜含开放格/抽屉混合结构，当前系统仍按标准梯柜模块试算，请人工留意这一步可能带来金额偏差。"
            + suffix
        )
    if stair_storage_mode == "standard":
        return ""

    match_band = str(pricing_compare_payload.get("match_band") or "").strip()
    diff_value = pricing_compare_payload.get("best_match_diff_value")
    if match_band != "mismatch":
        try:
            if float(diff_value or 0) < 500:
                return ""
        except (TypeError, ValueError):
            return ""

    return "若这单实际做的是开放格/无抽屉的非常规梯柜，当前系统仍按标准梯柜模块试算，请人工留意这一步可能带来金额偏差。"


def _find_child_bed_stair_follow_up(pricing_compare_payload: dict[str, Any]) -> str:
    item = _find_child_bed_stair_follow_up_item(pricing_compare_payload)
    return str(item.get("follow_up_question") or "").strip()


def _find_child_bed_stair_follow_up_item(pricing_compare_payload: dict[str, Any]) -> dict[str, Any]:
    for item in list(pricing_compare_payload.get("excluded_items") or []):
        if not isinstance(item, dict):
            continue
        product_name = str(item.get("product_name") or "").strip()
        follow_up_question = str(item.get("follow_up_question") or "").strip()
        if "儿童床" not in product_name:
            continue
        if "梯柜" in follow_up_question:
            return item
    return {}


def _build_route_evidence_hint(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
) -> str:
    candidate = _pick_effective_route_candidate(
        pricing_bridge_payload=pricing_bridge_payload,
        formal_quote_payload=formal_quote_payload,
    )
    if not candidate:
        return ""
    snippets = [
        str(item).strip()
        for item in list(candidate.get("evidence_snippets") or [])
        if str(item).strip()
    ]
    signals = [
        str(item).strip()
        for item in list(candidate.get("signals") or [])
        if str(item).strip()
    ]
    route = str(candidate.get("route") or "").strip()
    route_label = {
        "cabinet": "柜体路线",
        "modular_child_bed_combo": "床体+床下组合柜路线",
    }.get(route, route or "当前路线")
    if snippets:
        return f"本次优先按{route_label}试算，图下说明/结构备注命中：{'；'.join(snippets[:2])}。"
    if signals:
        return f"本次优先按{route_label}试算，命中路线信号：{'、'.join(signals[:3])}。"
    return ""


def _build_route_uncertainty_hint(formal_quote_payload: dict[str, Any]) -> str:
    if not formal_quote_payload.get("route_uncertainty"):
        return ""
    selected = formal_quote_payload.get("selected_route_candidate") or {}
    runner_up = formal_quote_payload.get("runner_up_route_candidate") or {}
    if not selected or not runner_up:
        return ""
    selected_desc = _describe_route_candidate(selected)
    runner_up_desc = _describe_route_candidate(runner_up)
    gap_text = str(formal_quote_payload.get("selected_vs_runner_up_diff") or "").strip()
    if gap_text:
        return (
            f"当前金额解释不唯一，系统先按{selected_desc}作为最接近候选；"
            f"但次优路线也接近：{runner_up_desc}，只差 {gap_text}，建议人工确认类目/结构。"
        )
    return f"当前金额解释不唯一，系统先按{selected_desc}作为最接近候选，但次优路线 {runner_up_desc} 也很接近。"


def _build_issue_summary(
    *,
    top_issue_titles: list[str],
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
    aggregate_follow_up_question: str,
) -> str:
    if _is_complete_multi_product_list_price_watch(pricing_compare_payload):
        return "整单金额已基本命中折前价，请留意折扣口径。"
    if top_issue_titles:
        return "；".join(top_issue_titles)
    if _has_lightweight_amount_signal(
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
    ) and formal_quote_payload.get("route_uncertainty"):
        return "当前金额与轻量试算基本一致，但项目解释仍不唯一。"
    if _has_lightweight_amount_signal(
        formal_quote_payload=formal_quote_payload,
        pricing_compare_payload=pricing_compare_payload,
    ):
        return "当前金额与轻量试算基本一致。"
    if aggregate_follow_up_question:
        return "当前还有待确认的拆单品项，补齐后可继续金额核对。"
    return "当前未发现高风险差异。"


def _is_approximate_quote_completed(formal_quote_payload: dict[str, Any]) -> bool:
    return str(formal_quote_payload.get("reason") or "").strip() == "approximate_quote_completed"


def _has_lightweight_amount_signal(
    *,
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> bool:
    if not _is_approximate_quote_completed(formal_quote_payload):
        return False
    return str(pricing_compare_payload.get("match_band") or "").strip() in {
        "exact_match",
        "close_match",
        "approximate_match",
        "mismatch",
    }


def _has_complete_multi_product_amount_signal(pricing_compare_payload: dict[str, Any]) -> bool:
    if str(pricing_compare_payload.get("aggregation_scope") or "").strip() != "multi_product_split_sum":
        return False
    if not pricing_compare_payload.get("aggregation_complete"):
        return False
    if int(pricing_compare_payload.get("excluded_item_count") or 0) > 0:
        return False
    if int(pricing_compare_payload.get("compared_item_count") or 0) <= 0:
        return False
    return bool(str(pricing_compare_payload.get("pricing_total") or "").strip())


def _is_complete_multi_product_list_price_watch(pricing_compare_payload: dict[str, Any]) -> bool:
    if not _has_complete_multi_product_amount_signal(pricing_compare_payload):
        return False
    if str(pricing_compare_payload.get("best_match_target") or "").strip() != "list_price_total":
        return False
    return str(pricing_compare_payload.get("match_band") or "").strip() in {
        "exact_match",
        "close_match",
        "approximate_match",
    }


def _build_next_question(
    issues: list[dict[str, Any]],
    *,
    aggregate_follow_up_question: str,
) -> str:
    if aggregate_follow_up_question:
        return aggregate_follow_up_question
    for item in issues:
        if item.get("issue_code") == "ocr_low_confidence":
            recommended = str(item.get("recommended_check") or "").strip()
            if recommended.startswith("请先向人工确认"):
                return recommended
    for item in issues:
        if item.get("issue_code") == "missing_required_field":
            return str(item.get("recommended_check") or "").strip()
    return ""


def _extract_aggregate_follow_up_question(pricing_compare_payload: dict[str, Any]) -> str:
    for item in list(pricing_compare_payload.get("excluded_items") or []):
        follow_up_question = str(item.get("follow_up_question") or "").strip()
        if follow_up_question:
            return follow_up_question
    return ""


def _prioritize_aggregate_follow_up_question(
    actions: list[str],
    *,
    follow_up_question: str,
) -> list[str]:
    normalized_follow_up = str(follow_up_question or "").strip()
    if not normalized_follow_up:
        return actions

    prioritized = [normalized_follow_up]
    seen = {normalized_follow_up}
    for action in actions:
        normalized_action = str(action or "").strip()
        if not normalized_action or normalized_action in seen:
            continue
        if normalized_action.startswith("请先核对这份合同的"):
            continue
        if "儿童床主尺寸图" in normalized_action:
            continue
        seen.add(normalized_action)
        prioritized.append(normalized_action)
    return prioritized


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


def _default_quote_conflict_causes(
    *,
    best_target: str,
    financials: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> list[str]:
    causes: list[str] = []
    if str(pricing_compare_payload.get("aggregation_scope") or "").strip() != "multi_product_split_sum":
        causes.extend(
            _build_route_specific_quote_conflict_causes(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
            )
        )
    dominant_item = _pick_dominant_multi_product_mismatch_item(pricing_compare_payload)
    if dominant_item is not None:
        product_name = str(dominant_item.get("product_name") or "").strip() or "某个品项"
        diff_text = str(dominant_item.get("difference") or "").strip()
        causes.append(f"当前整单剩余偏差主要集中在 {product_name}，该品项单项偏差约 {diff_text}。")
        dominant_hint = _build_dominant_item_fallback_hint(dominant_item)
        if dominant_hint:
            causes.append(dominant_hint["suspected_cause"])
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
    deduped: list[str] = []
    seen: set[str] = set()
    for cause in causes:
        normalized = str(cause or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:3]


def _build_quote_conflict_recommended_check(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    pricing_compare_payload: dict[str, Any],
) -> str:
    dominant_item = _pick_dominant_multi_product_mismatch_item(pricing_compare_payload)
    if dominant_item is not None:
        dominant_hint = _build_dominant_item_fallback_hint(dominant_item)
        if dominant_hint:
            return dominant_hint["recommended_check"]
        product_name = str(dominant_item.get("product_name") or "").strip() or "该品项"
        return f"请优先核对 {product_name} 这项的类目路线和默认模板；当前整单剩余偏差主要集中在这一项。"

    candidate = _pick_effective_route_candidate(
        pricing_bridge_payload=pricing_bridge_payload,
        formal_quote_payload=formal_quote_payload,
    )
    route = str(candidate.get("route") or "").strip()
    overrides = candidate.get("inferred_overrides") or {}

    if route == "cabinet":
        if str(overrides.get("has_door") or "").strip() == "no":
            return "请优先核对是否应按开放柜/无门路线计价，再核对柜体类目和门型默认条件是否一致。"
        category = str(overrides.get("category") or "").strip()
        if category:
            return f"请优先核对是否应按{category}路线计价，再核对门型和默认条件是否一致。"
    if route == "modular_child_bed":
        return "请优先核对这是不是梯柜/直梯/斜梯中的哪种儿童床路线，并向人工确认围栏样式、下层结构是否一致。"
    if route == "modular_child_bed_combo":
        return "请优先核对是否应按床体+床下组合柜路线计价，并确认床下柜体配置/互通关系是否已带入。"
    return "请优先核对数量、折扣、增项，以及门型/材质等默认条件是否一致。"


def _build_route_specific_quote_conflict_causes(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
) -> list[str]:
    candidate = _pick_effective_route_candidate(
        pricing_bridge_payload=pricing_bridge_payload,
        formal_quote_payload=formal_quote_payload,
    )
    route = str(candidate.get("route") or "").strip()
    if not route:
        return []

    signals = [
        str(item).strip()
        for item in list(candidate.get("signals") or [])
        if str(item).strip()
    ]
    snippets = [
        str(item).strip()
        for item in list(candidate.get("evidence_snippets") or [])
        if str(item).strip()
    ]
    overrides = candidate.get("inferred_overrides") or {}

    if route == "cabinet":
        display_signal = signals[0] if signals else ""
        if str(overrides.get("has_door") or "").strip() == "no":
            open_hint = display_signal or "开放柜"
            return [
                f"图下说明更像{open_hint}，当前报价路径或默认门路可能偏向带门路线。",
                _format_route_evidence_follow_up(snippets),
            ]
        category = str(overrides.get("category") or "").strip()
        if category:
            return [
                f"图下说明更像{category}路线，当前类目或报价路径可能选偏。",
                _format_route_evidence_follow_up(snippets),
            ]
        if str(overrides.get("has_door") or "").strip() == "yes":
            door_type = str(overrides.get("door_type") or "").strip()
            door_suffix = f"（{door_type}）" if door_type else ""
            return [
                f"图下说明更像带门柜体{door_suffix}，当前报价路径或默认门路可能不一致。",
                _format_route_evidence_follow_up(snippets),
            ]

    if route == "modular_child_bed":
        signal_text = "、".join(signals[:3])
        causes = ["图下说明更像模块化儿童床路线，当前儿童床类型或默认参数可能选偏。"]
        if signal_text:
            causes.append(f"已命中儿童床信号：{signal_text}，若床形态、梯柜或下层结构判断错，会直接放大金额差异。")
        elif snippets:
            causes.append(_format_route_evidence_follow_up(snippets))
        return causes

    if route == "modular_child_bed_combo":
        signal_text = "、".join(signals[:3])
        causes = ["图纸/图下注释更像床体+床下组合柜路线，当前报价路径或组合识别可能不一致。"]
        if signal_text:
            causes.append(f"已命中组合柜信号：{signal_text}，床下柜体配置带入不全时会放大金额差异。")
        elif snippets:
            causes.append(_format_route_evidence_follow_up(snippets))
        return causes

    return []


def _pick_effective_route_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
) -> dict[str, Any]:
    if str(formal_quote_payload.get("pricing_route") or "").strip() == "multi_product_aggregate":
        return {}
    selected_candidate = formal_quote_payload.get("selected_route_candidate") or {}
    if isinstance(selected_candidate, dict) and selected_candidate:
        return selected_candidate
    return _pick_route_evidence_candidate(pricing_bridge_payload)


def _pick_dominant_multi_product_mismatch_item(pricing_compare_payload: dict[str, Any]) -> dict[str, Any] | None:
    if str(pricing_compare_payload.get("aggregation_scope") or "").strip() != "multi_product_split_sum":
        return None

    items = [item for item in list(pricing_compare_payload.get("included_items") or []) if isinstance(item, dict)]
    if len(items) < 2:
        return None

    ranked_items: list[tuple[Decimal, dict[str, Any]]] = []
    for item in items:
        line_total = pricing_compare.parse_amount(item.get("line_total"))
        pricing_total = pricing_compare.parse_amount(item.get("pricing_total"))
        if line_total is None or pricing_total is None:
            continue
        diff = abs(pricing_total - line_total)
        ranked_items.append(
            (
                diff,
                {
                    "product_name": str(item.get("product_name") or "").strip(),
                    "product_code": str(item.get("product_code") or "").strip(),
                    "difference": pricing_compare.format_amount(diff),
                    "difference_value": float(diff),
                    "pricing_route": str(item.get("pricing_route") or "").strip(),
                    "fallback_strategy": str(item.get("fallback_strategy") or "").strip(),
                    "fallback_detail": item.get("fallback_detail") if isinstance(item.get("fallback_detail"), dict) else {},
                },
            )
        )

    if len(ranked_items) < 2:
        return None

    ranked_items.sort(key=lambda item: item[0], reverse=True)
    dominant_diff, dominant_item = ranked_items[0]
    runner_up_diff = ranked_items[1][0]
    if dominant_diff < Decimal("300"):
        return None
    if dominant_diff < runner_up_diff + Decimal("200"):
        return None
    return dominant_item


def _build_dominant_item_fallback_hint(item: dict[str, Any]) -> dict[str, str]:
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()
    if fallback_strategy != "generic_cabinet_projection_profile":
        return {}

    fallback_detail = item.get("fallback_detail") or {}
    profile_key = str(fallback_detail.get("profile_key") or "").strip()
    diff_text = str(
        fallback_detail.get("candidate_quote_diff")
        or item.get("difference")
        or ""
    ).strip()
    diff_value = fallback_detail.get("candidate_quote_diff_value")
    try:
        diff_amount = float(diff_value)
    except (TypeError, ValueError):
        diff_amount = float(item.get("difference_value") or 0)
    if diff_amount < 1000:
        return {}

    product_name = str(item.get("product_name") or "").strip() or "该品项"
    profile_label = profile_key or "柜体"
    return {
        "suspected_cause": f"当前 {product_name} 只是按通用{profile_label}投影面积试算，目录自动候选仍差 {diff_text}。",
        "recommended_check": (
            f"请优先核对 {product_name} 是否应改走更具体柜型或组合拆分；"
            f"当前仅按通用{profile_label}投影面积估算。"
        ),
    }


def _pick_route_evidence_candidate(pricing_bridge_payload: dict[str, Any]) -> dict[str, Any]:
    route_evidence = pricing_bridge_payload.get("route_evidence") or {}
    candidates = [item for item in list(route_evidence.get("candidates") or []) if isinstance(item, dict)]
    if not candidates:
        return {}
    recommended_route = str(route_evidence.get("recommended_route") or "").strip()
    if recommended_route:
        for candidate in candidates:
            if str(candidate.get("route") or "").strip() == recommended_route:
                return candidate
    return candidates[0]


def _build_route_specific_ocr_causes(pricing_bridge_payload: dict[str, Any]) -> list[str]:
    candidate = _pick_route_evidence_candidate(pricing_bridge_payload)
    route = str(candidate.get("route") or "").strip()
    signals = [str(item).strip() for item in list(candidate.get("signals") or []) if str(item).strip()]
    if route != "modular_child_bed":
        return []
    if signals:
        return [f"当前明细更像{'、'.join(signals[:3])}这条儿童床路线，但关键字段还需要人工补确认。"]
    snippets = [str(item).strip() for item in list(candidate.get("evidence_snippets") or []) if str(item).strip()]
    if snippets:
        return [_format_route_evidence_follow_up(snippets)]
    return []


def _build_route_specific_ocr_recommended_check(pricing_bridge_payload: dict[str, Any]) -> str:
    candidate = _pick_route_evidence_candidate(pricing_bridge_payload)
    route = str(candidate.get("route") or "").strip()
    if route != "modular_child_bed":
        return ""

    blocked_fields = {
        str(item).strip()
        for item in [*list(pricing_bridge_payload.get("blocked_fields") or []), *list(pricing_bridge_payload.get("strict_ocr_blocked_fields") or [])]
        if str(item).strip()
    }
    inferred_overrides = candidate.get("inferred_overrides") or {}
    bed_form = str(inferred_overrides.get("bed_form") or "").strip()
    lower_bed_type = str(inferred_overrides.get("lower_bed_type") or "").strip()

    if bed_form == "上下床" and "access_style" in blocked_fields:
        lower_suffix = f"，下层结构是否为{lower_bed_type}" if lower_bed_type else ""
        return f"请先向人工确认：这是不是梯柜上下床儿童床{lower_suffix}？若确认是，再补充围栏样式、梯柜参数和上下床尺寸后继续对账。"

    return "请先向人工确认这属于哪种儿童床路线（直梯/斜梯/梯柜，以及架式床/箱体床），再补齐围栏和尺寸参数后继续对账。"


def _format_route_evidence_follow_up(snippets: list[str]) -> str:
    if not snippets:
        return ""
    return f"图纸备注命中：{'；'.join(snippets[:1])}。"


def _describe_route_candidate(candidate: dict[str, Any]) -> str:
    route = str(candidate.get("route") or "").strip()
    overrides = candidate.get("inferred_overrides") or {}
    category = str(overrides.get("category") or "").strip()
    has_door = str(overrides.get("has_door") or "").strip()
    route_label = {
        "cabinet": "柜体路线",
        "modular_child_bed": "模块化儿童床路线",
        "modular_child_bed_combo": "床体+床下组合柜路线",
    }.get(route, route or "当前路线")

    parts = [route_label]
    if category:
        parts.append(category)
    if has_door == "yes":
        parts.append("带门")
    elif has_door == "no":
        parts.append("无门")
    return " / ".join(parts)


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
