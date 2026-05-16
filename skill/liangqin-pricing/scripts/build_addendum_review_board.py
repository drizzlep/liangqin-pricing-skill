#!/usr/bin/env python3
"""Build a human-facing review board for an addendum layer candidate."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DOMAIN_LABELS = {
    "cabinet": "柜体",
    "bed": "床",
    "table": "桌台",
    "door_panel": "门板",
    "accessory": "配件",
    "material": "材质",
    "child_room": "儿童房",
    "general": "通用",
}

BUCKET_LABELS = {
    "added_runtime": "可能影响报价",
    "manual_review": "拿不准，等人定",
    "removed_runtime": "旧规则没对上",
    "removed_index": "旧内容没对上",
    "added_index": "新内容，先抽查",
    "update_log": "更新记录，后面看",
}

BUCKET_CHOICES = {
    "added_runtime": ("采用", "暂缓", "找设计师确认"),
    "manual_review": ("采用", "只做提示", "排除", "找设计师确认"),
    "removed_runtime": ("保留旧规则", "确认废弃", "找设计师确认"),
    "removed_index": ("不用管", "保留旧内容", "找设计师确认"),
    "added_index": ("抽查", "暂缓", "排除"),
    "update_log": ("后面看", "从更新记录里拆规则"),
}

RISK_LABELS = {
    "high": "优先看",
    "medium": "普通",
    "low": "后面看",
}

BUCKET_ORDER = {
    "added_runtime": 0,
    "removed_runtime": 1,
    "manual_review": 2,
    "removed_index": 3,
    "added_index": 4,
    "update_log": 5,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a human-readable HTML review board for an addendum diff.")
    parser.add_argument("--base-layer", required=True, help="Current active layer id.")
    parser.add_argument("--candidate-layer", required=True, help="Candidate layer id.")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parent.parent),
        help="Skill root directory.",
    )
    parser.add_argument("--output", help="Path to write review-board HTML. Defaults to the candidate report directory.")
    return parser.parse_args(argv)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path | None, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if path is None or not path.exists():
        return dict(fallback or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else dict(fallback or {})


def normalize_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value)).lower()


def normalize_sentence(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split())


def truncate_text(value: Any, limit: int = 180) -> str:
    text = normalize_sentence(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def as_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [entry for entry in payload.get(key, []) if isinstance(entry, dict)]


def entry_title(entry: dict[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = normalize_sentence(entry.get(field, ""))
        if value:
            return value
    return ""


def index_entries_by_title(entries: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        title = entry_title(entry, fields)
        key = normalize_key(title)
        if key and key not in indexed:
            indexed[key] = entry
    return indexed


def index_entries_by_page(entries: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    indexed: dict[int, list[dict[str, Any]]] = {}
    for entry in entries:
        try:
            page = int(entry.get("page", 0) or 0)
        except (TypeError, ValueError):
            page = 0
        if page:
            indexed.setdefault(page, []).append(entry)
    return indexed


def domain_label(domain: Any) -> str:
    normalized = str(domain or "general").strip() or "general"
    return DOMAIN_LABELS.get(normalized, normalized)


def is_update_log_entry(title: str, source_path: str = "") -> bool:
    text = f"{title} {source_path}"
    return "更新日志" in text or bool(re.search(r"20\d{2}\.\d{1,2}\.\d{1,2}", text))


def source_label(entry: dict[str, Any]) -> str:
    source_title = normalize_sentence(entry.get("source_title", ""))
    source_path = normalize_sentence(entry.get("source_path", ""))
    source_page = normalize_sentence(entry.get("source_page", ""))
    parts = []
    if source_title:
        parts.append(source_title)
    if source_path and source_path != source_title:
        parts.append(source_path)
    if source_page:
        parts.append(f"源页 {source_page}")
    return " / ".join(parts) if parts else "未记录来源"


def find_index_entry(
    entry: dict[str, Any],
    *,
    index_by_title: dict[str, dict[str, Any]],
    index_by_page: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    for field in ("topic", "summary", "title"):
        key = normalize_key(entry.get(field, ""))
        if key in index_by_title:
            return index_by_title[key]
    try:
        page = int(entry.get("page", 0) or 0)
    except (TypeError, ValueError):
        page = 0
    if page and index_by_page.get(page):
        return index_by_page[page][0]
    return {}


def build_card(
    *,
    bucket: str,
    title: str,
    action: str,
    reason: str,
    entry: dict[str, Any] | None = None,
    summary: str = "",
    risk: str = "",
) -> dict[str, Any]:
    source_entry = entry or {}
    domain = str(source_entry.get("domain", "general")).strip() or "general"
    page = source_entry.get("page", "")
    return {
        "bucket": bucket,
        "bucket_label": BUCKET_LABELS.get(bucket, bucket),
        "title": title or "未命名候选项",
        "domain": domain,
        "domain_label": domain_label(domain),
        "page": page,
        "action": action,
        "reason": reason,
        "risk": risk or str(source_entry.get("risk_level", "")).strip() or "medium",
        "risk_label": RISK_LABELS.get(risk or str(source_entry.get("risk_level", "")).strip(), "普通"),
        "choices": BUCKET_CHOICES.get(bucket, ("确认", "暂缓")),
        "summary": summary or truncate_text(
            source_entry.get("summary")
            or source_entry.get("normalized_rule")
            or source_entry.get("detail")
            or source_entry.get("excerpt")
            or "",
            220,
        ),
        "source": source_label(source_entry),
        "source_node_id": normalize_sentence(source_entry.get("source_node_id", "")),
    }


def collect_cards(
    *,
    diff: dict[str, Any],
    base_index_entries: list[dict[str, Any]],
    candidate_index_entries: list[dict[str, Any]],
    base_runtime_rules: list[dict[str, Any]],
    candidate_runtime_rules: list[dict[str, Any]],
    candidate_coverage_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    base_index_by_title = index_entries_by_title(base_index_entries, ("clean_title", "heading", "normalized_rule"))
    candidate_index_by_title = index_entries_by_title(candidate_index_entries, ("clean_title", "heading", "normalized_rule"))
    candidate_index_by_page = index_entries_by_page(candidate_index_entries)
    base_runtime_keys = {
        normalize_key(entry_title(rule, ("title", "normalized_rule", "detail")))
        for rule in base_runtime_rules
        if entry_title(rule, ("title", "normalized_rule", "detail"))
    }
    seen_candidate_keys: set[str] = set()
    cards: list[dict[str, Any]] = []

    for rule in candidate_runtime_rules:
        title = entry_title(rule, ("title", "normalized_rule", "detail"))
        key = normalize_key(title)
        if not key or key in base_runtime_keys:
            continue
        seen_candidate_keys.add(key)
        cards.append(
            build_card(
                bucket="added_runtime",
                title=title,
                action="先请懂报价的人看一眼。确认没问题，再放进正式规则。",
                reason="线上版多了这条内容，系统判断它可能会影响报价或追问客户。",
                entry=rule,
                risk=str(rule.get("risk_level", "")).strip() or "high",
                summary=rule.get("user_summary") or rule.get("detail") or rule.get("normalized_rule") or "",
            )
        )

    for title in diff["runtime_rules"].get("removed", []):
        cards.append(
            build_card(
                bucket="removed_runtime",
                title=str(title),
                action="先别删。把旧版和线上版对一下，再决定保留还是废弃。",
                reason="旧版里有这条，线上版这次没有对上。可能是规则取消了，也可能只是标题变了或没识别出来。",
                risk="high",
            )
        )

    for coverage_entry in candidate_coverage_entries:
        if str(coverage_entry.get("publish_target", "")).strip() != "manual_review":
            continue
        index_entry = find_index_entry(
            coverage_entry,
            index_by_title=candidate_index_by_title,
            index_by_page=candidate_index_by_page,
        )
        merged = {**index_entry, **coverage_entry}
        title = entry_title(merged, ("topic", "clean_title", "heading", "summary"))
        key = normalize_key(title)
        if key:
            seen_candidate_keys.add(key)
        cards.append(
            build_card(
                bucket="manual_review",
                title=title,
                action="请人拿主意。它可以进正式规则，也可以只做提示，或者排除。",
                reason="这段文字像规则，但证据不够干净。直接交给系统自动用，风险有点高。",
                entry=merged,
                risk=str(merged.get("risk_level", "")).strip() or "high",
            )
        )

    for title in diff["rules_index"].get("removed", []):
        cards.append(
            build_card(
                bucket="removed_index",
                title=str(title),
                action="不用逐条看完。先抽查跟报价、尺寸、禁止做法有关的。",
                reason="旧版出现过这条，线上版这次没对上。大多不是急事，但关键规则不能漏。",
                risk="medium",
            )
        )

    for entry in candidate_index_entries:
        title = entry_title(entry, ("clean_title", "heading", "normalized_rule"))
        key = normalize_key(title)
        if not key or key in base_index_by_title or key in seen_candidate_keys:
            continue
        bucket = "update_log" if is_update_log_entry(title, str(entry.get("source_path", ""))) else "added_index"
        cards.append(
            build_card(
                bucket=bucket,
                title=title,
                action="先放后面" if bucket == "update_log" else "按类别抽几条看看",
                reason="这类多半只是更新记录，不等于可执行规则。" if bucket == "update_log" else "线上版多了这条，但现在还不会自动生效。",
                entry=entry,
                risk="low" if bucket == "update_log" else "medium",
            )
        )

    cards.sort(
        key=lambda card: (
            BUCKET_ORDER.get(str(card.get("bucket", "")), 99),
            str(card.get("domain_label", "")),
            str(card.get("title", "")),
        )
    )
    return cards


def build_review_model(skill_dir: Path, base_layer: str, candidate_layer: str) -> dict[str, Any]:
    scripts_dir = Path(__file__).resolve().parent
    compare_module = load_module("compare_addendum_layers_for_board", scripts_dir / "compare_addendum_layers.py")
    addenda_root = skill_dir / "references" / "addenda"
    base_manifest = compare_module.resolve_manifest(addenda_root, base_layer)
    candidate_manifest = compare_module.resolve_manifest(addenda_root, candidate_layer)
    diff = compare_module.build_layer_diff(skill_dir, base_layer, candidate_layer)

    def artifact(manifest: dict[str, Any], name: str) -> Path | None:
        return compare_module.resolve_artifact_path(manifest, name)

    base_index = load_json(artifact(base_manifest, "rules_index_file"), {"entries": []})
    candidate_index = load_json(artifact(candidate_manifest, "rules_index_file"), {"entries": []})
    base_runtime = load_json(artifact(base_manifest, "runtime_rules_file"), {"rules": []})
    candidate_runtime = load_json(artifact(candidate_manifest, "runtime_rules_file"), {"rules": []})
    candidate_coverage = load_json(artifact(candidate_manifest, "coverage_ledger_file"), {"entries": []})
    candidate_rules = load_json(artifact(candidate_manifest, "rules_candidate_file"), {})
    candidate_pages = as_list(candidate_rules, "pages")
    candidate_sections = as_list(candidate_rules, "sections")
    candidate_index_entries = as_list(candidate_index, "entries")

    cards = collect_cards(
        diff=diff,
        base_index_entries=as_list(base_index, "entries"),
        candidate_index_entries=candidate_index_entries,
        base_runtime_rules=as_list(base_runtime, "rules"),
        candidate_runtime_rules=as_list(candidate_runtime, "rules"),
        candidate_coverage_entries=as_list(candidate_coverage, "entries"),
    )
    bucket_counts = Counter(str(card.get("bucket", "")) for card in cards)
    domain_counts = Counter(str(card.get("domain", "general")) for card in cards)
    page_method_counts = Counter(str(page.get("extract_method", "unknown")) for page in candidate_pages)
    section_method_counts = Counter(str(section.get("extract_method", "unknown")) for section in candidate_sections)
    index_method_counts = Counter(str(entry.get("extract_method", "unknown")) for entry in candidate_index_entries)
    ocr_page_count = sum(
        count
        for method, count in page_method_counts.items()
        if method in {"hybrid", "ocr_fallback"} or "ocr" in method
    )
    confidence_values = [
        float(entry.get("confidence", 0) or 0)
        for entry in candidate_index_entries
        if isinstance(entry.get("confidence", 0), int | float)
    ]
    average_confidence = round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_layer": diff["base_layer"],
        "candidate_layer": diff["candidate_layer"],
        "diff": diff,
        "candidate_rules": {
            "artifact_count": candidate_rules.get("artifact_count", 0),
            "processed_artifact_count": candidate_rules.get("processed_artifact_count", 0),
            "skipped_artifact_count": candidate_rules.get("skipped_artifact_count", 0),
            "page_count": candidate_rules.get("page_count", candidate_index.get("page_count", 0)),
        },
        "coverage": {
            "entry_count": candidate_coverage.get("entry_count", 0),
            "status_counts": candidate_coverage.get("status_counts", {}),
            "publish_target_counts": candidate_coverage.get("publish_target_counts", {}),
        },
        "quality": {
            "ocr_page_count": ocr_page_count,
            "page_method_counts": dict(sorted(page_method_counts.items())),
            "section_method_counts": dict(sorted(section_method_counts.items())),
            "index_method_counts": dict(sorted(index_method_counts.items())),
            "average_confidence": average_confidence,
            "text_layer_page_ratio": round(page_method_counts.get("text_layer", 0) / max(len(candidate_pages), 1), 3),
            "unknown_page_count": page_method_counts.get("unknown", 0),
        },
        "counts": {
            "cards": len(cards),
            "bucket_counts": dict(sorted(bucket_counts.items())),
            "domain_counts": dict(sorted(domain_counts.items())),
            "rules_added": len(diff["rules_index"].get("added", [])),
            "rules_removed": len(diff["rules_index"].get("removed", [])),
            "runtime_added": len(diff["runtime_rules"].get("added", [])),
            "runtime_removed": len(diff["runtime_rules"].get("removed", [])),
        },
        "cards": cards,
    }


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
      <section class="metric">
        <div class="metric__label">{esc(label)}</div>
        <div class="metric__value">{esc(value)}</div>
        <div class="metric__hint">{esc(hint)}</div>
      </section>
    """


