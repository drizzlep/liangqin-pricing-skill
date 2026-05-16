#!/usr/bin/env python3
"""Build a human-facing validation board for enterprise Agent readiness."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"
READY = "可进入企业 Agent 样例"
REVIEW = "可用但需人工复核"
BLOCKED = "暂不适合上线"
SENSITIVE_PATTERNS = ("Signature=", "X-Amz-", "token=", "access_token=", "secret", "Bearer")
INTERNAL_REPLY_TERMS = (
    "runtime",
    "高置信复盘口径",
    "证据等级",
    "规则咨询入口",
    "OCR",
    "evidence_level",
    "constraint_code",
    "PREVIOUS_ACTIVE",
)
CURRENT_STANDARD_STATUS = "ACTIVE"

DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "id": "rock-slab-visual",
        "category": "岩板材料图文查询",
        "question": "读一下岩板圣勃朗鱼肚，给我对应整页图。",
        "topic": "岩板",
        "expected": "能返回岩板整页证据，不展示自动裁剪图。",
    },
    {
        "id": "sliding-door-visual-rule",
        "category": "推拉门相关规则",
        "question": "推拉门单小块门板需要内缩多少？给我对应页图。",
        "topic": "推拉门",
        "expected": "能解释推拉门规则，并返回整页图证据。",
    },
    {
        "id": "open-shelf-seam",
        "category": "开放格/分段缝/柜体结构",
        "question": "超高带门柜体有开放格时，分段缝应该怎么对齐？",
        "topic": "",
        "expected": "能命中开放格/分段缝规则；缺关键尺寸时应追问或提示复核。",
    },
    {
        "id": "cabinet-build-default",
        "category": "柜体结构规则",
        "question": "常规拆装柜体高度超过1700mm时，默认顶盖侧还是侧盖顶？",
        "topic": "",
        "expected": "能给出柜体结构默认规则或明确需要确认的信息。",
    },
    {
        "id": "rock-slab-pricing",
        "category": "报价注意点",
        "question": "岩板台面和岩板背板报价或设计有什么注意点？",
        "topic": "岩板",
        "expected": "能结合岩板规则和整页资料，避免只凭自动识别文字判断。",
    },
    {
        "id": "children-bed-safety",
        "category": "儿童床/安全规范",
        "question": "儿童床有什么安全规范要注意？给我对应整页图。",
        "topic": "安全规范",
        "expected": "能返回安全规范整页图；图片或文字不可读时，不给具体建议。",
    },
    {
        "id": "archived-standard-boundary",
        "category": "旧版资料边界",
        "question": "榻榻米组合柜空区加托称时，需要固定上墙吗？",
        "topic": "",
        "expected": "如果新版手册缺口径，应明确新版未覆盖，不再使用旧版兜底。",
    },
    {
        "id": "source-boundary",
        "category": "资料边界保护",
        "question": "良禽佳木可以选国产五金和进口五金吗？良禽有 BLUM 五金吗？",
        "topic": "",
        "expected": "资料未明确时不按行业常识编造，直接提示确认。",
    },
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an enterprise Agent validation pack for the designer manual.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="Active online designer-manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--output-dir", default="", help="Override output directory. Defaults to the candidate layer report dir.")
    return parser.parse_args(argv)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
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


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def excerpt(value: Any, limit: int = 240) -> str:
    text = normalize_inline(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def is_sensitive(value: Any) -> bool:
    text = str(value or "")
    return any(pattern.lower() in text.lower() for pattern in SENSITIVE_PATTERNS)


def relative_url(path: str, *, from_dir: Path) -> str:
    if not path or is_sensitive(path):
        return ""
    try:
        return Path(path).resolve().relative_to(from_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_uri()


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


def load_layer_statuses(skill_dir: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for manifest_path in sorted((skill_dir / "references" / "addenda").glob("*/manifest.json")):
        manifest = load_json(manifest_path, {})
        status = str(manifest.get("status") or "").strip().upper()
        layer_id = str(manifest.get("layer_id") or manifest_path.parent.name)
        layer_name = str(manifest.get("layer_name") or layer_id)
        if status:
            statuses[layer_id] = status
            statuses[layer_name] = status
    return statuses


def layer_names_from_guidance(guidance: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("follow_up_questions", "constraints", "adjustments"):
        for item in guidance.get(key, []) or []:
            if isinstance(item, dict):
                layer_name = normalize_inline(item.get("layer_name"))
                if layer_name and layer_name not in names:
                    names.append(layer_name)
    for note in guidance.get("addendum_notes", []) or []:
        text = normalize_inline(note)
        if "：" in text:
            layer_name = text.rsplit("：", 1)[-1]
            if layer_name and layer_name not in names:
                names.append(layer_name)
    return names


def current_standard_usage(guidance: dict[str, Any], layer_statuses: dict[str, str]) -> dict[str, Any]:
    layer_names = layer_names_from_guidance(guidance)
    non_current_layers = [name for name in layer_names if layer_statuses.get(name) and layer_statuses.get(name) != CURRENT_STANDARD_STATUS]
    if non_current_layers:
        return {"used": True, "status": "命中非当前标准，需排除", "layers": non_current_layers}
    if layer_names:
        return {"used": False, "status": "仅使用新版", "layers": layer_names}
    if guidance.get("matched") and guidance.get("evidence_level") == "high_confidence_review":
        return {"used": False, "status": "未暴露来源", "layers": []}
    return {"used": False, "status": "仅使用新版", "layers": []}


def previous_active_usage(guidance: dict[str, Any], layer_statuses: dict[str, str]) -> dict[str, Any]:
    return current_standard_usage(guidance, layer_statuses)


def visual_is_ready(evidence: dict[str, Any]) -> bool:
    return bool(evidence) and bool(evidence.get("page_images")) and not evidence.get("needs_human_review")


def classify_case(
    *,
    guidance: dict[str, Any],
    evidence: dict[str, Any],
    requires_visual: bool,
    previous_usage: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    guidance_matched = bool(guidance.get("matched"))
    reply_mode = str(guidance.get("recommended_reply_mode") or "")
    evidence_level = str(guidance.get("evidence_level") or "")

    if requires_visual:
        if not evidence.get("page_images"):
            return BLOCKED, ["没有对应整页图证据，不能作为企业 Agent 样例。"]
        if evidence.get("crop_images"):
            return REVIEW, ["正式证据里仍出现自动裁剪图，需要回到 page-first。"]
        if evidence.get("review_reason") == "blank_visual_asset" or any(
            match.get("page_image_looks_blank") for match in evidence.get("matches", []) if isinstance(match, dict)
        ):
            return REVIEW, ["对应整页图接近空白，不能据此给出具体建议，需要重新导出或人工补证据。"]
        if evidence.get("needs_human_review"):
            reasons.append("图文证据层标记需要人工复核。")
        if evidence.get("evidence_status") == "agent_visual_review":
            reasons.append("这页文字不够稳，建议看整页图复核。")

    if reply_mode == "follow_up":
        reasons.append("还缺必要信息，需要补齐后再判断。")
    if previous_usage.get("used"):
        reasons.append("命中非当前标准资料，不能作为当前良禽标准自动回答。")
    if evidence_level == "source_boundary":
        reasons.append("文档没写清楚，不往外补。")
    if not guidance_matched and not visual_is_ready(evidence):
        return BLOCKED, ["规则和图文证据均未命中。"]

    if reasons and not (evidence_level == "source_boundary" and len(reasons) == 1):
        return REVIEW, reasons
    return READY, reasons or ["回答和证据满足本阶段样例要求。"]


def human_reply_for_case(case: dict[str, Any], guidance: dict[str, Any], evidence: dict[str, Any], decision: str) -> str:
    visual_answer = normalize_inline(evidence.get("answer"))
    if evidence.get("review_reason") in {"blank_visual_asset", "missing_visual_asset", "no_match"}:
        return humanize_visual_problem_reply(evidence)
    missing_fields = guidance.get("missing_fields", []) or []
    if str(guidance.get("recommended_reply_mode") or "") == "follow_up" and missing_fields:
        return f"还差一个信息：{normalize_inline(missing_fields[0])}。补上后才能判断。"
    if decision == REVIEW and case.get("topic") and evidence.get("needs_human_review"):
        return humanize_visual_problem_reply(evidence)
    if str(guidance.get("evidence_level") or "") == "source_boundary":
        return humanize_source_boundary_reply(guidance)
    if case.get("topic") and evidence.get("page_images") and evidence.get("answer"):
        return humanize_visual_ready_reply(case, evidence)
    suggested = normalize_inline(guidance.get("suggested_reply") or guidance.get("answer_summary"))
    if suggested:
        return humanize_rule_reply(suggested)
    if visual_answer:
        return humanize_visual_ready_reply(case, evidence)
    return "当前文档没有给出足够稳定的信息，不能编造结论；需要回到原文或人工确认。"


def humanize_visual_problem_reply(evidence: dict[str, Any]) -> str:
    reason = str(evidence.get("review_reason") or "")
    if reason == "blank_visual_asset":
        return "这页现在看不出有效内容。图片几乎是空白，文字也没读出来。所以不能直接回答具体要求，需要重新导出来源页，或者让人先确认原文。"
    if reason == "missing_visual_asset":
        return "这题现在缺少可看的整页图。没有图就不能核对原文，所以先不要作为 Agent 样例。"
    if reason == "no_match":
        return "当前资料里没有找到能对应这题的内容。不能用行业常识补答案。"
    return "这题现在证据不够稳，不能直接给结论。需要先看原文或补一张可读的整页图。"


def humanize_source_boundary_reply(guidance: dict[str, Any]) -> str:
    text = normalize_inline(guidance.get("answer_summary") or guidance.get("suggested_reply"))
    if "未明确" in text or "不能替你" in text:
        return "文档里没写清楚这件事，所以不能替你确认。要得到准确口径，需要问设计师或门店。"
    return humanize_rule_reply(text)


def humanize_visual_ready_reply(case: dict[str, Any], evidence: dict[str, Any]) -> str:
    topic = normalize_inline(case.get("topic")) or "这项资料"
    source_refs = evidence.get("source_refs", []) if isinstance(evidence.get("source_refs"), list) else []
    first_ref = source_refs[0] if source_refs and isinstance(source_refs[0], dict) else {}
    source_title = normalize_inline(first_ref.get("source_title")) or topic
    source_page = first_ref.get("source_page") or ""
    answer = normalize_inline(evidence.get("answer"))
    if topic == "岩板":
        matched_name = extract_rock_slab_name(answer)
        if matched_name:
            return f"找到了对应页：{source_title}第 {source_page} 页。页面里能看到 {matched_name} 和规格信息，请以整页图为准。"
        return f"找到了对应页：{source_title}第 {source_page} 页。请看整页图核对，别只看自动识别文字。"
    if source_page:
        return f"找到了对应页：{source_title}第 {source_page} 页。请看整页图核对。"
    return "找到了对应整页图。请看原页核对，不要只看自动识别文字。"


def extract_rock_slab_name(text: str) -> str:
    match = re.search(r"##\s*([^#]{2,24}?)\s*##", text)
    if match:
        return normalize_inline(match.group(1))
    for keyword in ("圣勃朗鱼肚", "保加利亚浅灰", "劳伦特", "岩板"):
        if keyword in text:
            return keyword
    return ""


def humanize_rule_reply(text: str) -> str:
    cleaned = normalize_inline(text)
    cleaned = re.sub(r"这个场景有明确要求。?", "", cleaned)
    cleaned = re.sub(r"这块有明确的补充规则。?", "", cleaned)
    cleaned = re.sub(r"这块目前还是高置信复盘口径，?术语口径还没完全锁定。?", "这条还要以原文复核。", cleaned)
    cleaned = re.sub(r"如果是问(.+?)这组", r"\1这组", cleaned)
    cleaned = cleaned.replace("现有复盘里能稳定读到：", "文档里能读到：")
    cleaned = cleaned.replace("现有手册能稳定确认到：", "文档里能读到：")
    cleaned = cleaned.replace("目前能稳定确认到", "文档里能读到")
    cleaned = cleaned.replace("常见做法是", "一般写法是")
    cleaned = cleaned.replace("常见按", "通常按")
    cleaned = cleaned.replace("runtime 规则", "原规则")
    cleaned = cleaned.replace("高置信复盘口径", "复核口径")
    cleaned = cleaned.replace("；", "；")
    for term in INTERNAL_REPLY_TERMS:
        cleaned = cleaned.replace(term, "")
    parts = [part.strip() for part in re.split(r"(?<=[。；])", cleaned) if part.strip()]
    if len(parts) > 3:
        cleaned = "".join(parts[:3]).strip()
    return cleaned or "当前文档没有给出足够稳定的信息，不能编造结论；需要回到原文或人工确认。"


def build_case_result(
    case: dict[str, Any],
    *,
    guidance: dict[str, Any],
    evidence: dict[str, Any],
    layer_statuses: dict[str, str],
) -> dict[str, Any]:
    current_usage = current_standard_usage(guidance, layer_statuses)
    requires_visual = bool(case.get("topic"))
    decision, reasons = classify_case(
        guidance=guidance,
        evidence=evidence,
        requires_visual=requires_visual,
        previous_usage=current_usage,
    )
    suggested_reply = human_reply_for_case(case, guidance, evidence, decision)
    page_images = [path for path in evidence.get("page_images", []) if path and not is_sensitive(path)]
    source_refs = evidence.get("source_refs", []) if isinstance(evidence.get("source_refs"), list) else []
    rule_sources = layer_names_from_guidance(guidance)
    return {
        "id": case.get("id"),
        "category": case.get("category"),
        "question": case.get("question"),
        "expected": case.get("expected"),
        "topic": case.get("topic") or "",
        "decision": decision,
        "decision_reasons": reasons,
        "agent_sample_ready": decision == READY,
        "suggested_reply": suggested_reply,
        "guidance": {
            "matched": bool(guidance.get("matched")),
            "reply_mode": guidance.get("recommended_reply_mode") or "none",
            "evidence_level": guidance.get("evidence_level") or "",
            "missing_fields": guidance.get("missing_fields", []) or [],
            "constraint_code": guidance.get("constraint_code"),
        },
        "visual_evidence": {
            "evidence_status": evidence.get("evidence_status") or ("not_requested" if not requires_visual else "missing"),
            "needs_human_review": bool(evidence.get("needs_human_review")),
            "review_reason": evidence.get("review_reason") or "",
            "page_images": page_images,
            "crop_images": evidence.get("crop_images", []) or [],
            "debug_crop_image_count": len(evidence.get("debug_crop_images", []) or []),
            "source_refs": source_refs,
        },
        "rule_sources": rule_sources,
        "current_standard_usage": current_usage,
    }


def build_validation_model(
    *,
    skill_dir: Path,
    candidate_layer: str,
    cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    script_dir = skill_dir / "scripts"
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    guidance_module = load_module("query_addendum_guidance_for_agent_validation", script_dir / "query_addendum_guidance.py")
    evidence_module = load_module("query_manual_evidence_for_agent_validation", script_dir / "query_manual_evidence.py")
    layer_statuses = load_layer_statuses(skill_dir)
    addenda_root = skill_dir / "references" / "addenda"
    results: list[dict[str, Any]] = []
    for case in cases or DEFAULT_CASES:
        question = str(case["question"])
        guidance = guidance_module.query_guidance(question, addenda_root)
        evidence: dict[str, Any] = {}
        topic = str(case.get("topic") or "").strip()
        if topic:
            evidence = evidence_module.build_response(
                text=question,
                candidate_layer=candidate_layer,
                topic=topic,
                skill_dir=skill_dir,
            )
        results.append(build_case_result(case, guidance=guidance, evidence=evidence, layer_statuses=layer_statuses))

    decision_counts = Counter(result["decision"] for result in results)
    page_first_violations = sum(1 for result in results if result["visual_evidence"]["crop_images"])
    non_current_count = sum(1 for result in results if result["current_standard_usage"]["used"])
    review_count = decision_counts.get(REVIEW, 0)
    blocked_count = decision_counts.get(BLOCKED, 0)
    if blocked_count:
        recommended_action = "暂不封装：先处理暂不适合上线的验证题。"
    elif review_count:
        recommended_action = "可小范围试用：先把可进入样例的题放入企业 Agent demo，复核项单独消化。"
    else:
        recommended_action = "可进入企业 Agent 样例封装：当前验证题均满足 page-first 与规则边界要求。"

    return {
        "title": "良禽设计师手册企业 Agent 验证包",
        "candidate_layer": candidate_layer,
        "case_count": len(results),
        "decision_counts": dict(decision_counts),
        "page_first_violations": page_first_violations,
        "non_current_standard_case_count": non_current_count,
        "recommended_action": recommended_action,
        "cases": results,
    }


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
      <section class="metric">
        <div class="metric__label">{esc(label)}</div>
        <div class="metric__value">{esc(value)}</div>
        <div class="metric__hint">{esc(hint)}</div>
      </section>
    """


