#!/usr/bin/env python3
"""Build a visual evidence layer for image-heavy designer-manual topics."""

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

try:
    from PIL import Image
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Image = None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SENSITIVE_PATTERNS = ("Signature=", "X-Amz-Signature", "token=", "access_token=", "https://alidocs2")
LOW_CONFIDENCE_THRESHOLD = 0.75
BLANK_PAGE_NONWHITE_RATIO_THRESHOLD = 0.005
TOPIC_ALIASES = {
    "安全规范": ["安全规范", "安全技术规范", "婴幼儿及儿童家具安全技术规范", "家具结构安全技术规范", "GB 28007", "GB 28008"],
    "儿童床": ["儿童床", "儿童家具", "婴幼儿", "GB 28007", "GB 28008"],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build visual evidence assets for a paused designer-manual layer.")
    parser.add_argument("--candidate-layer", required=True, help="Candidate layer id or directory name.")
    parser.add_argument("--topic", required=True, help="Topic to scope the first visual evidence slice, for example 岩板.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
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


def char_count(value: Any) -> int:
    return len(re.sub(r"\s+", "", str(value or "")))


def excerpt(value: Any, limit: int = 360) -> str:
    text = normalize_inline(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def resolve_manifest(skill_dir: Path, layer: str) -> dict[str, Any]:
    compare_module = load_module("compare_addendum_layers_for_visual_evidence", skill_dir / "scripts" / "compare_addendum_layers.py")
    return compare_module.resolve_manifest(skill_dir / "references" / "addenda", layer)


def resolve_artifact_path(manifest: dict[str, Any], artifact_name: str) -> Path:
    artifacts = manifest.get("artifacts", {})
    raw_path = artifacts.get(artifact_name) if isinstance(artifacts, dict) else ""
    if not raw_path:
        raise SystemExit(f"Missing artifact in manifest: {artifact_name}")
    path = Path(str(raw_path))
    return path if path.is_absolute() else (Path(str(manifest["_manifest_dir"])) / path).resolve()


def report_dir_for_manifest(manifest: dict[str, Any]) -> Path:
    return resolve_artifact_path(manifest, "rules_candidate_file").parent


def is_sensitive_url(value: str) -> bool:
    return any(pattern.lower() in value.lower() for pattern in SENSITIVE_PATTERNS)


def public_path(value: Any) -> str:
    text = str(value or "").strip()
    if is_sensitive_url(text):
        return ""
    return text


def topic_terms(topic: str) -> list[str]:
    terms = [topic, *TOPIC_ALIASES.get(topic, [])]
    normalized: list[str] = []
    for term in terms:
        text = normalize_inline(term)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def relative_url(path: str, *, from_dir: Path) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(from_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_uri()


def topic_hit(item: dict[str, Any], topic: str) -> bool:
    haystack = " ".join(
        normalize_inline(item.get(field))
        for field in (
            "source_title",
            "source_path",
            "raw_text",
            "normalized_explanation",
            "default_decision_reason",
        )
    )
    ocr = item.get("ocr") if isinstance(item.get("ocr"), dict) else {}
    haystack = f"{haystack} {normalize_inline(ocr.get('text'))}"
    return any(term in haystack for term in topic_terms(topic))


def extract_keywords(*, topic: str, page: dict[str, Any], ocr_text: str) -> list[str]:
    candidates = [topic, page.get("source_title"), page.get("source_path")]
    candidates.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", ocr_text))
    keywords: list[str] = []
    for candidate in candidates:
        text = normalize_inline(candidate)
        if not text:
            continue
        if len(text) > 24:
            continue
        if text not in keywords:
            keywords.append(text)
    return keywords[:18]


def collect_crop_images(ocr: dict[str, Any]) -> list[str]:
    output_dir = Path(str(ocr.get("output_dir") or ""))
    if not output_dir.exists():
        return []
    crops: list[str] = []
    for path in sorted(output_dir.glob("paddleocr/page-*/imgs/*")):
        if path.suffix.lower() in IMAGE_SUFFIXES:
            crops.append(str(path.resolve()))
    return crops


def confidence_for(page: dict[str, Any], page_image: str, crop_images: list[str], ocr_text: str) -> float:
    score = 0.35
    if page_image:
        score += 0.35
    if crop_images:
        score += 0.05
    if char_count(ocr_text) >= 80:
        score += 0.20
    elif char_count(ocr_text) >= 20:
        score += 0.10
    return min(score, 0.95)


def nonwhite_ratio(image_path: str) -> float | None:
    if not image_path:
        return None
    if Image is None:
        return None
    try:
        image = Image.open(image_path).convert("RGB").resize((180, 255))
    except Exception:
        return None
    pixels = image.getdata()
    nonwhite = sum(1 for red, green, blue in pixels if red < 245 or green < 245 or blue < 245)
    return nonwhite / (image.width * image.height)


def page_image_looks_blank(page_image: str) -> bool:
    ratio = nonwhite_ratio(page_image)
    return ratio is not None and ratio < BLANK_PAGE_NONWHITE_RATIO_THRESHOLD


def build_visual_entry(topic: str, page: dict[str, Any]) -> dict[str, Any]:
    ocr = page.get("ocr") if isinstance(page.get("ocr"), dict) else {}
    image = page.get("image") if isinstance(page.get("image"), dict) else {}
    ocr_text = normalize_inline(ocr.get("text"))
    page_image = public_path(image.get("path")) if image.get("status") == "succeeded" else ""
    debug_crop_images = [public_path(path) for path in collect_crop_images(ocr)]
    debug_crop_images = [path for path in debug_crop_images if path]
    blank_page_image = page_image_looks_blank(page_image)
    confidence = confidence_for(page, page_image, [], ocr_text)
    needs_human_review = not page_image or blank_page_image
    evidence_status = evidence_status_for(
        page_image=page_image,
        confidence=confidence,
        ocr_status=str(ocr.get("status") or ""),
        blank_page_image=blank_page_image,
    )
    return {
        "topic": topic,
        "keywords": extract_keywords(topic=topic, page=page, ocr_text=ocr_text),
        "source_title": normalize_inline(page.get("source_title")),
        "source_path": normalize_inline(page.get("source_path")),
        "source_page": int(page.get("source_page") or 0),
        "source_node_id": normalize_inline(page.get("source_node_id")),
        "source_local_path": public_path(page.get("source_local_path")),
        "ocr_status": str(ocr.get("status") or "unknown"),
        "ocr_summary": excerpt(ocr_text),
        "page_image": page_image,
        "crop_images": [],
        "debug_crop_images": debug_crop_images,
        "page_image_nonwhite_ratio": round(nonwhite_ratio(page_image) or 0.0, 6) if page_image else 0.0,
        "page_image_looks_blank": blank_page_image,
        "confidence": confidence,
        "evidence_status": evidence_status,
        "needs_human_review": needs_human_review,
        "review_reason": review_reason(page_image=page_image, blank_page_image=blank_page_image),
        "agent_guidance": agent_guidance(evidence_status),
    }


def evidence_status_for(*, page_image: str, confidence: float, ocr_status: str, blank_page_image: bool = False) -> str:
    if not page_image:
        return "needs_human_review"
    if blank_page_image:
        return "needs_human_review"
    if ocr_status != "succeeded" or confidence < LOW_CONFIDENCE_THRESHOLD:
        return "agent_visual_review"
    return "agent_ready"


def review_reason(*, page_image: str, blank_page_image: bool = False) -> str:
    if not page_image:
        return "当前资料缺少可展示整页图，不能直接给企业 Agent 使用。"
    if blank_page_image:
        return "当前整页图接近空白，不能作为可读证据；需要重新导出来源页或人工补证据。"
    return ""


def agent_guidance(evidence_status: str) -> str:
    if evidence_status == "needs_human_review":
        return "缺少可展示整页图，需要补资料或人工确认。"
    if evidence_status == "agent_visual_review":
        return "有整页图但 OCR 文字偏弱，Agent 应直接阅读整页图，不要求人工先介入。"
    return "文字和整页图证据均可用，Agent 可直接引用。"


def build_visual_model(*, skill_dir: Path, candidate_layer: str, topic: str) -> dict[str, Any]:
    manifest = resolve_manifest(skill_dir, candidate_layer)
    report_dir = report_dir_for_manifest(manifest)
    board_path = report_dir / "blocking-pages-review-board.json"
    board = load_json(board_path, {"pages": []})
    entries = [build_visual_entry(topic, page) for page in board.get("pages", []) if isinstance(page, dict) and topic_hit(page, topic)]
    entries = sorted(entries, key=lambda item: (item["source_title"], item["source_page"]))
    topic_dir = report_dir / "visual-evidence" / topic
    html_path = topic_dir / "visual-evidence-board.html"
    asset_path = topic_dir / "visual-assets.json"
    missing_page_image_count = sum(1 for entry in entries if not entry.get("page_image"))
    low_confidence_count = sum(1 for entry in entries if float(entry.get("confidence") or 0) < LOW_CONFIDENCE_THRESHOLD)
    needs_human_review_count = sum(1 for entry in entries if entry.get("needs_human_review"))
    agent_visual_review_count = sum(1 for entry in entries if entry.get("evidence_status") == "agent_visual_review")
    agent_ready_count = sum(1 for entry in entries if entry.get("evidence_status") == "agent_ready")
    return {
        "layer_id": manifest.get("layer_id", candidate_layer),
        "layer_status": manifest.get("status", ""),
        "topic": topic,
        "asset_count": len(entries),
        "page_image_count": sum(1 for entry in entries if entry.get("page_image")),
        "crop_image_count": sum(len(entry.get("debug_crop_images", [])) for entry in entries),
        "missing_page_image_count": missing_page_image_count,
        "low_confidence_count": low_confidence_count,
        "agent_ready_count": agent_ready_count,
        "agent_visual_review_count": agent_visual_review_count,
        "needs_human_review_count": needs_human_review_count,
        "recommended_action": recommended_action(
            asset_count=len(entries),
            missing_page_image_count=missing_page_image_count,
            needs_human_review_count=needs_human_review_count,
            agent_visual_review_count=agent_visual_review_count,
        ),
        "source_board": str(board_path),
        "asset_path": str(asset_path),
        "html_path": str(html_path),
        "entries": entries,
    }


def recommended_action(*, asset_count: int, missing_page_image_count: int, needs_human_review_count: int, agent_visual_review_count: int = 0) -> str:
    if asset_count == 0:
        return "继续暂停：当前主题未找到可用页。"
    if missing_page_image_count:
        return "需要补资料：存在缺少整页图的条目。"
    if needs_human_review_count:
        return "需要人工兜底：存在不可展示的证据页。"
    if agent_visual_review_count:
        return "可进入 Agent 视觉阅读：有整页图，OCR 弱的页面由 Agent 直接读图处理。"
    return "可进入下一阶段：可作为企业 Agent page-first 样板继续封装。"


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
      <section class="metric">
        <div class="metric__label">{esc(label)}</div>
        <div class="metric__value">{esc(value)}</div>
        <div class="metric__hint">{esc(hint)}</div>
      </section>
    """


def render_entry_card(entry: dict[str, Any], *, html_dir: Path) -> str:
    page_image = str(entry.get("page_image") or "")
    page_image_html = ""
    if page_image:
        page_image_html = f'<img class="page-image" src="{esc(relative_url(page_image, from_dir=html_dir))}" alt="整页图">'
    debug_crop_count = len(entry.get("debug_crop_images") or entry.get("crop_images", []))
    status = str(entry.get("evidence_status") or "")
    review_badge = {
        "needs_human_review": "需要人工兜底",
        "agent_visual_review": "Agent 读整页图",
        "agent_ready": "可给 Agent 引用",
    }.get(status, "可给 Agent 引用")
    return f"""
      <article class="card" data-review="{esc(review_badge)}">
        <div class="meta">
          <span>{esc(entry.get('source_title'))}</span>
          <span>源页 {esc(entry.get('source_page'))}</span>
          <span>{esc(review_badge)}</span>
        </div>
        <h3>{esc(entry.get('source_title'))} · 第 {esc(entry.get('source_page'))} 页</h3>
        <p class="summary">{esc(entry.get('ocr_summary') or 'OCR 未读到可用文字。')}</p>
        <p class="hint">{esc(entry.get('review_reason') or entry.get('agent_guidance') or '默认只给对应整页图，避免自动裁剪图误导判断。')}</p>
        <div class="keyword-row">{''.join(f'<span>{esc(keyword)}</span>' for keyword in entry.get('keywords', [])[:10])}</div>
        {page_image_html}
        <p class="debug-note">自动裁剪候选图：{esc(debug_crop_count)} 张，已保留在 JSON 中，仅用于机器调试，不在人工看板默认展示。</p>
      </article>
    """


def render_html(model: dict[str, Any]) -> str:
    html_path = Path(str(model["html_path"]))
    html_dir = html_path.parent
    cards = "\n".join(render_entry_card(entry, html_dir=html_dir) for entry in model.get("entries", []))
    if not cards:
        cards = '<section class="empty">当前主题还没有可用图文证据。</section>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(model.get('topic'))}图文证据看板</title>
  <style>
    :root {{
      --paper: #f8f1e7;
      --card: #fffaf2;
      --ink: #271f18;
      --muted: #796a5b;
      --line: #e2d2bd;
      --accent: #87512d;
      --good: #3f6f4c;
      --warn: #a45c24;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); background: radial-gradient(circle at top left, #fff 0, var(--paper) 42%, #eadcc8 100%); font-family: "Songti SC", "Noto Serif CJK SC", serif; }}
    .shell {{ max-width: 1220px; margin: 0 auto; padding: 40px 22px 80px; }}
    .hero {{ padding: 34px; border: 1px solid var(--line); border-radius: 30px; background: rgba(255, 250, 242, .92); box-shadow: 0 24px 70px rgba(63, 41, 18, .13); }}
    .eyebrow {{ color: var(--accent); letter-spacing: .14em; font-size: 13px; }}
    h1 {{ margin: 12px 0; font-size: clamp(34px, 5vw, 58px); line-height: 1.04; }}
    .hero p {{ max-width: 850px; color: var(--muted); font-size: 18px; line-height: 1.8; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }}
    .metric {{ border: 1px solid var(--line); border-radius: 20px; background: rgba(255, 250, 242, .86); padding: 17px; }}
    .metric__label {{ color: var(--muted); font-size: 14px; }}
    .metric__value {{ font-size: 30px; font-weight: 900; margin: 8px 0; }}
    .metric__hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .board {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .card {{ border: 1px solid var(--line); border-radius: 24px; padding: 18px; background: var(--card); box-shadow: 0 16px 44px rgba(70, 46, 23, .09); }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 13px; }}
    .meta span, .keyword-row span {{ border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: #fffdf8; }}
    h3 {{ margin: 14px 0 8px; font-size: 22px; }}
    .summary {{ color: var(--ink); line-height: 1.75; }}
    .hint {{ color: var(--warn); line-height: 1.65; }}
    .keyword-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; color: var(--muted); font-size: 13px; }}
    img {{ object-fit: contain; background: white; }}
    .page-image {{ width: 100%; height: auto; max-height: 520px; margin-top: 10px; border: 1px solid var(--line); border-radius: 16px; }}
    .debug-note {{ margin: 10px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }}
    .empty, .empty-crops {{ color: var(--muted); padding: 20px; border: 1px dashed var(--line); border-radius: 18px; background: #fffdf8; }}
    .decision {{ margin: 18px 0; padding: 18px 20px; border: 1px solid var(--line); border-radius: 22px; background: rgba(255, 253, 248, .9); color: var(--ink); line-height: 1.7; }}
    .decision strong {{ color: var(--accent); }}
    @media (max-width: 900px) {{ .metrics, .board {{ grid-template-columns: 1fr; }} .shell {{ padding: 24px 14px 52px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 图文证据层</div>
      <h1>{esc(model.get('topic'))}资料问答 + 配图</h1>
      <p>第一版默认只给 Agent 和人工审核员看“对应整页图”，不把自动裁剪图作为主要证据。自动裁剪候选图只保留在 JSON 里用于机器调试，避免人类误判是裁错还是原图本身有透视。</p>
    </section>
    <section class="metrics">
      {render_metric("图文条目", model.get("asset_count", 0), "当前主题收录页数")}
      {render_metric("可用页图", model.get("page_image_count", 0), "可作为整页证据返回")}
      {render_metric("Agent 读图", model.get("agent_visual_review_count", 0), "有整页图但 OCR 偏弱")}
      {render_metric("人工兜底", model.get("needs_human_review_count", 0), "仅缺整页图时触发")}
    </section>
    <section class="decision"><strong>推荐动作：</strong>{esc(model.get("recommended_action"))}</section>
    <section class="board">{cards}</section>
  </main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    model = build_visual_model(skill_dir=skill_dir, candidate_layer=args.candidate_layer, topic=args.topic)
    asset_path = Path(str(model["asset_path"]))
    html_path = Path(str(model["html_path"]))
    write_json(asset_path, model)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(model), encoding="utf-8")
    print(json.dumps({"asset_path": str(asset_path), "html_path": str(html_path), "asset_count": model["asset_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
