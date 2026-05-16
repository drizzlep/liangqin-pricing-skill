#!/usr/bin/env python3
"""Machine-verifiable baseline rule gates for quote precheck."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BaselineRuleGate:
    rule_id: str
    source_title: str
    source_page: int
    category_type: str
    trigger_terms: tuple[str, ...]
    required_terms: tuple[str, ...]
    required_quote_fields: tuple[str, ...]
    missing_field: str
    question: str
    reason: str
    constraint_code: str
    hard_block: bool = False
    verification_mode: str = "static_machine_precheck_gate"


STATIC_BASELINE_RULE_GATES: tuple[BaselineRuleGate, ...] = (
    BaselineRuleGate(
        rule_id="landing-rule-0034",
        source_title="轨道插座电源标准",
        source_page=1,
        category_type="cabinet",
        trigger_terms=("轨道插座", "电力轨道", "轨道电源"),
        required_terms=("预留插座", "插座位置", "插线板", "不接线", "不现场接线", "不剪线", "不剪断电线"),
        required_quote_fields=("length",),
        missing_field="wall_or_install_condition",
        question="这组柜体如果要装轨道插座，我需要先确认客户家是否已经预留插座位置；这条不能承诺现场接线或剪断电线对接。请先确认插座预留情况。",
        reason="new baseline requires socket reservation confirmation before quoting track-socket cabinet",
        constraint_code="baseline.track_socket.power_reservation.required",
    ),
    BaselineRuleGate(
        rule_id="landing-rule-0069",
        source_title="悬空电视柜",
        source_page=1,
        category_type="cabinet",
        trigger_terms=("悬空电视柜", "悬空支架", "隐藏支架"),
        required_terms=("承重墙", "固定在承重墙", "可固定", "墙体能固定"),
        required_quote_fields=("length",),
        missing_field="wall_or_install_condition",
        question="悬空电视柜这条需要先确认安装墙体是否满足固定条件，尤其是否能固定在承重墙上；这个没确认前不能直接正式报价。",
        reason="new baseline requires load-bearing wall confirmation for floating TV cabinet",
        constraint_code="baseline.floating_tv_cabinet.load_bearing_wall.required",
    ),
    BaselineRuleGate(
        rule_id="landing-rule-0168",
        source_title="挂墙桌",
        source_page=1,
        category_type="table",
        trigger_terms=("挂墙桌", "壁挂桌", "墙上书桌", "挂墙书桌"),
        required_terms=("承重墙", "固定在承重墙", "可固定", "墙体能固定"),
        required_quote_fields=("length",),
        missing_field="wall_or_install_condition",
        question="挂墙桌必须先确认安装位置是否能固定在承重墙上；这个条件没确认前，我不能直接给正式报价。",
        reason="new baseline requires load-bearing wall confirmation for wall-mounted desk",
        constraint_code="baseline.wall_mounted_desk.load_bearing_wall.required",
    ),
    BaselineRuleGate(
        rule_id="landing-rule-0691",
        source_title="电动举升器",
        source_page=1,
        category_type="bed",
        trigger_terms=("电动举升器", "电动举升", "电动床箱", "电动开合"),
        required_terms=("床垫重量", "不超过50kg", "≤50kg", "小于50kg", "50kg以内"),
        required_quote_fields=("width", "length"),
        missing_field="mattress_weight",
        question="电动举升器这条需要先确认床垫重量，当前规则要求床垫重量应不超过 50kg；请先确认床垫重量后再继续报价。",
        reason="new baseline requires mattress weight confirmation for electric lift",
        constraint_code="baseline.electric_lift.mattress_weight.required",
    ),
    BaselineRuleGate(
        rule_id="landing-rule-0065",
        source_title="岩板柜",
        source_page=1,
        category_type="cabinet",
        trigger_terms=("岩板台面", "岩板柜", "岩板作为台面"),
        required_terms=("直边安全角", "圆角", "边角", "备注边角", "安全角"),
        required_quote_fields=("length",),
        missing_field="quote_note",
        question="岩板作为台面时需要先确认边角要求；默认是直边安全角，如果要其他边角需要备注。请先确认边角做法。",
        reason="new baseline requires rock-slab countertop edge note before formal quote",
        constraint_code="baseline.rock_slab.edge_note.required",
    ),
)


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _configured_gate_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "reports"
        / "addenda"
        / "designer-manual-online-2026-05-13"
        / "baseline-runtime-gates.json"
    )


def _load_configured_baseline_rule_gates(path: Path | None = None) -> tuple[BaselineRuleGate, ...]:
    gate_path = path or _configured_gate_path()
    if not gate_path.exists():
        return ()
    try:
        payload = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    raw_gates = payload.get("runtime_gates") if isinstance(payload, dict) else []
    gates: list[BaselineRuleGate] = []
    for raw_gate in (raw_gates if isinstance(raw_gates, list) else []):
        if not isinstance(raw_gate, dict):
            continue
        gates.append(
            BaselineRuleGate(
                rule_id=str(raw_gate.get("rule_id") or "").strip(),
                source_title=str(raw_gate.get("source_title") or "").strip(),
                source_page=_safe_int(raw_gate.get("source_page")),
                category_type=str(raw_gate.get("category_type") or "").strip(),
                trigger_terms=_tuple_of_strings(raw_gate.get("trigger_terms")),
                required_terms=_tuple_of_strings(raw_gate.get("required_terms")),
                required_quote_fields=_tuple_of_strings(raw_gate.get("required_quote_fields")),
                missing_field=str(raw_gate.get("missing_field") or "").strip(),
                question=str(raw_gate.get("question") or "").strip(),
                reason=str(raw_gate.get("reason") or "").strip(),
                constraint_code=str(raw_gate.get("constraint_code") or "").strip(),
                hard_block=bool(raw_gate.get("hard_block")),
                verification_mode=str(raw_gate.get("verification_mode") or "machine_shadow_config_gate").strip(),
            )
        )
    return tuple(gate for gate in gates if gate.rule_id and gate.category_type and gate.trigger_terms)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _merge_gates(static_gates: tuple[BaselineRuleGate, ...], configured_gates: tuple[BaselineRuleGate, ...]) -> tuple[BaselineRuleGate, ...]:
    merged: list[BaselineRuleGate] = []
    seen: set[str] = set()
    for gate in (*static_gates, *configured_gates):
        if gate.rule_id in seen:
            continue
        seen.add(gate.rule_id)
        merged.append(gate)
    return tuple(merged)


BASELINE_RULE_GATES: tuple[BaselineRuleGate, ...] = _merge_gates(
    STATIC_BASELINE_RULE_GATES,
    _load_configured_baseline_rule_gates(),
)


def _combined_text(args: Any, *, include_category: bool = True) -> str:
    fields = (
        "series",
        "shape",
        "variant_hint",
        "door_type",
        "bed_form",
        "access_style",
        "lower_bed_type",
        "guardrail_style",
    )
    parts = [str(getattr(args, field, "") or "") for field in fields]
    if include_category:
        parts.insert(0, str(getattr(args, "category", "") or ""))
    return " ".join(parts)


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _has_required_quote_fields(args: Any, fields: tuple[str, ...]) -> bool:
    return all(str(getattr(args, field, "") or "").strip() for field in fields)


def _gate_matches(gate: BaselineRuleGate, args: Any, category_type: str) -> bool:
    if gate.category_type != category_type:
        return False
    if not _has_required_quote_fields(args, gate.required_quote_fields):
        return False
    text = _combined_text(args)
    if not _has_any(text, gate.trigger_terms):
        return False
    if gate.verification_mode == "machine_shadow_config_gate" and not _has_any(
        _combined_text(args, include_category=False),
        gate.trigger_terms,
    ):
        return False
    return not _has_any(text, gate.required_terms)


def find_baseline_rule_gate(args: Any, category_type: str) -> dict[str, Any] | None:
    for gate in BASELINE_RULE_GATES:
        if not _gate_matches(gate, args, category_type):
            continue
        return {
            "rule_id": gate.rule_id,
            "source_title": gate.source_title,
            "source_page": gate.source_page,
            "category_type": gate.category_type,
            "missing_field": gate.missing_field,
            "question": gate.question,
            "reason": gate.reason,
            "constraint_code": gate.constraint_code,
            "hard_block": gate.hard_block,
            "verification_mode": gate.verification_mode,
        }
    return None


def apply_baseline_gate_metadata(response_payload: dict[str, Any], gate_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(response_payload)
    payload["baseline_rule_gate"] = {
        "rule_id": gate_payload["rule_id"],
        "source_title": gate_payload["source_title"],
        "source_page": gate_payload["source_page"],
        "status": "active_new_baseline_candidate",
        "verification_mode": "machine_precheck_gate",
    }
    return payload
