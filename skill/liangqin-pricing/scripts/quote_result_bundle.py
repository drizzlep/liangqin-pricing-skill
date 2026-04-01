#!/usr/bin/env python3
"""Conversation-scoped quote card bundle helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CARD_PROMPT_TEXT = "如果你需要，我可以把这次报价整理成一张图片发到当前会话。你回复“生成图片”就可以。"
NO_BUNDLE_MESSAGE = "当前会话里还没有可生成图片的完整报价。你可以先让我给出带总价的报价结果，再回复“生成图片”。"
DEFAULT_BUNDLE_ROOT = (
    Path.home() / ".openclaw" / "workspace" / "skills" / "liangqin-pricing" / "runtime" / "quote-result-bundles"
)

NEGATIVE_INTENT_PATTERNS = [
    re.compile(r"(先|暂时)?不(用|要|需要).{0,4}(生成|做|发|整理).{0,6}(图片|图|报价卡|卡片|jpg|JPG)", re.IGNORECASE),
    re.compile(r"别.{0,4}(生成|发).{0,6}(图片|图|报价卡|卡片)", re.IGNORECASE),
]
POSITIVE_INTENT_PATTERNS = [
    re.compile(r"^(生成|发|做)(一张)?(图片|图|报价卡|卡片|jpg|JPG)(吧|呀|呢)?[。.!！]?$", re.IGNORECASE),
    re.compile(r"(生成|发|做|整理成).{0,8}(图片|图|报价卡|卡片|jpg|JPG)", re.IGNORECASE),
    re.compile(r"(发图|发报价卡)", re.IGNORECASE),
]


def _parse_context_json(context_json: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(context_json, dict):
        return context_json
    try:
        payload = json.loads(context_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid context JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Conversation context must be a JSON object")
    return payload


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "conversation"


def resolve_conversation_context(context_json: str | dict[str, Any], *, channel: str) -> dict[str, Any]:
    payload = _parse_context_json(context_json)
    sender_id = str(payload.get("sender_id", "")).strip()
    message_id = str(payload.get("message_id", "")).strip()
    group_channel = str(payload.get("group_channel", "")).strip()
    is_group_chat = bool(payload.get("is_group_chat")) or bool(group_channel)

    if not sender_id:
        raise ValueError("Conversation context is missing sender_id")

    if group_channel:
        conversation_id = group_channel
    elif is_group_chat:
        conversation_label = str(payload.get("conversation_label", "")).strip()
        group_subject = str(payload.get("group_subject", "")).strip()
        group_seed = conversation_label or group_subject or sender_id
        conversation_id = f"agent:main:{channel}:group:{_slugify(group_seed)}"
    else:
        conversation_id = f"agent:main:{channel}:direct:{sender_id}"

    return {
        "channel": channel,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "sender_id": sender_id,
        "is_group_chat": is_group_chat,
        "raw_context": payload,
    }


def should_generate_quote_card(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if any(pattern.search(normalized) for pattern in NEGATIVE_INTENT_PATTERNS):
        return False
    return any(pattern.search(normalized) for pattern in POSITIVE_INTENT_PATTERNS)


def determine_quote_kind(prepared_payload: dict[str, Any]) -> str:
    return "reference" if prepared_payload.get("reference") else "formal"


def is_bundle_eligible(prepared_payload: dict[str, Any]) -> bool:
    items = prepared_payload.get("items")
    total = str(prepared_payload.get("total", "")).strip()
    return isinstance(items, list) and len(items) > 0 and bool(total)


def build_quote_result_bundle(
    *,
    prepared_payload: dict[str, Any],
    reply_text: str,
    conversation_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or datetime.now().astimezone().isoformat(timespec="seconds")
    bundle = {
        "prepared_payload": prepared_payload,
        "reply_text": reply_text,
        "quote_kind": determine_quote_kind(prepared_payload),
        "conversation_id": conversation_id,
        "eligible_for_card": is_bundle_eligible(prepared_payload),
        "created_at": timestamp,
    }
    customer_forward_text = str(prepared_payload.get("customer_forward_text", "")).strip()
    internal_summary = str(prepared_payload.get("internal_summary", "")).strip()
    audience_role = str(prepared_payload.get("audience_role", "")).strip()
    output_profile = str(prepared_payload.get("output_profile", "")).strip()
    quote_card_payload = prepared_payload.get("quote_card_payload")

    if customer_forward_text:
        bundle["customer_forward_text"] = customer_forward_text
    if internal_summary:
        bundle["internal_summary"] = internal_summary
    if audience_role:
        bundle["audience_role"] = audience_role
    if output_profile:
        bundle["output_profile"] = output_profile
    if isinstance(quote_card_payload, dict):
        bundle["quote_card_payload"] = quote_card_payload
    return bundle


def append_quote_card_prompt(reply_text: str, *, eligible_for_card: bool) -> str:
    normalized = reply_text.rstrip()
    if not eligible_for_card:
        return normalized
    if CARD_PROMPT_TEXT in normalized:
        return normalized
    return f"{normalized}\n\n{CARD_PROMPT_TEXT}"


def _bundle_dir(conversation_id: str, cache_root: Path) -> Path:
    return cache_root / _slugify(conversation_id)


def store_latest_quote_result_bundle(bundle: dict[str, Any], *, cache_root: Path = DEFAULT_BUNDLE_ROOT) -> Path:
    conversation_id = str(bundle.get("conversation_id", "")).strip()
    if not conversation_id:
        raise ValueError("Bundle is missing conversation_id")
    cache_dir = _bundle_dir(conversation_id, cache_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    latest_path = cache_dir / "latest.json"
    latest_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return latest_path


def load_latest_quote_result_bundle(conversation_id: str, *, cache_root: Path = DEFAULT_BUNDLE_ROOT) -> dict[str, Any] | None:
    latest_path = _bundle_dir(conversation_id, cache_root) / "latest.json"
    if not latest_path.exists():
        return None
    return json.loads(latest_path.read_text(encoding="utf-8"))


def clear_latest_quote_result_bundle(conversation_id: str, *, cache_root: Path = DEFAULT_BUNDLE_ROOT) -> bool:
    latest_path = _bundle_dir(conversation_id, cache_root) / "latest.json"
    if not latest_path.exists():
        return False
    latest_path.unlink()
    return True
