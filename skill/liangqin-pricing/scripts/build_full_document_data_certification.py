#!/usr/bin/env python3
"""Build a full-document data usability certification board."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"

READY = "可进入企业 Agent 数据点"
REVIEW = "需要人工复核"
EXTRACTION_FAILED = "提取失败或证据不足"
CONFLICT = "规则冲突"
NOT_AUTOMATED = "不适合自动回答"

QUOTE_CALC_RULE = "报价计算硬规则"
QUOTE_PRECHECK_RULE = "报价前追问/拦截规则"
DESIGNER_KNOWLEDGE = "设计师咨询知识"
MANUAL_REVIEW_LAYER = "人工复核"
NOT_EXPOSED_LAYER = "不开放"

DOMAIN_LABELS = {
    "cabinet": "柜体",
    "bed": "床榻",
    "table": "桌椅",
    "door_panel": "门板",
    "accessory": "配件",
    "material": "材质",
    "child_room": "儿童房",
    "general": "通用",
}

DECISION_ORDER = {
    READY: 0,
    REVIEW: 1,
    EXTRACTION_FAILED: 2,
    CONFLICT: 3,
    NOT_AUTOMATED: 4,
}

PRICING_LAYER_ORDER = {
    QUOTE_CALC_RULE: 0,
    QUOTE_PRECHECK_RULE: 1,
    DESIGNER_KNOWLEDGE: 2,
    MANUAL_REVIEW_LAYER: 3,
    NOT_EXPOSED_LAYER: 4,
}

CALC_KEYWORDS = (
    "报价",
    "加价",
    "补差",
    "折减",
    "公式",
    "单价",
    "价格",
    "收费",
    "超深",
    "纹理连续",
    "差价",
)

PRECHECK_KEYWORDS = (
    "尺寸限制",
    "限制",
    "≤",
    "≥",
    "不得",
    "不可",
    "不能",
    "必须",
    "需备注",
    "需要备注",
    "提前询问",
    "确认",
    "开启方式",
    "开启方向",
    "高度",
    "宽度",
    "深度",
    "上限",
    "下限",
)

SENSITIVE_PATTERNS = ("Signature=", "X-Amz-", "token=", "access_token=", "secret", "Bearer")
INTERNAL_HTML_TERMS = (
    "runtime_hard_rule",
    "excluded_background",
    "manual_review",
    "rules_index_seed",
    "rule_layer_status",
    "publish_target",
)

DEFAULT_QUERY_PROBES = (
    "天地铰链铝框门高度限制是多少？",
    "推拉门单小块门板内缩多少？",
    "岩板台面报价或设计有什么注意点？",
    "儿童床安全规范要注意什么？",
    "榻榻米空区托称需要固定上墙吗？",
)

IMPORTANT_QUERY_TERMS = (
    "天地铰链铝框门",
    "高度限制",
    "尺寸限制",
    "推拉门",
    "单小块",
    "内缩",
    "岩板台面",
    "岩板背板",
    "岩板",
    "台面",
    "报价",
    "设计注意",
    "儿童床",
    "安全规范",
    "家具安全",
    "GB 28007",
    "GB28007",
    "婴幼儿",
    "榻榻米组合柜",
    "榻榻米",
    "组合柜",
    "空区托称",
    "空区",
    "托称",
    "固定上墙",
)

QUERY_ALIASES = {
    "安全规范": ("GB 28007", "GB28007", "婴幼儿", "家具安全"),
    "儿童床": ("儿童家具", "婴幼儿", "GB 28007", "GB28007"),
    "固定上墙": ("承重墙", "膨胀螺丝"),
}

REQUIRED_TERM_GROUPS = {
    "内缩": (("内缩",),),
    "固定上墙": (("固定上墙", "承重墙", "膨胀螺丝"),),
    "安全规范": (("安全规范", "安全技术规范", "GB 28007", "GB28007", "婴幼儿", "儿童家具安全", "家具安全"),),
    "高度限制": (("高度", "尺寸限制", "H≤", "H=", "≤高度≤"),),
    "尺寸限制": (("尺寸限制", "高度", "宽度", "≤", "≥"),),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full-document data certification board.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="Designer manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--output-dir", default="", help="Override output directory.")
    parser.add_argument("--max-html-cards", type=int, default=0, help="Limit rendered cards. 0 renders all data points.")
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


def excerpt(value: Any, limit: int = 220) -> str:
    text = normalize_inline(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def is_sensitive(value: Any) -> bool:
    text = str(value or "")
    return any(pattern.lower() in text.lower() for pattern in SENSITIVE_PATTERNS)


def domain_label(domain: Any) -> str:
    normalized = str(domain or "general").strip() or "general"
    return DOMAIN_LABELS.get(normalized, normalized)


def resolve_candidate_report_dir(skill_dir: Path, candidate_layer: str) -> Path:
    manifest_path = skill_dir / "references" / "addenda" / candidate_layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rules_candidate_file = artifacts.get("rules_candidate_file")
    if not rules_candidate_file:
        return skill_dir / "reports" / "addenda" / candidate_layer
    raw_path = Path(str(rules_candidate_file))
    resolved = raw_path if raw_path.is_absolute() else (manifest_path.parent / raw_path).resolve()
    return resolved.parent


def resolve_coverage_ledger_path(skill_dir: Path, candidate_layer: str) -> Path:
    manifest_path = skill_dir / "references" / "addenda" / candidate_layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    raw = artifacts.get("coverage_ledger_file")
    if raw:
        path = Path(str(raw))
        return path if path.is_absolute() else (manifest_path.parent / path).resolve()
    return skill_dir / "reports" / "addenda" / candidate_layer / "coverage-ledger.json"


def classify_data_point(entry: dict[str, Any]) -> tuple[str, str]:
    summary = normalize_inline(entry.get("summary"))
    topic = normalize_inline(entry.get("topic"))
    source_title = normalize_inline(entry.get("source_title"))
    source_page = entry.get("source_page")
    status = str(entry.get("status") or "")
    publish_target = str(entry.get("publish_target") or "")
    rule_layer_status = str(entry.get("rule_layer_status") or "")
    joined_status = " ".join([status, publish_target, rule_layer_status]).lower()

    if not summary or not (topic or source_title) or not source_page:
        return EXTRACTION_FAILED, "缺少可用摘要、主题或来源页，不能稳定用于回答。"
    if "conflict" in joined_status or "冲突" in joined_status:
        return CONFLICT, "这条内容存在冲突标记，需要先统一口径。"
    if publish_target == "runtime" or status == "runtime_hard_rule" or rule_layer_status == "runtime":
        return READY, "已被规则层标记为可用数据，可进入企业 Agent 候选。"
    if publish_target == "knowledge" or status == "knowledge_ready" or rule_layer_status == "knowledge":
        return READY, "已被全书闭环标记为可回答知识，可进入企业 Agent 知识候选。"
    if publish_target == "manual_review" or rule_layer_status == "manual_review" or status == "unresolved":
        return REVIEW, "数据能提取出来，但还需要人工确认口径。"
    if status == "not_safe_for_auto_answer" or rule_layer_status == "not_auto":
        return NOT_AUTOMATED, "全书闭环已明确为不适合自动回答，不能进入报价或咨询自动链路。"
    if status == "needs_source_recheck" or rule_layer_status == "source_recheck":
        return NOT_AUTOMATED, "全书闭环已明确需要源证据复核，发布包中不自动开放。"
    if publish_target == "none" or status == "excluded_background" or rule_layer_status == "excluded":
        return NOT_AUTOMATED, "更像背景说明或非问答规则，默认不自动回答。"
    return REVIEW, "分类信号不够明确，先进入人工复核。"


def classify_pricing_system_layer(entry: dict[str, Any], decision: str) -> tuple[str, str]:
    if decision in {REVIEW, EXTRACTION_FAILED, CONFLICT}:
        return MANUAL_REVIEW_LAYER, "需要人工确认后才能接入报价或咨询链路。"
    if decision == NOT_AUTOMATED:
        return NOT_EXPOSED_LAYER, "背景说明或非问答规则不对用户自动开放。"

    text = normalize_inline(
        " ".join(
            [
                entry.get("topic", ""),
                entry.get("summary", ""),
                entry.get("source_title", ""),
                entry.get("source_path", ""),
                entry.get("status", ""),
                entry.get("publish_target", ""),
            ]
        )
    )
    if any(keyword in text for keyword in CALC_KEYWORDS):
        return QUOTE_CALC_RULE, "含价格、加价、折减、补差或公式信号，优先进入报价计算候选。"
    if any(keyword in text for keyword in PRECHECK_KEYWORDS):
        return QUOTE_PRECHECK_RULE, "含尺寸、限制、备注或确认信号，优先进入报价前追问/拦截。"
    return DESIGNER_KNOWLEDGE, "可用于设计师咨询回答，但不直接参与报价计算。"


def clean_answer_outline(summary: str) -> str:
    text = normalize_inline(summary)
    text = text.replace("本段主要描述", "文档说明")
    text = text.replace("本段主要给出", "文档给出")
    text = re.sub(r"识别标签：[^。；]*[。；]?", "", text)
    text = text.replace("关键信息：", "关键数据：")
    return excerpt(text, 260)


def trigger_questions(entry: dict[str, Any]) -> list[str]:
    source_title = normalize_inline(entry.get("source_title"))
    topic = normalize_inline(entry.get("topic"))
    domain = domain_label(entry.get("domain"))
    questions: list[str] = []
    if source_title:
        questions.append(f"{source_title}有什么要求？")
    if topic and topic != source_title:
        questions.append(f"{topic}怎么处理？")
    if domain and topic:
        questions.append(f"{domain}里关于{excerpt(topic, 28)}怎么说？")
    return questions[:3]


def build_data_point(entry: dict[str, Any], index: int) -> dict[str, Any]:
    decision, reason = classify_data_point(entry)
    pricing_layer, pricing_layer_reason = classify_pricing_system_layer(entry, decision)
    source_local_path = normalize_inline(entry.get("source_local_path"))
    return {
        "id": f"data-point-{index:04d}",
        "decision": decision,
        "decision_reason": reason,
        "pricing_system_layer": pricing_layer,
        "pricing_system_layer_reason": pricing_layer_reason,
        "agent_ready": decision == READY,
        "needs_human_review": decision in {REVIEW, EXTRACTION_FAILED, CONFLICT},
        "domain": str(entry.get("domain") or "general"),
        "domain_label": domain_label(entry.get("domain")),
        "topic": normalize_inline(entry.get("topic")),
        "extracted_data": normalize_inline(entry.get("summary")),
        "answer_outline": clean_answer_outline(str(entry.get("summary") or "")),
        "source": {
            "title": normalize_inline(entry.get("source_title")),
            "page": entry.get("source_page") or "",
            "path": normalize_inline(entry.get("source_path")),
            "local_path": "" if is_sensitive(source_local_path) else source_local_path,
            "node_id": normalize_inline(entry.get("source_node_id")),
        },
        "trigger_questions": trigger_questions(entry),
    }


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", normalize_inline(text))
    deduped: list[str] = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped


def extract_query_terms(question: str) -> list[str]:
    terms: list[str] = []
    normalized = normalize_inline(question)
    for term in sorted(IMPORTANT_QUERY_TERMS, key=len, reverse=True):
        if term in normalized and term not in terms:
            terms.append(term)
            for alias in QUERY_ALIASES.get(term, ()):
                if alias not in terms:
                    terms.append(alias)
    if terms:
        return terms
    return tokenize(question)


def score_data_point(question: str, point: dict[str, Any]) -> float:
    topic = str(point.get("topic") or "")
    source_title = point.get("source", {}).get("title", "")
    answer_text = normalize_inline(" ".join([point.get("extracted_data", ""), point.get("answer_outline", "")]))
    source_text = normalize_inline(" ".join([source_title, point.get("source", {}).get("path", "")]))
    haystack = normalize_inline(
        " ".join(
            [
                topic,
                answer_text,
                source_text,
            ]
        )
    )
    for query_term, required_groups in REQUIRED_TERM_GROUPS.items():
        if query_term not in question:
            continue
        for group in required_groups:
            if not any(required in haystack for required in group):
                return 0.0
    score = 0.0
    matched_terms = 0
    query_terms = extract_query_terms(question)
    for token in query_terms:
        if token in haystack:
            matched_terms += 1
            if token in source_title or token in topic:
                score += 6.0
            elif token in answer_text:
                score += 3.0
            else:
                score += 1.0
    numeric_terms = re.findall(r"\d+(?:\.\d+)?\s*(?:mm|cm|m|MM|CM|M)?", question)
    for number in numeric_terms:
        if number and number in haystack:
            score += 2.0
    if len(query_terms) >= 3 and matched_terms < 2:
        return 0.0
    if point.get("decision") == READY:
        score += 0.5
    return score


def query_data_points(question: str, data_points: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(
        ((score_data_point(question, point), point) for point in data_points),
        key=lambda item: item[0],
        reverse=True,
    )
    results: list[dict[str, Any]] = []
    for score, point in ranked:
        if score <= 0:
            continue
        compact = {
            "score": round(score, 3),
            "id": point["id"],
            "decision": point["decision"],
            "topic": point["topic"],
            "source": point["source"],
            "answer_outline": point["answer_outline"],
        }
        results.append(compact)
        if len(results) >= limit:
            break
    return results


def build_query_probe_results(data_points: list[dict[str, Any]], probes: tuple[str, ...] = DEFAULT_QUERY_PROBES) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for question in probes:
        matches = query_data_points(question, data_points, limit=3)
        results.append(
            {
                "question": question,
                "matched": bool(matches),
                "top_score": matches[0]["score"] if matches else 0,
                "top_match": matches[0] if matches else {},
                "matches": matches,
            }
        )
    return results


def build_certification_model(*, skill_dir: Path, candidate_layer: str) -> dict[str, Any]:
    coverage_path = resolve_coverage_ledger_path(skill_dir, candidate_layer)
    coverage = load_json(coverage_path, {"entries": []})
    entries = [entry for entry in coverage.get("entries", []) if isinstance(entry, dict)]
    data_points = [build_data_point(entry, index) for index, entry in enumerate(entries, start=1)]
    decision_counts = Counter(point["decision"] for point in data_points)
    pricing_layer_counts = Counter(point["pricing_system_layer"] for point in data_points)
    domain_counts = Counter(point["domain_label"] for point in data_points)
    unique_pages = {
        (point["source"]["local_path"], str(point["source"]["page"]))
        for point in data_points
        if point["source"]["local_path"] and point["source"]["page"]
    }
    unique_topics = {point["topic"] for point in data_points if point["topic"]}
    query_probe_results = build_query_probe_results(data_points)
    ready_count = decision_counts.get(READY, 0)
    review_count = decision_counts.get(REVIEW, 0)
    failed_count = decision_counts.get(EXTRACTION_FAILED, 0)
    conflict_count = decision_counts.get(CONFLICT, 0)
    if ready_count and not review_count and not failed_count and not conflict_count:
        recommended_action = "全书数据闭环已完成：可发布明确开放的数据点，未开放内容已落入排除或源证据复核状态。"
    elif ready_count and not failed_count:
        recommended_action = "可进入全量数据认证下一步：先开放可进入数据点，复核项单独处理。"
    elif ready_count:
        recommended_action = "可小范围开放通过数据点，但需先处理提取失败项。"
    else:
        recommended_action = "暂不开放：当前没有稳定可进入企业 Agent 的数据点。"
    return {
        "title": "良禽佳木设计师手册整本文档数据可用性认证",
        "candidate_layer": candidate_layer,
        "coverage_ledger": str(coverage_path),
        "entry_count": len(data_points),
        "covered_page_count": len(unique_pages),
        "topic_count": len(unique_topics),
        "decision_counts": dict(decision_counts),
        "pricing_system_layer_counts": dict(pricing_layer_counts),
        "domain_counts": dict(domain_counts),
        "ready_count": ready_count,
        "review_count": review_count,
        "recommended_action": recommended_action,
        "query_probe_results": query_probe_results,
        "data_points": data_points,
    }


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
      <section class="metric">
        <div class="metric__label">{esc(label)}</div>
        <div class="metric__value">{esc(value)}</div>
        <div class="metric__hint">{esc(hint)}</div>
      </section>
    """


