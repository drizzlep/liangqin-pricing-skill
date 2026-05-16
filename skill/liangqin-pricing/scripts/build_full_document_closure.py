#!/usr/bin/env python3
"""Close the full designer-manual ledger without leaving human-review limbo."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"
RUNTIME_RULE = "runtime_rule"
KNOWLEDGE_READY = "knowledge_ready"
EXCLUDED_BACKGROUND = "excluded_background"
NOT_SAFE = "not_safe_for_auto_answer"
SOURCE_RECHECK = "needs_source_recheck"
RESOLVED_FROM_REVIEW = {KNOWLEDGE_READY, NOT_SAFE, SOURCE_RECHECK}
KNOWN_RESOLUTIONS = {RUNTIME_RULE, KNOWLEDGE_READY, EXCLUDED_BACKGROUND, NOT_SAFE, SOURCE_RECHECK}

MONEY_OR_FORMULA_TERMS = ("报价", "加价", "补差", "折减", "公式", "单价", "价格", "收费", "差价")
HARD_RULE_TERMS = ("必须", "不得", "不可", "不能", "尺寸限制", "安全", "上限", "下限", "需备注", "需要备注")
NEGATED_CONTEXT_TERMS = ("不含", "不涉及", "无", "没有", "未涉及", "不包括", "非")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build full-document closure artifacts for an addendum layer.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="Designer manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
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
    spec.loader.exec_module(module)
    return module


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def excerpt(value: Any, limit: int = 180) -> str:
    text = normalize_inline(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def resolve_report_dir(skill_dir: Path, candidate_layer: str) -> Path:
    manifest_path = skill_dir / "references" / "addenda" / candidate_layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    raw = artifacts.get("rules_candidate_file")
    if not raw:
        return skill_dir / "reports" / "addenda" / candidate_layer
    path = Path(str(raw))
    return (path if path.is_absolute() else (manifest_path.parent / path).resolve()).parent


def page_key(value: dict[str, Any]) -> tuple[str, int]:
    try:
        page = int(value.get("source_page") or value.get("page") or 0)
    except (TypeError, ValueError):
        page = 0
    return (normalize_inline(value.get("source_title")), page)


def text_len(value: Any) -> int:
    return len(re.sub(r"\s+", "", str(value or "")))


def contains_unnegated_term(text: str, terms: tuple[str, ...]) -> bool:
    normalized = normalize_inline(text)
    for term in terms:
        for match in re.finditer(re.escape(term), normalized):
            prefix = normalized[max(0, match.start() - 14) : match.start()]
            if any(negation in prefix for negation in NEGATED_CONTEXT_TERMS):
                continue
            return True
    return False


def build_blocking_page_index(report_dir: Path) -> dict[tuple[str, int], dict[str, Any]]:
    blocking = load_json(report_dir / "blocking-pages-review-board.json", {"pages": []})
    pages = blocking.get("pages") if isinstance(blocking.get("pages"), list) else []
    return {page_key(page): page for page in pages if isinstance(page, dict)}


def build_quality_sample_index(report_dir: Path) -> dict[tuple[str, int], dict[str, Any]]:
    quality = load_json(report_dir / "quality-sample-board.json", {"samples": []})
    samples = quality.get("samples") if isinstance(quality.get("samples"), list) else []
    return {page_key(sample): sample for sample in samples if isinstance(sample, dict)}


def resolve_unknown_page(page: dict[str, Any], *, blocking: dict[tuple[str, int], dict[str, Any]], quality: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    key = page_key(page)
    blocking_page = blocking.get(key, {})
    quality_page = quality.get(key, {})
    evidence = blocking_page or quality_page or page
    ocr = evidence.get("ocr") if isinstance(evidence.get("ocr"), dict) else {}
    image = evidence.get("image") if isinstance(evidence.get("image"), dict) else evidence.get("render") if isinstance(evidence.get("render"), dict) else {}
    decision = normalize_inline(evidence.get("default_decision"))
    ocr_chars = int(ocr.get("char_count") or text_len(ocr.get("text")) or 0)
    image_ready = bool(image.get("status") == "succeeded" or image.get("path"))
    high_risk_text = " ".join([normalize_inline(page.get("source_title")), normalize_inline(ocr.get("text"))])
    high_risk = contains_unnegated_term(high_risk_text, MONEY_OR_FORMULA_TERMS + HARD_RULE_TERMS)

    if ocr_chars >= 80 and not high_risk:
        status = "machine_extractable_knowledge"
        runtime_action = "requeue_as_knowledge"
        reason = "OCR 文字足够且未命中金额/安全/限制高风险词，可作为知识候选回流。"
    elif decision == "OCR 可用" and ocr_chars >= 20:
        status = "machine_extractable_needs_rule_test"
        runtime_action = "requeue_for_rule_test"
        reason = "OCR 可用，但仍需下游规则测试后才能进入报价链路。"
    elif decision == "不影响规则":
        status = "not_machine_readable_excluded"
        runtime_action = "exclude_from_runtime"
        reason = "阻断页复核默认判断为不影响规则，闭环为不进入自动链路。"
    elif image_ready:
        status = "manual_source_only"
        runtime_action = "keep_as_evidence_only"
        reason = "截图证据可用，但机器文字证据不足；仅保留为人工证据，不进入自动回答。"
    else:
        status = "needs_source_recheck"
        runtime_action = "exclude_until_source_recheck"
        reason = "既无足够 OCR，也无稳定截图证据；需要源文件复核。"

    return {
        "source_title": key[0],
        "source_page": key[1],
        "source_local_path": normalize_inline(page.get("source_local_path")),
        "image_count": int(page.get("image_count") or 0),
        "resolution_status": status,
        "runtime_action": runtime_action,
        "reason": reason,
        "evidence": {
            "blocking_page_found": bool(blocking_page),
            "quality_sample_found": bool(quality_page),
            "default_decision": decision,
            "ocr_status": ocr.get("status"),
            "ocr_char_count": ocr_chars,
            "image_ready": image_ready,
        },
    }


def build_unknown_page_ledger(report_dir: Path) -> dict[str, Any]:
    candidate = load_json(report_dir / "rules-candidate.json", {"pages": []})
    pages = [page for page in candidate.get("pages", []) if isinstance(page, dict)]
    unknown_pages = [page for page in pages if str(page.get("extract_method")) == "unknown"]
    blocking = build_blocking_page_index(report_dir)
    quality = build_quality_sample_index(report_dir)
    entries = [resolve_unknown_page(page, blocking=blocking, quality=quality) for page in unknown_pages]
    counts = Counter(entry["resolution_status"] for entry in entries)
    return {
        "title": "新版设计师手册未知页机器闭环清单",
        "unknown_page_count": len(entries),
        "resolution_counts": dict(counts),
        "entries": entries,
    }


def classify_manual_review_entry(entry: dict[str, Any], *, unknown_page_statuses: dict[tuple[str, int], str]) -> tuple[str, str]:
    key = page_key(entry)
    page_status = unknown_page_statuses.get(key, "")
    summary = normalize_inline(entry.get("summary"))
    topic = normalize_inline(entry.get("topic"))
    source_title = normalize_inline(entry.get("source_title"))
    text = " ".join([topic, summary, source_title])
    if not summary or not topic or not source_title:
        return SOURCE_RECHECK, "缺少稳定摘要、主题或来源标题，闭环为源证据复核。"
    if page_status in {"manual_source_only", "needs_source_recheck"}:
        return SOURCE_RECHECK, f"来源页状态为 {page_status}，不进入自动链路。"
    if contains_unnegated_term(text, MONEY_OR_FORMULA_TERMS) or contains_unnegated_term(text, HARD_RULE_TERMS):
        return NOT_SAFE, "含金额、公式、安全或强限制信号，但未完成专项运行测试，闭环为不自动回答。"
    return KNOWLEDGE_READY, "文本证据和来源完整，且未命中高风险报价/安全信号，可作为设计师咨询知识。"


def looks_like_closed_review_state(entry: dict[str, Any]) -> bool:
    return str(entry.get("status") or "") in RESOLVED_FROM_REVIEW or str(entry.get("rule_layer_status") or "") in {
        "knowledge",
        "not_auto",
        "source_recheck",
    }


def preserved_original_value(
    entry: dict[str, Any],
    *,
    original_key: str,
    current_key: str,
    review_fallback: str,
) -> str:
    original = str(entry.get(original_key) or "")
    current = str(entry.get(current_key) or "")
    resolution = str(entry.get("closure_resolution") or "")
    if original and original != current:
        return original
    if resolution in RESOLVED_FROM_REVIEW or looks_like_closed_review_state(entry):
        return review_fallback
    return original or current


def close_coverage_ledger(report_dir: Path, *, unknown_page_ledger: dict[str, Any]) -> dict[str, Any]:
    coverage_path = report_dir / "coverage-ledger.json"
    original = load_json(coverage_path, {"entries": []})
    entries = [entry for entry in original.get("entries", []) if isinstance(entry, dict)]
    unknown_statuses = {
        (entry["source_title"], int(entry["source_page"])): str(entry["resolution_status"])
        for entry in unknown_page_ledger.get("entries", [])
        if isinstance(entry, dict)
    }
    closed_entries: list[dict[str, Any]] = []
    resolution_counts: Counter[str] = Counter()
    for entry in entries:
        closed = dict(entry)
        existing_resolution = str(entry.get("closure_resolution") or "")
        original_status = preserved_original_value(entry, original_key="original_status", current_key="status", review_fallback="unresolved")
        original_publish_target = preserved_original_value(
            entry,
            original_key="original_publish_target",
            current_key="publish_target",
            review_fallback="manual_review",
        )
        original_rule_layer_status = preserved_original_value(
            entry,
            original_key="original_rule_layer_status",
            current_key="rule_layer_status",
            review_fallback="manual_review",
        )
        closed["original_status"] = original_status
        closed["original_publish_target"] = original_publish_target
        closed["original_rule_layer_status"] = original_rule_layer_status

        if (
            str(entry.get("status") or "") == NOT_SAFE
            or str(entry.get("rule_layer_status") or "") == "not_auto"
            or original_status == NOT_SAFE
            or original_rule_layer_status == "not_auto"
        ):
            resolution, reason = NOT_SAFE, "已闭环为不适合自动回答，保持不可自动开放。"
            closed.update({"status": NOT_SAFE, "publish_target": "none", "rule_layer_status": "not_auto"})
        elif (
            str(entry.get("status") or "") == SOURCE_RECHECK
            or str(entry.get("rule_layer_status") or "") == "source_recheck"
            or original_status == SOURCE_RECHECK
            or original_rule_layer_status == "source_recheck"
        ):
            resolution, reason = SOURCE_RECHECK, "已闭环为源证据复核，保持不可自动开放。"
            closed.update({"status": SOURCE_RECHECK, "publish_target": "none", "rule_layer_status": "source_recheck"})
        elif str(entry.get("status") or "") == KNOWLEDGE_READY or str(entry.get("rule_layer_status") or "") == "knowledge":
            resolution, reason = KNOWLEDGE_READY, "已闭环为知识层，保持设计师咨询知识。"
            closed.update({"status": KNOWLEDGE_READY, "publish_target": "knowledge", "rule_layer_status": "knowledge"})
        elif existing_resolution in KNOWN_RESOLUTIONS:
            resolution = existing_resolution
            reason = str(entry.get("closure_reason") or "沿用已完成的全书闭环分类。")
            if resolution == RUNTIME_RULE:
                closed.update({"status": "runtime_hard_rule", "publish_target": "runtime", "rule_layer_status": "runtime"})
            elif resolution == EXCLUDED_BACKGROUND:
                closed.update({"status": EXCLUDED_BACKGROUND, "publish_target": "none", "rule_layer_status": "excluded"})
            elif resolution == KNOWLEDGE_READY:
                closed.update({"status": KNOWLEDGE_READY, "publish_target": "knowledge", "rule_layer_status": "knowledge"})
            elif resolution == NOT_SAFE:
                closed.update({"status": NOT_SAFE, "publish_target": "none", "rule_layer_status": "not_auto"})
            else:
                closed.update({"status": SOURCE_RECHECK, "publish_target": "none", "rule_layer_status": "source_recheck"})
        elif original_publish_target == "runtime" or original_status == "runtime_hard_rule" or original_rule_layer_status == "runtime":
            resolution, reason = RUNTIME_RULE, "已接入 runtime，保持运行规则。"
            closed.update({"status": "runtime_hard_rule", "publish_target": "runtime", "rule_layer_status": "runtime"})
        elif original_status == "excluded_background" or original_publish_target == "none" or original_rule_layer_status == "excluded":
            resolution, reason = EXCLUDED_BACKGROUND, "已明确为背景或不开放内容，保持排除。"
            closed.update({"status": EXCLUDED_BACKGROUND, "publish_target": "none", "rule_layer_status": "excluded"})
        else:
            resolution, reason = classify_manual_review_entry(entry, unknown_page_statuses=unknown_statuses)
            if resolution == KNOWLEDGE_READY:
                closed.update({"status": KNOWLEDGE_READY, "publish_target": "knowledge", "rule_layer_status": "knowledge"})
            elif resolution == NOT_SAFE:
                closed.update({"status": NOT_SAFE, "publish_target": "none", "rule_layer_status": "not_auto"})
            else:
                closed.update({"status": SOURCE_RECHECK, "publish_target": "none", "rule_layer_status": "source_recheck"})

        closed["closure_resolution"] = resolution
        closed["closure_reason"] = reason
        resolution_counts[resolution] += 1
        closed_entries.append(closed)

    closed = dict(original)
    closed["closure_status"] = "complete"
    closed["human_rule_by_rule_review_required"] = False
    closed["status_counts"] = dict(Counter(str(entry.get("status") or "") for entry in closed_entries))
    closed["publish_target_counts"] = dict(Counter(str(entry.get("publish_target") or "") for entry in closed_entries))
    closed["closure_resolution_counts"] = dict(resolution_counts)
    closed["entries"] = closed_entries
    write_json(coverage_path, closed)
    return closed


def build_knowledge_layer(report_dir: Path, *, candidate_layer: str, coverage: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for entry in coverage.get("entries", []):
        if not isinstance(entry, dict) or entry.get("closure_resolution") != KNOWLEDGE_READY:
            continue
        entries.append(
            {
                "topic": normalize_inline(entry.get("topic")),
                "answerable_summary": normalize_inline(entry.get("summary")),
                "evidence_level": "machine_full_document_closure",
                "source_pages": [entry.get("source_page")] if entry.get("source_page") else [],
                "source_title": normalize_inline(entry.get("source_title")),
                "trigger_terms": [term for term in [normalize_inline(entry.get("source_title")), normalize_inline(entry.get("topic"))] if term],
                "do_not_overclaim": "这条来自全书机器闭环知识层，只能按当前摘要解释；涉及报价、尺寸、安全或下单约束时需转人工或专项规则。",
            }
        )
    layer = {
        "layer_id": candidate_layer,
        "layer_name": "设计师手册全书闭环知识层",
        "entries": entries,
    }
    write_json(report_dir / "knowledge-layer.json", layer)
    return layer


def run_certification_builder(skill_dir: Path, candidate_layer: str) -> dict[str, Any]:
    module = load_module("build_full_document_data_certification_for_closure", skill_dir / "scripts" / "build_full_document_data_certification.py")
    model = module.build_certification_model(skill_dir=skill_dir, candidate_layer=candidate_layer)
    report_dir = resolve_report_dir(skill_dir, candidate_layer)
    model["output_json"] = str(report_dir / "full-document-data-certification.json")
    model["output_html"] = str(report_dir / "full-document-data-certification.html")
    module.write_json(report_dir / "full-document-data-certification.json", model)
    (report_dir / "full-document-data-certification.html").write_text(module.render_html(model), encoding="utf-8")
    return model


def render_markdown(model: dict[str, Any]) -> str:
    counts = model["closure_counts"]
    review_counts = model["closed_review_resolution_counts"]
    unknown_counts = model["unknown_page_resolution_counts"]
    return f"""# 新版设计师手册全书闭环报告

