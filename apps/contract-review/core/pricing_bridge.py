from __future__ import annotations

import importlib
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from liangqin_paths import resolve_pricing_scripts_dir
import pricing_compare


DEFAULT_CONFIDENCE_THRESHOLD = 0.85
CHILD_BED_OCR_CONFIDENCE_CAP = 0.84
CHILD_BED_KEYWORDS = ("儿童床", "上下床", "子母床", "高架床", "半高床", "错层床")
LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS = {
    "guardrail_height": "320mm",
    "access_height": "1200mm",
    "stair_width": "500mm",
    "stair_depth": "500mm",
}
LIGHTWEIGHT_ROUTE_UNCERTAINTY_GAP = Decimal("200.00")

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "category": ("category", "product_category", "sheet", "product_type"),
    "series": ("series", "product_name", "product_series", "style", "model_name"),
    "material": ("material", "wood_material", "main_material"),
    "length": ("length", "cabinet_length", "table_length", "bed_length"),
    "depth": ("depth", "cabinet_depth", "table_depth"),
    "height": ("height", "cabinet_height", "table_height"),
    "width": ("width", "bed_width", "mattress_width", "table_width"),
    "quote_kind": ("quote_kind", "pricing_kind", "quote_mode"),
    "has_door": ("has_door", "door_presence"),
    "door_type": ("door_type", "door_style", "door_model"),
    "shape": ("shape", "cabinet_shape", "special_shape"),
    "bed_form": ("bed_form", "bed_type", "child_bed_form"),
    "access_style": ("access_style", "ladder_style", "access_mode"),
    "lower_bed_type": ("lower_bed_type", "lower_structure"),
    "guardrail_style": ("guardrail_style", "rail_style"),
    "guardrail_length": ("guardrail_length",),
    "guardrail_height": ("guardrail_height",),
    "access_height": ("access_height", "ladder_height"),
    "stair_width": ("stair_width",),
    "stair_depth": ("stair_depth",),
    "underbed_cabinet_mode": ("underbed_cabinet_mode", "underbed_mode"),
    "front_cabinet_length": ("front_cabinet_length",),
    "front_cabinet_height": ("front_cabinet_height",),
    "front_cabinet_depth": ("front_cabinet_depth",),
    "front_cabinet_mode": ("front_cabinet_mode",),
    "rear_cabinet_length": ("rear_cabinet_length",),
    "rear_cabinet_height": ("rear_cabinet_height",),
    "rear_cabinet_depth": ("rear_cabinet_depth",),
    "rear_cabinet_mode": ("rear_cabinet_mode",),
    "interconnected_rows": ("interconnected_rows",),
}

SENSITIVE_PRICING_FIELDS = {
    "category",
    "series",
    "material",
    "length",
    "depth",
    "height",
    "width",
    "quote_kind",
    "has_door",
    "door_type",
    "shape",
    "bed_form",
    "access_style",
    "lower_bed_type",
    "guardrail_style",
    "guardrail_length",
    "guardrail_height",
    "access_height",
    "stair_width",
    "stair_depth",
    "underbed_cabinet_mode",
    "front_cabinet_length",
    "front_cabinet_height",
    "front_cabinet_depth",
    "front_cabinet_mode",
    "rear_cabinet_length",
    "rear_cabinet_height",
    "rear_cabinet_depth",
    "rear_cabinet_mode",
    "interconnected_rows",
}

CHILD_BED_STRICT_OCR_FIELDS = {
    "quote_kind",
    "material",
    "length",
    "width",
    "bed_form",
    "access_style",
    "lower_bed_type",
    "guardrail_style",
    "guardrail_length",
    "guardrail_height",
    "access_height",
    "stair_width",
    "stair_depth",
    "underbed_cabinet_mode",
    "front_cabinet_length",
    "front_cabinet_height",
    "front_cabinet_depth",
    "front_cabinet_mode",
    "rear_cabinet_length",
    "rear_cabinet_height",
    "rear_cabinet_depth",
    "rear_cabinet_mode",
    "interconnected_rows",
}


