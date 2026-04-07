#!/usr/bin/env python3
"""Unified audience-aware entry routing for Liangqin quote conversations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import classify_quote_role
import detect_special_cabinet_rule
import inquiry_intake
import query_addendum_guidance
import query_bed_weight_guidance
import quote_flow_state
import quote_result_bundle


DEFAULT_ADDENDA_ROOT = Path(__file__).resolve().parent.parent / "references" / "addenda"
QUOTE_REQUEST_KEYWORDS = (
    "多少钱",
    "报价",
    "报个价",
    "先报价",
    "正式报价",
    "参考价",
    "先给我一个报价",
)
NEW_QUOTE_TOPIC_KEYWORDS = (
    "重新来一单",
    "重新报价",
    "新报价",
    "重新来",
    "再来一单",
)
PRODUCT_CATEGORY_KEYWORDS = (
    "衣柜",
    "书柜",
    "玄关柜",
    "电视柜",
    "餐边柜",
    "床",
    "上下床",
    "高架床",
    "半高床",
    "榻榻米",
    "书桌",
)
RULE_CONSULTATION_KEYWORDS = (
    "规则",
    "工艺",
    "结构",
    "节点",
    "默认做",
    "允许范围",
    "怎么做",
    "什么规则",
    "专项",
    "加价",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route Liangqin quote messages through the audience-aware entry layer.")
    parser.add_argument("--text", required=True, help="Current user message.")
    parser.add_argument("--context-json", help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", help="Current channel id, such as feishu or dingtalk-connector.")
    parser.add_argument("--product-context-json", help="Optional product context JSON for non-quote inquiry intake.")
    parser.add_argument(
        "--role-override",
        choices=["customer", "designer", "consultant", "auto"],
        help="Optional manual audience-role override.",
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
    parser.add_argument("--apply-context-reset", action="store_true", help="Clear prior state and bundle when a new quote topic is detected.")
    return parser.parse_args(argv)


def resolve_output_profile(audience_role: str) -> str:
    if audience_role == "designer":
        return "designer_full"
    if audience_role == "consultant":
        return "consultant_dual"
    return "customer_simple"


def is_quote_request(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in QUOTE_REQUEST_KEYWORDS)


def looks_like_new_quote_topic(text: str) -> bool:
    normalized = str(text or "").strip()
    if any(keyword in normalized for keyword in NEW_QUOTE_TOPIC_KEYWORDS):
        return True
    if is_quote_request(normalized) and any(keyword in normalized for keyword in PRODUCT_CATEGORY_KEYWORDS):
        return True
    return False


def looks_like_rule_consultation(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in RULE_CONSULTATION_KEYWORDS)


def route_message(
    *,
    text: str,
    context_json: str | None = None,
    channel: str | None = None,
    product_context: dict[str, Any] | None = None,
    role_override: str | None = None,
    state_root: Path = quote_flow_state.DEFAULT_FLOW_STATE_ROOT,
    bundle_root: Path = quote_result_bundle.DEFAULT_BUNDLE_ROOT,
    addenda_root: Path = DEFAULT_ADDENDA_ROOT,
    apply_context_reset: bool = False,
) -> dict[str, Any]:
    normalized_text = str(text or "").strip()
    conversation_id = ""
    existing_state: dict[str, Any] | None = None
    existing_bundle: dict[str, Any] | None = None

    if context_json and channel:
        context = quote_result_bundle.resolve_conversation_context(context_json, channel=channel)
        conversation_id = context["conversation_id"]
        existing_state = quote_flow_state.load_quote_flow_state(conversation_id, cache_root=state_root)
        existing_bundle = quote_result_bundle.load_latest_quote_result_bundle(conversation_id, cache_root=bundle_root)

    if quote_result_bundle.should_generate_quote_card(normalized_text):
        audience_role = (
            str((existing_state or {}).get("audience_role", "")).strip()
            or str((existing_bundle or {}).get("audience_role", "")).strip()
            or "customer"
        )
        return {
            "audience_role": audience_role,
            "output_profile": resolve_output_profile(audience_role),
            "preferred_next_tool": "generate_quote_card_reply",
            "detected_intent": "image_request",
            "should_generate_quote_card": True,
            "should_clear_previous_context": False,
            "context_reset_applied": False,
            "conversation_id": conversation_id,
        }

    should_clear_previous_context = bool(conversation_id) and bool(existing_state or existing_bundle) and looks_like_new_quote_topic(normalized_text)
    context_reset_applied = False
    if should_clear_previous_context and apply_context_reset and conversation_id:
        quote_result_bundle.clear_latest_quote_result_bundle(conversation_id, cache_root=bundle_root)
        quote_flow_state.clear_quote_flow_state(conversation_id, cache_root=state_root)
        existing_state = None
        existing_bundle = None
        context_reset_applied = True

    role_result = classify_quote_role.classify_role(
        text=normalized_text,
        context_json=context_json,
        channel=channel,
        role_override=role_override,
        state_root=state_root,
    )
    audience_role = str(role_result.get("audience_role", "customer")).strip() or "customer"
    output_profile = resolve_output_profile(audience_role)
    entry_mode = str(role_result.get("entry_mode", "") or "").strip()
    inquiry_result = inquiry_intake.classify_inquiry(
        normalized_text,
        product_context=product_context,
    )
    inquiry_family = str(inquiry_result.get("inquiry_family") or "quote_flow").strip() or "quote_flow"
    inquiry_confidence = float(inquiry_result.get("inquiry_confidence") or 0.0)
    can_answer_directly = bool(inquiry_result.get("can_answer_directly"))
    needs_product_context = bool(inquiry_result.get("needs_product_context"))
    resolved_product_context = inquiry_result.get("resolved_product_context") or {}

    bed_weight_result = query_bed_weight_guidance.query_guidance(normalized_text)
    addendum_result = query_addendum_guidance.query_guidance(normalized_text, addenda_root)
    special_result = detect_special_cabinet_rule.detect_rule(normalized_text)

    preferred_next_tool = "precheck_quote"
    if inquiry_family == "material_config":
        preferred_next_tool = "query_addendum_guidance"
    elif inquiry_family != "quote_flow":
        preferred_next_tool = "inquiry_reply"
    elif bed_weight_result.get("matched"):
        preferred_next_tool = "query_bed_weight_guidance"
    elif (
        audience_role == "customer"
        and entry_mode == "customer_guided_discovery"
        and not looks_like_rule_consultation(normalized_text)
    ):
        preferred_next_tool = "precheck_quote"
    elif addendum_result.get("matched") and (
        str(addendum_result.get("recommended_reply_mode", "")).strip() == "follow_up" or not is_quote_request(normalized_text)
    ):
        preferred_next_tool = "query_addendum_guidance"
    elif special_result.get("special_rule"):
        preferred_next_tool = "detect_special_cabinet_rule"

    if inquiry_family != "quote_flow":
        detected_intent = "pre_sales_inquiry"
    elif preferred_next_tool in {"query_addendum_guidance", "query_bed_weight_guidance"}:
        detected_intent = "quote_follow_up" if is_quote_request(normalized_text) else "rule_consultation"
    else:
        detected_intent = "quote_request" if is_quote_request(normalized_text) else "quote_request"

    return {
        "audience_role": audience_role,
        "output_profile": output_profile,
        "preferred_next_tool": preferred_next_tool,
        "preferred_next_stage": "inquiry_reply" if inquiry_family != "quote_flow" else "quote_flow",
        "inquiry_family": inquiry_family,
        "inquiry_confidence": inquiry_confidence,
        "can_answer_directly": can_answer_directly,
        "needs_product_context": needs_product_context,
        "resolved_product_context": resolved_product_context,
        "detected_intent": detected_intent,
        "should_generate_quote_card": False,
        "should_clear_previous_context": should_clear_previous_context,
        "context_reset_applied": context_reset_applied,
        "role_result": role_result,
        "bed_weight_result": bed_weight_result if preferred_next_tool == "query_bed_weight_guidance" else {},
        "addendum_result": addendum_result if preferred_next_tool == "query_addendum_guidance" else {},
        "special_result": special_result if preferred_next_tool == "detect_special_cabinet_rule" else {},
        "conversation_id": conversation_id,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product_context = None
    if args.product_context_json:
        product_context = json.loads(args.product_context_json)
        if not isinstance(product_context, dict):
            raise SystemExit("product_context_json must be a JSON object")
    payload = route_message(
        text=args.text,
        context_json=args.context_json,
        channel=args.channel,
        product_context=product_context,
        role_override=args.role_override,
        state_root=Path(args.state_root).expanduser().resolve(),
        bundle_root=Path(args.bundle_root).expanduser().resolve(),
        addenda_root=Path(args.addenda_root).expanduser().resolve(),
        apply_context_reset=args.apply_context_reset,
    )
    json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