- 状态：{model['closure_status']}
- 候选层：{model['candidate_layer']}
- 总数据点：{model['entry_count']}
- 原待复核项闭环：{model['closed_review_item_count']}
- runtime 规则：{counts.get(RUNTIME_RULE, 0)}
- 知识层：{counts.get(KNOWLEDGE_READY, 0)}
- 排除背景：{counts.get(EXCLUDED_BACKGROUND, 0)}
- 不自动回答：{counts.get(NOT_SAFE, 0)}
- 源证据复核但不开放：{counts.get(SOURCE_RECHECK, 0)}
- 未知页：{model['unknown_page_count']}

## 未知页闭环
{chr(10).join(f'- {key}: {value}' for key, value in unknown_counts.items()) or '- 无'}

## 原待复核项闭环
{chr(10).join(f'- {key}: {value}' for key, value in review_counts.items()) or '- 无'}

## 发布口径
- `coverage-ledger.json` 已不保留 `unresolved` / `manual_review` 作为最终状态。
- 未经过专项测试的高风险金额、公式、安全、尺寸限制内容不会自动进入报价。
- 可发布技能包只应包含运行必需文件和闭环报告，不应包含原始 PDF、页面大图或 OCR 裁图。
"""


def render_html(model: dict[str, Any]) -> str:
    counts = model["closure_counts"]
    unknown_counts = model["unknown_page_resolution_counts"]
    cards = "\n".join(
        f"<article><b>{esc(label)}</b><span>{esc(value)}</span></article>"
        for label, value in [
            ("runtime 规则", counts.get(RUNTIME_RULE, 0)),
            ("知识层", counts.get(KNOWLEDGE_READY, 0)),
            ("排除背景", counts.get(EXCLUDED_BACKGROUND, 0)),
            ("不自动回答", counts.get(NOT_SAFE, 0)),
            ("源证据复核", counts.get(SOURCE_RECHECK, 0)),
            ("未知页", model.get("unknown_page_count", 0)),
            ("原待复核项", model.get("closed_review_item_count", 0)),
        ]
    )
    unknown = "\n".join(f"<li>{esc(key)}: {esc(value)}</li>" for key, value in unknown_counts.items())
    review = "\n".join(f"<li>{esc(key)}: {esc(value)}</li>" for key, value in model["closed_review_resolution_counts"].items())
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>新版设计师手册全书闭环</title>
  <style>
    body {{ margin:0; font-family:"Songti SC","Noto Serif CJK SC",serif; color:#281f17; background:#f7efe3; }}
    main {{ max-width:1120px; margin:0 auto; padding:42px 20px 72px; }}
    .hero, article, section {{ background:#fffaf1; border:1px solid #dfcdb6; border-radius:24px; box-shadow:0 18px 50px rgba(80,48,20,.08); }}
    .hero {{ padding:32px; }}
    h1 {{ margin:8px 0 12px; font-size:44px; line-height:1.08; }}
    .status {{ display:inline-flex; border-radius:999px; background:#edf6ea; color:#416d46; padding:8px 14px; font-weight:800; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; margin:20px 0; }}
    article {{ padding:20px; }}
    article b {{ display:block; color:#825431; font-size:15px; }}
    article span {{ display:block; font-size:34px; font-weight:900; margin-top:8px; }}
    section {{ padding:22px; line-height:1.8; margin-top:16px; }}
    @media(max-width:760px) {{ .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:32px; }} }}
  </style>
</head>
<body>
  <main>
    <div class="hero">
      <div class="status">{esc(model['closure_status'])}</div>
      <h1>新版设计师手册全书闭环完成</h1>
      <p>本页是发布前的人类入口：所有原 `manual_review/unresolved` 项均已改写为明确的机器闭环状态；未知页也已落入可抽取、排除、仅人工证据或源证据复核，不再阻塞技能封装。</p>
    </div>
    <div class="grid">{cards}</div>
    <section>
      <h2>未知页处理</h2>
      <ul>{unknown}</ul>
    </section>
    <section>
      <h2>原待复核项处理</h2>
      <ul>{review}</ul>
    </section>
    <section>
      <h2>发布护栏</h2>
      <p>本闭环不代表所有手册内容都自动参与报价。高风险金额、公式、安全和尺寸限制内容，未通过专项测试前只会保留为不自动回答或源证据复核状态。</p>
    </section>
  </main>
</body>
</html>
"""


