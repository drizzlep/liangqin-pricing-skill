#!/usr/bin/env python3
"""Build a machine-first migration ledger for the new designer manual baseline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"
DEFAULT_OLD_LAYER = "designer-manual-2026-03-22"
QUOTE_CALC_ACTION = "接入报价计算"
PRECHECK_ACTION = "接入报价前追问/拦截"

CSV_COLUMNS = [
    "landing_id",
    "source_data_point_id",
    "machine_status",
    "baseline_decision",
    "conflict_status",
    "landing_confidence",
    "risk_level",
    "landing_action",
    "suggested_module",
    "source_title",
    "source_page",
    "topic",
    "machine_reason",
    "old_rule_match_count",
    "old_rule_titles",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a machine-first baseline migration ledger.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="New designer manual layer id.")
    parser.add_argument("--old-layer", default=DEFAULT_OLD_LAYER, help="Old designer manual layer id.")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parent.parent),
        help="Skill root directory.",
    )
    parser.add_argument("--landing-pack", default="", help="Override agent-rule-landing-pack.json path.")
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


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "")).lower()


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


def resolve_artifact_path(skill_dir: Path, layer: str, artifact_name: str) -> Path | None:
    manifest_path = skill_dir / "references" / "addenda" / layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    raw = artifacts.get(artifact_name)
    if not raw:
        return None
    raw_path = Path(str(raw))
    return raw_path if raw_path.is_absolute() else (manifest_path.parent / raw_path).resolve()


def landing_pack_path(skill_dir: Path, candidate_layer: str, override: str = "") -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return resolve_report_dir(skill_dir, candidate_layer) / "agent-rule-landing-pack.json"


def load_runtime_rules(skill_dir: Path, layer: str) -> list[dict[str, Any]]:
    path = resolve_artifact_path(skill_dir, layer, "runtime_rules_file")
    if path is None:
        return []
    payload = load_json(path, {})
    rules = payload.get("rules")
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, dict)]


def source_title(rule: dict[str, Any]) -> str:
    source = rule.get("source") if isinstance(rule.get("source"), dict) else {}
    return normalize_inline(source.get("title"))


def source_page(rule: dict[str, Any]) -> str:
    source = rule.get("source") if isinstance(rule.get("source"), dict) else {}
    return str(source.get("page") or "").strip()


def rule_text(rule: dict[str, Any]) -> str:
    return " ".join(
        normalize_inline(part)
        for part in (
            rule.get("topic"),
            rule.get("rule_excerpt"),
            source_title(rule),
            rule.get("expected_behavior"),
        )
        if normalize_inline(part)
    )


def old_rule_text(rule: dict[str, Any]) -> str:
    return " ".join(
        normalize_inline(part)
        for part in (
            rule.get("title"),
            rule.get("detail"),
            rule.get("normalized_rule"),
            rule.get("source_heading"),
            " ".join(str(item) for item in rule.get("trigger_terms", []) or []),
        )
        if normalize_inline(part)
    )


def extract_signals(text: str) -> set[str]:
    signals: set[str] = set()
    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text):
        if len(token) >= 2:
            signals.add(token)
    return signals


def find_old_matches(rule: dict[str, Any], old_rules: list[dict[str, Any]]) -> list[dict[str, str]]:
    title_key = normalize_key(source_title(rule))
    topic_key = normalize_key(rule.get("topic"))
    signals = extract_signals(rule_text(rule))
    matches: list[dict[str, str]] = []
    for old_rule in old_rules:
        old_text = old_rule_text(old_rule)
        old_key = normalize_key(old_text)
        old_title = normalize_inline(old_rule.get("title"))
        old_source = normalize_inline(old_rule.get("source_heading"))
        if title_key and title_key in old_key:
            matches.append({"title": old_title or old_source, "match_type": "source_title"})
            continue
        if topic_key and len(topic_key) >= 16 and (topic_key in old_key or old_key in topic_key):
            matches.append({"title": old_title or old_source, "match_type": "topic_overlap"})
            continue
        old_signals = extract_signals(old_text)
        shared = signals & old_signals
        if len(shared) >= 4 and any(len(item) >= 4 for item in shared):
            matches.append({"title": old_title or old_source, "match_type": "signal_overlap"})
    deduped: list[dict[str, str]] = []
    seen = set()
    for match in matches:
        key = (match["title"], match["match_type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(match)
    return deduped[:5]


def resolve_machine_status(rule: dict[str, Any], old_matches: list[dict[str, str]]) -> tuple[str, str, str, str]:
    confidence = str(rule.get("landing_confidence") or "").strip()
    action = str(rule.get("landing_action") or "").strip()
    risk = str(rule.get("risk_level") or "").strip()
    flags = [str(item).strip() for item in rule.get("quality_flags", []) or [] if str(item).strip()]

    if confidence != "high" or flags:
        return (
            "paused_unverified",
            "not_in_runtime",
            "paused_quality_or_ocr",
            "机器置信度不足或来源片段化，先暂停，不进入正式报价。",
        )
    if action == PRECHECK_ACTION:
        if old_matches:
            return (
                "active_new_baseline_candidate",
                "new_overrides_old_after_tests",
                "old_overlap_shadow_required",
                "新版高置信追问/拦截规则可自动推进；存在旧版相近规则，需 shadow 和回归测试后覆盖。",
            )
        return (
            "active_new_baseline_candidate",
            "new_rule_addition",
            "no_old_overlap",
            "新版高置信追问/拦截规则，未发现旧版相近规则，可进入自动接入队列。",
        )
    if action == QUOTE_CALC_ACTION:
        if risk.startswith("P0"):
            return (
                "conflict_paused",
                "requires_formula_tests",
                "money_rule_paused",
                "金额规则影响收费，必须补公式字段和金额回归测试后再激活。",
            )
        return (
            "paused_unverified",
            "requires_formula_tests",
            "money_rule_paused",
            "金额候选规则先暂停，等待机器生成公式字段和金额测试。",
        )
    return (
        "paused_unverified",
        "not_in_runtime",
        "unknown_action",
        "规则动作暂不能自动映射到运行层。",
    )


def build_ledger_model(*, skill_dir: Path, candidate_layer: str, old_layer: str, pack_path: Path) -> dict[str, Any]:
    pack = load_json(pack_path, {})
    rules = [rule for rule in pack.get("rules", []) if isinstance(rule, dict)]
    old_rules = load_runtime_rules(skill_dir, old_layer)

    entries: list[dict[str, Any]] = []
    for rule in rules:
        old_matches = find_old_matches(rule, old_rules)
        machine_status, baseline_decision, conflict_status, machine_reason = resolve_machine_status(rule, old_matches)
        entries.append(
            {
                "landing_id": rule.get("landing_id"),
                "source_data_point_id": rule.get("source_data_point_id"),
                "machine_status": machine_status,
                "baseline_decision": baseline_decision,
                "conflict_status": conflict_status,
                "machine_reason": machine_reason,
                "old_rule_match_count": len(old_matches),
                "old_rule_matches": old_matches,
                "landing_confidence": rule.get("landing_confidence"),
                "quality_flags": rule.get("quality_flags") or [],
                "risk_level": rule.get("risk_level"),
                "landing_action": rule.get("landing_action"),
                "suggested_module": rule.get("suggested_module"),
                "source": rule.get("source") if isinstance(rule.get("source"), dict) else {},
                "topic": rule.get("topic"),
                "required_fields": rule.get("required_fields") or [],
                "expected_behavior": rule.get("expected_behavior"),
                "test_suggestion": rule.get("test_suggestion"),
            }
        )

    status_counts = Counter(str(entry["machine_status"]) for entry in entries)
    decision_counts = Counter(str(entry["baseline_decision"]) for entry in entries)
    conflict_counts = Counter(str(entry["conflict_status"]) for entry in entries)
    module_counts = Counter(str(entry["suggested_module"]) for entry in entries)
    ready_for_auto_landing = [
        entry
        for entry in entries
        if entry["machine_status"] == "active_new_baseline_candidate"
        and str(entry["suggested_module"]).startswith("precheck_quote:")
    ]
    return {
        "title": "新版设计师手册机器优先基准迁移台账",
        "candidate_layer": candidate_layer,
        "old_layer": old_layer,
        "source_landing_pack": str(pack_path),
        "total_rules": len(entries),
        "old_runtime_rule_count": len(old_rules),
        "machine_status_counts": dict(status_counts),
        "baseline_decision_counts": dict(decision_counts),
        "conflict_status_counts": dict(conflict_counts),
        "module_counts": dict(module_counts),
        "ready_for_auto_landing_count": len(ready_for_auto_landing),
        "guardrails": [
            "不要求人工逐条理解规则。",
            "机器无法验证的规则暂停，不进入正式报价。",
            "金额规则必须有公式字段和金额回归测试后才能激活。",
            "旧版相近规则只作为冲突证据，不作为新版运行兜底。",
        ],
        "entries": entries,
        "ready_for_auto_landing": ready_for_auto_landing,
    }


def csv_row(entry: dict[str, Any]) -> dict[str, str]:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    return {
        "landing_id": str(entry.get("landing_id") or ""),
        "source_data_point_id": str(entry.get("source_data_point_id") or ""),
        "machine_status": str(entry.get("machine_status") or ""),
        "baseline_decision": str(entry.get("baseline_decision") or ""),
        "conflict_status": str(entry.get("conflict_status") or ""),
        "landing_confidence": str(entry.get("landing_confidence") or ""),
        "risk_level": str(entry.get("risk_level") or ""),
        "landing_action": str(entry.get("landing_action") or ""),
        "suggested_module": str(entry.get("suggested_module") or ""),
        "source_title": str(source.get("title") or ""),
        "source_page": str(source.get("page") or ""),
        "topic": str(entry.get("topic") or ""),
        "machine_reason": str(entry.get("machine_reason") or ""),
        "old_rule_match_count": str(entry.get("old_rule_match_count") or 0),
        "old_rule_titles": " | ".join(match.get("title", "") for match in entry.get("old_rule_matches") or []),
    }


def write_csv(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(csv_row(entry))
    os.replace(temp_path, path)


def render_summary(model: dict[str, Any]) -> str:
    status_lines = "\n".join(f"- {key}: {value}" for key, value in model["machine_status_counts"].items())
    conflict_lines = "\n".join(f"- {key}: {value}" for key, value in model["conflict_status_counts"].items())
    return f"""# 新版设计师手册机器迁移台账摘要