def render_page_images(result: dict[str, Any], *, html_dir: Path) -> str:
    images = result["visual_evidence"].get("page_images", [])[:3]
    if not images:
        return '<p class="no-image">本题没有默认整页图证据。</p>'
    image_tags = []
    for image_path in images:
        url = relative_url(str(image_path), from_dir=html_dir)
        if url:
            image_tags.append(f'<a href="{esc(url)}"><img src="{esc(url)}" alt="对应整页图"></a>')
    return f'<div class="page-images">{"".join(image_tags)}</div>' if image_tags else '<p class="no-image">整页图路径不可安全展示。</p>'


def render_case_card(result: dict[str, Any], *, html_dir: Path) -> str:
    visual = result["visual_evidence"]
    guidance = result["guidance"]
    current_usage = result["current_standard_usage"]
    source_refs = visual.get("source_refs", [])[:3]
    source_html = "".join(
        f"<li>{esc(ref.get('source_title'))} 第 {esc(ref.get('source_page'))} 页</li>"
        for ref in source_refs
        if isinstance(ref, dict)
    )
    if not source_html:
        source_html = "<li>无整页图来源，或本题不需要图文证据。</li>"
    reasons = "".join(f"<li>{esc(reason)}</li>" for reason in result.get("decision_reasons", []))
    rule_sources = result.get("rule_sources", [])
    rule_source_text = "、".join(rule_sources) if rule_sources else "未暴露规则层来源或本题仅为资料边界保护"
    missing_fields = guidance.get("missing_fields") or []
    missing_text = "、".join(str(field) for field in missing_fields) if missing_fields else "无"
    answer_state = "能回答" if guidance.get("matched") and result.get("agent_sample_ready") else "需要确认" if result.get("decision") == REVIEW else "暂不回答"
    return f"""
      <article class="case-card" data-decision="{esc(result.get('decision'))}">
        <div class="case-topline">
          <span>{esc(result.get('category'))}</span>
          <span>{esc(result.get('decision'))}</span>
        </div>
        <h2>{esc(result.get('question'))}</h2>
        <p class="expected"><strong>验收点：</strong>{esc(result.get('expected'))}</p>
        <section class="reply">
          <h3>Agent 建议回答</h3>
          <p>{esc(excerpt(result.get('suggested_reply'), 520) or '当前没有稳定回答。')}</p>
        </section>
        <section class="facts">
          <div><strong>回答状态：</strong>{esc(answer_state)}</div>
          <div><strong>还缺什么：</strong>{esc(missing_text)}</div>
          <div><strong>当前标准：</strong>{esc(current_usage.get('status'))}</div>
          <div><strong>整页图：</strong>{esc('有' if visual.get('page_images') else '无')}</div>
          <div><strong>需人工复核：</strong>{esc('是' if visual.get('needs_human_review') or result.get('decision') == REVIEW else '否')}</div>
          <div><strong>可作为样例：</strong>{esc('是' if result.get('agent_sample_ready') else '否')}</div>
          <div><strong>调试裁剪图：</strong>{esc(visual.get('debug_crop_image_count'))} 张，仅 JSON 保留</div>
        </section>
        <section class="sources">
          <h3>规则或资料来源</h3>
          <p>{esc(rule_source_text)}</p>
          <ul>{source_html}</ul>
        </section>
        <section class="reasons">
          <h3>判断理由</h3>
          <ul>{reasons}</ul>
        </section>
        {render_page_images(result, html_dir=html_dir)}
      </article>
    """


