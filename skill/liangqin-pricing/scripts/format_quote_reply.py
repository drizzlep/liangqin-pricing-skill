#!/usr/bin/env python3
import argparse
import json
import sys
from typing import Any

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


def item_lines(item: dict[str, Any], index: int, multiple: bool) -> list[str]:
    title = str(formalize_text(str(item.get("product", "")).strip()) or "").strip()
    confirmed = str(formalize_text(str(item.get("confirmed", "")).strip()) or "").strip()
    pricing_method = str(formalize_text(str(item.get("pricing_method", "")).strip()) or "").strip()
    subtotal = str(item.get("subtotal", "")).strip()
    steps = [str(formalize_text(str(step).strip()) or "").strip() for step in (item.get("calculation_steps") or [])]
    if not title or not confirmed or not pricing_method or not subtotal or not steps:
        raise SystemExit(
            f"Item {index + 1} is missing required fields: product, confirmed, pricing_method, calculation_steps, subtotal"
        )

    label = f"产品{index + 1}" if multiple else "产品"
    lines = [
        f"{label}：{title}",
        f"已确认：{confirmed}",
        f"计价方式：{pricing_method}",
        "计算过程：",
    ]
    for step in steps:
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
    if note:
        lines.append(f"说明：{note}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Format Liangqin quote reply")
    parser.add_argument("--input-json", help="Quote payload JSON. If omitted, read from stdin.")
    args = parser.parse_args()

    raw = args.input_json if args.input_json is not None else sys.stdin.read()
    if not raw.strip():
        raise SystemExit("Quote payload is required")

    payload = load_payload(raw)
    print(render(payload))


if __name__ == "__main__":
    main()
