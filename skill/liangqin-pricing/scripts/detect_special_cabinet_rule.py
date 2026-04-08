#!/usr/bin/env python3
"""Detect special cabinet-rule scenarios from raw user text."""

from __future__ import annotations

import argparse
import json
import sys

from quote_response_metadata import build_response_metadata


DOUBLE_SIDED_DOOR_KEYWORDS = ("双面门", "双面柜门", "双面开门", "两面开门")
FRIDGE_CABINET_KEYWORDS = ("冰箱柜", "无底板柜", "冰箱位无底板", "无底板预留")
HIDDEN_SURFACE_KEYWORDS = ("非见光面", "不见光面", "内侧", "柜内侧", "背面")
ROSEWOOD_KEYWORDS = ("玫瑰木", "乌拉圭玫瑰木")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_hidden_rosewood_discount(text: str) -> bool:
    return _contains_any(text, HIDDEN_SURFACE_KEYWORDS) and _contains_any(text, ROSEWOOD_KEYWORDS)


def detect_rule(text: str) -> dict[str, object]:
    normalized = str(text or "").strip()
    if "钻石柜" in normalized:
        payload = {
            "special_rule": "diamond_cabinet",
            "next_required_field": "shape",
            "next_question": "这个钻石柜我还需要确认一下结构关系：钻石柜这部分和旁边柜体是同类型吗？比如都开放，或都带门；如果不是，请直接告诉我是钻石柜开放、旁边带门，还是相反。",
        }
        payload.update(
            build_response_metadata(
                route="special_cabinet_rule",
                next_required_field="shape",
                ready=False,
            )
        )
        return payload
    if _contains_any(normalized, FRIDGE_CABINET_KEYWORDS):
        payload = {
            "special_rule": "fridge_cabinet",
            "next_required_field": "fridge_opening_height",
            "next_question": "这个冰箱柜我还需要确认一个关键尺寸：预留的冰箱净高大概是多少？如果你更方便，也可以直接告诉我上柜准备做多高。",
        }
        payload.update(
            build_response_metadata(
                route="special_cabinet_rule",
                next_required_field="fridge_opening_height",
                ready=False,
            )
        )
        return payload
    if _looks_like_hidden_rosewood_discount(normalized):
        payload = {
            "special_rule": "hidden_rosewood_discount",
            "next_required_field": None,
            "next_question": None,
        }
        payload.update(
            build_response_metadata(
                route="special_cabinet_rule",
                ready=False,
                constraint_code="special_cabinet_rule.hidden_rosewood_discount",
                detail_level_hint="rule_routing",
            )
        )
        return payload
    if _contains_any(normalized, DOUBLE_SIDED_DOOR_KEYWORDS):
        payload = {
            "special_rule": "double_sided_door",
            "next_required_field": "door_type",
            "next_question": "这组双面门柜体我还需要确认两边分别是什么门型。你可以直接告诉我组合，例如拼框/拼框、拼框/平板、格栅/平板、平板/平板。",
        }
        payload.update(
            build_response_metadata(
                route="special_cabinet_rule",
                next_required_field="door_type",
                ready=False,
            )
        )
        return payload
    if "操作空区" in normalized or "空区" in normalized:
        payload = {
            "special_rule": "operation_gap",
            "next_required_field": "gap_size",
            "next_question": "这个操作空区带背板区域我还需要确认宽和高，大概分别是多少？",
        }
        payload.update(
            build_response_metadata(
                route="special_cabinet_rule",
                next_required_field="gap_size",
                ready=False,
            )
        )
        return payload
    payload = {
        "special_rule": None,
        "next_required_field": None,
        "next_question": None,
    }
    payload.update(
        build_response_metadata(
            route="special_cabinet_rule",
            ready=False,
        )
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect special cabinet-rule scenarios.")
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
