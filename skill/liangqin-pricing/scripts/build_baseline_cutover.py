#!/usr/bin/env python3
"""Build final machine cutover artifacts for the online designer-manual baseline."""

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final machine cutover artifacts.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="New designer manual layer id.")
    parser.add_argument("--old-layer", default=DEFAULT_OLD_LAYER, help="Old designer manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--ledger", default="", help="Override baseline-migration-ledger.json path.")
    parser.add_argument("--output-dir", default="", help="Override output directory.")
    return parser.parse_args(argv)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def resolve_money_pack_path(skill_dir: Path, layer: str) -> Path:
    return resolve_report_dir(skill_dir, layer) / "money-rule-regression-pack.json"


def manifest_status(skill_dir: Path, layer: str) -> str:
    manifest = load_json(skill_dir / "references" / "addenda" / layer / "manifest.json", {})
    return str(manifest.get("status") or "").strip().upper()


def load_shadow_builder(skill_dir: Path) -> Any:
    return load_module(
        "build_baseline_shadow_verification_for_cutover",
        skill_dir / "scripts" / "build_baseline_shadow_verification.py",
    )


def is_ready_precheck(entry: dict[str, Any]) -> bool:
    return (
        entry.get("machine_status") == "active_new_baseline_candidate"
        and str(entry.get("suggested_module") or "").startswith("precheck_quote:")
        and not entry.get("quality_flags")
        and str(entry.get("landing_action") or "") == "接入报价前追问/拦截"
    )


def money_cutover_guard(money_pack: dict[str, Any], *, expected_count: int = 20) -> dict[str, Any]:
    counts = money_pack.get("counts") if isinstance(money_pack.get("counts"), dict) else {}
    rules = money_pack.get("rules") if isinstance(money_pack.get("rules"), list) else []
    failures: list[str] = []

    if counts.get("money_rule_total") != expected_count:
        failures.append("money_rule_total_mismatch")
    if counts.get("activated_count") != expected_count:
        failures.append("activated_count_mismatch")
    if counts.get("still_paused_count") != 0:
        failures.append("still_paused_count_not_zero")
    if counts.get("golden_amount_ready_count") != expected_count:
        failures.append("golden_ready_count_mismatch")
    if counts.get("golden_amount_blocked_count") != 0:
        failures.append("golden_blocked_count_not_zero")

    blocked_rule_ids: list[str] = []
    regression_failed_rule_ids: list[str] = []
    non_ready_source_rule_ids: list[str] = []
    zero_impact_rule_ids: list[str] = []
    zero_impact_amount_failures: list[str] = []
    old_runtime_source_rule_ids: list[str] = []
    route_counts: Counter[str] = Counter()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("landing_id") or "").strip()
        amount_source = rule.get("amount_source") if isinstance(rule.get("amount_source"), dict) else {}
        regression_result = rule.get("regression_result") if isinstance(rule.get("regression_result"), dict) else {}
        runtime_route = str(amount_source.get("runtime_route") or "").strip()
        route_counts[runtime_route] += 1
        if rule.get("runtime_action") != "activate_formal_amount_calculation":
            blocked_rule_ids.append(rule_id)
        if regression_result.get("status") != "passed":
            regression_failed_rule_ids.append(rule_id)
        if amount_source.get("status") != "ready":
            non_ready_source_rule_ids.append(rule_id)
        if str(amount_source.get("source_type") or "").startswith("old_"):
            old_runtime_source_rule_ids.append(rule_id)
        if runtime_route == "special_adjustment.manual_zero_impact":
            zero_impact_rule_ids.append(rule_id)
            if amount_source.get("expected_amount") != 0 or regression_result.get("actual_amount") != 0:
                zero_impact_amount_failures.append(rule_id)

    if blocked_rule_ids:
        failures.append("rules_not_activated")
    if regression_failed_rule_ids:
        failures.append("regression_not_passed")
    if non_ready_source_rule_ids:
        failures.append("amount_source_not_ready")
    if zero_impact_amount_failures:
        failures.append("zero_impact_amount_changed")
    if old_runtime_source_rule_ids:
        failures.append("old_runtime_source_used")

    passed = not failures and len(rules) == expected_count
    return {
        "status": "passed" if passed else "failed",
        "expected_money_rule_count": expected_count,
        "counts": counts,
        "route_counts": dict(route_counts),
        "zero_impact_rule_ids": zero_impact_rule_ids,
        "zero_impact_rule_count": len(zero_impact_rule_ids),
        "failures": failures,
        "blocked_rule_ids": blocked_rule_ids,
        "regression_failed_rule_ids": regression_failed_rule_ids,
        "non_ready_source_rule_ids": non_ready_source_rule_ids,
        "zero_impact_amount_failures": zero_impact_amount_failures,
        "old_runtime_source_rule_ids": old_runtime_source_rule_ids,
    }


