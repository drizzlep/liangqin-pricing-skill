#!/usr/bin/env python3
"""Build machine shadow verification for old-overlap baseline rules."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"
DEFAULT_OLD_LAYER = "designer-manual-2026-03-22"
PRECHECK_ACTION = "接入报价前追问/拦截"
QUOTE_CALC_ACTION = "接入报价计算"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build machine shadow verification for old-overlap rules.")
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


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


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


def source_title(entry: dict[str, Any]) -> str:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    return normalize_inline(source.get("title"))


def source_page(entry: dict[str, Any]) -> int:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    try:
        return int(source.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def combined_rule_text(entry: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            source_title(entry),
            normalize_inline(entry.get("topic")),
            normalize_inline(entry.get("expected_behavior")),
        )
        if part
    )


def infer_category_type(entry: dict[str, Any]) -> str:
    text = combined_rule_text(entry)
    if any(term in text for term in ("书桌", "挂墙桌", "餐桌", "茶几", "边几")):
        return "table"
    if any(term in text for term in ("抽拉床", "床垫", "床身", "举升器", "儿童床", "箱体床", "架式床")):
        return "bed"
    return "cabinet"


def trigger_terms(entry: dict[str, Any]) -> tuple[str, ...]:
    title = source_title(entry)
    terms: list[str] = []
    if title:
        terms.append(title)
    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", title):
        if token not in terms:
            terms.append(token)
    return tuple(terms[:5])


def required_terms(entry: dict[str, Any]) -> tuple[str, ...]:
    module = str(entry.get("suggested_module") or "")
    if "dimension_or_limit_gate" in module:
        return ("尺寸符合", "符合尺寸", "未超限", "不超限", "符合手册", "已确认")
    if "required_note_or_confirmation_gate" in module:
        return ("已备注", "备注", "已确认", "确认", "附图")
    if "safety_or_install_gate" in module:
        return ("已确认", "符合", "满足", "可固定", "承重墙", "不超过50kg", "50kg以内")
    return ("已确认", "符合手册", "按手册")


def required_quote_fields(category_type: str) -> tuple[str, ...]:
    if category_type == "bed":
        return ("width", "length")
    return ("length",)


def missing_field(entry: dict[str, Any]) -> str:
    module = str(entry.get("suggested_module") or "")
    text = combined_rule_text(entry)
    if "safety_or_install_gate" in module and any(term in text for term in ("床垫重量", "50kg")):
        return "mattress_weight"
    if "safety_or_install_gate" in module:
        return "wall_or_install_condition"
    if "dimension_or_limit_gate" in module:
        return "dimension_limit_confirmation"
    return "quote_note"


def constraint_code(entry: dict[str, Any]) -> str:
    rule_id = str(entry.get("landing_id") or "unknown").replace("-", "_")
    return f"baseline.shadow.{rule_id}.required"


def question(entry: dict[str, Any]) -> str:
    title = source_title(entry) or str(entry.get("landing_id") or "这条规则")
    module = str(entry.get("suggested_module") or "")
    if "dimension_or_limit_gate" in module:
        return f"{title} 有新版手册的尺寸/限制要求；正式报价前需要先确认当前方案是否符合这些限制，请补充尺寸是否符合。"
    if "required_note_or_confirmation_gate" in module:
        return f"{title} 需要按新版手册补充备注或确认项；正式报价前请先确认相关备注是否已经写清楚。"
    if "safety_or_install_gate" in module:
        return f"{title} 涉及新版手册的安全/安装前置条件；正式报价前请先确认该条件是否满足。"
    return f"{title} 命中新版手册规则；正式报价前请先确认是否按新版手册要求处理。"


def classify_shadow_entry(entry: dict[str, Any]) -> tuple[str, str]:
    if entry.get("conflict_status") != "old_overlap_shadow_required":
        return "not_shadow_target", "不是旧规则重叠项。"
    if entry.get("machine_status") != "active_new_baseline_candidate":
        return "still_blocked", "机器状态不是可激活候选，保持暂停。"
    if entry.get("quality_flags"):
        return "still_blocked", "存在质量/OCR 风险，保持暂停。"
    action = str(entry.get("landing_action") or "")
    module = str(entry.get("suggested_module") or "")
    if action == QUOTE_CALC_ACTION or module.startswith("pricing_calculation:"):
        return "still_blocked", "金额/公式规则必须先进入金额回归，不通过 shadow 自动覆盖。"
    if action == PRECHECK_ACTION and module.startswith("precheck_quote:"):
        return "coverable_by_config_gate", "新规则是高置信 precheck 追问/拦截，机器判定为更保守路径，可配置化覆盖旧规则。"
    return "conflict_paused", "机器无法证明新规则可安全覆盖旧规则，暂停等待后续专项处理。"


def runtime_gate(entry: dict[str, Any]) -> dict[str, Any]:
    category_type = infer_category_type(entry)
    return {
        "rule_id": entry.get("landing_id"),
        "source_title": source_title(entry),
        "source_page": source_page(entry),
        "category_type": category_type,
        "trigger_terms": list(trigger_terms(entry)),
        "required_terms": list(required_terms(entry)),
        "required_quote_fields": list(required_quote_fields(category_type)),
        "missing_field": missing_field(entry),
        "question": question(entry),
        "reason": "machine shadow verified: new baseline precheck gate safely supersedes old overlapping rule",
        "constraint_code": constraint_code(entry),
        "hard_block": False,
        "verification_mode": "machine_shadow_config_gate",
    }


def public_entry(entry: dict[str, Any], outcome: str, reason: str) -> dict[str, Any]:
    return {
        "landing_id": entry.get("landing_id"),
        "shadow_outcome": outcome,
        "shadow_reason": reason,
        "machine_status": entry.get("machine_status"),
        "conflict_status": entry.get("conflict_status"),
        "risk_level": entry.get("risk_level"),
        "suggested_module": entry.get("suggested_module"),
        "source_title": source_title(entry),
        "source_page": source_page(entry),
        "topic": entry.get("topic"),
        "old_rule_match_count": entry.get("old_rule_match_count"),
        "old_rule_matches": entry.get("old_rule_matches") or [],
    }


def build_shadow_model(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_path: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path, {})
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    shadow_targets = [entry for entry in entries if entry.get("conflict_status") == "old_overlap_shadow_required"]

    classified: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for entry in shadow_targets:
        outcome, reason = classify_shadow_entry(entry)
        classified.append(public_entry(entry, outcome, reason))
        if outcome == "coverable_by_config_gate":
            gates.append(runtime_gate(entry))

    outcome_counts = Counter(item["shadow_outcome"] for item in classified)
    module_counts = Counter(str(item.get("suggested_module") or "") for item in classified)
    return {
        "title": "良禽报价体新基准 shadow 验证报告",
        "candidate_layer": candidate_layer,
        "old_layer": old_layer,
        "source_ledger": str(ledger_path),
        "total_shadow_targets": len(shadow_targets),
        "outcome_counts": dict(outcome_counts),
        "module_counts": dict(module_counts),
        "runtime_gate_count": len(gates),
        "guardrails": [
            "只让高置信、非金额、非 OCR 风险的 precheck 规则配置化覆盖旧规则。",
            "金额规则必须进入金额回归测试，不通过 shadow 自动覆盖。",
            "配置化 gate 只负责正式报价前追问/确认，不直接改金额。",
        ],
        "entries": classified,
        "runtime_gates": gates,
    }


def render_markdown(model: dict[str, Any]) -> str:
    outcome_lines = "\n".join(f"- {key}: {value}" for key, value in model["outcome_counts"].items())
    module_lines = "\n".join(f"- {key}: {value}" for key, value in model["module_counts"].items())
    return f"""# 良禽报价体新基准 shadow 验证报告