目标：以 `{model['candidate_layer']}` 作为良禽报价系统的新基准，使用机器证据、自动测试和 shadow 验证推进，不要求人工逐条确认。

## 总览
- 新版候选规则：{model['total_rules']}
- 旧版运行规则：{model['old_runtime_rule_count']}
- 可自动接入 precheck 队列：{model['ready_for_auto_landing_count']}

## 机器状态
{status_lines}

## 冲突状态
{conflict_lines}

## 执行规则
- 机器无法验证的规则暂停，不进入正式报价。
- 金额规则先暂停，补齐公式字段和金额回归测试后再激活。
- 旧版相近规则只作为冲突证据，不作为新版运行兜底。
"""


def build_and_write(*, skill_dir: Path, candidate_layer: str, old_layer: str, pack_override: str, output_dir: Path) -> dict[str, Any]:
    pack_path = landing_pack_path(skill_dir, candidate_layer, pack_override)
    model = build_ledger_model(skill_dir=skill_dir, candidate_layer=candidate_layer, old_layer=old_layer, pack_path=pack_path)
    output_json = output_dir / "baseline-migration-ledger.json"
    output_csv = output_dir / "baseline-migration-ledger.csv"
    output_summary = output_dir / "baseline-migration-summary.md"
    model["outputs"] = {
        "json": str(output_json),
        "csv": str(output_csv),
        "summary": str(output_summary),
    }
    write_json(output_json, model)
    write_csv(output_csv, model["entries"])
    output_summary.write_text(render_summary(model), encoding="utf-8")
    return model


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else resolve_report_dir(skill_dir, args.candidate_layer)
    model = build_and_write(
        skill_dir=skill_dir,
        candidate_layer=args.candidate_layer,
        old_layer=args.old_layer,
        pack_override=args.landing_pack,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                **model["outputs"],
                "total_rules": model["total_rules"],
                "ready_for_auto_landing_count": model["ready_for_auto_landing_count"],
                "machine_status_counts": model["machine_status_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
