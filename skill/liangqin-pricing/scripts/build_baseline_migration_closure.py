#!/usr/bin/env python3
"""Build a machine-first closure report for the designer-manual baseline migration."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"
DEFAULT_OLD_LAYER = "designer-manual-2026-03-22"
PRECHECK_MODULE_PREFIX = "precheck_quote:"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the machine-first baseline migration closure report.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="New designer manual layer id.")
    parser.add_argument("--old-layer", default=DEFAULT_OLD_LAYER, help="Old designer manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--ledger", default="", help="Override baseline-migration-ledger.json path.")
    parser.add_argument("--output-dir", default="", help="Override output directory.")
    return parser.parse_args(argv)


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else dict(fallback or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def resolve_report_dir(skill_dir: Path, layer: str) -> Path:
    manifest_path = skill_dir / "references" / "addenda" / layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rules_candidate_file = artifacts.get("rules_candidate_file")
    if not rules_candidate_file:
        return skill_dir / "reports" / "addenda" / layer
    raw_path = Path(str(rules_candidate_file))
    resolved = raw_path if raw_path.is_absolute() else (manifest_path.parent / raw_path).resolve()
    return resolved.parent


def resolve_ledger_path(skill_dir: Path, layer: str, override: str = "") -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return resolve_report_dir(skill_dir, layer) / "baseline-migration-ledger.json"


def runtime_gate_ids(skill_dir: Path) -> set[str]:
    module = load_module("baseline_rule_gates_for_closure", skill_dir / "scripts" / "baseline_rule_gates.py")
    gates = getattr(module, "BASELINE_RULE_GATES", ())
    return {str(getattr(gate, "rule_id", "")).strip() for gate in gates if str(getattr(gate, "rule_id", "")).strip()}


def is_precheck_candidate(entry: dict[str, Any]) -> bool:
    return (
        entry.get("machine_status") == "active_new_baseline_candidate"
        and str(entry.get("suggested_module") or "").startswith(PRECHECK_MODULE_PREFIX)
    )


def public_entry(entry: dict[str, Any], *, runtime_gate_active: bool = False) -> dict[str, Any]:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    return {
        "landing_id": entry.get("landing_id"),
        "machine_status": entry.get("machine_status"),
        "baseline_decision": entry.get("baseline_decision"),
        "conflict_status": entry.get("conflict_status"),
        "risk_level": entry.get("risk_level"),
        "landing_action": entry.get("landing_action"),
        "suggested_module": entry.get("suggested_module"),
        "source_title": source.get("title"),
        "source_page": source.get("page"),
        "topic": entry.get("topic"),
        "machine_reason": entry.get("machine_reason"),
        "old_rule_match_count": entry.get("old_rule_match_count"),
        "runtime_gate_active": runtime_gate_active,
    }


def build_closure_model(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_path: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path, {})
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    active_gate_ids = runtime_gate_ids(skill_dir)

    machine_status_counts = Counter(str(entry.get("machine_status") or "") for entry in entries)
    conflict_status_counts = Counter(str(entry.get("conflict_status") or "") for entry in entries)
    precheck_candidates = [entry for entry in entries if is_precheck_candidate(entry)]
    runtime_precheck_entries = [entry for entry in precheck_candidates if str(entry.get("landing_id") or "") in active_gate_ids]
    runtime_gap_entries = [entry for entry in precheck_candidates if str(entry.get("landing_id") or "") not in active_gate_ids]
    shadow_required_entries = [entry for entry in entries if entry.get("conflict_status") == "old_overlap_shadow_required"]
    shadow_gate_entries = [entry for entry in shadow_required_entries if str(entry.get("landing_id") or "") in active_gate_ids]
    money_paused_entries = [entry for entry in entries if entry.get("conflict_status") == "money_rule_paused"]
    quality_paused_entries = [entry for entry in entries if entry.get("conflict_status") == "paused_quality_or_ocr"]
    conflict_paused_entries = [entry for entry in entries if entry.get("machine_status") == "conflict_paused"]

    money_rules_are_parked = len(money_paused_entries) == conflict_status_counts.get("money_rule_paused", 0)
    quality_rules_are_parked = len(quality_paused_entries) == conflict_status_counts.get("paused_quality_or_ocr", 0)
    shadow_rules_are_covered = len(shadow_gate_entries) == len(shadow_required_entries)
    t_plus_1_complete = bool(entries) and bool(runtime_precheck_entries) and money_rules_are_parked
    t_plus_24_complete = (
        bool(entries)
        and not runtime_gap_entries
        and shadow_rules_are_covered
        and money_rules_are_parked
        and quality_rules_are_parked
    )

    return {
        "title": "良禽报价体新基准机器迁移闭环报告",
        "candidate_layer": candidate_layer,
        "old_layer": old_layer,
        "source_ledger": str(ledger_path),
        "contract_status": {
            "t_plus_1": "complete" if t_plus_1_complete else "in_progress",
            "t_plus_24": "complete" if t_plus_24_complete else "in_progress",
            "human_rule_by_rule_review_required": False,
        },
        "counts": {
            "total_rules": len(entries),
            "runtime_gate_count": len(active_gate_ids),
            "precheck_candidate_count": len(precheck_candidates),
            "runtime_precheck_gate_count": len(runtime_precheck_entries),
            "precheck_runtime_gap_count": len(runtime_gap_entries),
            "shadow_required_count": len(shadow_required_entries),
            "shadow_runtime_gate_count": len(shadow_gate_entries),
            "money_rule_paused_count": len(money_paused_entries),
            "quality_or_ocr_paused_count": len(quality_paused_entries),
            "conflict_paused_count": len(conflict_paused_entries),
            "money_rules_are_parked": money_rules_are_parked,
            "quality_rules_are_parked": quality_rules_are_parked,
            "shadow_rules_are_covered": shadow_rules_are_covered,
        },
        "machine_status_counts": dict(machine_status_counts),
        "conflict_status_counts": dict(conflict_status_counts),
        "runtime_gate_ids": sorted(active_gate_ids),
        "runtime_precheck_gates": [
            public_entry(entry, runtime_gate_active=True)
            for entry in sorted(runtime_precheck_entries, key=lambda item: str(item.get("landing_id") or ""))
        ],
        "next_machine_work": [
            {
                "workstream": "precheck_runtime_expansion",
                "remaining_count": len(runtime_gap_entries),
                "rule_ids": [str(entry.get("landing_id") or "") for entry in runtime_gap_entries[:25]],
            },
            {
                "workstream": "shadow_verification",
                "remaining_count": max(0, len(shadow_required_entries) - len(shadow_gate_entries)),
                "rule_ids": [
                    str(entry.get("landing_id") or "")
                    for entry in shadow_required_entries
                    if str(entry.get("landing_id") or "") not in active_gate_ids
                ][:25],
            },
            {
                "workstream": "money_regression",
                "remaining_count": len(money_paused_entries),
                "rule_ids": [str(entry.get("landing_id") or "") for entry in money_paused_entries[:25]],
            },
            {
                "workstream": "quality_or_ocr_pause",
                "remaining_count": len(quality_paused_entries),
                "rule_ids": [str(entry.get("landing_id") or "") for entry in quality_paused_entries[:25]],
            },
        ],
        "guardrails": [
            "人不逐条确认规则。",
            "机器可验证规则进入 runtime gate；不可验证规则暂停。",
            "金额规则没有公式字段和金额回归测试前不影响正式报价金额。",
            "旧规则只作为 shadow 对照和冲突证据，不作为默认报价真相。",
        ],
    }


def render_markdown(model: dict[str, Any]) -> str:
    counts = model["counts"]
    work_lines = "\n".join(
        f"- {item['workstream']}: {item['remaining_count']}"
        for item in model["next_machine_work"]
    )
    gate_lines = "\n".join(f"- {rule_id}" for rule_id in model["runtime_gate_ids"]) or "- 无"
    return f"""# 良禽报价体新基准机器迁移闭环报告