def build_cutover_model(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_path: Path) -> dict[str, Any]:
    shadow_builder = load_shadow_builder(skill_dir)
    ledger = load_json(ledger_path, {})
    money_pack_path = resolve_money_pack_path(skill_dir, candidate_layer)
    money_pack = load_json(money_pack_path, {})
    money_guard = money_cutover_guard(money_pack)
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    ready_precheck_entries = [entry for entry in entries if is_ready_precheck(entry)]
    runtime_gates = [shadow_builder.runtime_gate(entry) for entry in ready_precheck_entries]

    money_paused = [entry for entry in entries if entry.get("conflict_status") == "money_rule_paused"]
    quality_paused = [entry for entry in entries if entry.get("conflict_status") == "paused_quality_or_ocr"]
    conflict_paused = [entry for entry in entries if entry.get("machine_status") == "conflict_paused"]
    runtime_gate_ids = {str(gate.get("rule_id") or "") for gate in runtime_gates}

    candidate_status = manifest_status(skill_dir, candidate_layer)
    old_status = manifest_status(skill_dir, old_layer)
    cutover_complete = (
        candidate_status == "ACTIVE"
        and old_status != "ACTIVE"
        and money_guard["status"] == "passed"
        and len(runtime_gate_ids) == len(ready_precheck_entries)
        and bool(runtime_gate_ids)
    )

    return {
        "title": "良禽报价体新设计师手册基准 cutover 报告",
        "candidate_layer": candidate_layer,
        "old_layer": old_layer,
        "source_ledger": str(ledger_path),
        "source_money_regression_pack": str(money_pack_path),
        "cutover_status": "complete" if cutover_complete else "in_progress",
        "maintenance_status": "COMPLETED_MAINTENANCE" if cutover_complete else "CUTOVER_IN_PROGRESS",
        "maintenance_summary": "迁移线已完成并进入维护状态。" if cutover_complete else "迁移线仍在 cutover 收口中。",
        "layer_status": {
            "candidate": candidate_status,
            "old": old_status,
            "old_runtime_truth": "disabled" if old_status != "ACTIVE" else "still_active",
        },
        "money_cutover_guard": money_guard,
        "counts": {
            "total_rules": len(entries),
            "ready_precheck_rules": len(ready_precheck_entries),
            "runtime_gate_count": len(runtime_gates),
            "money_rule_historical_paused_count": len(money_paused),
            "money_rule_paused_count": int((money_guard.get("counts") or {}).get("still_paused_count") or 0),
            "money_rule_activated_count": int((money_guard.get("counts") or {}).get("activated_count") or 0),
            "quality_or_ocr_paused_count": len(quality_paused),
            "conflict_paused_count": len(conflict_paused),
        },
        "module_counts": dict(Counter(str(entry.get("suggested_module") or "") for entry in ready_precheck_entries)),
        "runtime_gate_ids": sorted(runtime_gate_ids),
        "runtime_gates": runtime_gates,
        "paused": {
            "money_rule_ids": [str(entry.get("landing_id") or "") for entry in money_paused],
            "quality_or_ocr_rule_ids": [str(entry.get("landing_id") or "") for entry in quality_paused],
            "conflict_rule_ids": [str(entry.get("landing_id") or "") for entry in conflict_paused],
        },
        "guardrails": [
            "新版设计师手册是默认报价基准。",
            "旧版设计师手册只保留为 shadow/回归证据，不作为默认运行真相。",
            "金额规则必须满足 20/20 activated、0 paused、全部 runtime regression passed。",
            "zero-impact 结构规则只能输出 0 元，不得改变真实报价金额。",
            "OCR/质量风险规则保持暂停，不进入正式报价链路。",
        ],
    }


