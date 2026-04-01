#!/usr/bin/env python3
import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from apply_addendum_layers import apply_addendum_layers
from material_names import formalize_text
import quote_flow_state
from quote_result_bundle import (
    DEFAULT_BUNDLE_ROOT,
    append_quote_card_prompt,
    build_quote_result_bundle,
    is_bundle_eligible,
    resolve_conversation_context,
    store_latest_quote_result_bundle,
)


INTERNAL_PROCESS_PHRASES = (
    "我先运行预检",
    "我先查价",
    "直接走预检",
    "根据 SKILL.md",
    "让我先看脚本",
    "现在运行玫瑰木折减计算",
    "现在运行门板补差计算",
)
FORMAL_QUOTE_FOLLOW_UP_PHRASES = (
    "还需要确认",
    "请问",
    "先确认",
    "告诉我",
    "能不能补充",
)


def _assertion_result(passed: bool, detail: str) -> dict[str, Any]:
    return {"passed": passed, "detail": detail}


def validate_output_contract(rendered_text: str, *, reference: bool) -> dict[str, Any]:
    text = str(rendered_text or "")
    assertions = {
        "has_product_line": _assertion_result(bool(re.search(r"^产品\d*：", text, re.MULTILINE)), "必须包含产品行"),
        "has_confirmed_line": _assertion_result("已确认：" in text, "必须包含已确认行"),
        "has_pricing_method_line": _assertion_result("这次按" in text, "必须包含计价方式行"),
        "has_calculation_steps": _assertion_result("计算过程：" in text and "\n- " in text, "必须展开计算过程"),
        "has_subtotal_line": _assertion_result("小计：" in text, "必须包含分项小计"),
        "has_total_line": _assertion_result(
            ("参考总价（仅供参考）：" in text) if reference else ("正式报价：" in text),
            "必须包含最终总价",
        ),
        "no_internal_process_leak": _assertion_result(
            not any(phrase in text for phrase in INTERNAL_PROCESS_PHRASES),
            "不能暴露内部执行过程",
        ),
        "no_follow_up_after_quote": _assertion_result(
            reference or not any(phrase in text for phrase in FORMAL_QUOTE_FOLLOW_UP_PHRASES),
            "正式报价后不能继续追问",
        ),
    }
    assertions["output_contract_pass"] = _assertion_result(
        all(result["passed"] for result in assertions.values()),
        "正式报价输出契约通过",
    )
    return {
        "passed": assertions["output_contract_pass"]["passed"],
        "assertions": assertions,
    }


def load_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON payload: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("Payload must be a JSON object")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise SystemExit("Payload.items must be a non-empty array")
    return payload


def prepare_payload(payload: dict[str, Any], *, addenda_root: Path, disable_addenda: bool) -> dict[str, Any]:
    if disable_addenda:
        return payload
    return apply_addendum_layers(payload, addenda_root)


