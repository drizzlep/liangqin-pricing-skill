#!/usr/bin/env python3
"""Conversation-scoped quote-flow state helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_FLOW_STATE_ROOT = (
    Path.home() / ".openclaw" / "workspace" / "skills" / "liangqin-pricing" / "runtime" / "quote-flow-states"
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "conversation"


def _state_dir(conversation_id: str, cache_root: Path) -> Path:
    return cache_root / _slugify(conversation_id)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_quote_flow_state(
    *,
    conversation_id: str,
    audience_role: str = "customer",
    manual_override: str | None = None,
    entry_mode: str = "customer_quote_request",
    customer_strategy: str = "",
    confirmed_fields: dict[str, Any] | None = None,
    missing_fields: list[str] | None = None,
    active_route: str = "",
    last_quote_kind: str = "",
    last_formal_payload: dict[str, Any] | None = None,
    internal_summary: str = "",
    customer_forward_text: str = "",
    handoff_summary: str = "",
    active_inquiry_family: str = "",
    captured_product_context: dict[str, Any] | None = None,
    last_non_quote_reply: str = "",
    last_safe_boundary_reason: str = "",
    quote_confidence: str = "",
    quote_stage: str = "",
    option_set: list[dict[str, Any]] | None = None,
    budget_adjustment_suggestions: list[str] | None = None,
    next_best_action: dict[str, Any] | None = None,
    decision_risk_points: list[str] | None = None,
    conversion_intent_level: str = "",
    consultant_handoff_plan: dict[str, Any] | None = None,
    compare_plan: dict[str, Any] | None = None,
    follow_up_script_set: dict[str, Any] | None = None,
    consultant_quick_actions: list[dict[str, Any]] | None = None,
    consultant_action_queue: list[dict[str, Any]] | None = None,
    consultant_workbench: dict[str, Any] | None = None,
    quote_followup_state: dict[str, Any] | None = None,
    quote_feedback_signal: dict[str, Any] | None = None,
    quote_outcome: dict[str, Any] | None = None,
    post_quote_stage: dict[str, Any] | None = None,
    quote_version_summary: dict[str, Any] | None = None,
    quote_version_actions: dict[str, Any] | None = None,
    objection_playbook: dict[str, Any] | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or _now_iso()
    updated = updated_at or created
    normalized_missing_fields = list(missing_fields or [])
    normalized_confirmed_fields = confirmed_fields or {}
    normalized_last_formal_payload = last_formal_payload or {}
    normalized_product_context = captured_product_context or {}
    normalized_option_set = option_set or []
    normalized_budget_suggestions = list(budget_adjustment_suggestions or [])
    normalized_next_best_action = next_best_action or {}
    normalized_decision_risk_points = list(decision_risk_points or [])
    normalized_consultant_handoff_plan = consultant_handoff_plan or {}
    normalized_compare_plan = compare_plan or {}
    normalized_follow_up_script_set = follow_up_script_set or {}
    normalized_consultant_quick_actions = consultant_quick_actions or []
    normalized_consultant_action_queue = consultant_action_queue or []
    normalized_consultant_workbench = consultant_workbench or {}
    normalized_quote_followup_state = quote_followup_state or {}
    normalized_quote_feedback_signal = quote_feedback_signal or {}
    normalized_quote_outcome = quote_outcome or {}
    normalized_post_quote_stage = post_quote_stage or {}
    normalized_quote_version_summary = quote_version_summary or {}
    normalized_quote_version_actions = quote_version_actions or {}
    normalized_objection_playbook = objection_playbook or {}

    return {
        "conversation_id": conversation_id,
        "audience_role": audience_role,
        "manual_override": manual_override,
        "manual_override_active": bool(manual_override),
        "entry_mode": entry_mode,
        "customer_strategy": customer_strategy,
        "confirmed_fields": normalized_confirmed_fields,
        "missing_fields": normalized_missing_fields,
        "active_route": active_route,
        "last_quote_kind": last_quote_kind,
        "last_formal_payload": normalized_last_formal_payload,
        "internal_summary": internal_summary,
        "customer_forward_text": customer_forward_text,
        "handoff_summary": handoff_summary,
        "active_inquiry_family": active_inquiry_family,
        "captured_product_context": normalized_product_context,
        "last_non_quote_reply": last_non_quote_reply,
        "last_safe_boundary_reason": last_safe_boundary_reason,
        "quote_confidence": quote_confidence,
        "quote_stage": quote_stage,
        "option_set": normalized_option_set,
        "budget_adjustment_suggestions": normalized_budget_suggestions,
        "next_best_action": normalized_next_best_action,
        "decision_risk_points": normalized_decision_risk_points,
        "conversion_intent_level": conversion_intent_level,
        "consultant_handoff_plan": normalized_consultant_handoff_plan,
        "compare_plan": normalized_compare_plan,
        "follow_up_script_set": normalized_follow_up_script_set,
        "consultant_quick_actions": normalized_consultant_quick_actions,
        "consultant_action_queue": normalized_consultant_action_queue,
        "consultant_workbench": normalized_consultant_workbench,
        "quote_followup_state": normalized_quote_followup_state,
        "quote_feedback_signal": normalized_quote_feedback_signal,
        "quote_outcome": normalized_quote_outcome,
        "post_quote_stage": normalized_post_quote_stage,
        "quote_version_summary": normalized_quote_version_summary,
        "quote_version_actions": normalized_quote_version_actions,
        "objection_playbook": normalized_objection_playbook,
        "role": {
            "audience_role": audience_role,
            "entry_mode": entry_mode,
            "customer_strategy": customer_strategy,
            "manual_override": manual_override,
            "manual_override_active": bool(manual_override),
        },
        "override": {
            "audience_role": manual_override or "",
            "active": bool(manual_override),
        },
        "route": {
            "active_route": active_route,
            "active_inquiry_family": active_inquiry_family,
        },
        "summaries": {
            "internal_summary": internal_summary,
            "customer_forward_text": customer_forward_text,
            "handoff_summary": handoff_summary,
            "last_non_quote_reply": last_non_quote_reply,
        },
        "last_payload": {
            "last_quote_kind": last_quote_kind,
            "last_formal_payload": normalized_last_formal_payload,
        },
        "inquiry": {
            "active_inquiry_family": active_inquiry_family,
            "captured_product_context": normalized_product_context,
            "last_safe_boundary_reason": last_safe_boundary_reason,
        },
        "conversion": {
            "quote_confidence": quote_confidence,
            "quote_stage": quote_stage,
            "option_set": normalized_option_set,
            "budget_adjustment_suggestions": normalized_budget_suggestions,
            "next_best_action": normalized_next_best_action,
            "decision_risk_points": normalized_decision_risk_points,
            "conversion_intent_level": conversion_intent_level,
            "consultant_handoff_plan": normalized_consultant_handoff_plan,
            "compare_plan": normalized_compare_plan,
            "follow_up_script_set": normalized_follow_up_script_set,
            "consultant_quick_actions": normalized_consultant_quick_actions,
            "consultant_action_queue": normalized_consultant_action_queue,
            "consultant_workbench": normalized_consultant_workbench,
            "quote_followup_state": normalized_quote_followup_state,
            "quote_feedback_signal": normalized_quote_feedback_signal,
            "quote_outcome": normalized_quote_outcome,
            "post_quote_stage": normalized_post_quote_stage,
            "quote_version_summary": normalized_quote_version_summary,
            "quote_version_actions": normalized_quote_version_actions,
            "objection_playbook": normalized_objection_playbook,
        },
        "created_at": created,
        "updated_at": updated,
    }


def _extract_existing_state_fields(state: dict[str, Any]) -> dict[str, Any]:
    summaries = state.get("summaries") or {}
    last_payload = state.get("last_payload") or {}
    route = state.get("route") or {}
    inquiry = state.get("inquiry") or {}
    conversion = state.get("conversion") or {}
    manual_override_value = state.get("manual_override")
    if manual_override_value is None:
        normalized_manual_override = None
    else:
        normalized_manual_override = str(manual_override_value).strip() or None
    return {
        "conversation_id": str(state.get("conversation_id", "")).strip(),
        "audience_role": str(state.get("audience_role", "customer") or "customer").strip() or "customer",
        "manual_override": normalized_manual_override,
        "entry_mode": str(state.get("entry_mode", "customer_quote_request") or "customer_quote_request").strip()
        or "customer_quote_request",
        "customer_strategy": str(state.get("customer_strategy", ((state.get("role") or {}).get("customer_strategy", ""))) or "").strip(),
        "confirmed_fields": state.get("confirmed_fields") or {},
        "missing_fields": list(state.get("missing_fields") or []),
        "active_route": str(state.get("active_route", route.get("active_route", "")) or "").strip(),
        "last_quote_kind": str(state.get("last_quote_kind", last_payload.get("last_quote_kind", "")) or "").strip(),
        "last_formal_payload": state.get("last_formal_payload") or last_payload.get("last_formal_payload") or {},
        "internal_summary": str(state.get("internal_summary", summaries.get("internal_summary", "")) or "").strip(),
        "customer_forward_text": str(
            state.get("customer_forward_text", summaries.get("customer_forward_text", "")) or ""
        ).strip(),
        "handoff_summary": str(state.get("handoff_summary", summaries.get("handoff_summary", "")) or "").strip(),
        "active_inquiry_family": str(
            state.get("active_inquiry_family", inquiry.get("active_inquiry_family", route.get("active_inquiry_family", ""))) or ""
        ).strip(),
        "captured_product_context": state.get("captured_product_context") or inquiry.get("captured_product_context") or {},
        "last_non_quote_reply": str(state.get("last_non_quote_reply", summaries.get("last_non_quote_reply", "")) or "").strip(),
        "last_safe_boundary_reason": str(
            state.get("last_safe_boundary_reason", inquiry.get("last_safe_boundary_reason", "")) or ""
        ).strip(),
        "quote_confidence": str(state.get("quote_confidence", conversion.get("quote_confidence", "")) or "").strip(),
        "quote_stage": str(state.get("quote_stage", conversion.get("quote_stage", "")) or "").strip(),
        "option_set": state.get("option_set") or conversion.get("option_set") or [],
        "budget_adjustment_suggestions": list(
            state.get("budget_adjustment_suggestions") or conversion.get("budget_adjustment_suggestions") or []
        ),
        "next_best_action": state.get("next_best_action") or conversion.get("next_best_action") or {},
        "decision_risk_points": list(state.get("decision_risk_points") or conversion.get("decision_risk_points") or []),
        "conversion_intent_level": str(
            state.get("conversion_intent_level", conversion.get("conversion_intent_level", "")) or ""
        ).strip(),
        "consultant_handoff_plan": state.get("consultant_handoff_plan") or conversion.get("consultant_handoff_plan") or {},
        "compare_plan": state.get("compare_plan") or conversion.get("compare_plan") or {},
        "follow_up_script_set": state.get("follow_up_script_set") or conversion.get("follow_up_script_set") or {},
        "consultant_quick_actions": state.get("consultant_quick_actions") or conversion.get("consultant_quick_actions") or [],
        "consultant_action_queue": state.get("consultant_action_queue") or conversion.get("consultant_action_queue") or [],
        "consultant_workbench": state.get("consultant_workbench") or conversion.get("consultant_workbench") or {},
        "quote_followup_state": state.get("quote_followup_state") or conversion.get("quote_followup_state") or {},
        "quote_feedback_signal": state.get("quote_feedback_signal") or conversion.get("quote_feedback_signal") or {},
        "quote_outcome": state.get("quote_outcome") or conversion.get("quote_outcome") or {},
        "post_quote_stage": state.get("post_quote_stage") or conversion.get("post_quote_stage") or {},
        "quote_version_summary": state.get("quote_version_summary") or conversion.get("quote_version_summary") or {},
        "quote_version_actions": state.get("quote_version_actions") or conversion.get("quote_version_actions") or {},
        "objection_playbook": state.get("objection_playbook") or conversion.get("objection_playbook") or {},
        "created_at": str(state.get("created_at", "")).strip() or None,
    }


def store_quote_flow_state(state: dict[str, Any], *, cache_root: Path = DEFAULT_FLOW_STATE_ROOT) -> Path:
    conversation_id = str(state.get("conversation_id", "")).strip()
    if not conversation_id:
        raise ValueError("Flow state is missing conversation_id")
    cache_dir = _state_dir(conversation_id, cache_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    latest_path = cache_dir / "latest.json"
    latest_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return latest_path


def load_quote_flow_state(conversation_id: str, *, cache_root: Path = DEFAULT_FLOW_STATE_ROOT) -> dict[str, Any] | None:
    latest_path = _state_dir(conversation_id, cache_root) / "latest.json"
    if not latest_path.exists():
        return None
    return json.loads(latest_path.read_text(encoding="utf-8"))


def merge_quote_flow_state(
    conversation_id: str,
    *,
    updates: dict[str, Any],
    cache_root: Path = DEFAULT_FLOW_STATE_ROOT,
) -> dict[str, Any]:
    existing = load_quote_flow_state(conversation_id, cache_root=cache_root)
    merged_fields = _extract_existing_state_fields(existing or build_quote_flow_state(conversation_id=conversation_id))
    for key, value in updates.items():
        if key in {"missing_fields", "budget_adjustment_suggestions", "decision_risk_points"} and value is not None:
            merged_fields[key] = list(value)
        elif key in {
            "confirmed_fields",
            "last_formal_payload",
            "next_best_action",
            "consultant_handoff_plan",
            "compare_plan",
            "follow_up_script_set",
            "consultant_workbench",
            "quote_followup_state",
            "quote_feedback_signal",
            "quote_outcome",
            "consultant_quick_actions",
            "post_quote_stage",
            "quote_version_summary",
            "quote_version_actions",
            "objection_playbook",
        } and value is not None:
            merged_fields[key] = value
        elif key in {"option_set", "consultant_quick_actions", "consultant_action_queue"} and value is not None:
            merged_fields[key] = list(value)
        elif key in {
            "audience_role",
            "manual_override",
            "entry_mode",
            "customer_strategy",
            "active_route",
            "last_quote_kind",
            "internal_summary",
            "customer_forward_text",
            "handoff_summary",
            "active_inquiry_family",
            "last_non_quote_reply",
            "last_safe_boundary_reason",
            "quote_confidence",
            "quote_stage",
            "conversion_intent_level",
        }:
            merged_fields[key] = value
        elif key in {"captured_product_context"} and value is not None:
            merged_fields[key] = value
    merged_state = build_quote_flow_state(
        conversation_id=conversation_id,
        audience_role=str(merged_fields["audience_role"] or "customer"),
        manual_override=merged_fields["manual_override"],
        entry_mode=str(merged_fields["entry_mode"] or "customer_quote_request"),
        customer_strategy=str(merged_fields["customer_strategy"] or ""),
        confirmed_fields=merged_fields["confirmed_fields"],
        missing_fields=merged_fields["missing_fields"],
        active_route=str(merged_fields["active_route"] or ""),
        last_quote_kind=str(merged_fields["last_quote_kind"] or ""),
        last_formal_payload=merged_fields["last_formal_payload"],
        internal_summary=str(merged_fields["internal_summary"] or ""),
        customer_forward_text=str(merged_fields["customer_forward_text"] or ""),
        handoff_summary=str(merged_fields["handoff_summary"] or ""),
        active_inquiry_family=str(merged_fields["active_inquiry_family"] or ""),
        captured_product_context=merged_fields["captured_product_context"],
        last_non_quote_reply=str(merged_fields["last_non_quote_reply"] or ""),
        last_safe_boundary_reason=str(merged_fields["last_safe_boundary_reason"] or ""),
        quote_confidence=str(merged_fields["quote_confidence"] or ""),
        quote_stage=str(merged_fields["quote_stage"] or ""),
        option_set=merged_fields["option_set"],
        budget_adjustment_suggestions=merged_fields["budget_adjustment_suggestions"],
        next_best_action=merged_fields["next_best_action"],
        decision_risk_points=merged_fields["decision_risk_points"],
        conversion_intent_level=str(merged_fields["conversion_intent_level"] or ""),
        consultant_handoff_plan=merged_fields["consultant_handoff_plan"],
        compare_plan=merged_fields["compare_plan"],
        follow_up_script_set=merged_fields["follow_up_script_set"],
        consultant_quick_actions=merged_fields["consultant_quick_actions"],
        consultant_action_queue=merged_fields["consultant_action_queue"],
        consultant_workbench=merged_fields["consultant_workbench"],
        quote_followup_state=merged_fields["quote_followup_state"],
        quote_feedback_signal=merged_fields["quote_feedback_signal"],
        quote_outcome=merged_fields["quote_outcome"],
        post_quote_stage=merged_fields["post_quote_stage"],
        quote_version_summary=merged_fields["quote_version_summary"],
        quote_version_actions=merged_fields["quote_version_actions"],
        objection_playbook=merged_fields["objection_playbook"],
        created_at=merged_fields["created_at"],
    )
    store_quote_flow_state(merged_state, cache_root=cache_root)
    return merged_state


def clear_quote_flow_state(conversation_id: str, *, cache_root: Path = DEFAULT_FLOW_STATE_ROOT) -> bool:
    latest_path = _state_dir(conversation_id, cache_root) / "latest.json"
    if not latest_path.exists():
        return False
    latest_path.unlink()
    return True