def render_probe(probe: dict[str, Any]) -> str:
    top = probe.get("top_match") if isinstance(probe.get("top_match"), dict) else {}
    source = top.get("source") if isinstance(top.get("source"), dict) else {}
    return f"""
      <article class="probe">
        <h3>{esc(probe.get('question'))}</h3>
        <p><strong>命中状态：</strong>{esc('已命中' if probe.get('matched') else '未命中')} · <strong>分数：</strong>{esc(probe.get('top_score', 0))}</p>
        <p><strong>命中数据：</strong>{esc(top.get('topic') or '无')}</p>
        <p><strong>来源：</strong>{esc(source.get('title') or '无')} 第 {esc(source.get('page') or '')} 页</p>
        <p>{esc(excerpt(top.get('answer_outline') or '', 180))}</p>
      </article>
    """


def render_data_point_card(point: dict[str, Any]) -> str:
    source = point["source"]
    questions = "".join(f"<li>{esc(question)}</li>" for question in point.get("trigger_questions", []))
    return f"""
      <article class="data-card" data-decision="{esc(point.get('decision'))}">
        <div class="card-topline">
          <span>{esc(point.get('domain_label'))}</span>
          <span>{esc(point.get('decision'))}</span>
        </div>
        <h3>{esc(excerpt(point.get('topic'), 90) or source.get('title') or point.get('id'))}</h3>
        <p class="answer"><strong>提取数据：</strong>{esc(excerpt(point.get('answer_outline'), 260))}</p>
        <div class="facts">
          <div><strong>来源：</strong>{esc(source.get('title'))} 第 {esc(source.get('page'))} 页</div>
          <div><strong>报价系统分层：</strong>{esc(point.get('pricing_system_layer'))}</div>
          <div><strong>处理建议：</strong>{esc(point.get('decision_reason'))}</div>
          <div><strong>分层理由：</strong>{esc(point.get('pricing_system_layer_reason'))}</div>
          <div><strong>可进 Agent：</strong>{esc('是' if point.get('agent_ready') else '否')}</div>
          <div><strong>需复核：</strong>{esc('是' if point.get('needs_human_review') else '否')}</div>
        </div>
        <section>
          <h4>可触发问法</h4>
          <ul>{questions or '<li>暂无自动问法，需人工补充。</li>'}</ul>
        </section>
      </article>
    """


