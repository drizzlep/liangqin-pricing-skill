from __future__ import annotations

import importlib
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from liangqin_paths import resolve_pricing_scripts_dir


def execute_formal_quote(
    precheck_args: dict[str, Any],
    *,
    job_id: str,
    runtime_root: Path,
    disable_addenda: bool = True,
) -> dict[str, Any]:
    if not str(precheck_args.get("category") or "").strip():
        return {
            "status": "skipped",
            "reason": "missing_category",
            "pricing_route": "",
            "pricing_total": "",
            "pricing_total_value": None,
            "raw_result": None,
        }

    module = _load_handle_quote_message_module()
    state_root = runtime_root / "state"
    bundle_root = runtime_root / "bundles"
    context_json = json.dumps(
        {
            "message_id": f"contract-review-{job_id}",
            "sender_id": "contract-review",
            "sender": "contract-review",
        },
        ensure_ascii=False,
    )

    try:
        result = module.handle_message(
            text="请直接正式报价。",
            context_json=context_json,
            channel="manual",
            precheck_args=dict(precheck_args),
            execute_quote_when_ready=True,
            state_root=state_root,
            bundle_root=bundle_root,
            disable_addenda=disable_addenda,
            apply_context_reset=True,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "reason": "formal_quote_execution_failed",
            "pricing_route": "",
            "pricing_total": "",
            "pricing_total_value": None,
            "error": str(exc),
            "raw_result": None,
        }
    prepared_payload = ((result.get("downstream_result") or {}).get("prepared_payload") or {})
    pricing_total = str(prepared_payload.get("total") or "").strip()

    return {
        "status": "completed" if pricing_total else "failed",
        "reason": "formal_quote_completed" if pricing_total else "formal_quote_total_missing",
        "handled_by": str(result.get("handled_by") or "").strip(),
        "pricing_route": str(result.get("pricing_route") or prepared_payload.get("pricing_route") or "").strip(),
        "pricing_total": pricing_total,
        "pricing_total_value": _decimal_to_float(parse_amount(pricing_total)),
        "reply_text": str(result.get("reply_text") or "").strip(),
        "prepared_payload": prepared_payload,
        "raw_result": result,
    }


