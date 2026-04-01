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
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or _now_iso()
    updated = updated_at or created
    normalized_missing_fields = list(missing_fields or [])
    normalized_confirmed_fields = confirmed_fields or {}
    normalized_last_formal_payload = last_formal_payload or {}

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
        },
        "summaries": {
            "internal_summary": internal_summary,
            "customer_forward_text": customer_forward_text,
            "handoff_summary": handoff_summary,
        },
        "last_payload": {
            "last_quote_kind": last_quote_kind,
            "last_formal_payload": normalized_last_formal_payload,
        },
        "created_at": created,
        "updated_at": updated,
    }


def _extract_existing_state_fields(state: dict[str, Any]) -> dict[str, Any]:
    summaries = state.get("summaries") or {}
    last_payload = state.get("last_payload") or {}
    route = state.get("route") or {}
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
        if key in {"missing_fields"} and value is not None:
            merged_fields[key] = list(value)
        elif key in {"confirmed_fields", "last_formal_payload"} and value is not None:
            merged_fields[key] = value
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
        }:
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