目标：以 `{model['candidate_layer']}` 作为良禽报价系统的新基准，机器判断规则接入、暂停和验证状态，避免人工逐条确认。

## 合同状态
- T+1 小时合同：{model['contract_status']['t_plus_1']}
- T+24 小时合同：{model['contract_status']['t_plus_24']}
- 是否需要人工逐条审规则：否

## 当前进度
- 新规则总数：{counts['total_rules']}
- precheck 候选规则：{counts['precheck_candidate_count']}
- 已进入 runtime gate：{counts['runtime_precheck_gate_count']}
- precheck 尚未接入 runtime：{counts['precheck_runtime_gap_count']}
- 需要 shadow 验证：{counts['shadow_required_count']}
- 已通过 runtime gate 覆盖的 shadow 规则：{counts['shadow_runtime_gate_count']}
- 金额规则暂停：{counts['money_rule_paused_count']}
- OCR/质量暂停：{counts['quality_or_ocr_paused_count']}
- 冲突暂停：{counts['conflict_paused_count']}

## 已接入 runtime gate
{gate_lines}

## 下一批机器工作
{work_lines}

## 机器护栏
- 机器可验证规则进入 runtime gate；不可验证规则暂停。
- 金额规则没有公式字段和金额回归测试前不影响正式报价金额。
- 旧规则只作为 shadow 对照和冲突证据，不作为默认报价真相。
"""


def build_and_write(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_override: str, output_dir: Path) -> dict[str, Any]:
    ledger_path = resolve_ledger_path(skill_dir, candidate_layer, ledger_override)
    model = build_closure_model(skill_dir=skill_dir, candidate_layer=candidate_layer, old_layer=old_layer, ledger_path=ledger_path)
    output_json = output_dir / "baseline-migration-closure.json"
    output_summary = output_dir / "baseline-migration-closure.md"
    model["outputs"] = {"json": str(output_json), "summary": str(output_summary)}
    write_json(output_json, model)
    output_summary.write_text(render_markdown(model), encoding="utf-8")
    return model


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else resolve_report_dir(skill_dir, args.candidate_layer)
    model = build_and_write(
        skill_dir=skill_dir,
        candidate_layer=args.candidate_layer,
        old_layer=args.old_layer,
        ledger_override=args.ledger,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                **model["outputs"],
                "contract_status": model["contract_status"],
                "counts": model["counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
