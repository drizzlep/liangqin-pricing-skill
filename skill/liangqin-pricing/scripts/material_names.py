#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any


MATERIAL_SPECS = (
    {
        "internal": "黑胡桃",
        "formal": "北美黑胡桃木",
        "aliases": ("北美黑胡桃木", "北美黑胡桃", "黑胡桃木", "黑胡桃"),
        "text_patterns": (
            r"北美\s*黑胡桃(?!木)",
            r"(?<!北美)黑胡桃木",
            r"(?<!北美)黑胡桃",
        ),
    },
    {
        "internal": "樱桃木",
        "formal": "北美樱桃木",
        "aliases": ("北美樱桃木", "北美樱桃", "樱桃木", "樱桃"),
        "text_patterns": (
            r"北美\s*樱桃(?!木)",
            r"(?<!北美)樱桃木",
            r"(?<!北美)樱桃(?!木)",
        ),
    },
    {
        "internal": "白橡木",
        "formal": "北美白橡木",
        "aliases": ("北美白橡木", "北美白橡", "白橡木", "白橡"),
        "text_patterns": (
            r"北美\s*白橡(?!木)",
            r"(?<!北美)白橡木",
            r"(?<!北美)白橡(?!木)",
        ),
    },
    {
        "internal": "白蜡木",
        "formal": "北美白蜡木",
        "aliases": ("北美白蜡木", "北美白蜡", "白蜡木", "白蜡"),
        "text_patterns": (
            r"北美\s*白蜡(?!木)",
            r"(?<!北美)白蜡木",
            r"(?<!北美)白蜡(?!木)",
        ),
    },
    {
        "internal": "玫瑰木",
        "formal": "乌拉圭玫瑰木",
        "aliases": ("乌拉圭玫瑰木", "玫瑰木"),
        "text_patterns": (
            r"(?<!乌拉圭)玫瑰木",
        ),
    },
)


def _compact_material_key(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


INTERNAL_TO_FORMAL = {spec["internal"]: spec["formal"] for spec in MATERIAL_SPECS}
FORMAL_TO_INTERNAL = {spec["formal"]: spec["internal"] for spec in MATERIAL_SPECS}
ALIAS_TO_INTERNAL = {
    _compact_material_key(alias): spec["internal"]
    for spec in MATERIAL_SPECS
    for alias in spec["aliases"]
}
TEXT_PATTERNS = [
    (re.compile(pattern), spec["formal"])
    for spec in MATERIAL_SPECS
    for pattern in spec["text_patterns"]
]


def normalize_material_for_query(name: str | None) -> str | None:
    if not name:
        return None
    value = name.strip()
    compact = _compact_material_key(value)
    return ALIAS_TO_INTERNAL.get(compact, FORMAL_TO_INTERNAL.get(value, value))


def formalize_material_name(name: str | None) -> str | None:
    if not name:
        return name
    value = name.strip()
    normalized = normalize_material_for_query(value)
    return INTERNAL_TO_FORMAL.get(str(normalized or "").strip(), value)


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