def bridge_contract_to_pricing_precheck(
    normalized_fields: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    child_bed_analysis = _resolve_child_bed_analysis(normalized_fields)
    route_evidence = _resolve_route_evidence(normalized_fields)
    mapping = map_contract_fields_to_precheck_args(
        normalized_fields,
        min_confidence=min_confidence,
    )
    precheck_args = mapping["precheck_args"]

    if not str(precheck_args.get("category") or "").strip():
        return {
            "status": "manual_confirmation_required",
            "reason": "category_missing_or_untrusted",
            "precheck_args": precheck_args,
            "precheck_result": None,
            "mapped_fields": mapping["mapped_fields"],
            "blocked_fields": mapping["blocked_fields"],
            "withheld_source_fields": mapping["withheld_source_fields"],
            "strict_ocr_blocked_fields": mapping["strict_ocr_blocked_fields"],
            "confidence_overrides": mapping["confidence_overrides"],
            "child_bed_analysis": child_bed_analysis,
            "route_evidence": route_evidence,
        }

    if child_bed_analysis.get("requires_primary_drawing_review"):
        review_block_fields = [str(item).strip() for item in list(child_bed_analysis.get("review_block_fields") or []) if str(item).strip()]
        combined_blocked_fields = sorted(set([*mapping["blocked_fields"], *review_block_fields]))
        combined_strict_fields = sorted(set([*mapping["strict_ocr_blocked_fields"], *review_block_fields]))
        return {
            "status": "manual_confirmation_required",
            "reason": "child_bed_primary_drawing_review_required",
            "precheck_args": precheck_args,
            "precheck_result": None,
            "mapped_fields": mapping["mapped_fields"],
            "blocked_fields": combined_blocked_fields,
            "withheld_source_fields": mapping["withheld_source_fields"],
            "strict_ocr_blocked_fields": combined_strict_fields,
            "confidence_overrides": mapping["confidence_overrides"],
            "child_bed_analysis": child_bed_analysis,
            "route_evidence": route_evidence,
        }

    if mapping["blocked_fields"]:
        return {
            "status": "manual_confirmation_required",
            "reason": "sensitive_fields_below_confidence_threshold",
            "precheck_args": precheck_args,
            "precheck_result": None,
            "mapped_fields": mapping["mapped_fields"],
            "blocked_fields": mapping["blocked_fields"],
            "withheld_source_fields": mapping["withheld_source_fields"],
            "strict_ocr_blocked_fields": mapping["strict_ocr_blocked_fields"],
            "confidence_overrides": mapping["confidence_overrides"],
            "child_bed_analysis": child_bed_analysis,
            "route_evidence": route_evidence,
        }

    precheck_result = run_liangqin_pricing_precheck(precheck_args)
    status = "ready_for_formal_quote" if precheck_result.get("ready_for_formal_quote") else "needs_input"
    return {
        "status": status,
        "reason": "pricing_precheck_completed",
        "precheck_args": precheck_args,
        "precheck_result": precheck_result,
        "mapped_fields": mapping["mapped_fields"],
        "blocked_fields": mapping["blocked_fields"],
        "withheld_source_fields": mapping["withheld_source_fields"],
        "strict_ocr_blocked_fields": mapping["strict_ocr_blocked_fields"],
        "confidence_overrides": mapping["confidence_overrides"],
        "child_bed_analysis": child_bed_analysis,
        "route_evidence": route_evidence,
    }


def map_contract_fields_to_precheck_args(
    normalized_fields: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    fields_payload = _resolve_fields_payload(normalized_fields)
    child_bed_analysis = _resolve_child_bed_analysis(normalized_fields)
    precheck_args: dict[str, Any] = {}
    mapped_fields: dict[str, dict[str, Any]] = {}
    blocked_fields: list[str] = []
    withheld_source_fields: list[str] = []
    strict_ocr_blocked_fields: list[str] = []
    confidence_overrides: list[dict[str, Any]] = []

    for target_field, aliases in FIELD_ALIASES.items():
        source_name, field_payload = _pick_field_payload(fields_payload, aliases)
        if source_name is None:
            continue

        value, confidence = _extract_value_and_confidence(field_payload)
        if _is_blank(value):
            continue
        effective_confidence = confidence
        strict_ocr_override = False
        if _should_apply_child_bed_ocr_cap(
            target_field=target_field,
            field_payload=field_payload,
            precheck_args=precheck_args,
            child_bed_analysis=child_bed_analysis,
        ):
            effective_confidence = min(effective_confidence, CHILD_BED_OCR_CONFIDENCE_CAP)
            if effective_confidence < confidence:
                strict_ocr_override = True
                confidence_overrides.append(
                    {
                        "target_field": target_field,
                        "source_field": source_name,
                        "reason": "child_bed_ocr_requires_manual_confirmation",
                        "original_confidence": round(confidence, 2),
                        "effective_confidence": round(effective_confidence, 2),
                    }
                )
        if effective_confidence < min_confidence:
            withheld_source_fields.append(source_name)
            if target_field in SENSITIVE_PRICING_FIELDS:
                blocked_fields.append(target_field)
            if strict_ocr_override:
                strict_ocr_blocked_fields.append(target_field)
            continue

        normalized_value = _normalize_value_for_pricing(target_field, value)
        precheck_args[target_field] = normalized_value
        mapped_fields[target_field] = {
            "source_field": source_name,
            "value": normalized_value,
            "confidence": effective_confidence,
        }

    _apply_underbed_mode_fallback(precheck_args, mapped_fields)
    _apply_table_depth_fallback(precheck_args, mapped_fields)
    _apply_cabinet_depth_fallback_from_width(precheck_args, mapped_fields)

    return {
        "precheck_args": precheck_args,
        "mapped_fields": mapped_fields,
        "blocked_fields": sorted(set(blocked_fields)),
        "withheld_source_fields": sorted(set(withheld_source_fields)),
        "strict_ocr_blocked_fields": sorted(set(strict_ocr_blocked_fields)),
        "confidence_overrides": confidence_overrides,
    }


def run_liangqin_pricing_precheck(precheck_args: dict[str, Any]) -> dict[str, Any]:
    module = _load_handle_quote_message_module()
    return module._run_precheck(precheck_args)


def build_lightweight_amount_check_quote_payload(
    normalized_fields: dict[str, Any],
    *,
    pricing_bridge_payload: dict[str, Any],
    contract_total: str | None = None,
) -> dict[str, Any] | None:
    route_evidence = _resolve_route_evidence(normalized_fields)
    if _is_lightweight_child_bed_combo_candidate(
        pricing_bridge_payload=pricing_bridge_payload,
        route_evidence=route_evidence,
    ):
        child_bed_payload = _build_lightweight_child_bed_combo_quote_payload(
            normalized_fields,
            route_evidence=route_evidence,
            contract_total=contract_total,
        )
        if child_bed_payload is not None:
            return child_bed_payload

    cabinet_payload = _build_lightweight_cabinet_quote_payload(
        normalized_fields,
        pricing_bridge_payload=pricing_bridge_payload,
        route_evidence=route_evidence,
        contract_total=contract_total,
    )
    if cabinet_payload is not None:
        return cabinet_payload
    return None


def _build_lightweight_child_bed_combo_quote_payload(
    normalized_fields: dict[str, Any],
    *,
    route_evidence: dict[str, Any],
    contract_total: str | None,
) -> dict[str, Any] | None:
    relaxed_mapping = map_contract_fields_to_precheck_args(normalized_fields, min_confidence=0.0)
    precheck_args = dict(relaxed_mapping["precheck_args"])
    assumptions = _apply_lightweight_child_bed_combo_defaults(precheck_args)
    if not _has_lightweight_child_bed_combo_requirements(precheck_args):
        return None

    module = _load_handle_quote_message_module()
    precheck_result = {
        "pricing_route": "modular_child_bed_combo",
        "quote_decision": "reference_quote",
    }
    try:
        payload = module._build_quote_payload_from_precheck(
            precheck_args=precheck_args,
            precheck_result=precheck_result,
        )
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    pricing_total = str(payload.get("total") or "").strip()
    pricing_total_value = pricing_compare.parse_amount(pricing_total)
    if not pricing_total or pricing_total_value is None:
        return None

    payload = {
        "status": "completed",
        "reason": "approximate_quote_completed",
        "handled_by": "contract_review_lightweight_amount_check",
        "pricing_route": str(payload.get("pricing_route") or "modular_child_bed_combo").strip(),
        "pricing_total": pricing_total,
        "pricing_total_value": float(pricing_total_value),
        "reply_text": "",
        "prepared_payload": payload,
        "assumed_defaults": assumptions,
        "raw_result": {
            "quote_decision": "reference_quote",
            "approximate_amount_check": True,
        },
    }
    route_candidate = _pick_route_candidate(route_evidence, route="modular_child_bed_combo") or {
        "route": "modular_child_bed_combo",
        "inferred_overrides": {},
    }
    candidate_summary = _build_lightweight_route_candidate_summary(
        payload=payload,
        route_candidate=route_candidate,
        candidate_key="modular_child_bed_combo",
        contract_total=contract_total,
    )
    return _attach_lightweight_route_candidates(
        payload=payload,
        candidate_summaries=[candidate_summary],
    )


def _build_lightweight_cabinet_quote_payload(
    normalized_fields: dict[str, Any],
    *,
    pricing_bridge_payload: dict[str, Any],
    route_evidence: dict[str, Any],
    contract_total: str | None,
) -> dict[str, Any] | None:
    route_candidate = _pick_route_candidate(route_evidence, route="cabinet")
    base_precheck_args = dict(map_contract_fields_to_precheck_args(normalized_fields, min_confidence=0.0)["precheck_args"])
    if not route_candidate and not _looks_like_cabinet_precheck_payload(pricing_bridge_payload):
        return None

    candidate_results: list[dict[str, Any]] = []
    for candidate_spec in _build_lightweight_cabinet_candidate_specs(
        precheck_args=base_precheck_args,
        route_candidate=route_candidate,
    ):
        candidate_result = _run_lightweight_cabinet_candidate(
            base_precheck_args=base_precheck_args,
            candidate_spec=candidate_spec,
            contract_total=contract_total,
        )
        if candidate_result is not None:
            candidate_results.append(candidate_result)
    if not candidate_results:
        return None
    return _select_lightweight_route_candidate_payloads(
        candidate_results,
        contract_total=contract_total,
    )


def _build_lightweight_cabinet_candidate_specs(
    *,
    precheck_args: dict[str, Any],
    route_candidate: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    candidate_specs: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    route_overrides = dict((route_candidate or {}).get("inferred_overrides") or {})
    resolved_category = str(route_overrides.get("category") or precheck_args.get("category") or "").strip()
    explicit_has_door = str(precheck_args.get("has_door") or "").strip()
    preferred_has_door = str(route_overrides.get("has_door") or explicit_has_door or "").strip()

    def add_spec(overrides: dict[str, Any], *, score: float) -> None:
        candidate_key = _build_lightweight_candidate_key(route="cabinet", overrides=overrides)
        if candidate_key in seen_keys:
            return
        seen_keys.add(candidate_key)
        spec_candidate = {
            "route": "cabinet",
            "score": score,
            "signals": list((route_candidate or {}).get("signals") or []),
            "evidence_snippets": list((route_candidate or {}).get("evidence_snippets") or []),
            "source_asset_ids": list((route_candidate or {}).get("source_asset_ids") or []),
            "inferred_overrides": dict(overrides),
        }
        candidate_specs.append(
            {
                "candidate_key": candidate_key,
                "candidate": spec_candidate,
            }
        )

    if route_candidate:
        add_spec(route_overrides, score=float(route_candidate.get("score") or 0))

    if explicit_has_door not in {"yes", "no"}:
        comparison_score = float(route_candidate.get("score") or 0) if route_candidate else 0.0
        for has_door in ("no", "yes"):
            overrides = {}
            if resolved_category:
                overrides["category"] = resolved_category
            overrides["has_door"] = has_door
            if has_door == "yes" and preferred_has_door == "yes":
                door_type = str(route_overrides.get("door_type") or "").strip()
                if door_type:
                    overrides["door_type"] = door_type
            add_spec(overrides, score=comparison_score)

    if not candidate_specs and explicit_has_door in {"yes", "no"}:
        add_spec({"has_door": explicit_has_door}, score=0.0)
    return candidate_specs


def _run_lightweight_cabinet_candidate(
    *,
    base_precheck_args: dict[str, Any],
    candidate_spec: dict[str, Any],
    contract_total: str | None,
) -> dict[str, Any] | None:
    precheck_args = dict(base_precheck_args)
    candidate = dict(candidate_spec.get("candidate") or {})
    assumptions = _apply_lightweight_route_overrides(precheck_args, candidate)
    if not _has_lightweight_cabinet_requirements(precheck_args):
        return None

    precheck_args["approximate_only"] = True
    precheck_result = run_liangqin_pricing_precheck(precheck_args)
    if not precheck_result.get("ready_for_formal_quote"):
        return None
    if str(precheck_result.get("quote_decision") or "").strip() != "reference_quote":
        return None

    module = _load_handle_quote_message_module()
    try:
        prepared_payload = module._build_quote_payload_from_precheck(
            precheck_args=precheck_args,
            precheck_result=precheck_result,
        )
    except Exception:
        return None

    if not isinstance(prepared_payload, dict):
        return None
    pricing_total = str(prepared_payload.get("total") or "").strip()
    pricing_total_value = pricing_compare.parse_amount(pricing_total)
    if not pricing_total or pricing_total_value is None:
        return None

    payload = {
        "status": "completed",
        "reason": "approximate_quote_completed",
        "handled_by": "contract_review_lightweight_amount_check",
        "pricing_route": str(prepared_payload.get("pricing_route") or "cabinet_projection_area").strip(),
        "pricing_total": pricing_total,
        "pricing_total_value": float(pricing_total_value),
        "reply_text": "",
        "prepared_payload": prepared_payload,
        "assumed_defaults": assumptions + list(precheck_result.get("assumed_defaults") or []),
        "raw_result": {
            "quote_decision": "reference_quote",
            "approximate_amount_check": True,
            "route_evidence": candidate,
        },
    }
    candidate_summary = _build_lightweight_route_candidate_summary(
        payload=payload,
        route_candidate=candidate,
        candidate_key=str(candidate_spec.get("candidate_key") or "").strip(),
        contract_total=contract_total,
    )
    return {
        "payload": payload,
        "summary": candidate_summary,
    }


def _build_lightweight_route_candidate_summary(
    *,
    payload: dict[str, Any],
    route_candidate: dict[str, Any],
    candidate_key: str,
    contract_total: str | None,
) -> dict[str, Any]:
    summary = {
        "candidate_key": candidate_key,
        "route": str(route_candidate.get("route") or "").strip(),
        "score": float(route_candidate.get("score") or 0),
        "pricing_route": str(payload.get("pricing_route") or "").strip(),
        "pricing_total": str(payload.get("pricing_total") or "").strip(),
        "pricing_total_value": payload.get("pricing_total_value"),
        "signals": [str(item).strip() for item in list(route_candidate.get("signals") or []) if str(item).strip()],
        "evidence_snippets": [str(item).strip() for item in list(route_candidate.get("evidence_snippets") or []) if str(item).strip()],
        "source_asset_ids": [str(item).strip() for item in list(route_candidate.get("source_asset_ids") or []) if str(item).strip()],
        "inferred_overrides": dict(route_candidate.get("inferred_overrides") or {}),
    }
    contract_total_value = pricing_compare.parse_amount(contract_total)
    pricing_total_value = pricing_compare.parse_amount(summary["pricing_total"])
    if contract_total_value is not None and pricing_total_value is not None:
        match_diff = abs(pricing_total_value - contract_total_value)
        summary["match_diff"] = pricing_compare.format_amount(match_diff)
        summary["match_diff_value"] = float(match_diff)
    else:
        summary["match_diff"] = ""
        summary["match_diff_value"] = None
    return summary


def _select_lightweight_route_candidate_payloads(
    candidate_results: list[dict[str, Any]],
    *,
    contract_total: str | None,
) -> dict[str, Any]:
    ordered_results = list(candidate_results)
    contract_total_value = pricing_compare.parse_amount(contract_total)
    if contract_total_value is not None:
        ordered_results.sort(
            key=lambda item: (
                item["summary"].get("match_diff_value")
                if item["summary"].get("match_diff_value") is not None
                else float("inf"),
                -float(item["summary"].get("score") or 0),
            )
        )
    selected_payload = dict(ordered_results[0]["payload"])
    candidate_summaries = [item["summary"] for item in ordered_results]
    return _attach_lightweight_route_candidates(
        payload=selected_payload,
        candidate_summaries=candidate_summaries,
    )


def _attach_lightweight_route_candidates(
    *,
    payload: dict[str, Any],
    candidate_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    result = dict(payload)
    result["route_candidates"] = list(candidate_summaries)
    result["selected_route_candidate"] = candidate_summaries[0] if candidate_summaries else {}
    result["runner_up_route_candidate"] = candidate_summaries[1] if len(candidate_summaries) > 1 else {}
    result["route_uncertainty"] = False
    result["route_uncertainty_reason"] = ""
    result["selected_vs_runner_up_diff"] = ""
    result["selected_vs_runner_up_diff_value"] = None

    if len(candidate_summaries) < 2:
        return result
    selected_diff = candidate_summaries[0].get("match_diff_value")
    runner_up_diff = candidate_summaries[1].get("match_diff_value")
    if selected_diff is None or runner_up_diff is None:
        return result
    gap = abs(Decimal(str(runner_up_diff)) - Decimal(str(selected_diff)))
    if gap > LIGHTWEIGHT_ROUTE_UNCERTAINTY_GAP:
        return result
    result["route_uncertainty"] = True
    result["route_uncertainty_reason"] = "multiple_close_candidates"
    result["selected_vs_runner_up_diff"] = pricing_compare.format_amount(gap)
    result["selected_vs_runner_up_diff_value"] = float(gap)
    return result


def _build_lightweight_candidate_key(*, route: str, overrides: dict[str, Any]) -> str:
    category = str(overrides.get("category") or "").strip() or "-"
    has_door = str(overrides.get("has_door") or "").strip() or "unknown"
    door_type = str(overrides.get("door_type") or "").strip() or "-"
    return f"{route}|{category}|{has_door}|{door_type}"


def _resolve_fields_payload(normalized_fields: dict[str, Any]) -> dict[str, Any]:
    fields_payload = normalized_fields.get("fields")
    if isinstance(fields_payload, dict):
        return fields_payload
    return normalized_fields


def _is_lightweight_child_bed_combo_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    route_evidence: dict[str, Any],
) -> bool:
    if str(pricing_bridge_payload.get("status") or "").strip() == "ready_for_formal_quote":
        return False
    precheck_result = pricing_bridge_payload.get("precheck_result") or {}
    child_bed_analysis = pricing_bridge_payload.get("child_bed_analysis") or {}
    candidate = _pick_route_candidate(route_evidence, route="modular_child_bed_combo")
    route = str(
        precheck_result.get("pricing_route")
        or child_bed_analysis.get("suggested_pricing_route")
        or (candidate or {}).get("route")
        or ""
    ).strip()
    return route == "modular_child_bed_combo"


def _apply_lightweight_child_bed_combo_defaults(precheck_args: dict[str, Any]) -> list[dict[str, str]]:
    assumptions: list[dict[str, str]] = []
    if not precheck_args.get("quote_kind"):
        precheck_args["quote_kind"] = "custom"
        assumptions.append({"field": "quote_kind", "value": "custom", "reason": "金额核对默认按定制路线试算"})

    if not precheck_args.get("guardrail_length") and precheck_args.get("length"):
        precheck_args["guardrail_length"] = precheck_args["length"]
        assumptions.append({"field": "guardrail_length", "value": str(precheck_args["length"]), "reason": "围栏长度暂按床垫长度试算"})

    if not precheck_args.get("guardrail_height"):
        precheck_args["guardrail_height"] = LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["guardrail_height"]
        assumptions.append({"field": "guardrail_height", "value": LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["guardrail_height"], "reason": "围栏高度暂按常用档位试算"})

    access_style = str(precheck_args.get("access_style") or "").strip()
    if access_style in {"直梯", "斜梯"} and not precheck_args.get("access_height"):
        precheck_args["access_height"] = LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["access_height"]
        assumptions.append({"field": "access_height", "value": LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["access_height"], "reason": "梯子垂直高度暂按常用档位试算"})

    if access_style == "梯柜":
        if not precheck_args.get("stair_width"):
            precheck_args["stair_width"] = LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["stair_width"]
            assumptions.append({"field": "stair_width", "value": LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["stair_width"], "reason": "梯柜踏步宽度暂按常用档位试算"})
        if not precheck_args.get("stair_depth"):
            fallback_depth = (
                str(precheck_args.get("front_cabinet_depth") or "").strip()
                or str(precheck_args.get("rear_cabinet_depth") or "").strip()
                or LIGHTWEIGHT_CHILD_BED_COMBO_ACCESSORY_DEFAULTS["stair_depth"]
            )
            precheck_args["stair_depth"] = fallback_depth
            assumptions.append({"field": "stair_depth", "value": fallback_depth, "reason": "梯柜进深暂按柜体进深或常用档位试算"})

    return assumptions


def _has_lightweight_child_bed_combo_requirements(precheck_args: dict[str, Any]) -> bool:
    required_fields = (
        "category",
        "quote_kind",
        "material",
        "bed_form",
        "access_style",
        "guardrail_style",
        "guardrail_length",
        "guardrail_height",
        "width",
        "length",
    )
    if any(not str(precheck_args.get(field_name) or "").strip() for field_name in required_fields):
        return False

    bed_form = str(precheck_args.get("bed_form") or "").strip()
    if bed_form not in {"半高床", "高架床"}:
        return False

    access_style = str(precheck_args.get("access_style") or "").strip()
    if access_style in {"直梯", "斜梯"} and not str(precheck_args.get("access_height") or "").strip():
        return False
    if access_style == "梯柜" and not (
        str(precheck_args.get("stair_width") or "").strip()
        and str(precheck_args.get("stair_depth") or "").strip()
    ):
        return False

    has_front = all(
        str(precheck_args.get(field_name) or "").strip()
        for field_name in ("front_cabinet_length", "front_cabinet_height", "front_cabinet_depth", "front_cabinet_mode")
    )
    has_rear = all(
        str(precheck_args.get(field_name) or "").strip()
        for field_name in ("rear_cabinet_length", "rear_cabinet_height", "rear_cabinet_depth", "rear_cabinet_mode")
    )
    if not has_front and not has_rear:
        return False
    if precheck_args.get("interconnected_rows") and not has_rear:
        return False
    return True


def _resolve_child_bed_analysis(normalized_fields: dict[str, Any]) -> dict[str, Any]:
    payload = normalized_fields.get("child_bed_analysis")
    if isinstance(payload, dict):
        return payload
    return {}


def _resolve_route_evidence(normalized_fields: dict[str, Any]) -> dict[str, Any]:
    payload = normalized_fields.get("route_evidence")
    if isinstance(payload, dict):
        return payload
    return {}


def _pick_route_candidate(route_evidence: dict[str, Any], *, route: str) -> dict[str, Any] | None:
    for item in list(route_evidence.get("candidates") or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("route") or "").strip() == route:
            return item
    return None


def _looks_like_cabinet_precheck_payload(pricing_bridge_payload: dict[str, Any]) -> bool:
    precheck_result = pricing_bridge_payload.get("precheck_result") or {}
    normalized_type = str(
        precheck_result.get("normalized_category_type")
        or precheck_result.get("category_type")
        or ""
    ).strip()
    if normalized_type == "cabinet":
        return True
    precheck_args = pricing_bridge_payload.get("precheck_args") or {}
    category = str(precheck_args.get("category") or "").strip()
    precheck_quote = _load_precheck_quote_module()
    return precheck_quote.normalize_category_label(category) == "cabinet"


def _apply_lightweight_route_overrides(
    precheck_args: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> list[dict[str, str]]:
    if not candidate:
        return []
    assumptions: list[dict[str, str]] = []
    for field_name, raw_value in dict(candidate.get("inferred_overrides") or {}).items():
        if _is_blank(raw_value):
            continue
        current_value = str(precheck_args.get(field_name) or "").strip()
        if field_name == "category":
            precheck_quote = _load_precheck_quote_module()
            normalized_current = precheck_quote.normalize_category_label(current_value)
            if current_value and normalized_current == "cabinet":
                continue
        elif current_value:
            continue
        normalized_value = _normalize_value_for_pricing(field_name, raw_value)
        precheck_args[field_name] = normalized_value
        assumptions.append(
            {
                "field": field_name,
                "value": str(normalized_value),
                "reason": "根据图下说明/结构备注补充轻量选路字段",
            }
        )
    return assumptions


def _has_lightweight_cabinet_requirements(precheck_args: dict[str, Any]) -> bool:
    required_fields = ("category", "length", "height", "material")
    if any(not str(precheck_args.get(field_name) or "").strip() for field_name in required_fields):
        return False
    precheck_quote = _load_precheck_quote_module()
    category = str(precheck_args.get("category") or "").strip()
    return precheck_quote.normalize_category_label(category) == "cabinet"


def _pick_field_payload(fields_payload: dict[str, Any], aliases: tuple[str, ...]) -> tuple[str | None, Any]:
    for alias in aliases:
        if alias in fields_payload:
            return alias, fields_payload[alias]
    return None, None


def _extract_value_and_confidence(payload: Any) -> tuple[Any, float]:
    if isinstance(payload, dict):
        return payload.get("value"), _to_confidence(payload.get("confidence"))
    return payload, 1.0


def _to_confidence(value: Any) -> float:
    try:
        if value is None or value == "":
            return 1.0
        return float(value)
    except (TypeError, ValueError):
        return 1.0


def _normalize_value_for_pricing(target_field: str, value: Any) -> Any:
    if isinstance(value, bool):
        if target_field == "has_door":
            return "yes" if value else "no"
        return value
    if target_field in {"interconnected_rows", "approximate_only"}:
        return bool(value)
    return str(value).strip()


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _apply_underbed_mode_fallback(
    precheck_args: dict[str, Any],
    mapped_fields: dict[str, dict[str, Any]],
) -> None:
    if precheck_args.get("front_cabinet_mode"):
        return
    if not precheck_args.get("underbed_cabinet_mode"):
        return
    if any(precheck_args.get(field) for field in ("rear_cabinet_length", "rear_cabinet_height", "rear_cabinet_depth", "rear_cabinet_mode")):
        return
    if not all(precheck_args.get(field) for field in ("front_cabinet_length", "front_cabinet_height", "front_cabinet_depth")):
        return

    fallback_value = precheck_args["underbed_cabinet_mode"]
    precheck_args["front_cabinet_mode"] = fallback_value

    underbed_mapping = mapped_fields.get("underbed_cabinet_mode", {})
    mapped_fields["front_cabinet_mode"] = {
        "source_field": underbed_mapping.get("source_field", "underbed_cabinet_mode"),
        "value": fallback_value,
        "confidence": underbed_mapping.get("confidence", 1.0),
        "fallback_from": "underbed_cabinet_mode",
    }


def _should_apply_child_bed_ocr_cap(
    *,
    target_field: str,
    field_payload: Any,
    precheck_args: dict[str, Any],
    child_bed_analysis: dict[str, Any],
) -> bool:
    if target_field not in CHILD_BED_STRICT_OCR_FIELDS:
        return False
    if not _is_child_bed_context(
        target_field=target_field,
        precheck_args=precheck_args,
        child_bed_analysis=child_bed_analysis,
    ):
        return False
    if _is_primary_child_bed_drawing_field(
        target_field=target_field,
        field_payload=field_payload,
        child_bed_analysis=child_bed_analysis,
    ):
        return False
    return _is_ocr_only_field_payload(field_payload)


def _is_child_bed_context(
    *,
    target_field: str,
    precheck_args: dict[str, Any],
    child_bed_analysis: dict[str, Any],
) -> bool:
    if child_bed_analysis.get("is_child_bed"):
        return True
    category = str(precheck_args.get("category") or "").strip()
    if any(keyword in category for keyword in CHILD_BED_KEYWORDS):
        return True
    if str(precheck_args.get("bed_form") or "").strip() in {"上下床", "半高床", "高架床", "错层床"}:
        return True
    return False


def _is_ocr_only_field_payload(field_payload: Any) -> bool:
    if not isinstance(field_payload, dict):
        return False
    evidence_refs = [item for item in list(field_payload.get("evidence_refs") or []) if isinstance(item, dict)]
    if not evidence_refs:
        return False
    source_kinds = {str(item.get("source_kind") or "").strip() for item in evidence_refs}
    source_kinds.discard("")
    if not source_kinds:
        return False
    return all(source_kind.startswith("ocr") for source_kind in source_kinds)


def _is_primary_child_bed_drawing_field(
    *,
    target_field: str,
    field_payload: Any,
    child_bed_analysis: dict[str, Any],
) -> bool:
    if not isinstance(field_payload, dict):
        return False
    if child_bed_analysis.get("requires_primary_drawing_review"):
        return False
    if str(child_bed_analysis.get("primary_drawing_confidence") or "").strip() != "high":
        return False
    primary_asset_id = str(child_bed_analysis.get("primary_drawing_asset_id") or "").strip()
    if not primary_asset_id:
        return False
    main_drawing_field_hits = {
        str(item).strip() for item in list(child_bed_analysis.get("main_drawing_field_hits") or []) if str(item).strip()
    }
    if target_field not in main_drawing_field_hits:
        return False
    evidence_refs = [item for item in list(field_payload.get("evidence_refs") or []) if isinstance(item, dict)]
    if not evidence_refs:
        return False
    return str(evidence_refs[0].get("asset_id") or "").strip() == primary_asset_id


def _apply_table_depth_fallback(
    precheck_args: dict[str, Any],
    mapped_fields: dict[str, dict[str, Any]],
) -> None:
    category = str(precheck_args.get("category") or "").strip()
    if not category:
        return

    precheck_quote = _load_precheck_quote_module()
    normalized_type = precheck_quote.normalize_category_label(category)
    if normalized_type != "table" and "桌" not in category:
        return
    if precheck_args.get("depth") or not precheck_args.get("width"):
        return

    fallback_value = precheck_args["width"]
    precheck_args["depth"] = fallback_value
    width_mapping = mapped_fields.get("width", {})
    mapped_fields["depth"] = {
        "source_field": width_mapping.get("source_field", "width"),
        "value": fallback_value,
        "confidence": width_mapping.get("confidence", 1.0),
        "fallback_from": "width",
    }


def _apply_cabinet_depth_fallback_from_width(
    precheck_args: dict[str, Any],
    mapped_fields: dict[str, dict[str, Any]],
) -> None:
    category = str(precheck_args.get("category") or "").strip()
    if not category:
        return
    if precheck_args.get("depth") or not precheck_args.get("width"):
        return

    precheck_quote = _load_precheck_quote_module()
    normalized_type = precheck_quote.normalize_category_label(category)
    if normalized_type != "cabinet" and "柜" not in category:
        return

    fallback_value = precheck_args["width"]
    precheck_args["depth"] = fallback_value
    width_mapping = mapped_fields.get("width", {})
    mapped_fields["depth"] = {
        "source_field": width_mapping.get("source_field", "width"),
        "value": fallback_value,
        "confidence": width_mapping.get("confidence", 1.0),
        "fallback_from": "width",
    }


def _load_handle_quote_message_module():
    scripts_dir = resolve_pricing_scripts_dir(Path(__file__))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("handle_quote_message")


def _load_precheck_quote_module():
    scripts_dir = resolve_pricing_scripts_dir(Path(__file__))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("precheck_quote")
