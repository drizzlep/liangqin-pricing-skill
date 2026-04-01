#!/usr/bin/env python3
"""Return strict customer-facing guidance for mattress-weight / 750N questions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from quote_response_metadata import build_response_metadata


DIMENSION_PAIR_PATTERN = re.compile(
    r"(?P<first>\d+(?:\.\d+)?)\s*(?:米|m)?\s*[xX×乘*]\s*(?P<second>\d+(?:\.\d+)?)\s*(?:米|m)?"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query strict mattress-weight / 750N reply guidance.")
    parser.add_argument("--text", required=True, help="User message to inspect.")
    return parser.parse_args(argv)


def to_mm(value: float) -> int:
    if value > 10:
        return int(round(value))
    return int(round(value * 1000))


def extract_dimensions_mm(text: str) -> tuple[int | None, int | None]:
    match = DIMENSION_PAIR_PATTERN.search(text)
    if not match:
        return None, None
    first = to_mm(float(match.group("first")))
    second = to_mm(float(match.group("second")))
    width = min(first, second)
    length = max(first, second)
    return width, length


def is_bed_weight_question(text: str) -> bool:
    required_any = ("床垫重量", "举升器", "750N")
    bed_any = ("床", "箱体床", "尾翻")
    return any(term in text for term in required_any) and any(term in text for term in bed_any)


def build_suggested_reply(text: str, *, width_mm: int | None, length_mm: int | None) -> str:
    lines = ["这个单子还需要先确认床垫重量。"]

    if width_mm is not None and length_mm is not None:
        lines.append(f"当前已知尺寸：W={width_mm}mm，L={length_mm}mm。")

    lines.append("按良禽规则：床垫重量应≤50kg。")
    lines.append("床垫超重时，可改为两套750N举升器。")
    lines.append("当W＞1800且L≤2000时，默认使用两套750N举升器，需要单独收费。")
    lines.append("在床垫重量未知前，这一轮只补问，不直接下“一套”或“两套”的结论。")
    if width_mm is not None and width_mm == 1800:
        lines.append("当前W=1800属于临界值，只能先记为待床垫重量确认，不能直接写成单套结论。")
    elif width_mm is not None and width_mm < 1800:
        lines.append("当前仅知W＜1800，也仍需结合床垫重量确认，不能先写成单套结论。")
    lines.append("下单备注：床垫重量、举升器数量。")
    lines.append("请确认床垫重量。")
    return "\n".join(lines)


def query_guidance(text: str) -> dict[str, Any]:
    normalized = str(text or "").strip()
    width_mm, length_mm = extract_dimensions_mm(normalized)
    matched = is_bed_weight_question(normalized)
    payload = {
        "matched": matched,
        "width_mm": width_mm,
        "length_mm": length_mm,
        "follow_up_question": "请确认床垫重量" if matched else "",
        "suggested_reply": build_suggested_reply(normalized, width_mm=width_mm, length_mm=length_mm) if matched else "",
    }
    payload.update(
        build_response_metadata(
            route="bed_weight_guidance",
            next_required_field="mattress_weight" if matched else None,
            ready=False,
        )
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = query_guidance(args.text)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
