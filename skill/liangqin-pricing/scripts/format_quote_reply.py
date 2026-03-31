#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from apply_addendum_layers import apply_addendum_layers
from material_names import formalize_text
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


def render_with_quote_card_follow_up(
    payload: dict[str, Any],
    *,
    context_json: str | None = None,
    channel: str | None = None,
    bundle_root: Path = DEFAULT_BUNDLE_ROOT,
) -> str:
    reply_text = render(payload)
    eligible_for_card = is_bundle_eligible(payload)

    if eligible_for_card and context_json and channel:
        context = resolve_conversation_context(context_json, channel=channel)
        bundle = build_quote_result_bundle(
            prepared_payload=payload,
            reply_text=reply_text,
            conversation_id=context["conversation_id"],
        )
        store_latest_quote_result_bundle(bundle, cache_root=bundle_root)

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
    parser.add_argument(
        "--bundle-root",
        default=str(DEFAULT_BUNDLE_ROOT),
        help="Directory used to cache the latest quote result bundle for each conversation.",
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
        )
    )


if __name__ == "__main__":
    main()
