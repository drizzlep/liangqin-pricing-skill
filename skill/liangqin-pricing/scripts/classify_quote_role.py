#!/usr/bin/env python3
"""Deterministic audience-role classification for Liangqin quote conversations."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import quote_flow_state
import quote_result_bundle


VALID_ROLES = {"customer", "designer", "consultant"}
CUSTOMER_PRECISE_PRODUCT_KEYWORDS = (
    "书柜",
    "衣柜",
    "玄关柜",
    "餐边柜",
    "电视柜",
    "床",
    "书桌",
    "家具",
    "柜子",
    "柜体",
    "收纳柜",
)
CUSTOMER_RENOVATION_BROWSE_KEYWORDS = (
    "装修",
    "先看看",
    "过来看看",
    "先了解",
    "先逛逛",
    "先参考",
    "做做功课",
)
CUSTOMER_GUIDED_DISCOVERY_KEYWORDS = (
    "不知道做什么",
    "不清楚做什么",
    "不知道该做什么",
    "不知道怎么做",
    "利用起来",
    "做点东西",
    "做点家具",
    "做点什么",
    "做什么收纳",
    "增加收纳",
    "做点收纳",
    "能做什么",
)
CONSULTANT_KEYWORDS = (
    "发客户",
    "给客户",
    "回客户",
    "转给客户",
    "转发话术",
    "客户版",
    "门店",
    "客服",
    "咨询顾问",
)
DESIGNER_KEYWORDS = (
    "工艺",
    "结构",
    "节点",
    "牙称",
    "顶盖侧",
    "侧盖顶",
    "默认做",
    "允许范围",
    "分段缝",
    "开放格",
    "岩板",
    "纹理连续",
    "限位器",
    "围栏",
    "凹槽内退",
    "开关位置",
    "排骨架",
    "安装方式",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify Liangqin quote audience role.")
    parser.add_argument("--text", required=True, help="User message to classify.")
    parser.add_argument("--context-json", help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", help="Current channel id, such as feishu or dingtalk-connector.")
    parser.add_argument(
        "--role-override",
        choices=["customer", "designer", "consultant", "auto"],
        help="Optional manual override for the current conversation.",
    )
    parser.add_argument(
        "--state-root",
        default=str(quote_flow_state.DEFAULT_FLOW_STATE_ROOT),
        help="Directory containing saved quote flow states.",
    )
    return parser.parse_args(argv)


def _keyword_matches(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _infer_auto_role(text: str) -> tuple[str, float, list[str], str, str]:
    normalized = str(text or "").strip()
    consultant_hits = _keyword_matches(normalized, CONSULTANT_KEYWORDS)
    if consultant_hits:
        return (
            "consultant",
            0.96 if len(consultant_hits) >= 2 else 0.88,
            [f"consultant_keyword:{keyword}" for keyword in consultant_hits],
            "consultant_handoff",
            "",
        )

    explicit_designer = bool(re.search(r"(设计师|工艺|结构|节点|默认做|允许范围)", normalized))
    designer_hits = _keyword_matches(normalized, DESIGNER_KEYWORDS)
    if explicit_designer or designer_hits:
        reason_codes = [f"designer_keyword:{keyword}" for keyword in designer_hits] or ["designer_keyword:explicit_role"]
        return (
            "designer",
            0.95 if explicit_designer or len(designer_hits) >= 2 else 0.84,
            reason_codes,
            "designer_rule_consultation",
            "",
        )

    customer_guided_hits = _keyword_matches(normalized, CUSTOMER_GUIDED_DISCOVERY_KEYWORDS)
    if customer_guided_hits:
        return (
            "customer",
            0.72,
            [f"customer_guided_keyword:{keyword}" for keyword in customer_guided_hits],
            "customer_guided_discovery",
            "guided_discovery",
        )

    customer_browse_hits = _keyword_matches(normalized, CUSTOMER_RENOVATION_BROWSE_KEYWORDS)
    if customer_browse_hits:
        return (
            "customer",
            0.7,
            [f"customer_browse_keyword:{keyword}" for keyword in customer_browse_hits],
            "customer_guided_discovery",
            "renovation_browse",
        )

    customer_precise_hits = _keyword_matches(normalized, CUSTOMER_PRECISE_PRODUCT_KEYWORDS)
    if customer_precise_hits or re.search(r"(想做个|想定个|定个|做个|想做一组|想打一组)", normalized):
        reason_codes = [f"customer_precise_keyword:{keyword}" for keyword in customer_precise_hits] or [
            "customer_precise_keyword:intent_pattern"
        ]
        return (
            "customer",
            0.68,
            reason_codes,
            "customer_guided_discovery",
            "precise_need",
        )

    return ("customer", 0.55, ["customer_default"], "customer_guided_discovery", "default")


def classify_role(
    *,
    text: str,
    context_json: str | None = None,
    channel: str | None = None,
    role_override: str | None = None,
    state_root: Path = quote_flow_state.DEFAULT_FLOW_STATE_ROOT,
) -> dict[str, Any]:
    conversation_id = ""
    existing_state: dict[str, Any] | None = None
    if context_json and channel:
        context = quote_result_bundle.resolve_conversation_context(context_json, channel=channel)
        conversation_id = context["conversation_id"]
        existing_state = quote_flow_state.load_quote_flow_state(conversation_id, cache_root=state_root)

    normalized_override = str(role_override or "").strip()
    auto_reset_requested = normalized_override == "auto"
    if normalized_override == "auto":
        normalized_override = ""
        if conversation_id:
            quote_flow_state.merge_quote_flow_state(
                conversation_id,
                updates={"manual_override": None},
                cache_root=state_root,
            )
            existing_state = quote_flow_state.load_quote_flow_state(conversation_id, cache_root=state_root)

    if normalized_override in VALID_ROLES:
        payload = {
            "audience_role": normalized_override,
            "confidence": 1.0,
            "reason_codes": [f"manual_override:{normalized_override}"],
            "entry_mode": "manual_override",
            "manual_override_active": True,
        }
        if conversation_id:
            quote_flow_state.merge_quote_flow_state(
                conversation_id,
                updates={
                    "audience_role": normalized_override,
                    "manual_override": normalized_override,
                    "entry_mode": "manual_override",
                },
                cache_root=state_root,
            )
            payload["conversation_id"] = conversation_id
        return payload

    if existing_state and existing_state.get("manual_override"):
        manual_role = str(existing_state["manual_override"]).strip()
        payload = {
            "audience_role": manual_role,
            "confidence": 1.0,
            "reason_codes": ["state_manual_override"],
            "entry_mode": "manual_override",
            "manual_override_active": True,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return payload

    audience_role, confidence, reason_codes, entry_mode, customer_strategy = _infer_auto_role(str(text or ""))
    existing_role = ""
    if existing_state:
        existing_role = str(existing_state.get("audience_role") or "").strip()
    if (
        not auto_reset_requested
        and existing_role in {"consultant", "designer"}
        and audience_role == "customer"
        and confidence < 0.8
        and reason_codes == ["customer_default"]
    ):
        audience_role = existing_role
        confidence = 0.78
        reason_codes = ["state_role_resume"]
        entry_mode = str(existing_state.get("entry_mode") or "customer_guided_discovery").strip() or "customer_guided_discovery"
        customer_strategy = str(existing_state.get("customer_strategy") or "").strip()

    payload = {
        "audience_role": audience_role,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "entry_mode": entry_mode,
        "customer_strategy": customer_strategy,
        "manual_override_active": False,
    }
    if conversation_id:
        quote_flow_state.merge_quote_flow_state(
            conversation_id,
            updates={
                "audience_role": audience_role,
                "entry_mode": entry_mode,
            },
            cache_root=state_root,
        )
        payload["conversation_id"] = conversation_id
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = classify_role(
        text=args.text,
        context_json=args.context_json,
        channel=args.channel,
        role_override=args.role_override,
        state_root=Path(args.state_root).expanduser().resolve(),
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
