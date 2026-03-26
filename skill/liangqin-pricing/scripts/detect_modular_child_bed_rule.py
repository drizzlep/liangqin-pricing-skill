#!/usr/bin/env python3
"""Detect modular child-bed follow-up or constraint scenarios from raw user text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


CHILD_BED_KEYWORDS = ("儿童床", "上下床", "半高床", "半高", "高架床", "高架", "错层床", "错层", "子母床", "上铺床")
COMBO_KEYWORDS = ("床下", "前后双排", "前排", "后排", "后方", "互通", "有门无背板", "无门有背板")
GUARDRAIL_ALIAS_KEYWORDS = ("经典护栏款", "经典护栏", "护栏经典款")


def _normalize(text: str) -> str:
    return str(text or "").strip()


def _parse_metric_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value >= 10:
        return value / 1000.0
    return value


def _extract_bed_width(text: str) -> float | None:
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:米|m)?\s*[*xX×乘]\s*(\d+(?:\.\d+)?)\s*(?:米|m)?", text):
        first = _parse_metric_number(match.group(1))
        second = _parse_metric_number(match.group(2))
        if first is None or second is None:
            continue
        width = min(first, second)
        length = max(first, second)
        if 0.7 <= width <= 2.0 and 1.7 <= length <= 2.5:
            return width
    return None


def _extract_row_depth(text: str, prefixes: tuple[str, ...]) -> float | None:
    for prefix in prefixes:
        pattern = rf"{prefix}[^。；\n]*?深(?:度)?\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, text)
        if match:
            return _parse_metric_number(match.group(1))
    return None


def _extract_guardrail_alias(text: str) -> bool:
    return any(keyword in text for keyword in GUARDRAIL_ALIAS_KEYWORDS)


def detect_rule(text: str) -> dict[str, Any]:
    normalized = _normalize(text)
    if not normalized or not any(keyword in normalized for keyword in CHILD_BED_KEYWORDS):
        return {
            "matched": False,
            "recommended_reply_mode": "none",
            "pricing_route": None,
            "next_required_field": None,
            "next_question": None,
            "follow_up_questions": [],
            "constraints": [],
        }

    bed_width = _extract_bed_width(normalized)
    is_combo = any(keyword in normalized for keyword in COMBO_KEYWORDS)
    has_rear_row = any(keyword in normalized for keyword in ("后排", "后方", "后面"))
    front_depth = _extract_row_depth(normalized, ("前排", "前面", "前方"))
    rear_depth = _extract_row_depth(normalized, ("后排", "后方", "后面"))
    guardrail_alias = _extract_guardrail_alias(normalized)

    if ("高架床" in normalized or "半高床" in normalized) and bed_width is not None and bed_width > 1.2:
        return {
            "matched": True,
            "recommended_reply_mode": "constraint",
            "pricing_route": "modular_child_bed",
            "next_required_field": "width",
            "next_question": "这类上铺或高架床当前只支持床垫宽度不大于 1.2 米；你这个宽度已经超出范围，所以现在不能直接正式报价。如果要继续，我建议先确认是否能调整到 1.2 米以内。",
            "follow_up_questions": [],
            "constraints": ["上铺或高架床床垫宽度需不大于 1.2 米"],
        }

    if is_combo and front_depth is not None and front_depth > 0.45:
        return {
            "matched": True,
            "recommended_reply_mode": "constraint",
            "pricing_route": "modular_child_bed_combo",
            "next_required_field": "front_cabinet_depth",
            "next_question": "前排柜体当前只支持单排进深不大于 450mm 的组合报价；你这个进深已经超出范围，当前不能直接正式报价。如果要继续，我建议先把前排进深调整到 450mm 以内。",
            "follow_up_questions": [],
            "constraints": ["床下组合柜当前只支持单排进深不大于 450mm"],
        }

    if is_combo and rear_depth is not None and rear_depth > 0.45:
        return {
            "matched": True,
            "recommended_reply_mode": "constraint",
            "pricing_route": "modular_child_bed_combo",
            "next_required_field": "rear_cabinet_depth",
            "next_question": "后排柜体当前只支持单排进深不大于 450mm 的组合报价；你这个进深已经超出范围，当前不能直接正式报价。如果要继续，我建议先把后排进深调整到 450mm 以内。",
            "follow_up_questions": [],
            "constraints": ["床下组合柜当前只支持单排进深不大于 450mm"],
        }

    if is_combo and has_rear_row and rear_depth is None:
        follow_ups: list[dict[str, str]] = [
            {
                "field": "rear_cabinet_depth",
                "question": "后排柜体进深我还需要单独确认；前排深度或梯柜进深都不能直接代替后排。请告诉我后排柜体大概做多深？",
            }
        ]
        if guardrail_alias:
            follow_ups.append(
                {
                    "field": "guardrail_style",
                    "question": "你说的经典护栏款我还需要先对应成标准围栏名称。请确认是胶囊围栏、蘑菇围栏、田园围栏、篱笆围栏、圆柱围栏、方圆围栏还是城堡围栏。",
                }
            )
        return {
            "matched": True,
            "recommended_reply_mode": "follow_up",
            "pricing_route": "modular_child_bed_combo",
            "next_required_field": "rear_cabinet_depth",
            "next_question": follow_ups[0]["question"],
            "follow_up_questions": follow_ups,
            "constraints": [],
        }

    if is_combo and front_depth is None and any(keyword in normalized for keyword in ("前排", "前面", "前方")):
        return {
            "matched": True,
            "recommended_reply_mode": "follow_up",
            "pricing_route": "modular_child_bed_combo",
            "next_required_field": "front_cabinet_depth",
            "next_question": "前排柜体进深我还需要先确认一下，请告诉我前排大概做多深？",
            "follow_up_questions": [
                {
                    "field": "front_cabinet_depth",
                    "question": "前排柜体进深我还需要先确认一下，请告诉我前排大概做多深？",
                }
            ],
            "constraints": [],
        }

    if guardrail_alias:
        return {
            "matched": True,
            "recommended_reply_mode": "follow_up",
            "pricing_route": "modular_child_bed_combo" if is_combo else "modular_child_bed",
            "next_required_field": "guardrail_style",
            "next_question": "你说的经典护栏款我还需要先对应成标准围栏名称。请确认是胶囊围栏、蘑菇围栏、田园围栏、篱笆围栏、圆柱围栏、方圆围栏还是城堡围栏。",
            "follow_up_questions": [
                {
                    "field": "guardrail_style",
                    "question": "你说的经典护栏款我还需要先对应成标准围栏名称。请确认是胶囊围栏、蘑菇围栏、田园围栏、篱笆围栏、圆柱围栏、方圆围栏还是城堡围栏。",
                }
            ],
            "constraints": [],
        }

    return {
        "matched": False,
        "recommended_reply_mode": "none",
        "pricing_route": "modular_child_bed_combo" if is_combo else "modular_child_bed",
        "next_required_field": None,
        "next_question": None,
        "follow_up_questions": [],
        "constraints": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect modular child-bed rule scenarios from raw user text.")
    parser.add_argument("--text", required=True, help="Raw user text.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = detect_rule(args.text)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