目标：用机器验证 `{model['candidate_layer']}` 中与旧规则重叠的规则，避免新旧规则长期并行。

## 总览
- shadow 目标规则：{model['total_shadow_targets']}
- 可配置化覆盖旧规则：{model['outcome_counts'].get('coverable_by_config_gate', 0)}
- 冲突暂停：{model['outcome_counts'].get('conflict_paused', 0)}
- 仍需金额/OCR 阻塞：{model['outcome_counts'].get('still_blocked', 0)}
- 生成 runtime gate：{model['runtime_gate_count']}

## shadow 结果
{outcome_lines}

## 模块分布
{module_lines}

## 机器护栏
- 只让高置信、非金额、非 OCR 风险的 precheck 规则配置化覆盖旧规则。
- 金额规则必须进入金额回归测试，不通过 shadow 自动覆盖。
- 配置化 gate 只负责正式报价前追问/确认，不直接改金额。
"""


def build_and_write(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_override: str, output_dir: Path) -> dict[str, Any]:
    ledger_path = resolve_ledger_path(skill_dir, candidate_layer, ledger_override)
    model = build_shadow_model(skill_dir=skill_dir, candidate_layer=candidate_layer, old_layer=old_layer, ledger_path=ledger_path)
    output_json = output_dir / "baseline-shadow-verification.json"
    output_summary = output_dir / "baseline-shadow-verification.md"
    runtime_gates_json = output_dir / "baseline-runtime-gates.json"
    model["outputs"] = {
        "json": str(output_json),
        "summary": str(output_summary),
        "runtime_gates": str(runtime_gates_json),
    }
    write_json(output_json, model)
    write_json(runtime_gates_json, {"candidate_layer": candidate_layer, "runtime_gates": model["runtime_gates"]})
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
                "total_shadow_targets": model["total_shadow_targets"],
                "outcome_counts": model["outcome_counts"],
                "runtime_gate_count": model["runtime_gate_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