def render_html(model: dict[str, Any], *, max_cards: int = 0) -> str:
    decision_counts = model.get("decision_counts", {})
    pricing_layer_counts = model.get("pricing_system_layer_counts", {})
    data_points = sorted(
        model.get("data_points", []),
        key=lambda point: (
            PRICING_LAYER_ORDER.get(point.get("pricing_system_layer"), 99),
            DECISION_ORDER.get(point.get("decision"), 99),
            point.get("domain_label", ""),
            point.get("id", ""),
        ),
    )
    rendered_points = data_points if max_cards <= 0 else data_points[:max_cards]
    cards = "\n".join(render_data_point_card(point) for point in rendered_points)
    probes = "\n".join(render_probe(probe) for probe in model.get("query_probe_results", []))
    hidden_count = max(0, len(data_points) - len(rendered_points))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(model.get('title'))}</title>
  <style>
    :root {{
      --paper: #f4eee3;
      --card: #fffaf1;
      --ink: #251d16;
      --muted: #756656;
      --line: #dcc9b1;
      --accent: #815331;
      --green: #3f6d4b;
      --amber: #a56228;
      --red: #963f36;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); background: radial-gradient(circle at top left, #fff7e8, var(--paper) 44%, #e8d8c2); font-family: "Songti SC", "Noto Serif CJK SC", serif; }}
    .shell {{ max-width: 1320px; margin: 0 auto; padding: 42px 22px 80px; }}
    .hero {{ border: 1px solid var(--line); border-radius: 30px; padding: 34px; background: rgba(255, 250, 241, .93); box-shadow: 0 24px 70px rgba(62, 41, 20, .12); }}
    .eyebrow {{ color: var(--accent); letter-spacing: .16em; font-size: 13px; }}
    h1 {{ margin: 12px 0; font-size: clamp(34px, 5vw, 58px); line-height: 1.06; }}
    .hero p {{ max-width: 900px; color: var(--muted); font-size: 18px; line-height: 1.8; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 20px 0; }}
    .metric, .probe, .data-card, .decision {{ border: 1px solid var(--line); border-radius: 22px; background: rgba(255, 250, 241, .92); padding: 18px; }}
    .metric__label {{ color: var(--muted); font-size: 14px; }}
    .metric__value {{ font-size: 30px; font-weight: 900; margin: 8px 0; }}
    .metric__hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .decision {{ margin: 18px 0 24px; line-height: 1.7; background: #fffdf8; }}
    .section-title {{ margin: 30px 0 12px; font-size: 26px; }}
    .probes {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }}
    .probe h3 {{ margin: 0 0 8px; font-size: 17px; line-height: 1.4; }}
    .probe p {{ margin: 7px 0; color: var(--muted); line-height: 1.6; }}
    .board {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 14px; }}
    .data-card {{ box-shadow: 0 14px 40px rgba(70, 46, 23, .08); }}
    .data-card[data-decision="{READY}"] {{ border-color: rgba(63, 109, 75, .46); }}
    .data-card[data-decision="{REVIEW}"] {{ border-color: rgba(165, 98, 40, .48); }}
    .data-card[data-decision="{EXTRACTION_FAILED}"], .data-card[data-decision="{CONFLICT}"] {{ border-color: rgba(150, 63, 54, .48); }}
    .card-topline {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 13px; }}
    .card-topline span {{ border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: #fffdf8; }}
    h3 {{ line-height: 1.4; }}
    h4 {{ margin: 12px 0 6px; color: var(--accent); }}
    p, li, .facts div {{ line-height: 1.65; }}
    .answer, .facts {{ color: var(--muted); }}
    .facts {{ display: grid; grid-template-columns: 1fr; gap: 6px; margin: 10px 0; font-size: 14px; }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    .more {{ color: var(--muted); border: 1px dashed var(--line); border-radius: 18px; padding: 14px; margin-top: 14px; }}
    @media (max-width: 1100px) {{ .metrics, .probes, .board {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 720px) {{ .metrics, .probes, .board {{ grid-template-columns: 1fr; }} .shell {{ padding: 24px 14px 52px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 整本文档数据认证</div>
      <h1>{esc(model.get('title'))}</h1>
      <p>本看板把设计师手册从少量样例验证升级为整本文档级数据认证。成功标准是：能提取数据、用户问题能命中对应文档数据、回答基于文档本身。整页图不是硬门槛，只在用户要求看原文或人工核对时按来源页补充。</p>
    </section>
    <section class="metrics">
      {render_metric("候选数据点", model.get("entry_count", 0), "来自整本文档覆盖清单")}
      {render_metric("覆盖页", model.get("covered_page_count", 0), "按来源文件和页码去重")}
      {render_metric("主题数", model.get("topic_count", 0), "按候选主题去重")}
      {render_metric("可进 Agent", decision_counts.get(READY, 0), "可作为回答数据候选")}
      {render_metric("需复核", decision_counts.get(REVIEW, 0), "数据已提取但口径需确认")}
      {render_metric("提取失败", decision_counts.get(EXTRACTION_FAILED, 0), "缺摘要、主题或来源页")}
      {render_metric("规则冲突", decision_counts.get(CONFLICT, 0), "需先统一口径")}
      {render_metric("不自动答", decision_counts.get(NOT_AUTOMATED, 0), "背景类或非问答内容")}
      {render_metric("报价计算", pricing_layer_counts.get(QUOTE_CALC_RULE, 0), "可进入计算候选")}
      {render_metric("追问/拦截", pricing_layer_counts.get(QUOTE_PRECHECK_RULE, 0), "可接 precheck")}
      {render_metric("设计咨询", pricing_layer_counts.get(DESIGNER_KNOWLEDGE, 0), "仅回答不算价")}
      {render_metric("不开放/复核", pricing_layer_counts.get(MANUAL_REVIEW_LAYER, 0) + pricing_layer_counts.get(NOT_EXPOSED_LAYER, 0), "不直接上线")}
    </section>
    <section class="decision"><strong>推荐动作：</strong>{esc(model.get('recommended_action'))}</section>
    <h2 class="section-title">问题命中抽查</h2>
    <section class="probes">{probes}</section>
    <h2 class="section-title">全量数据点</h2>
    <section class="board">{cards}</section>
    {f'<div class="more">另有 {hidden_count} 条未在 HTML 中展开，完整内容见 JSON。</div>' if hidden_count else ''}
  </main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else resolve_candidate_report_dir(skill_dir, args.candidate_layer)
    output_json = output_dir / "full-document-data-certification.json"
    output_html = output_dir / "full-document-data-certification.html"
    model = build_certification_model(skill_dir=skill_dir, candidate_layer=args.candidate_layer)
    model["output_json"] = str(output_json)
    model["output_html"] = str(output_html)
    write_json(output_json, model)
    output_html.write_text(render_html(model, max_cards=args.max_html_cards), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(output_json),
                "html": str(output_html),
                "entry_count": model["entry_count"],
                "decision_counts": model["decision_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
