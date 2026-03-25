#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from apply_addendum_layers import apply_addendum_layers
from material_names import formalize_text


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
        f"这次按{pricing_method}。",
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

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Format Liangqin quote reply")
    parser.add_argument("--input-json", help="Quote payload JSON. If omitted, read from stdin.")
    parser.add_argument(
        "--addenda-root",
        default=str(Path(__file__).resolve().parent.parent / "references" / "addenda"),
        help="Directory containing active addendum layers.",
    )
    parser.add_argument("--disable-addenda", action="store_true", help="Skip applying addendum layers before rendering.")
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
    print(render(payload))


if __name__ == "__main__":
    main()