def _normalize_role(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in {"customer", "designer", "consultant"} else ""


def _resolve_output_profile(audience_role: str | None, output_profile: str | None) -> str:
    normalized_profile = str(output_profile or "").strip()
    if normalized_profile in {"customer_simple", "designer_full", "consultant_dual"}:
        return normalized_profile
    normalized_role = _normalize_role(audience_role)
    if normalized_role == "customer":
        return "customer_simple"
    if normalized_role == "designer":
        return "designer_full"
    if normalized_role == "consultant":
        return "consultant_dual"
    return "legacy"


def _merge_note_entries(payload: dict[str, Any]) -> list[str]:
    note = str(formalize_text(str(payload.get("note", "")).strip()) or "").strip()
    addendum_notes = [
        str(formalize_text(str(note_item).strip()) or "").strip()
        for note_item in (payload.get("addendum_notes") or [])
    ]
    return [entry for entry in [note, *addendum_notes] if entry]


def _customer_safe_notes(payload: dict[str, Any]) -> list[str]:
    return [
        entry
        for entry in _merge_note_entries(payload)
        if entry and not entry.startswith("已套用设计师追加规则") and entry != "按当前规则可正式报价"
    ]


def render_customer_simple(payload: dict[str, Any]) -> str:
    items = payload["items"]
    multiple = len(items) > 1
    total_label = "参考总价（仅供参考）" if payload.get("reference") else "正式报价"
    total_value = str(payload.get("total", "")).strip()
    if not total_value:
        raise SystemExit("Payload.total is required")

    lines = [
        "这次我先按你现在给到的条件，给你一个参考报价。" if payload.get("reference") else "这次可以正式报价，我先把结果给你。",
    ]
    for index, item in enumerate(items):
        title = str(formalize_text(str(item.get("product", "")).strip()) or "").strip()
        confirmed = str(formalize_text(str(item.get("confirmed", "")).strip()) or "").strip()
        pricing_method = str(formalize_text(str(item.get("pricing_method", "")).strip()) or "").strip()
        subtotal = str(item.get("subtotal", "")).strip()
        if not title or not confirmed or not pricing_method or not subtotal:
            raise SystemExit(f"Item {index + 1} is missing required fields for customer output")

        label = f"产品{index + 1}" if multiple else "产品"
        lines.append(f"{label}：{title}")
        lines.append(f"已确认：{confirmed}")
        lines.append(f"这次{pricing_method if pricing_method.startswith('按') else f'按{pricing_method}'}。")
        if multiple:
            lines.append(f"小计：{subtotal}")

    lines.append(f"{total_label}：{total_value}")
    lines.append("关键前提：先按目前已经确认的尺寸、材质和做法计算。")
    safe_notes = _customer_safe_notes(payload)
    if safe_notes:
        lines.append(f"补充：{'；'.join(safe_notes)}")
    lines.append(
        "下一步：如果后面尺寸、门型、结构或附加项还有调整，我再按新条件更新。"
        if not payload.get("reference")
        else "下一步：等关键条件补齐后，我再给你正式报价。"
    )
    rendered = "\n".join(lines)
    if any(phrase in rendered for phrase in INTERNAL_PROCESS_PHRASES):
        raise SystemExit("Rendered customer output leaks internal process")
    return rendered


def build_customer_card_payload(payload: dict[str, Any]) -> dict[str, Any]:
    quote_card_payload = {
        "items": [],
        "total": str(payload.get("total", "")).strip(),
    }
    if payload.get("reference"):
        quote_card_payload["reference"] = True
    for item in payload.get("items", []):
        quote_card_payload["items"].append(
            {
                "product": item.get("product", ""),
                "confirmed": item.get("confirmed", ""),
                "pricing_method": item.get("pricing_method", ""),
                "calculation_steps": [str(step) for step in (item.get("calculation_steps") or [])[:2]],
                "subtotal": item.get("subtotal", ""),
            }
        )
    safe_notes = _customer_safe_notes(payload)
    if safe_notes:
        quote_card_payload["note"] = "；".join(safe_notes)
    return quote_card_payload


def item_lines(item: dict[str, Any], index: int, multiple: bool) -> list[str]:
    title = str(formalize_text(str(item.get("product", "")).strip()) or "").strip()
    confirmed = str(formalize_text(str(item.get("confirmed", "")).strip()) or "").strip()
    pricing_method = str(formalize_text(str(item.get("pricing_method", "")).strip()) or "").strip()
    subtotal = str(item.get("subtotal", "")).strip()
    steps = [str(formalize_text(str(step).strip()) or "").strip() for step in (item.get("calculation_steps") or [])]
    addendum_adjustments = [
        str(formalize_text(str(step).strip()) or "").strip() for step in (item.get("addendum_adjustments") or [])
    ]
    decisions = item.get("addendum_decisions") or {}
    structured_adjustments = [
        f"追加规则：{str(formalize_text(str(entry.get('title', '')).strip()) or '').strip()}；{str(formalize_text(str(entry.get('detail', '')).strip()) or '').strip()}".strip("；")
        for entry in decisions.get("adjustments", [])
    ]
    structured_constraints = [
        f"追加限制：{str(formalize_text(str(entry.get('title', '')).strip()) or '').strip()}；{str(formalize_text(str(entry.get('detail', '')).strip()) or '').strip()}".strip("；")
        for entry in decisions.get("constraints", [])
    ]
    structured_follow_ups = [
        f"追加确认：{str(formalize_text(str(entry.get('question', '')).strip()) or '').strip()}；{str(formalize_text(str(entry.get('detail', '')).strip()) or '').strip()}".strip("；")
        for entry in decisions.get("follow_up_questions", [])
    ]
    rendered_addendum_adjustments = addendum_adjustments if not decisions else []
    merged_steps = [
        step
        for step in [
            *steps,
            *rendered_addendum_adjustments,
            *structured_adjustments,
            *structured_constraints,
            *structured_follow_ups,
        ]
        if step
    ]
    if not title or not confirmed or not pricing_method or not subtotal or not merged_steps:
        raise SystemExit(
            f"Item {index + 1} is missing required fields: product, confirmed, pricing_method, calculation_steps, subtotal"
        )

    label = f"产品{index + 1}" if multiple else "产品"
    lines = [
        f"{label}：{title}",
        f"已确认：{confirmed}",
        f"这次{pricing_method if pricing_method.startswith('按') else f'按{pricing_method}'}。",
        "计算过程：",
    ]
    for step in merged_steps:
        lines.append(f"- {str(step).strip()}")
    lines.append(f"小计：{subtotal}")
    return lines


def render(payload: dict[str, Any]) -> str:
    items = payload["items"]
    multiple = len(items) > 1
    lines: list[str] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SystemExit(f"Item {index + 1} must be an object")
        if lines:
            lines.append("")
        lines.extend(item_lines(item, index, multiple))

    lines.append("")
    total_label = "参考总价（仅供参考）" if payload.get("reference") else "正式报价"
    total_value = str(payload.get("total", "")).strip()
    if not total_value:
        raise SystemExit("Payload.total is required")
    lines.append(f"{total_label}：{total_value}")

    note = str(formalize_text(str(payload.get("note", "")).strip()) or "").strip()
    addendum_notes = [str(formalize_text(str(note_item).strip()) or "").strip() for note_item in (payload.get("addendum_notes") or [])]
    merged_notes = [entry for entry in [note, *addendum_notes] if entry]
    if merged_notes:
        lines.append(f"补充：{'；'.join(merged_notes)}")

    rendered = "\n".join(lines)
    contract = validate_output_contract(rendered, reference=bool(payload.get("reference")))
    if not contract["passed"]:
        failed = [name for name, result in contract["assertions"].items() if not result["passed"]]
        raise SystemExit(f"Rendered quote violates output contract: {', '.join(failed)}")
    return rendered


def render_for_output_profile(
    payload: dict[str, Any],
    *,
    audience_role: str | None = None,
    output_profile: str | None = None,
) -> dict[str, Any]:
    resolved_role = _normalize_role(audience_role or str(payload.get("audience_role", "")).strip())
    resolved_profile = _resolve_output_profile(resolved_role, output_profile or str(payload.get("output_profile", "")).strip())

    internal_summary_input = str(payload.get("internal_summary", "")).strip()
    customer_forward_input = str(payload.get("customer_forward_text", "")).strip()

    if resolved_profile == "customer_simple":
        reply_text = customer_forward_input or render_customer_simple(payload)
        internal_summary = internal_summary_input
        customer_forward_text = reply_text
    elif resolved_profile == "designer_full":
        reply_text = internal_summary_input or render(payload)
        internal_summary = reply_text
        customer_forward_text = customer_forward_input
    elif resolved_profile == "consultant_dual":
        internal_summary = internal_summary_input or render(payload)
        customer_forward_text = customer_forward_input or render_customer_simple(payload)
        reply_text = customer_forward_text
    else:
        reply_text = render(payload)
        internal_summary = internal_summary_input
        customer_forward_text = customer_forward_input

    prepared_payload = copy.deepcopy(payload)
    if resolved_role:
        prepared_payload["audience_role"] = resolved_role
    if resolved_profile != "legacy":
        prepared_payload["output_profile"] = resolved_profile
    if internal_summary:
        prepared_payload["internal_summary"] = internal_summary
    if customer_forward_text:
        prepared_payload["customer_forward_text"] = customer_forward_text

    quote_card_payload = None
    if resolved_profile in {"customer_simple", "consultant_dual"}:
        quote_card_payload = build_customer_card_payload(payload)
        prepared_payload["quote_card_payload"] = quote_card_payload

    return {
        "audience_role": resolved_role,
        "output_profile": resolved_profile,
        "reply_text": reply_text,
        "internal_summary": internal_summary,
        "customer_forward_text": customer_forward_text,
        "prepared_payload": prepared_payload,
        "quote_card_payload": quote_card_payload,
    }


def render_with_quote_card_follow_up(
    payload: dict[str, Any],
    *,
    context_json: str | None = None,
    channel: str | None = None,
    bundle_root: Path = DEFAULT_BUNDLE_ROOT,
    audience_role: str | None = None,
    output_profile: str | None = None,
    flow_state_root: Path = quote_flow_state.DEFAULT_FLOW_STATE_ROOT,
) -> str:
    render_bundle = render_for_output_profile(
        payload,
        audience_role=audience_role,
        output_profile=output_profile,
    )
    prepared_payload = render_bundle["prepared_payload"]
    reply_text = render_bundle["reply_text"]
    eligible_for_card = is_bundle_eligible(prepared_payload)

    if context_json and channel:
        context = resolve_conversation_context(context_json, channel=channel)
        if eligible_for_card:
            bundle = build_quote_result_bundle(
                prepared_payload=prepared_payload,
                reply_text=reply_text,
                conversation_id=context["conversation_id"],
            )
            store_latest_quote_result_bundle(bundle, cache_root=bundle_root)

        confirmed_items = [
            {
                "product": str(item.get("product", "")).strip(),
                "confirmed": str(item.get("confirmed", "")).strip(),
            }
            for item in prepared_payload.get("items", [])
            if isinstance(item, dict)
        ]
        product_names = "、".join(item["product"] for item in confirmed_items[:3] if item["product"]) or "当前报价"
        quote_kind = "reference" if prepared_payload.get("reference") else "formal"
        quote_flow_state.merge_quote_flow_state(
            context["conversation_id"],
            updates={
                "audience_role": render_bundle["audience_role"] or "customer",
                "confirmed_fields": {"items": confirmed_items},
                "missing_fields": list(prepared_payload.get("missing_fields", [])),
                "active_route": str(
                    prepared_payload.get("pricing_route", "") or prepared_payload.get("route", "") or ""
                ).strip(),
                "last_quote_kind": quote_kind,
                "last_formal_payload": prepared_payload if quote_kind == "formal" else {},
                "internal_summary": render_bundle["internal_summary"],
                "customer_forward_text": render_bundle["customer_forward_text"],
                "handoff_summary": f"{product_names} 当前已生成{'参考' if quote_kind == 'reference' else '正式'}报价。",
            },
            cache_root=flow_state_root,
        )

    return append_quote_card_prompt(reply_text, eligible_for_card=eligible_for_card)


def main() -> None:
    parser = argparse.ArgumentParser(description="Format Liangqin quote reply")
    parser.add_argument("--input-json", help="Quote payload JSON. If omitted, read from stdin.")
    parser.add_argument(
        "--addenda-root",
        default=str(Path(__file__).resolve().parent.parent / "references" / "addenda"),
        help="Directory containing active addendum layers.",
    )
    parser.add_argument("--disable-addenda", action="store_true", help="Skip applying addendum layers before rendering.")
    parser.add_argument("--context-json", help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", help="Current OpenClaw channel id, such as feishu or dingtalk-connector.")
    parser.add_argument("--audience-role", choices=["customer", "designer", "consultant"], help="Audience role.")
    parser.add_argument(
        "--output-profile",
        choices=["customer_simple", "designer_full", "consultant_dual"],
        help="Quote output profile.",
    )
    parser.add_argument(
        "--bundle-root",
        default=str(DEFAULT_BUNDLE_ROOT),
        help="Directory used to cache the latest quote result bundle for each conversation.",
    )
    parser.add_argument(
        "--flow-state-root",
        default=str(quote_flow_state.DEFAULT_FLOW_STATE_ROOT),
        help="Directory used to persist quote flow state for each conversation.",
    )
    args = parser.parse_args()

    raw = args.input_json if args.input_json is not None else sys.stdin.read()
    if not raw.strip():
        raise SystemExit("Quote payload is required")

    payload = load_payload(raw)
    payload = prepare_payload(
        payload,
        addenda_root=Path(args.addenda_root).expanduser().resolve(),
        disable_addenda=args.disable_addenda,
    )
    print(
        render_with_quote_card_follow_up(
            payload,
            context_json=args.context_json,
            channel=args.channel,
            bundle_root=Path(args.bundle_root).expanduser().resolve(),
            audience_role=args.audience_role,
            output_profile=args.output_profile,
            flow_state_root=Path(args.flow_state_root).expanduser().resolve(),
        )
    )


if __name__ == "__main__":
    main()
