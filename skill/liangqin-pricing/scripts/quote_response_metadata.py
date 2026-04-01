#!/usr/bin/env python3
"""Shared structured response metadata for Liangqin quote scripts."""

from __future__ import annotations

from typing import Any


def build_response_metadata(
    *,
    route: str,
    next_required_field: str | None = None,
    ready: bool = False,
    hard_block: bool = False,
    question_code: str | None = None,
    missing_fields: list[str] | None = None,
    constraint_code: str | None = None,
    detail_level_hint: str | None = None,
) -> dict[str, Any]:
    normalized_missing_fields = list(missing_fields or [])
    if not normalized_missing_fields and next_required_field:
        normalized_missing_fields = [next_required_field]

    resolved_question_code = question_code
    if resolved_question_code is None and next_required_field:
        suffix = "blocked" if hard_block else "required"
        resolved_question_code = f"{route}.{next_required_field}.{suffix}"

    resolved_detail_level_hint = detail_level_hint
    if not resolved_detail_level_hint:
        if ready:
            resolved_detail_level_hint = "full_quote_ready"
        elif hard_block:
            resolved_detail_level_hint = "constraint_explanation"
        elif normalized_missing_fields:
            resolved_detail_level_hint = "single_question_follow_up"
        else:
            resolved_detail_level_hint = "none"

    return {
        "route": route,
        "question_code": resolved_question_code,
        "missing_fields": normalized_missing_fields,
        "constraint_code": constraint_code,
        "detail_level_hint": resolved_detail_level_hint,
    }