def render_markdown(model: dict[str, Any]) -> str:
    counts = model["counts"]
    money_guard = model["money_cutover_guard"]
    money_counts = money_guard["counts"]
    module_lines = "\n".join(f"- {key}: {value}" for key, value in model["module_counts"].items())
    return f"""# 良禽报价体新设计师手册基准 Cutover 报告

目标：将 `{model['candidate_layer']}` 作为良禽报价体默认基准，旧版仅保留为 shadow/回归证据。

## Cutover 状态
- 状态：{model['cutover_status']}
- 维护状态：{model['maintenance_status']}
- 维护说明：{model['maintenance_summary']}
- 新版层状态：{model['layer_status']['candidate']}
- 旧版层状态：{model['layer_status']['old']}
- 旧版是否仍是默认运行真相：{model['layer_status']['old_runtime_truth']}

## 机器接入结果
- 新规则总数：{counts['total_rules']}
- 机器可验证 precheck 规则：{counts['ready_precheck_rules']}
- 配置驱动 runtime gate：{counts['runtime_gate_count']}
- 金额规则激活：{counts['money_rule_activated_count']}
- 金额规则暂停：{counts['money_rule_paused_count']}
- 历史 ledger 金额暂停记录：{counts['money_rule_historical_paused_count']}（仅作 shadow/迁移证据）
- OCR/质量暂停：{counts['quality_or_ocr_paused_count']}
- 冲突暂停：{counts['conflict_paused_count']}

## 金额 Cutover Guard
- 状态：{money_guard['status']}
- 金额规则总数：{money_counts.get('money_rule_total', 0)}
- golden ready：{money_counts.get('golden_amount_ready_count', 0)}
- golden blocked：{money_counts.get('golden_amount_blocked_count', 0)}
- zero-impact 规则：{money_guard['zero_impact_rule_count']}
- 失败项：{', '.join(money_guard['failures']) if money_guard['failures'] else '无'}

## precheck 模块分布
{module_lines}

## 机器护栏
- 新版设计师手册是默认报价基准。
- 旧版设计师手册只保留为 shadow/回归证据，不作为默认运行真相。
- 金额规则必须满足 20/20 activated、0 paused、全部 runtime regression passed。
- zero-impact 结构规则只能输出 0 元，不得改变真实报价金额。
- OCR/质量风险规则保持暂停，不进入正式报价链路。
"""


