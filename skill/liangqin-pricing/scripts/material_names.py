#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any


INTERNAL_TO_FORMAL = {
    "黑胡桃": "北美黑胡桃木",
    "黑胡桃木": "北美黑胡桃木",
    "樱桃木": "北美樱桃木",
    "白橡木": "北美白橡木",
    "白蜡木": "北美白蜡木",
    "玫瑰木": "乌拉圭玫瑰木",
    "乌拉圭玫瑰木": "乌拉圭玫瑰木",
}

FORMAL_TO_INTERNAL = {
    "北美黑胡桃木": "黑胡桃",
    "北美樱桃木": "樱桃木",
    "北美白橡木": "白橡木",
    "北美白蜡木": "白蜡木",
    "乌拉圭玫瑰木": "玫瑰木",
}

TEXT_PATTERNS = [
    (re.compile(r"(?<!北美)黑胡桃木"), "北美黑胡桃木"),
    (re.compile(r"(?<!北美)黑胡桃"), "北美黑胡桃木"),
    (re.compile(r"(?<!北美)樱桃木"), "北美樱桃木"),
    (re.compile(r"(?<!北美)白橡木"), "北美白橡木"),
    (re.compile(r"(?<!北美)白蜡木"), "北美白蜡木"),
    (re.compile(r"(?<!乌拉圭)玫瑰木"), "乌拉圭玫瑰木"),
]


def normalize_material_for_query(name: str | None) -> str | None:
    if not name:
        return None
    value = name.strip()
    return FORMAL_TO_INTERNAL.get(value, value)


def formalize_material_name(name: str | None) -> str | None:
    if not name:
        return name
    value = name.strip()
    return INTERNAL_TO_FORMAL.get(value, value)


def formalize_text(text: str | None) -> str | None:
    if text is None:
        return None
    result = text
    for pattern, replacement in TEXT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def formalize_materials(materials: dict[str, Any] | None) -> dict[str, Any] | None:
    if materials is None:
        return None
    normalized: dict[str, Any] = {}
    for key, value in materials.items():
        normalized[formalize_material_name(key) or key] = value
    return normalized
