#!/usr/bin/env python3
"""Build a human-readable alignment board for active vs candidate addendum layers."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SENSITIVE_PATTERNS = ("Signature=", "X-Amz-Signature", "token=", "access_token=", "https://alidocs2")
VISUAL_REFERENCE_TOPICS = {"岩板", "推拉门", "儿童床", "安全规范"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an addendum alignment review board without mutating layers.")
    parser.add_argument("--base-layer", default="designer-manual-2026-03-22", help="Current ACTIVE addendum layer id.")
    parser.add_argument("--candidate-layer", default="designer-manual-online-2026-05-13", help="PAUSED candidate layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def normalize_key(value: Any) -> str:
    return re.sub(r"[\W_]+", "", str(value or "")).lower()


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def excerpt(value: Any, limit: int = 180) -> str:
    text = normalize_inline(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def is_sensitive(value: Any) -> bool:
    text = str(value or "")
    return any(pattern.lower() in text.lower() for pattern in SENSITIVE_PATTERNS)


def resolve_artifact_path(manifest: dict[str, Any], artifact_name: str) -> Path | None:
    artifacts = manifest.get("artifacts", {})
    raw_path = artifacts.get(artifact_name) if isinstance(artifacts, dict) else ""
    if not raw_path:
        return None
    path = Path(str(raw_path))
    return path if path.is_absolute() else (Path(str(manifest["_manifest_dir"])) / path).resolve()


def source_ref(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": normalize_inline(entry.get("source_title") or entry.get("topic") or entry.get("clean_title") or entry.get("title")),
        "page": entry.get("source_page") or entry.get("page") or 0,
        "path": normalize_inline(entry.get("source_path")),
    }


def topic_name(entry: dict[str, Any]) -> str:
    for field in ("source_title", "topic", "clean_title", "title", "heading"):
        text = normalize_inline(entry.get(field))
        if text:
            return text[:80]
    return "未命名主题"


def collect_base_topics(base_manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    refs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for artifact_name, list_key in (
        ("rules_index_file", "entries"),
        ("runtime_rules_file", "rules"),
        ("knowledge_layer_file", "entries"),
        ("coverage_ledger_file", "entries"),
    ):
        payload = load_json(resolve_artifact_path(base_manifest, artifact_name), {})
        for entry in payload.get(list_key, []):
            if not isinstance(entry, dict):
                continue
            refs[normalize_key(topic_name(entry))].append(source_ref(entry))
    return refs


def visual_assets_by_topic(report_dir: Path) -> dict[str, dict[str, Any]]:
    visual_root = report_dir / "visual-evidence"
    assets: dict[str, dict[str, Any]] = {}
    if not visual_root.exists():
        return assets
    for path in sorted(visual_root.glob("*/visual-assets.json")):
        payload = load_json(path, {})
        topic = normalize_inline(payload.get("topic") or path.parent.name)
        if topic:
            assets[topic] = payload
    return assets


def classify_candidate_topic(
    *,
    topic: str,
    candidate_entries: list[dict[str, Any]],
    base_refs: list[dict[str, Any]],
    visual_asset: dict[str, Any] | None,
) -> dict[str, Any]:
    statuses = Counter(str(entry.get("status") or "") for entry in candidate_entries)
    publish_targets = Counter(str(entry.get("publish_target") or "") for entry in candidate_entries)
    risk_levels = Counter(str(entry.get("risk_level") or "") for entry in candidate_entries)
    source_refs = [source_ref(entry) for entry in candidate_entries[:8]]
    page_images = []
    evidence_status = "text_only"
    if visual_asset:
        entries = visual_asset.get("entries", [])
        page_images = [str(entry.get("page_image")) for entry in entries if entry.get("page_image") and not is_sensitive(entry.get("page_image"))]
        if visual_asset.get("needs_human_review_count", 0):
            evidence_status = "needs_human_review"
        elif visual_asset.get("agent_visual_review_count", 0):
            evidence_status = "agent_visual_review"
        elif visual_asset.get("agent_ready_count", 0):
            evidence_status = "agent_ready"
        elif page_images:
            evidence_status = "page_image_available"
    alignment_status = "defer"
    risk_level = "medium"
    reason = "候选内容需要后续归类。"
    if base_refs and not candidate_entries:
        alignment_status = "conflict_with_active"
        risk_level = "high"
        reason = "旧版存在但新版未覆盖，需要确认是否删除、改名或被合并。"
    elif visual_asset and topic in VISUAL_REFERENCE_TOPICS:
        alignment_status = "visual_reference_only"
        risk_level = "low"
        reason = "已有整页图证据，适合先给 Agent 做 page-first 图文参考，不进入报价规则。"
    elif statuses.get("runtime_hard_rule") or publish_targets.get("runtime"):
        if base_refs:
            alignment_status = "duplicate_or_no_change"
            risk_level = "low"
            reason = "新版与旧版存在同主题覆盖，暂不自动替换。"
        else:
            alignment_status = "safe_rule_candidate"
            risk_level = "medium"
            reason = "新版候选为 runtime 规则，但仍需抽样确认后才能合并。"
    elif statuses.get("unresolved") or publish_targets.get("manual_review"):
        alignment_status = "defer"
        risk_level = "high" if risk_levels.get("high") else "medium"
        reason = "候选层仍标记为 manual_review/unresolved，暂缓进入正式规则。"
    elif base_refs:
        alignment_status = "duplicate_or_no_change"
        risk_level = "low"
        reason = "旧版已有同主题内容，未发现必须迁移的新规则。"
    if not page_images and visual_asset:
        alignment_status = "insufficient_evidence"
        risk_level = "high"
        reason = "图文主题缺少可展示整页图，需补资料。"
    return {
        "topic": topic,
        "active_refs": base_refs[:8],
        "candidate_refs": source_refs,
        "change_type": "existing_topic" if base_refs and candidate_entries else "candidate_added" if candidate_entries else "active_removed",
        "candidate_entry_count": len(candidate_entries),
        "candidate_status_counts": dict(statuses),
        "candidate_publish_target_counts": dict(publish_targets),
        "evidence_status": evidence_status,
        "alignment_status": alignment_status,
        "recommended_action": recommended_action(alignment_status),
        "risk_level": risk_level,
        "reason": reason,
        "source_pages": sorted({int(ref.get("page") or 0) for ref in source_refs if ref.get("page")})[:20],
        "page_images": page_images[:8],
    }


def recommended_action(alignment_status: str) -> str:
    return {
        "safe_rule_candidate": "进入待合并候选清单，先抽样确认再合并。",
        "visual_reference_only": "先进入 Agent 图文证据层，不进入报价规则。",
        "conflict_with_active": "单独列出差异，不自动合并或删除旧规则。",
        "insufficient_evidence": "保持暂停，补整页图或来源证据。",
        "duplicate_or_no_change": "保持旧版 active，不需要迁移。",
        "defer": "暂缓，等待后续人工抽检或更强证据。",
    }.get(alignment_status, "暂缓。")


def build_alignment_model(skill_dir: Path, base_layer: str, candidate_layer: str) -> dict[str, Any]:
    compare_module = load_module("compare_addendum_layers_for_alignment", Path(__file__).resolve().parent / "compare_addendum_layers.py")
    diff = compare_module.build_layer_diff(skill_dir, base_layer, candidate_layer)
    addenda_root = skill_dir / "references" / "addenda"
    base_manifest = compare_module.resolve_manifest(addenda_root, base_layer)
    candidate_manifest = compare_module.resolve_manifest(addenda_root, candidate_layer)
    report_dir = resolve_artifact_path(candidate_manifest, "rules_candidate_file").parent
    base_topic_refs = collect_base_topics(base_manifest)
    coverage = load_json(resolve_artifact_path(candidate_manifest, "coverage_ledger_file"), {"entries": []})
    candidate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in coverage.get("entries", []):
        if isinstance(entry, dict):
            candidate_groups[topic_name(entry)].append(entry)
    visual_assets = visual_assets_by_topic(report_dir)
    for topic in visual_assets:
        candidate_groups.setdefault(topic, [])
    active_removed = sorted(set(base_topic_refs) - {normalize_key(topic) for topic in candidate_groups})
    topics = [
        classify_candidate_topic(
            topic=topic,
            candidate_entries=entries,
            base_refs=base_topic_refs.get(normalize_key(topic), []),
            visual_asset=visual_assets.get(topic),
        )
        for topic, entries in sorted(candidate_groups.items(), key=lambda item: item[0])
    ]
    topics.extend(
        classify_candidate_topic(topic=f"旧版待确认：{key}", candidate_entries=[], base_refs=base_topic_refs[key], visual_asset=None)
        for key in active_removed[:80]
    )
    status_counts = Counter(topic["alignment_status"] for topic in topics)
    risk_counts = Counter(topic["risk_level"] for topic in topics)
    output_json = report_dir / "alignment-review.json"
    output_html = report_dir / "alignment-review-board.html"
    return {
        "base_layer": diff["base_layer"],
        "candidate_layer": diff["candidate_layer"],
        "diff_summary": {
            "rules_index": {k: diff["rules_index"][k] for k in ("base_count", "candidate_count", "common_count")},
            "runtime_rules": {k: diff["runtime_rules"][k] for k in ("base_count", "candidate_count", "common_count")},
            "knowledge_layer": {k: diff["knowledge_layer"][k] for k in ("base_count", "candidate_count", "common_count")},
            "coverage_ledger": diff["coverage_ledger"],
        },
        "alignment_status_counts": dict(status_counts),
        "risk_counts": dict(risk_counts),
        "topic_count": len(topics),
        "recommended_migration_strategy": migration_strategy(status_counts),
        "topics": topics,
        "json_path": str(output_json),
        "html_path": str(output_html),
    }


def migration_strategy(status_counts: Counter[str]) -> str:
    return (
        "不建议整体替换旧版。先把 visual_reference_only 接入 Agent 图文证据层；"
        "safe_rule_candidate 进入待合并清单；conflict_with_active 和 defer 暂不自动合并。"
    )


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""<section class="metric"><span>{esc(label)}</span><strong>{esc(value)}</strong><small>{esc(hint)}</small></section>"""