def render_html(model: dict[str, Any]) -> str:
    counts = model["counts"]
    money_guard = model["money_cutover_guard"]
    status_label = "已完全切换" if model["cutover_status"] == "complete" else "仍需阻断"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>良禽报价体金额 Cutover Guard</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f1e8; color: #2f281f; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 40px 24px; }}
    .hero {{ background: #1f342b; color: #fffaf0; border-radius: 28px; padding: 32px; box-shadow: 0 18px 50px rgba(31,52,43,.18); }}
    .hero small {{ color: #d7c7a4; letter-spacing: .12em; text-transform: uppercase; }}
    h1 {{ margin: 8px 0 10px; font-size: 36px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 22px 0; }}
    .card {{ background: #fffaf0; border: 1px solid #e4d8c2; border-radius: 20px; padding: 18px; }}
    .card b {{ display: block; font-size: 30px; color: #1f342b; }}
    .card span {{ color: #736654; }}
    .ok {{ color: #476b3d; font-weight: 700; }}
    .warn {{ color: #9a4b26; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: #fffaf0; border-radius: 18px; overflow: hidden; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid #eadfcb; text-align: left; }}
    th {{ background: #eadfcb; color: #4b3f30; }}
    code {{ background: #efe3ce; padding: 2px 6px; border-radius: 8px; }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <small>Money Cutover Guard</small>
    <h1>{status_label}</h1>
    <p>{model['maintenance_summary']} 新版设计师手册是默认报价基准；旧版只保留为 shadow/回归证据。金额规则必须保持 20/20 activated、0 paused。</p>
  </section>
  <section class="grid">
    <div class="card"><b>{counts['money_rule_activated_count']}</b><span>金额规则已激活</span></div>
    <div class="card"><b>{counts['money_rule_paused_count']}</b><span>金额规则暂停</span></div>
    <div class="card"><b>{money_guard['zero_impact_rule_count']}</b><span>zero-impact 规则</span></div>
    <div class="card"><b>{counts['runtime_gate_count']}</b><span>precheck runtime gates</span></div>
  </section>
  <section class="card">
    <h2>机器护栏</h2>
    <table>
      <tr><th>检查项</th><th>结果</th></tr>
      <tr><td>金额规则 20/20 activated</td><td class="{ 'ok' if counts['money_rule_activated_count'] == 20 else 'warn' }">{counts['money_rule_activated_count']}/20</td></tr>
      <tr><td>金额规则 0 paused</td><td class="{ 'ok' if counts['money_rule_paused_count'] == 0 else 'warn' }">{counts['money_rule_paused_count']}</td></tr>
      <tr><td>金额 runtime regression</td><td class="{ 'ok' if money_guard['status'] == 'passed' else 'warn' }">{money_guard['status']}</td></tr>
      <tr><td>旧版 runtime truth</td><td class="{ 'ok' if model['layer_status']['old_runtime_truth'] == 'disabled' else 'warn' }">{model['layer_status']['old_runtime_truth']}</td></tr>
      <tr><td>zero-impact 金额污染</td><td class="{ 'ok' if not money_guard['zero_impact_amount_failures'] else 'warn' }">{'无' if not money_guard['zero_impact_amount_failures'] else ', '.join(money_guard['zero_impact_amount_failures'])}</td></tr>
    </table>
  </section>
  <section class="card">
    <h2>证据文件</h2>
    <p><code>{model['source_money_regression_pack']}</code></p>
    <p><code>{model['source_ledger']}</code></p>
  </section>
</main>
</body>
</html>
"""


def build_and_write(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_override: str, output_dir: Path) -> dict[str, Any]:
    ledger_path = resolve_ledger_path(skill_dir, candidate_layer, ledger_override)
    model = build_cutover_model(skill_dir=skill_dir, candidate_layer=candidate_layer, old_layer=old_layer, ledger_path=ledger_path)
    output_json = output_dir / "baseline-cutover-report.json"
    output_summary = output_dir / "baseline-cutover-report.md"
    output_board = output_dir / "baseline-cutover-board.html"
    runtime_gates_json = output_dir / "baseline-runtime-gates.json"
    model["outputs"] = {
        "json": str(output_json),
        "summary": str(output_summary),
        "board": str(output_board),
        "runtime_gates": str(runtime_gates_json),
    }
    write_json(output_json, model)
    write_json(runtime_gates_json, {"candidate_layer": candidate_layer, "runtime_gates": model["runtime_gates"]})
    output_summary.write_text(render_markdown(model), encoding="utf-8")
    output_board.write_text(render_html(model), encoding="utf-8")
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
                "cutover_status": model["cutover_status"],
                "layer_status": model["layer_status"],
                "counts": model["counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