def render_quality_note(quality: dict[str, Any]) -> str:
    page_method_counts = quality.get("page_method_counts", {})
    index_method_counts = quality.get("index_method_counts", {})
    page_text = "，".join(f"{method}: {count}" for method, count in page_method_counts.items()) or "暂无"
    index_text = "，".join(f"{method}: {count}" for method, count in index_method_counts.items()) or "暂无"
    ocr_note = (
        "本次没有跑 OCR。PDF 用可复制文字层，钉钉在线文档用导出的正文 Markdown。"
        if int(quality.get("ocr_page_count", 0) or 0) == 0
        else f"本次有 {quality.get('ocr_page_count')} 页触发 OCR，需要单独抽样核对。"
    )
    return f"""
      <section class="quality-note">
        <h2>这次文字从哪里来</h2>
        <p>{esc(ocr_note)}</p>
        <p>页级来源：{esc(page_text)}。规则条目来源：{esc(index_text)}。平均置信度：{esc(quality.get('average_confidence'))}。</p>
        <p>这个分数是抽取链路的可信度，不是人工逐字校对后的准确率。要给 OCR 准确率，需要另外抽样做人工标注。</p>
      </section>
    """


def render_filter_buttons(cards: list[dict[str, Any]]) -> str:
    buckets = Counter(str(card.get("bucket", "")) for card in cards)
    priority_count = sum(
        count
        for bucket, count in buckets.items()
        if bucket in {"added_runtime", "removed_runtime", "manual_review"}
    )
    buttons = [
        f'<button class="filter-chip is-active" data-filter-bucket="priority">优先确认 {priority_count}</button>',
        '<button class="filter-chip" data-filter-bucket="all">全部</button>',
    ]
    for bucket, _count in sorted(buckets.items(), key=lambda item: BUCKET_ORDER.get(item[0], 99)):
        label = f"{BUCKET_LABELS.get(bucket, bucket)} {buckets[bucket]}"
        buttons.append(f'<button class="filter-chip" data-filter-bucket="{esc(bucket)}">{esc(label)}</button>')
    return "\n".join(buttons)