def render_topic_card(topic: dict[str, Any]) -> str:
    refs = "".join(
        f"<li>{esc(ref.get('title'))} · 页 {esc(ref.get('page'))}</li>"
        for ref in topic.get("candidate_refs", [])[:4]
    ) or "<li>无新版来源页</li>"
    return f"""
    <article class="card {esc(topic.get('risk_level'))}">
      <div class="badges">
        <span>{esc(topic.get('alignment_status'))}</span>
        <span>{esc(topic.get('risk_level'))}</span>
        <span>{esc(topic.get('evidence_status'))}</span>
      </div>
      <h3>{esc(topic.get('topic'))}</h3>
      <p>{esc(topic.get('reason'))}</p>
      <p class="action">{esc(topic.get('recommended_action'))}</p>
      <ul>{refs}</ul>
    </article>
    """


def render_html(model: dict[str, Any]) -> str:
    counts = model.get("alignment_status_counts", {})
    base = model.get("base_layer", {})
    candidate = model.get("candidate_layer", {})
    cards = "\n".join(render_topic_card(topic) for topic in model.get("topics", [])[:120])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>良禽佳木设计师手册新旧版对齐看板</title>
  <style>
    :root {{ --paper:#f8f0e5; --card:#fffaf2; --ink:#291f18; --muted:#756655; --line:#dfceb8; --accent:#86512e; --danger:#9e3f2f; --ok:#3d704c; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:linear-gradient(135deg,#fffaf3 0%,var(--paper) 58%,#e9d9c3 100%); font-family:"Songti SC","Noto Serif CJK SC",serif; }}
    main {{ max-width:1240px; margin:0 auto; padding:42px 22px 80px; }}
    .hero,.metric,.card {{ border:1px solid var(--line); background:rgba(255,250,242,.9); box-shadow:0 18px 48px rgba(66,43,22,.09); }}
    .hero {{ border-radius:30px; padding:32px; }}
    .eyebrow {{ color:var(--accent); letter-spacing:.14em; font-size:13px; }}
    h1 {{ margin:12px 0; font-size:clamp(34px,5vw,58px); line-height:1.05; }}
    .hero p {{ color:var(--muted); font-size:18px; line-height:1.8; max-width:950px; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:18px 0; }}
    .metric {{ border-radius:20px; padding:16px; }}
    .metric span,.metric small {{ color:var(--muted); display:block; }}
    .metric strong {{ display:block; font-size:30px; margin:8px 0; }}
    .strategy {{ border:1px solid var(--line); border-radius:22px; padding:18px 20px; margin:18px 0; background:#fffdf8; line-height:1.7; }}
    .cards {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
    .card {{ border-radius:22px; padding:18px; }}
    .card.high {{ border-color:#d7a293; }}
    .card.low {{ border-color:#b7d0b8; }}
    .badges {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .badges span {{ border:1px solid var(--line); border-radius:999px; padding:5px 9px; background:#fffdf8; color:var(--accent); font-size:13px; }}
    h3 {{ margin:12px 0 8px; font-size:22px; }}
    p,li {{ color:var(--muted); line-height:1.65; }}
    .action {{ color:var(--accent); font-weight:700; }}
    @media(max-width:880px) {{ .metrics,.cards {{ grid-template-columns:1fr; }} main {{ padding:24px 14px 52px; }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 设计师手册新旧版对齐</div>
      <h1>新旧版整体对齐看板</h1>
      <p>旧版 active：{esc(base.get('layer_id'))} / {esc(base.get('status'))}。新版候选：{esc(candidate.get('layer_id'))} / {esc(candidate.get('status'))}。本看板只做只读对齐评估，不激活新版、不覆盖旧版、不修改报价或合同审核链路。</p>
    </section>
    <section class="metrics">
      {render_metric("新增候选主题", counts.get("safe_rule_candidate", 0), "可进入待合并清单")}
      {render_metric("图文参考主题", counts.get("visual_reference_only", 0), "先给 Agent 使用")}
      {render_metric("冲突待确认", counts.get("conflict_with_active", 0), "不自动删除旧版")}
      {render_metric("暂缓/证据不足", counts.get("defer", 0) + counts.get("insufficient_evidence", 0), "继续暂停")}
    </section>
    <section class="strategy"><strong>推荐迁移策略：</strong>{esc(model.get('recommended_migration_strategy'))}</section>
    <section class="cards">{cards}</section>
  </main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    model = build_alignment_model(skill_dir, args.base_layer, args.candidate_layer)
    json_path = Path(str(model["json_path"]))
    html_path = Path(str(model["html_path"]))
    write_json(json_path, model)
    html_path.write_text(render_html(model), encoding="utf-8")
    print(json.dumps({"json_path": str(json_path), "html_path": str(html_path), "topic_count": model["topic_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