def build_closure_model(*, skill_dir: Path, candidate_layer: str, output_dir: Path | None = None) -> dict[str, Any]:
    report_dir = output_dir or resolve_report_dir(skill_dir, candidate_layer)
    unknown_ledger = build_unknown_page_ledger(report_dir)
    write_json(report_dir / "unknown-page-resolution-ledger.json", unknown_ledger)
    coverage = close_coverage_ledger(report_dir, unknown_page_ledger=unknown_ledger)
    knowledge_layer = build_knowledge_layer(report_dir, candidate_layer=candidate_layer, coverage=coverage)
    certification = run_certification_builder(skill_dir, candidate_layer)
    closure_counts = coverage.get("closure_resolution_counts") if isinstance(coverage.get("closure_resolution_counts"), dict) else {}
    closed_review_resolution_counts = Counter(
        str(entry.get("closure_resolution") or "")
        for entry in coverage.get("entries", [])
        if isinstance(entry, dict) and str(entry.get("closure_resolution") or "") in RESOLVED_FROM_REVIEW
    )
    model = {
        "title": "新版设计师手册全书闭环报告",
        "candidate_layer": candidate_layer,
        "closure_status": "complete",
        "human_rule_by_rule_review_required": False,
        "entry_count": len(coverage.get("entries", [])),
        "coverage_status_counts": coverage.get("status_counts", {}),
        "coverage_publish_target_counts": coverage.get("publish_target_counts", {}),
        "closure_counts": closure_counts,
        "closed_review_item_count": sum(closed_review_resolution_counts.values()),
        "closed_review_resolution_counts": dict(closed_review_resolution_counts),
        "unknown_page_count": unknown_ledger["unknown_page_count"],
        "unknown_page_resolution_counts": unknown_ledger["resolution_counts"],
        "knowledge_entry_count": len(knowledge_layer["entries"]),
        "certification_recommended_action": certification.get("recommended_action"),
        "outputs": {
            "coverage_ledger": str(report_dir / "coverage-ledger.json"),
            "unknown_page_resolution_ledger": str(report_dir / "unknown-page-resolution-ledger.json"),
            "knowledge_layer": str(report_dir / "knowledge-layer.json"),
            "certification": str(report_dir / "full-document-data-certification.json"),
            "closure_json": str(report_dir / "full-document-closure-report.json"),
            "closure_html": str(report_dir / "full-document-closure-board.html"),
            "closure_md": str(report_dir / "full-document-closure-report.md"),
        },
    }
    write_json(report_dir / "full-document-closure-report.json", model)
    (report_dir / "full-document-closure-report.md").write_text(render_markdown(model), encoding="utf-8")
    (report_dir / "full-document-closure-board.html").write_text(render_html(model), encoding="utf-8")
    return model


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
    model = build_closure_model(skill_dir=skill_dir, candidate_layer=args.candidate_layer, output_dir=output_dir)
    print(f"Wrote full-document closure report to {model['outputs']['closure_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