def build_pricing_comparison(
    *,
    contract_audit_payload: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
    quote_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    financials = contract_audit_payload.get("financials") or {}
    quote_payload = quote_payload or {}

    references = {
        "contract_total": _reference_entry(financials.get("contract_total")),
        "list_price_total": _reference_entry(financials.get("list_price_total")),
        "discounted_total": _reference_entry(financials.get("discounted_total")),
    }
    pricing_total_text = str(quote_payload.get("pricing_total") or "").strip()
    pricing_total_decimal = parse_amount(pricing_total_text)

    if quote_payload.get("status") != "completed" or pricing_total_decimal is None:
        return {
            "status": "skipped",
            "reason": str(quote_payload.get("reason") or "formal_quote_not_available"),
            "pricing_route": str(quote_payload.get("pricing_route") or "").strip(),
            "pricing_total": pricing_total_text,
            "reference_totals": references,
            "diffs": {},
            "best_match_target": "",
            "best_match_diff": None,
            "match_band": "unavailable",
            "precheck_status": str(pricing_bridge_payload.get("status") or "").strip(),
        }

    diffs: dict[str, dict[str, Any]] = {}
    for key, entry in references.items():
        amount = parse_amount(entry.get("value"))
        if amount is None:
            continue
        diff = pricing_total_decimal - amount
        abs_diff = abs(diff)
        diffs[key] = {
            "reference_total": entry.get("value", ""),
            "difference": format_amount(diff),
            "absolute_difference": format_amount(abs_diff),
            "absolute_difference_value": _decimal_to_float(abs_diff),
        }

    best_match_target = ""
    best_match_diff_decimal: Decimal | None = None
    if diffs:
        best_match_target, best_match_entry = min(
            diffs.items(),
            key=lambda item: item[1]["absolute_difference_value"] if item[1]["absolute_difference_value"] is not None else float("inf"),
        )
        best_match_diff_decimal = _to_decimal(best_match_entry["absolute_difference_value"])

    match_band = _classify_match_band(best_match_diff_decimal)
    if best_match_target:
        status = f"{match_band}_{best_match_target}"
    else:
        status = "missing_reference_total"

    return {
        "status": status,
        "reason": "pricing_total_compared",
        "pricing_route": str(quote_payload.get("pricing_route") or "").strip(),
        "pricing_total": pricing_total_text,
        "pricing_total_value": _decimal_to_float(pricing_total_decimal),
        "reference_totals": references,
        "diffs": diffs,
        "best_match_target": best_match_target,
        "best_match_diff": format_amount(best_match_diff_decimal) if best_match_diff_decimal is not None else "",
        "best_match_diff_value": _decimal_to_float(best_match_diff_decimal),
        "match_band": match_band,
        "precheck_status": str(pricing_bridge_payload.get("status") or "").strip(),
    }


def build_multi_product_aggregate_comparison(
    *,
    contract_audit_payload: dict[str, Any],
    product_split_payload: dict[str, Any],
) -> dict[str, Any]:
    items = product_split_payload.get("items") or []
    included_items: list[dict[str, Any]] = []
    excluded_items: list[dict[str, Any]] = []
    item_ledger: list[dict[str, Any]] = []
    aggregate_total = Decimal("0.00")

    for item in items:
        formal_quote = item.get("formal_quote") or {}
        item_compare_payload = item.get("pricing_compare") or {}
        pricing_total_text = str(
            formal_quote.get("pricing_total")
            or item_compare_payload.get("pricing_total")
            or ""
        ).strip()
        pricing_total = parse_amount(pricing_total_text)
        item_summary = {
            "product_name": str(item.get("product_name") or "").strip(),
            "product_code": str(item.get("product_code") or "").strip(),
            "split_status": str(item.get("split_status") or "").strip(),
            "line_total": str(item.get("line_total") or "").strip(),
        }
        parent_product_name = str(item.get("parent_product_name") or "").strip()
        parent_product_code = str(item.get("parent_product_code") or "").strip()
        if parent_product_name:
            item_summary["parent_product_name"] = parent_product_name
        if parent_product_code:
            item_summary["parent_product_code"] = parent_product_code
        component_index = item.get("component_index")
        if component_index not in {None, ""}:
            item_summary["component_index"] = component_index
        pricing_route = str(
            formal_quote.get("pricing_route")
            or item_compare_payload.get("pricing_route")
            or ""
        ).strip()
        if pricing_route:
            item_summary["pricing_route"] = pricing_route
        fallback_strategy = str(formal_quote.get("fallback_strategy") or "").strip()
        if fallback_strategy:
            item_summary["fallback_strategy"] = fallback_strategy
        fallback_detail = formal_quote.get("fallback_detail")
        if isinstance(fallback_detail, dict) and fallback_detail:
            item_summary["fallback_detail"] = fallback_detail
        if pricing_total is None:
            item_summary["reason"] = str(
                formal_quote.get("reason")
                or item_compare_payload.get("reason")
                or "pricing_total_missing"
            ).strip()
            follow_up_question = _build_split_follow_up_question(item)
            if follow_up_question:
                item_summary["follow_up_question"] = follow_up_question
            item_summary.update(_extract_split_stair_storage_watch(item))
            excluded_items.append(item_summary)
            item_ledger.append(
                _build_pending_item_ledger_entry(
                    item=item_summary,
                    detail_resolution=item.get("detail_resolution") or {},
                )
            )
            continue

        aggregate_total += pricing_total
        item_summary["pricing_total"] = format_amount(pricing_total)
        included_items.append(item_summary)
        item_ledger.append(
            _build_compared_item_ledger_entry(
                item=item_summary,
                pricing_total=pricing_total,
                detail_resolution=item.get("detail_resolution") or {},
                reason=str(
                    formal_quote.get("reason")
                    or item_compare_payload.get("reason")
                    or "pricing_total_compared"
                ).strip(),
            )
        )

    if not included_items:
        return {
            "status": "skipped",
            "reason": "multi_product_formal_quote_not_available",
            "pricing_route": "multi_product_aggregate",
            "pricing_total": "",
            "pricing_total_value": None,
            "reference_totals": {
                "contract_total": _reference_entry((contract_audit_payload.get("financials") or {}).get("contract_total")),
                "list_price_total": _reference_entry((contract_audit_payload.get("financials") or {}).get("list_price_total")),
                "discounted_total": _reference_entry((contract_audit_payload.get("financials") or {}).get("discounted_total")),
            },
            "diffs": {},
            "best_match_target": "",
            "best_match_diff": "",
            "best_match_diff_value": None,
            "match_band": "unavailable",
            "precheck_status": "multi_product_contract",
            "aggregation_scope": "multi_product_split_sum",
            "aggregation_complete": False,
            "compared_item_count": 0,
            "excluded_item_count": len(excluded_items),
            "included_items": included_items,
            "excluded_items": excluded_items,
            "item_ledger": item_ledger,
        }

    aggregate_quote_payload = {
        "status": "completed",
        "reason": "multi_product_aggregate_quote_completed",
        "pricing_route": "multi_product_aggregate",
        "pricing_total": format_amount(aggregate_total),
        "pricing_total_value": _decimal_to_float(aggregate_total),
    }
    result = build_pricing_comparison(
        contract_audit_payload=contract_audit_payload,
        pricing_bridge_payload={"status": "multi_product_contract"},
        quote_payload=aggregate_quote_payload,
    )
    result.update(
        {
            "reason": "multi_product_aggregate_pricing_total_compared",
            "aggregation_scope": "multi_product_split_sum",
            "aggregation_complete": not excluded_items,
            "compared_item_count": len(included_items),
            "excluded_item_count": len(excluded_items),
            "included_items": included_items,
            "excluded_items": excluded_items,
            "item_ledger": item_ledger,
        }
    )
    return result


def _build_compared_item_ledger_entry(
    *,
    item: dict[str, Any],
    pricing_total: Decimal,
    detail_resolution: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    line_total = parse_amount(item.get("line_total"))
    difference = abs(pricing_total - line_total) if line_total is not None else None
    entry = {
        "product_name": str(item.get("product_name") or "").strip(),
        "product_code": str(item.get("product_code") or "").strip(),
        "split_status": str(item.get("split_status") or "").strip(),
        "ledger_status": "compared",
        "contract_amount": str(item.get("line_total") or "").strip(),
        "pricing_amount": str(item.get("pricing_total") or "").strip(),
        "difference": format_amount(difference) if difference is not None else "",
        "difference_value": _decimal_to_float(difference),
        "pricing_route": str(item.get("pricing_route") or "").strip(),
        "reason": str(reason or "").strip(),
    }
    if str(item.get("parent_product_name") or "").strip():
        entry["parent_product_name"] = str(item.get("parent_product_name") or "").strip()
    if str(item.get("parent_product_code") or "").strip():
        entry["parent_product_code"] = str(item.get("parent_product_code") or "").strip()
    if item.get("component_index") not in {None, ""}:
        entry["component_index"] = item.get("component_index")
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()
    if fallback_strategy:
        entry["fallback_strategy"] = fallback_strategy
        entry["fallback_label"] = _describe_item_fallback(item)
    fallback_detail = item.get("fallback_detail")
    if isinstance(fallback_detail, dict) and fallback_detail:
        entry["fallback_detail"] = fallback_detail
    entry.update(_summarize_detail_resolution(detail_resolution))
    return entry


def _build_pending_item_ledger_entry(
    *,
    item: dict[str, Any],
    detail_resolution: dict[str, Any],
) -> dict[str, Any]:
    entry = {
        "product_name": str(item.get("product_name") or "").strip(),
        "product_code": str(item.get("product_code") or "").strip(),
        "split_status": str(item.get("split_status") or "").strip(),
        "ledger_status": "pending",
        "contract_amount": str(item.get("line_total") or "").strip(),
        "pricing_amount": "",
        "difference": "",
        "difference_value": None,
        "pricing_route": str(item.get("pricing_route") or "").strip(),
        "reason": str(item.get("reason") or "pricing_total_missing").strip(),
    }
    if str(item.get("parent_product_name") or "").strip():
        entry["parent_product_name"] = str(item.get("parent_product_name") or "").strip()
    if str(item.get("parent_product_code") or "").strip():
        entry["parent_product_code"] = str(item.get("parent_product_code") or "").strip()
    if item.get("component_index") not in {None, ""}:
        entry["component_index"] = item.get("component_index")
    follow_up_question = str(item.get("follow_up_question") or "").strip()
    if follow_up_question:
        entry["follow_up_question"] = follow_up_question
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()
    if fallback_strategy:
        entry["fallback_strategy"] = fallback_strategy
        entry["fallback_label"] = _describe_item_fallback(item)
    fallback_detail = item.get("fallback_detail")
    if isinstance(fallback_detail, dict) and fallback_detail:
        entry["fallback_detail"] = fallback_detail
    stair_storage_mode = str(item.get("stair_storage_mode") or "").strip()
    if stair_storage_mode:
        entry["stair_storage_mode"] = stair_storage_mode
    stair_storage_evidence_snippets = [
        str(snippet).strip()
        for snippet in list(item.get("stair_storage_evidence_snippets") or [])
        if str(snippet).strip()
    ]
    if stair_storage_evidence_snippets:
        entry["stair_storage_evidence_snippets"] = stair_storage_evidence_snippets
    entry.update(_summarize_detail_resolution(detail_resolution))
    return entry


def _summarize_detail_resolution(detail_resolution: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(detail_resolution, dict) or not detail_resolution:
        return {}
    payload: dict[str, Any] = {}
    detail_page_no = detail_resolution.get("detail_page_no")
    if detail_page_no not in {None, ""}:
        payload["detail_page_no"] = detail_page_no
    for field_name in ("anchor_method", "anchor_confidence", "stop_reason", "evidence_scope"):
        value = str(detail_resolution.get(field_name) or "").strip()
        if value:
            payload[field_name] = value
    linked_range = detail_resolution.get("linked_contract_page_range") or {}
    if isinstance(linked_range, dict) and any(
        linked_range.get(key) not in {None, ""} for key in ("start", "end")
    ):
        payload["linked_contract_page_range"] = {
            "start": linked_range.get("start"),
            "end": linked_range.get("end"),
        }
    return payload


def _describe_item_fallback(item: dict[str, Any]) -> str:
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()
    fallback_detail = item.get("fallback_detail") or {}
    profile_key = str(fallback_detail.get("profile_key") or "").strip()
    if fallback_strategy == "generic_cabinet_projection_profile":
        profile_label = profile_key or "柜体"
        return f"通用{profile_label}投影面积估算"
    if fallback_strategy == "generic_cabinet_unit_candidate":
        return "目录柜类候选估算"
    if fallback_strategy == "dining_cabinet_unit_price_combo":
        return "餐边柜组合估算"
    if fallback_strategy == "generic_tatami_projection_profile":
        return "榻榻米投影面积估算"
    if fallback_strategy == "tatami_wardrobe_combo_tatami_component":
        return "榻榻米+衣柜组合拆分：榻榻米组件"
    if fallback_strategy == "modular_child_bed_dimension_probe":
        return "儿童床轻量试算"
    if fallback_strategy == "explicit_catalog_code":
        return "目录编码回放"
    if fallback_strategy == "standard_bed_mattress_candidate":
        return "床垫尺寸回放"
    return ""


def _build_split_follow_up_question(item: dict[str, Any]) -> str:
    pricing_precheck = item.get("pricing_precheck") or {}
    precheck_result = pricing_precheck.get("precheck_result") or {}
    next_question = str(precheck_result.get("next_question") or "").strip()
    if next_question:
        return next_question

    detail_resolution = item.get("detail_resolution") or {}
    detail_status = str(detail_resolution.get("status") or "").strip()
    stop_reason = str(detail_resolution.get("stop_reason") or "").strip()
    if detail_status in {"missing_detail_in_source_text", "detail_not_resolved", "detail_anchor_missing"} or stop_reason == "detail_anchor_missing":
        product_name = str(item.get("product_name") or "当前品项").strip() or "当前品项"
        return f"请先人工确认 {product_name} 的详情首页和连续图纸页是否切对，再继续金额核对。"

    route_evidence = pricing_precheck.get("route_evidence") or ((item.get("normalized_fields") or {}).get("route_evidence") or {})
    candidate = _pick_split_route_candidate(route_evidence)
    route = str(candidate.get("route") or "").strip()
    if route != "modular_child_bed":
        return ""

    blocked_fields = {
        str(field_name).strip()
        for field_name in [*list(pricing_precheck.get("blocked_fields") or []), *list(pricing_precheck.get("strict_ocr_blocked_fields") or [])]
        if str(field_name).strip()
    }
    inferred_overrides = candidate.get("inferred_overrides") or {}
    bed_form = str(inferred_overrides.get("bed_form") or "").strip()
    lower_bed_type = str(inferred_overrides.get("lower_bed_type") or "").strip()
    if bed_form == "上下床" and "access_style" in blocked_fields:
        lower_suffix = f"，下层结构是否为{lower_bed_type}" if lower_bed_type else ""
        return f"请人工确认：这是不是梯柜上下床儿童床{lower_suffix}？若是，再补充围栏样式、梯柜参数和上下床尺寸。"
    return "请人工确认这属于哪种儿童床路线（直梯/斜梯/梯柜，以及架式床/箱体床），再继续金额核对。"


def _extract_split_stair_storage_watch(item: dict[str, Any]) -> dict[str, Any]:
    pricing_precheck = item.get("pricing_precheck") or {}
    normalized_fields = item.get("normalized_fields") or {}
    child_bed_analysis = (
        pricing_precheck.get("child_bed_analysis")
        or normalized_fields.get("child_bed_analysis")
        or {}
    )
    route_evidence = pricing_precheck.get("route_evidence") or (normalized_fields.get("route_evidence") or {})
    candidate = _pick_split_route_candidate(route_evidence)
    inferred_overrides = candidate.get("inferred_overrides") or {}

    mode = str(
        child_bed_analysis.get("stair_storage_mode")
        or inferred_overrides.get("stair_storage_mode")
        or ""
    ).strip()
    if not mode:
        return {}

    signals = [
        str(item).strip()
        for item in list(child_bed_analysis.get("stair_storage_signals") or [])
        if str(item).strip()
    ]
    snippets = [
        str(item).strip()
        for item in list(child_bed_analysis.get("stair_storage_evidence_snippets") or [])
        if str(item).strip()
    ]
    if not snippets:
        snippets = [
            str(item).strip()
            for item in list(candidate.get("evidence_snippets") or [])
            if str(item).strip()
        ]

    payload = {"stair_storage_mode": mode}
    if signals:
        payload["stair_storage_signals"] = signals[:3]
    if snippets:
        payload["stair_storage_evidence_snippets"] = snippets[:2]
    return payload


def _pick_split_route_candidate(route_evidence: dict[str, Any]) -> dict[str, Any]:
    candidates = [item for item in list(route_evidence.get("candidates") or []) if isinstance(item, dict)]
    if not candidates:
        return {}
    recommended_route = str(route_evidence.get("recommended_route") or "").strip()
    if recommended_route:
        for candidate in candidates:
            if str(candidate.get("route") or "").strip() == recommended_route:
                return candidate
    return candidates[0]


def parse_amount(value: Any) -> Decimal | None:
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


def format_amount(value: Decimal | None) -> str:
    if value is None:
        return ""
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized == quantized.to_integral():
        return f"{int(quantized)}元"
    normalized = format(quantized.normalize(), "f")
    return f"{normalized}元"


def _reference_entry(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    value = str(payload.get("value") or "").strip()
    return {
        "value": value,
        "amount_value": _decimal_to_float(parse_amount(value)),
        "evidence_text": str(payload.get("evidence_text") or "").strip(),
    }


def _classify_match_band(diff: Decimal | None) -> str:
    if diff is None:
        return "unavailable"
    if diff <= Decimal("1.00"):
        return "exact_match"
    if diff <= Decimal("100.00"):
        return "close_match"
    if diff <= Decimal("500.00"):
        return "approximate_match"
    return "mismatch"


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _load_handle_quote_message_module():
    scripts_dir = resolve_pricing_scripts_dir(Path(__file__))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("handle_quote_message")