def render_html(model: dict[str, Any], *, html_path: Path) -> str:
    html_dir = html_path.parent
    cards = "\n".join(render_case_card(result, html_dir=html_dir) for result in model.get("cases", []))
    decision_counts = model.get("decision_counts", {})
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(model.get('title'))}</title>
  <style>
    :root {{
      --paper: #f6efe4;
      --card: #fffaf1;
      --ink: #261e17;
      --muted: #756656;
      --line: #decdb8;
      --accent: #82502e;
      --green: #416f4f;
      --amber: #a3612a;
      --red: #934038;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); background: linear-gradient(135deg, #fffaf1 0%, var(--paper) 52%, #eadcc8 100%); font-family: "Songti SC", "Noto Serif CJK SC", serif; }}
    .shell {{ max-width: 1240px; margin: 0 auto; padding: 42px 22px 80px; }}
    .hero {{ border: 1px solid var(--line); border-radius: 30px; padding: 34px; background: rgba(255, 250, 241, .92); box-shadow: 0 24px 70px rgba(62, 41, 20, .12); }}
    .eyebrow {{ color: var(--accent); letter-spacing: .16em; font-size: 13px; }}
    h1 {{ margin: 12px 0; font-size: clamp(34px, 5vw, 60px); line-height: 1.05; }}
    .hero p {{ max-width: 880px; color: var(--muted); font-size: 18px; line-height: 1.8; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 20px 0; }}
    .metric {{ border: 1px solid var(--line); border-radius: 20px; background: rgba(255, 250, 241, .88); padding: 17px; }}
    .metric__label {{ color: var(--muted); font-size: 14px; }}
    .metric__value {{ font-size: 30px; font-weight: 900; margin: 8px 0; }}
    .metric__hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .decision {{ margin: 18px 0 26px; border: 1px solid var(--line); border-radius: 22px; padding: 18px 20px; background: #fffdf8; line-height: 1.7; }}
    .board {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .case-card {{ border: 1px solid var(--line); border-radius: 24px; padding: 20px; background: var(--card); box-shadow: 0 16px 44px rgba(70, 46, 23, .09); }}
    .case-card[data-decision="{READY}"] {{ border-color: rgba(65, 111, 79, .42); }}
    .case-card[data-decision="{REVIEW}"] {{ border-color: rgba(163, 97, 42, .5); }}
    .case-card[data-decision="{BLOCKED}"] {{ border-color: rgba(147, 64, 56, .5); }}
    .case-topline {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 13px; }}
    .case-topline span {{ border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: #fffdf8; }}
    h2 {{ font-size: 22px; line-height: 1.35; margin: 14px 0 8px; }}
    h3 {{ margin: 14px 0 8px; font-size: 16px; color: var(--accent); }}
    p, li, .facts div {{ line-height: 1.7; }}
    .expected, .sources, .reasons {{ color: var(--muted); }}
    .reply {{ border: 1px solid var(--line); border-radius: 18px; background: #fffdf8; padding: 12px 14px; }}
    .facts {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; margin: 14px 0; font-size: 14px; }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    .page-images {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }}
    .page-images img {{ width: 100%; height: 220px; object-fit: contain; border: 1px solid var(--line); border-radius: 14px; background: white; }}
    .no-image {{ color: var(--muted); border: 1px dashed var(--line); border-radius: 14px; padding: 12px; }}
    @media (max-width: 920px) {{ .metrics, .board, .facts {{ grid-template-columns: 1fr; }} .page-images {{ grid-template-columns: 1fr; }} .shell {{ padding: 24px 14px 52px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 企业 Agent 验证包</div>
      <h1>{esc(model.get('title'))}</h1>
      <p>本看板用真实业务问题检查当前设计师手册能力包是否适合给企业 Agent 使用。默认采用 page-first：只把对应整页图作为正式图文证据，自动裁剪图只留在 JSON 调试字段里。</p>
    </section>
    <section class="metrics">
      {render_metric("验证题", model.get("case_count", 0), "覆盖图文、规则、报价和边界保护")}
      {render_metric("可进样例", decision_counts.get(READY, 0), "可作为企业 Agent demo")}
      {render_metric("需复核", decision_counts.get(REVIEW, 0), "需要人工确认或补字段")}
      {render_metric("暂不上线", decision_counts.get(BLOCKED, 0), "不建议进入样例")}
    </section>
    <section class="decision"><strong>推荐动作：</strong>{esc(model.get('recommended_action'))}</section>
    <section class="board">{cards}</section>
  </main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else resolve_candidate_report_dir(skill_dir, args.candidate_layer)
    output_json = output_dir / "agent-validation-pack.json"
    output_html = output_dir / "agent-validation-pack.html"
    model = build_validation_model(skill_dir=skill_dir, candidate_layer=args.candidate_layer)
    model["output_json"] = str(output_json)
    model["output_html"] = str(output_html)
    write_json(output_json, model)
    output_html.write_text(render_html(model, html_path=output_html), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "html": str(output_html), "case_count": model["case_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