def render_domain_options(cards: list[dict[str, Any]]) -> str:
    domains = Counter(str(card.get("domain", "general")) for card in cards)
    options = ['<option value="all">全部领域</option>']
    for domain, count in sorted(domains.items(), key=lambda item: domain_label(item[0])):
        options.append(f'<option value="{esc(domain)}">{esc(domain_label(domain))}（{count}）</option>')
    return "\n".join(options)


def render_cards(cards: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for index, card in enumerate(cards, start=1):
        searchable = " ".join(str(card.get(field, "")) for field in ("title", "summary", "source", "action", "reason", "domain_label"))
        choices = " / ".join(str(choice) for choice in card.get("choices", []))
        rendered.append(
            f"""
            <article class="card" data-bucket="{esc(card.get('bucket'))}" data-domain="{esc(card.get('domain'))}" data-search="{esc(searchable.lower())}">
              <div class="card__topline">
                <span class="badge badge--{esc(card.get('bucket'))}">{esc(card.get('bucket_label'))}</span>
                <span class="card__meta">{esc(card.get('domain_label'))} · p{esc(card.get('page') or '-')} · {esc(card.get('risk_label'))}</span>
              </div>
              <h3>{esc(card.get('title'))}</h3>
              <p class="card__summary">{esc(card.get('summary') or '这条没有抓到好摘要，需要打开来源看。')}</p>
              <dl>
                <div><dt>这条怎么处理</dt><dd>{esc(card.get('action'))}</dd></div>
                <div><dt>可选判断</dt><dd>{esc(choices)}</dd></div>
                <div><dt>为什么放这里</dt><dd>{esc(card.get('reason'))}</dd></div>
                <div><dt>从哪里来的</dt><dd>{esc(card.get('source'))}</dd></div>
              </dl>
              <div class="card__footer">#{index}</div>
            </article>
            """
        )
    return "\n".join(rendered)


def render_html(model: dict[str, Any]) -> str:
    candidate = model["candidate_layer"]
    base = model["base_layer"]
    counts = model["counts"]
    coverage = model["coverage"]
    candidate_rules = model["candidate_rules"]
    quality = model["quality"]
    cards = model["cards"]
    publish_counts = coverage.get("publish_target_counts", {})
    status_class = "safe" if str(candidate.get("status", "")).upper() == "PAUSED" else "danger"
    recommendation = (
        "这份线上手册还没有接进正式报价。先看上面默认筛出的几类：可能影响报价、旧规则没对上、系统拿不准。看完再决定要不要启用。"
        if status_class == "safe"
        else "这份手册看起来已经在生效。先停一下，确认后再继续。"
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>设计师手册线上版审核台</title>
  <style>
    :root {{
      --bg: #f6f0e7;
      --ink: #241c17;
      --muted: #71675f;
      --line: rgba(36, 28, 23, .14);
      --panel: rgba(255, 252, 246, .86);
      --accent: #8b4b2f;
      --accent-2: #2f6658;
      --warn: #a15f12;
      --danger: #9d2f22;
      --shadow: 0 18px 48px rgba(57, 39, 24, .12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 8% 0%, rgba(139, 75, 47, .16), transparent 28rem),
        radial-gradient(circle at 88% 12%, rgba(47, 102, 88, .14), transparent 30rem),
        linear-gradient(135deg, #fbf6ed 0%, var(--bg) 46%, #efe2d1 100%);
      font-family: "Songti SC", "Noto Serif SC", "Source Han Serif SC", serif;
      line-height: 1.55;
    }}
    .shell {{ width: min(1440px, calc(100% - 40px)); margin: 0 auto; padding: 36px 0 72px; }}
    .hero {{
      border: 1px solid var(--line);
      background: rgba(255, 252, 246, .78);
      box-shadow: var(--shadow);
      border-radius: 28px;
      padding: 34px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -7rem -10rem auto;
      width: 26rem;
      height: 26rem;
      background: radial-gradient(circle, rgba(139, 75, 47, .12), transparent 68%);
      pointer-events: none;
    }}
    .eyebrow {{ color: var(--accent); font-size: 13px; letter-spacing: .18em; text-transform: uppercase; font-weight: 700; }}
    h1 {{ margin: 10px 0 12px; font-size: clamp(32px, 4.8vw, 64px); line-height: 1.02; letter-spacing: -.04em; }}
    .hero p {{ max-width: 900px; color: var(--muted); font-size: 18px; margin: 0; }}
    .status {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      margin-top: 22px;
      padding: 10px 14px;
      border-radius: 999px;
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 14px;
      font-weight: 700;
      background: rgba(47, 102, 88, .12);
      color: var(--accent-2);
    }}
    .status.danger {{ background: rgba(157, 47, 34, .12); color: var(--danger); }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 20px 0; }}
    .metric {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 22px;
      padding: 20px;
      min-height: 132px;
    }}
    .metric__label {{ color: var(--muted); font-family: "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 13px; }}
    .metric__value {{ font-size: 36px; font-weight: 800; margin: 8px 0 2px; letter-spacing: -.04em; }}
    .metric__hint {{ color: var(--muted); font-size: 13px; }}
    .quality-note {{
      border: 1px solid var(--line);
      background: rgba(255, 252, 246, .78);
      border-radius: 24px;
      padding: 22px;
      margin: 20px 0;
      box-shadow: 0 12px 32px rgba(57, 39, 24, .07);
    }}
    .quality-note h2 {{ margin: 0 0 8px; font-size: 24px; letter-spacing: -.02em; }}
    .quality-note p {{ margin: 8px 0 0; color: var(--muted); font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }}
    .toolbar {{
      position: sticky;
      top: 12px;
      z-index: 4;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: center;
      margin: 22px 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: rgba(255, 252, 246, .92);
      backdrop-filter: blur(18px);
      box-shadow: 0 12px 32px rgba(57, 39, 24, .08);
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    .toolbar input, .toolbar select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fffaf1;
      color: var(--ink);
      padding: 12px 14px;
      font: inherit;
      outline: none;
    }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .filter-chip {{
      border: 1px solid var(--line);
      background: #fffaf1;
      color: var(--ink);
      border-radius: 999px;
      padding: 9px 12px;
      cursor: pointer;
      font: inherit;
    }}
    .filter-chip.is-active {{ background: var(--ink); color: #fffaf1; }}
    .board {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .card {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 24px;
      padding: 18px;
      box-shadow: 0 14px 36px rgba(57, 39, 24, .08);
      min-height: 290px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .card.is-hidden {{ display: none; }}
    .card__topline, .card__footer {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }}
    .card__meta, .card__footer {{ color: var(--muted); font-size: 12px; }}
    .badge {{ display: inline-flex; border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 800; background: rgba(139, 75, 47, .12); color: var(--accent); }}
    .badge--added_runtime, .badge--removed_runtime {{ background: rgba(157, 47, 34, .12); color: var(--danger); }}
    .badge--manual_review {{ background: rgba(161, 95, 18, .14); color: var(--warn); }}
    .badge--update_log {{ background: rgba(47, 102, 88, .12); color: var(--accent-2); }}
    h3 {{ margin: 0; font-size: 20px; line-height: 1.28; letter-spacing: -.02em; }}
    .card__summary {{ margin: 0; color: var(--ink); font-size: 14px; }}
    dl {{ margin: auto 0 0; display: grid; gap: 9px; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 13px; }}
    dl div {{ border-top: 1px solid var(--line); padding-top: 9px; }}
    dt {{ color: var(--muted); font-weight: 700; }}
    dd {{ margin: 3px 0 0; }}
    .empty {{ display: none; padding: 48px; text-align: center; color: var(--muted); border: 1px dashed var(--line); border-radius: 24px; background: rgba(255,255,255,.38); }}
    @media (max-width: 980px) {{
      .metrics, .board {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .toolbar {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 680px) {{
      .shell {{ width: min(100% - 24px, 1440px); padding-top: 18px; }}
      .hero {{ padding: 24px; }}
      .metrics, .board {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 设计师手册</div>
      <h1>线上版要不要接进报价？先看这张审核台</h1>
      <p>{esc(recommendation)}</p>
      <div class="status {esc(status_class)}">{esc('还没生效' if status_class == 'safe' else '可能已生效')} · {esc(candidate.get('layer_id'))}</div>
    </section>

    <section class="metrics">
      {render_metric("可能影响报价", counts["runtime_added"], "新增内容里，系统觉得可能会改报价或追问方式")}
      {render_metric("旧规则没对上", counts["runtime_removed"], "旧版正式用过，但线上版这次没匹配到")}
      {render_metric("拿不准", publish_counts.get("manual_review", 0), "像规则，但还不能放心交给系统自动用")}
      {render_metric("已读完", f"{candidate_rules.get('processed_artifact_count', 0)}/{candidate_rules.get('artifact_count', 0)}", f"共 {candidate_rules.get('page_count', 0)} 页，跳过 {candidate_rules.get('skipped_artifact_count', 0)} 个文件")}
    </section>

    <section class="metrics">
      {render_metric("新增内容", counts["rules_added"], "线上版多出来的标题，里面有些只是目录或更新记录")}
      {render_metric("旧内容缺口", counts["rules_removed"], "旧版有，线上版没对上的标题")}
      {render_metric("触发 OCR 页", quality.get("ocr_page_count", 0), "0 表示本次没有用 OCR 识别文本；不代表不需要复核")}
      {render_metric("平均可信度", quality.get("average_confidence", 0), "抽取链路的内部分数，不等于人工校对准确率")}
    </section>

    {render_quality_note(quality)}

    <section class="metrics">
      {render_metric("可先放进规则", publish_counts.get("runtime", 0), "机器初筛结果。仍建议人工抽查")}
      {render_metric("先不处理", publish_counts.get("none", 0), "背景、目录、噪音，或者暂时不适合进规则")}
      {render_metric("PDF 文字层页占比", quality.get("text_layer_page_ratio", 0), "越高越说明不是靠 OCR 猜字")}
      {render_metric("没读到文字页", quality.get("unknown_page_count", 0), "这类页要按需回看原文或图片")}
    </section>

    <section class="toolbar">
      <input id="searchBox" type="search" placeholder="搜一个词，比如：柜体 / 加价 / 更新记录 / 门板">
      <select id="domainFilter">{render_domain_options(cards)}</select>
      <div class="filters">{render_filter_buttons(cards)}</div>
    </section>

    <section id="board" class="board">
      {render_cards(cards)}
    </section>
    <section id="emptyState" class="empty">没找到。可以清空搜索，或者换一个分类看。</section>
  </main>
  <script>
    const searchBox = document.querySelector('#searchBox');
    const domainFilter = document.querySelector('#domainFilter');
    const chips = [...document.querySelectorAll('.filter-chip')];
    const cards = [...document.querySelectorAll('.card')];
    const emptyState = document.querySelector('#emptyState');
    let activeBucket = 'priority';

    function applyFilters() {{
      const query = (searchBox.value || '').trim().toLowerCase();
      const domain = domainFilter.value;
      let visible = 0;
      for (const card of cards) {{
        const matchesBucket = activeBucket === 'all'
          || card.dataset.bucket === activeBucket
          || (activeBucket === 'priority' && ['added_runtime', 'removed_runtime', 'manual_review'].includes(card.dataset.bucket));
        const matchesDomain = domain === 'all' || card.dataset.domain === domain;
        const matchesQuery = !query || (card.dataset.search || '').includes(query);
        const show = matchesBucket && matchesDomain && matchesQuery;
        card.classList.toggle('is-hidden', !show);
        if (show) visible += 1;
      }}
      emptyState.style.display = visible ? 'none' : 'block';
    }}

    searchBox.addEventListener('input', applyFilters);
    domainFilter.addEventListener('change', applyFilters);
    chips.forEach((chip) => {{
      chip.addEventListener('click', () => {{
        activeBucket = chip.dataset.filterBucket;
        chips.forEach((item) => item.classList.toggle('is-active', item === chip));
        applyFilters();
      }});
    }});
    applyFilters();
  </script>
</body>
</html>
"""


def default_output_path(model: dict[str, Any], skill_dir: Path) -> Path:
    candidate_layer_id = str(model["candidate_layer"].get("layer_id", "")).strip()
    candidate_slug = "".join(char.lower() if char.isalnum() else "-" for char in candidate_layer_id).strip("-")
    return skill_dir / "reports" / "addenda" / candidate_slug / "review-board.html"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    model = build_review_model(skill_dir, args.base_layer, args.candidate_layer)
    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(model, skill_dir)
    write_text(output_path, render_html(model))
    print(f"Wrote addendum review board to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
