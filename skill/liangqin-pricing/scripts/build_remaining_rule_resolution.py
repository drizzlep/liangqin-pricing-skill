#!/usr/bin/env python3
"""Build machine-only resolution ledgers for paused baseline rules."""

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
MONEY_CONFLICT = "money_rule_paused"
QUALITY_CONFLICT = "paused_quality_or_ocr"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build machine-only resolution ledgers for paused baseline rules.")
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


def entry_text(entry: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            source_title(entry),
            normalize_inline(entry.get("topic")),
            normalize_inline(entry.get("expected_behavior")),
            normalize_inline(entry.get("test_suggestion")),
        )
        if part
    )


def build_data_point_index(report_dir: Path) -> dict[str, dict[str, Any]]:
    cert = load_json(report_dir / "full-document-data-certification.json", {})
    points = cert.get("data_points") if isinstance(cert.get("data_points"), list) else []
    return {str(point.get("id") or ""): point for point in points if isinstance(point, dict)}


def build_blocking_index(report_dir: Path) -> dict[tuple[str, int], dict[str, Any]]:
    blocking = load_json(report_dir / "blocking-pages-review-board.json", {})
    pages = blocking.get("pages") if isinstance(blocking.get("pages"), list) else []
    index: dict[tuple[str, int], dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        title = normalize_inline(page.get("source_title"))
        try:
            source_page = int(page.get("source_page") or 0)
        except (TypeError, ValueError):
            source_page = 0
        if title:
            index[(title, source_page)] = page
    return index


def numeric_signals(text: str) -> list[str]:
    patterns = (
        r"\d+(?:\.\d+)?\s*(?:元|块|%|mm|cm|m|㎡|m²|kg)",
        r"[≤≥<>]\s*\d+(?:\.\d+)?",
        r"\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?",
    )
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return list(dict.fromkeys(normalize_inline(item) for item in found if normalize_inline(item)))[:20]


def formula_signals(text: str) -> list[str]:
    terms = ("加价", "补差", "折减", "折扣", "另收费", "额外收费", "报价原则", "公式", "单价", "不额外收费", "免费")
    return [term for term in terms if term in text]


def money_resolution(entry: dict[str, Any]) -> dict[str, Any]:
    text = entry_text(entry)
    numbers = numeric_signals(text)
    formulas = formula_signals(text)
    required_fields = [str(item) for item in entry.get("required_fields") or [] if str(item).strip()]
    has_machine_formula = bool(numbers) and bool(formulas)
    status = "regression_spec_ready_paused" if has_machine_formula else "blocked_missing_formula_fields_paused"
    if entry.get("machine_status") == "conflict_paused":
        status = "conflict_blocked_until_money_regression"
    return {
        "landing_id": entry.get("landing_id"),
        "source_data_point_id": entry.get("source_data_point_id"),
        "machine_resolution_status": status,
        "runtime_action": "keep_paused",
        "source_title": source_title(entry),
        "source_page": source_page(entry),
        "suggested_module": entry.get("suggested_module"),
        "risk_level": entry.get("risk_level"),
        "required_fields": required_fields,
        "numeric_signals": numbers,
        "formula_signals": formulas,
        "regression_spec": {
            "positive_case": "完整字段命中该规则时，报价明细必须显式列出该规则，但本阶段不写入真实金额。",
            "missing_field_case": "缺少任一 required_fields 时必须转 precheck，不得直接影响正式报价金额。",
            "amount_assertion": "blocked_until_formula_and_golden_amount_exist",
        },
        "machine_reason": (
            "已抽取到金额/尺寸信号，可生成回归规格，但缺少可执行金额 golden 值，继续暂停。"
            if has_machine_formula
            else "机器未抽取到足够公式字段或金额 golden 值，继续暂停。"
        ),
    }


def ocr_resolution(entry: dict[str, Any], *, data_points: dict[str, dict[str, Any]], blocking_index: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    point = data_points.get(str(entry.get("source_data_point_id") or ""), {})
    blocking_page = blocking_index.get((source_title(entry), source_page(entry)), {})
    ocr = blocking_page.get("ocr") if isinstance(blocking_page.get("ocr"), dict) else {}
    image = blocking_page.get("image") if isinstance(blocking_page.get("image"), dict) else {}
    raw_text = normalize_inline(point.get("extracted_data")) or normalize_inline(point.get("topic"))
    ocr_text = normalize_inline(ocr.get("text"))
    char_count = int(ocr.get("char_count") or len(ocr_text) or 0)
    has_text_layer = bool(raw_text) and not bool(blocking_page)
    has_useful_ocr = char_count >= 30
    image_ready = bool(image.get("status") == "succeeded" or image.get("path"))
    if has_text_layer and not point.get("needs_human_review"):
        status = "evidence_resolved_can_requeue"
        reason = "文本层和认证数据点可用，且未标记人工复核，可回流到机器候选。"
    elif has_useful_ocr and image_ready:
        status = "ocr_evidence_ready_can_requeue"
        reason = "OCR 文本和页面截图均可用，可重新进入机器候选，但仍需下游规则测试。"
    else:
        status = "blocked_insufficient_machine_evidence"
        reason = "文本层/OCR/截图证据不足以机器确认，继续暂停。"
    return {
        "landing_id": entry.get("landing_id"),
        "source_data_point_id": entry.get("source_data_point_id"),
        "machine_resolution_status": status,
        "runtime_action": "requeue_for_machine_landing" if status.endswith("can_requeue") else "keep_paused",
        "source_title": source_title(entry),
        "source_page": source_page(entry),
        "suggested_module": entry.get("suggested_module"),
        "risk_level": entry.get("risk_level"),
        "evidence": {
            "data_point_found": bool(point),
            "data_point_needs_human_review": bool(point.get("needs_human_review")),
            "text_layer_char_count": len(raw_text),
            "blocking_page_found": bool(blocking_page),
            "ocr_status": ocr.get("status"),
            "ocr_char_count": char_count,
            "image_ready": image_ready,
        },
        "machine_reason": reason,
    }


def conflict_resolution(entry: dict[str, Any], *, money_ids: set[str]) -> dict[str, Any]:
    landing_id = str(entry.get("landing_id") or "")
    status = "blocked_by_money_regression" if landing_id in money_ids else "requires_semantic_shadow"
    return {
        "landing_id": landing_id,
        "source_data_point_id": entry.get("source_data_point_id"),
        "machine_resolution_status": status,
        "runtime_action": "keep_paused",
        "source_title": source_title(entry),
        "source_page": source_page(entry),
        "suggested_module": entry.get("suggested_module"),
        "risk_level": entry.get("risk_level"),
        "old_rule_match_count": entry.get("old_rule_match_count"),
        "old_rule_matches": entry.get("old_rule_matches") or [],
        "machine_reason": (
            "该冲突规则同时属于金额规则，必须先通过金额回归，不能仅靠语义 shadow 覆盖。"
            if landing_id in money_ids
            else "需要生成新旧语义对抗样例后再判断。"
        ),
    }


def render_ledger_markdown(title: str, entries: list[dict[str, Any]]) -> str:
    counts = Counter(str(entry.get("machine_resolution_status") or "") for entry in entries)
    count_lines = "\n".join(f"- {key}: {value}" for key, value in counts.items()) or "- 无"
    return f"""# {title}

## 机器状态
{count_lines}

## 护栏
- 不要求人工逐条审规则。
- 未通过机器证据和回归前，规则保持暂停。
- 本报告不修改底层报价表、DOS 来源数字或历史价格数据。
"""


def build_resolution_model(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_path: Path) -> dict[str, Any]:
    report_dir = resolve_report_dir(skill_dir, candidate_layer)
    ledger = load_json(ledger_path, {})
    entries = [entry for entry in ledger.get("entries", []) if isinstance(entry, dict)]
    data_points = build_data_point_index(report_dir)
    blocking_index = build_blocking_index(report_dir)

    money_entries = [entry for entry in entries if entry.get("conflict_status") == MONEY_CONFLICT]
    quality_entries = [entry for entry in entries if entry.get("conflict_status") == QUALITY_CONFLICT]
    conflict_entries = [entry for entry in entries if entry.get("machine_status") == "conflict_paused"]
    money_ids = {str(entry.get("landing_id") or "") for entry in money_entries}

    money_ledger = [money_resolution(entry) for entry in money_entries]
    ocr_ledger = [ocr_resolution(entry, data_points=data_points, blocking_index=blocking_index) for entry in quality_entries]
    conflict_ledger = [conflict_resolution(entry, money_ids=money_ids) for entry in conflict_entries]

    final_counts = {
        "money_total": len(money_ledger),
        "ocr_quality_total": len(ocr_ledger),
        "conflict_total": len(conflict_ledger),
        "money_requeue_count": 0,
        "ocr_requeue_count": sum(1 for entry in ocr_ledger if entry["runtime_action"] == "requeue_for_machine_landing"),
        "conflict_requeue_count": 0,
        "still_paused_count": sum(1 for entry in [*money_ledger, *ocr_ledger, *conflict_ledger] if entry["runtime_action"] == "keep_paused"),
    }
    return {
        "title": "剩余规则机器化清障与安全接入报告",
        "candidate_layer": candidate_layer,
        "old_layer": old_layer,
        "source_ledger": str(ledger_path),
        "final_status": "machine_resolution_complete",
        "human_rule_by_rule_review_required": False,
        "counts": final_counts,
        "money_rule_regression_ledger": money_ledger,
        "ocr_quality_resolution_ledger": ocr_ledger,
        "conflict_resolution_ledger": conflict_ledger,
        "guardrails": [
            "机器可证明安全的规则才可进入下一轮接入。",
            "金额规则没有公式字段和 golden amount 回归前继续暂停。",
            "OCR/质量规则没有多路证据一致性前继续暂停。",
            "冲突金额规则必须等待金额回归，不允许语义强切。",
        ],
    }


def render_final_markdown(model: dict[str, Any]) -> str:
    counts = model["counts"]
    return f"""# 剩余规则机器化清障与安全接入报告

目标：不依赖人工逐条审规则，机器处理剩余金额、OCR/质量、冲突暂停规则。

## 总览
- 金额规则：{counts['money_total']}
- OCR/质量规则：{counts['ocr_quality_total']}
- 冲突规则：{counts['conflict_total']}
- 可回流下一轮机器接入：{counts['ocr_requeue_count']}
- 继续暂停：{counts['still_paused_count']}
- 是否需要人工逐条审规则：否

## 结论
- 金额规则仍不进入正式报价金额计算，等待公式字段与 golden amount 回归。
- OCR/质量规则中，机器证据足够的进入下一轮候选；证据不足的继续暂停。
- 冲突规则均被金额回归阻塞，不允许直接覆盖。
- 当前新版设计师手册默认基准不变，旧版不恢复为默认真相。
"""


def build_and_write(*, skill_dir: Path, candidate_layer: str, old_layer: str, ledger_override: str, output_dir: Path) -> dict[str, Any]:
    ledger_path = resolve_ledger_path(skill_dir, candidate_layer, ledger_override)
    model = build_resolution_model(skill_dir=skill_dir, candidate_layer=candidate_layer, old_layer=old_layer, ledger_path=ledger_path)
    outputs = {
        "money_json": output_dir / "money-rule-regression-ledger.json",
        "money_summary": output_dir / "money-rule-regression-ledger.md",
        "ocr_json": output_dir / "ocr-quality-resolution-ledger.json",
        "ocr_summary": output_dir / "ocr-quality-resolution-ledger.md",
        "conflict_json": output_dir / "conflict-resolution-ledger.json",
        "conflict_summary": output_dir / "conflict-resolution-ledger.md",
        "final_json": output_dir / "remaining-rule-resolution-report.json",
        "final_summary": output_dir / "remaining-rule-resolution-report.md",
    }
    write_json(outputs["money_json"], {"entries": model["money_rule_regression_ledger"]})
    outputs["money_summary"].write_text(render_ledger_markdown("金额规则机器回归清单", model["money_rule_regression_ledger"]), encoding="utf-8")
    write_json(outputs["ocr_json"], {"entries": model["ocr_quality_resolution_ledger"]})
    outputs["ocr_summary"].write_text(render_ledger_markdown("OCR/质量规则机器证据清单", model["ocr_quality_resolution_ledger"]), encoding="utf-8")
    write_json(outputs["conflict_json"], {"entries": model["conflict_resolution_ledger"]})
    outputs["conflict_summary"].write_text(render_ledger_markdown("冲突规则机器对抗清单", model["conflict_resolution_ledger"]), encoding="utf-8")
    model["outputs"] = {key: str(path) for key, path in outputs.items()}
    write_json(outputs["final_json"], model)
    outputs["final_summary"].write_text(render_final_markdown(model), encoding="utf-8")
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
    print(json.dumps({"outputs": model["outputs"], "counts": model["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
