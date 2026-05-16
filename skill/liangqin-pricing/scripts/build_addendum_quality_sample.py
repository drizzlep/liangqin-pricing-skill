#!/usr/bin/env python3
"""Build a human quality sample board for a designer-manual addendum layer."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from PyPDF2 import PdfReader, PdfWriter
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    PdfReader = None
    PdfWriter = None


RISK_KEYWORDS = (
    "报价",
    "加价",
    "折减",
    "尺寸",
    "限制",
    "必须",
    "不可",
    "不建议",
    "门",
    "柜",
    "床",
    "铰链",
    "岩板",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a quality sample board for a paused online addendum layer.")
    parser.add_argument("--candidate-layer", required=True, help="Candidate layer id or directory name.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--sample-size", type=int, default=48, help="Maximum number of page samples shown on the board.")
    parser.add_argument("--ocr-sample-size", type=int, default=8, help="Maximum number of page samples checked with PaddleOCR.")
    parser.add_argument("--render-sample-size", type=int, default=24, help="Maximum number of page samples rendered to images.")
    parser.add_argument("--run-ocr", action="store_true", help="Run PaddleOCR on the highest-risk sampled pages.")
    parser.add_argument("--skip-render", action="store_true", help="Skip rendering PDF pages to PNG thumbnails.")
    parser.add_argument("--paddleocr-lang", default="ch", help="Language hint passed to PaddleOCR when used.")
    parser.add_argument("--paddleocr-device", default="cpu", help="Device hint passed to PaddleOCR when used.")
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


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def char_count(value: Any) -> int:
    return len(re.sub(r"\s+", "", str(value or "")))


def excerpt(value: Any, limit: int = 180) -> str:
    text = normalize_inline(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def resolve_manifest(skill_dir: Path, layer: str) -> dict[str, Any]:
    compare_module = load_module("compare_addendum_layers_for_quality", skill_dir / "scripts" / "compare_addendum_layers.py")
    return compare_module.resolve_manifest(skill_dir / "references" / "addenda", layer)


def resolve_artifact_path(manifest: dict[str, Any], artifact_name: str) -> Path:
    artifacts = manifest.get("artifacts", {})
    raw_path = artifacts.get(artifact_name) if isinstance(artifacts, dict) else ""
    if not raw_path:
        raise SystemExit(f"Missing artifact in manifest: {artifact_name}")
    path = Path(str(raw_path))
    return path if path.is_absolute() else (Path(str(manifest["_manifest_dir"])) / path).resolve()


def page_sort_key(page: dict[str, Any]) -> tuple[str, int]:
    return (str(page.get("source_title", "")), int(page.get("source_page", page.get("page", 0)) or 0))


def has_risk_keyword(text: str) -> bool:
    return any(keyword in text for keyword in RISK_KEYWORDS)


def sample_evenly_by_source(pages: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for page in pages:
        source_key = str(page.get("source_local_path") or page.get("source_title") or "")
        if source_key in seen_sources:
            continue
        selected.append(page)
        seen_sources.add(source_key)
        if len(selected) >= limit:
            return selected
    for page in pages:
        if page not in selected:
            selected.append(page)
            if len(selected) >= limit:
                break
    return selected


def mark_sample(page: dict[str, Any], reason: str, priority: int) -> dict[str, Any]:
    item = dict(page)
    reasons = list(item.get("_sample_reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    item["_sample_reasons"] = reasons
    item["_sample_priority"] = min(int(item.get("_sample_priority", priority) or priority), priority)
    return item


def select_page_samples(pages: list[dict[str, Any]], *, sample_size: int) -> list[dict[str, Any]]:
    samples_by_key: dict[tuple[str, int], dict[str, Any]] = {}

    def add(items: list[dict[str, Any]], reason: str, priority: int, limit: int) -> None:
        for page in sample_evenly_by_source(items, limit):
            key = (str(page.get("source_local_path") or page.get("source_title") or ""), int(page.get("source_page") or 0))
            marked = mark_sample(page, reason, priority)
            if key in samples_by_key:
                merged = dict(samples_by_key[key])
                existing = list(merged.get("_sample_reasons") or [])
                for item in marked.get("_sample_reasons") or []:
                    if item not in existing:
                        existing.append(item)
                merged["_sample_reasons"] = existing
                merged["_sample_priority"] = min(int(merged.get("_sample_priority", priority) or priority), priority)
                samples_by_key[key] = merged
            else:
                samples_by_key[key] = marked

    unknown_pages = sorted(
        [page for page in pages if str(page.get("extract_method")) == "unknown"],
        key=page_sort_key,
    )
    image_pages = sorted(
        [page for page in pages if int(page.get("image_count") or 0) >= 3],
        key=lambda page: (-int(page.get("image_count") or 0), page_sort_key(page)),
    )
    short_pages = sorted(
        [
            page
            for page in pages
            if str(page.get("extract_method")) == "text_layer" and char_count(page.get("raw_text")) < 80
        ],
        key=lambda page: (char_count(page.get("raw_text")), page_sort_key(page)),
    )
    risky_pages = sorted(
        [
            page
            for page in pages
            if has_risk_keyword(str(page.get("raw_text", "")) + str(page.get("source_title", "")))
        ],
        key=lambda page: (-int(page.get("image_count") or 0), -char_count(page.get("raw_text")), page_sort_key(page)),
    )
    normal_pages = [page for page in pages if str(page.get("extract_method")) == "text_layer" and char_count(page.get("raw_text")) >= 120]
    rng = random.Random(20260513)
    rng.shuffle(normal_pages)

    add(unknown_pages, "PDF 文字层没有读到内容", 1, max(8, sample_size // 4))
    add(image_pages, "图片较多，文字层可能漏掉图中标注", 2, max(10, sample_size // 4))
    add(short_pages, "文字很少，可能是图示页或扫描页", 2, max(10, sample_size // 4))
    add(risky_pages, "包含可能影响报价或设计限制的词", 3, max(10, sample_size // 4))
    add(normal_pages, "普通页抽查，用来校准整体稳定性", 4, max(6, sample_size // 8))

    return sorted(samples_by_key.values(), key=lambda page: (int(page.get("_sample_priority", 9)), page_sort_key(page)))[:sample_size]


def select_ocr_samples(samples: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(
        samples,
        key=lambda page: (
            0 if str(page.get("extract_method")) == "unknown" else 1,
            -int(page.get("image_count") or 0),
            char_count(page.get("raw_text")),
            page_sort_key(page),
        ),
    )[:limit]


def write_single_page_pdf(source_pdf: Path, source_page: int, output_pdf: Path) -> None:
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("PyPDF2 is required to create one-page OCR samples.")
    reader = PdfReader(str(source_pdf))
    if source_page < 1 or source_page > len(reader.pages):
        raise RuntimeError(f"Invalid source page {source_page} for {source_pdf}")
    writer = PdfWriter()
    writer.add_page(reader.pages[source_page - 1])
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with output_pdf.open("wb") as handle:
        writer.write(handle)


def safe_name(value: Any) -> str:
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", str(value or "")).strip("_")
    return normalized[:80] or "sample"


def sample_id(page: dict[str, Any]) -> str:
    return f"{safe_name(page.get('source_title'))}__p{int(page.get('source_page') or 0):03d}"


def run_sample_ocr(
    *,
    extract_module: Any,
    sample: dict[str, Any],
    ocr_root: Path,
    lang: str,
    device: str,
) -> dict[str, Any]:
    source_pdf = Path(str(sample.get("source_local_path") or ""))
    source_page = int(sample.get("source_page") or 0)
    output_dir = ocr_root / sample_id(sample)
    one_page_pdf = output_dir / "source-page.pdf"
    try:
        write_single_page_pdf(source_pdf, source_page, one_page_pdf)
        page_texts = extract_module.ocr_pdf_document_with_paddleocr(
            one_page_pdf,
            output_dir=output_dir / "paddleocr",
            lang=lang,
            device=device,
        )
        ocr_text = normalize_inline(page_texts.get(1, ""))
        return {
            "status": "succeeded" if ocr_text else "empty",
            "text": ocr_text,
            "char_count": char_count(ocr_text),
            "output_dir": str(output_dir),
            "one_page_pdf": str(one_page_pdf),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "char_count": 0,
            "output_dir": str(output_dir),
            "one_page_pdf": str(one_page_pdf),
        }


def render_sample_page(
    *,
    extract_module: Any,
    sample: dict[str, Any],
    image_root: Path,
) -> dict[str, Any]:
    source_pdf = Path(str(sample.get("source_local_path") or ""))
    source_page = int(sample.get("source_page") or 0)
    png_path = image_root / f"{sample_id(sample)}.png"
    try:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        extract_module.render_pdf_page_to_png(source_pdf, source_page, png_path)
        return {"status": "succeeded", "path": str(png_path)}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "path": str(png_path)}


def enrich_samples(
    *,
    samples: list[dict[str, Any]],
    extract_module: Any,
    report_dir: Path,
    run_ocr: bool,
    ocr_sample_size: int,
    render_sample_size: int,
    skip_render: bool,
    lang: str,
    device: str,
) -> list[dict[str, Any]]:
    enriched = [dict(sample) for sample in samples]
    ocr_targets = {sample_id(sample) for sample in select_ocr_samples(enriched, ocr_sample_size)} if run_ocr else set()
    render_targets = {sample_id(sample) for sample in enriched[:render_sample_size]} if not skip_render else set()
    ocr_root = report_dir / "quality-sample" / "ocr"
    image_root = report_dir / "quality-sample" / "images"

    for sample in enriched:
        sid = sample_id(sample)
        if sid in render_targets:
            sample["render"] = render_sample_page(extract_module=extract_module, sample=sample, image_root=image_root)
        if sid in ocr_targets:
            sample["ocr"] = run_sample_ocr(
                extract_module=extract_module,
                sample=sample,
                ocr_root=ocr_root,
                lang=lang,
                device=device,
            )
    return enriched


def load_unknown_page_closure(report_dir: Path) -> dict[str, Any]:
    closure = load_json(report_dir / "unknown-page-resolution-ledger.json", {})
    entries = closure.get("entries") if isinstance(closure.get("entries"), list) else []
    unknown_count = int(closure.get("unknown_page_count") or len(entries))
    unresolved = [
        entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("resolution_status") or "") in {"", "unknown", "needs_source_recheck"}
    ]
    return {
        "exists": bool(closure),
        "unknown_page_count": unknown_count,
        "resolved_count": max(0, len(entries) - len(unresolved)),
        "unresolved_count": len(unresolved),
        "resolution_counts": closure.get("resolution_counts", {}),
    }


def quality_verdict(
    samples: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    unknown_page_closure: dict[str, Any] | None = None,
) -> tuple[str, str]:
    method_counts = Counter(str(page.get("extract_method")) for page in pages)
    unknown_count = method_counts.get("unknown", 0)
    closure = unknown_page_closure or {}
    if unknown_count and closure.get("exists") and not closure.get("unresolved_count"):
        return (
            "full_document_closed",
            f"{unknown_count} 页 PDF 文字层未知页已全部写入 unknown-page-resolution-ledger，不再阻塞发布。",
        )
    ocr_checked = [sample for sample in samples if isinstance(sample.get("ocr"), dict)]
    ocr_failed = [sample for sample in ocr_checked if str(sample["ocr"].get("status")) == "failed"]
    ocr_empty = [sample for sample in ocr_checked if str(sample["ocr"].get("status")) == "empty"]
    if unknown_count:
        return "needs_review", f"有 {unknown_count} 页 PDF 文字层没有读到内容，不能直接当作全书已稳定提取。"
    if ocr_failed or ocr_empty:
        return "needs_review", "抽样 OCR 里有失败或空结果，建议先回看这些页。"
    return "usable_with_sampling", "当前没有发现阻断项，但仍建议按抽样页做人工确认后再激活。"


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
      <section class="metric">
        <div class="metric__label">{esc(label)}</div>
        <div class="metric__value">{esc(value)}</div>
        <div class="metric__hint">{esc(hint)}</div>
      </section>
    """


def relative_url(path: str, *, from_dir: Path) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(from_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_uri()


def render_sample_card(sample: dict[str, Any], *, html_dir: Path) -> str:
    reasons = " / ".join(str(reason) for reason in sample.get("_sample_reasons") or [])
    raw_chars = char_count(sample.get("raw_text"))
    ocr = sample.get("ocr") if isinstance(sample.get("ocr"), dict) else {}
    render = sample.get("render") if isinstance(sample.get("render"), dict) else {}
    ocr_status = str(ocr.get("status") or "未抽样 OCR")
    ocr_hint = {
        "succeeded": f"PaddleOCR 读到 {ocr.get('char_count', 0)} 字，可对照原文。",
        "empty": "PaddleOCR 没补到文字，建议回看原 PDF。",
        "failed": "PaddleOCR 执行失败，建议回看原 PDF 或重跑。",
        "未抽样 OCR": "这页未进入本轮 OCR 抽样。",
    }.get(ocr_status, ocr_status)
    image_html = ""
    if render.get("status") == "succeeded":
        image_html = f'<img src="{esc(relative_url(str(render.get("path")), from_dir=html_dir))}" alt="页面截图">'
    elif render:
        image_html = f'<div class="image-fallback">页面截图生成失败：{esc(render.get("error"))}</div>'
    return f"""
      <article class="sample-card" data-method="{esc(sample.get('extract_method'))}">
        <div class="sample-card__meta">
          <span>{esc(sample.get('source_title'))}</span>
          <span>源页 {esc(sample.get('source_page'))}</span>
          <span>{esc(sample.get('extract_method'))}</span>
        </div>
        <h3>{esc(reasons)}</h3>
        <div class="sample-grid">
          <div>
            <p class="label">原文字层</p>
            <p>{esc(excerpt(sample.get('raw_text'), 240) or '这页没有读到文字。')}</p>
            <p class="hint">文字层字数：{esc(raw_chars)}；图片数：{esc(sample.get('image_count', 0))}</p>
          </div>
          <div>
            <p class="label">PaddleOCR 抽样结果</p>
            <p>{esc(excerpt(ocr.get('text'), 240) or ocr_hint)}</p>
            <p class="hint">{esc(ocr_hint)}</p>
          </div>
        </div>
        {image_html}
      </article>
    """


def render_html(model: dict[str, Any]) -> str:
    samples = model["samples"]
    html_path = Path(model["html_path"])
    html_dir = html_path.parent
    verdict_label = "需要先复核" if model["verdict"] == "needs_review" else "可发布闭环"
    cards = "\n".join(render_sample_card(sample, html_dir=html_dir) for sample in samples)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>设计师手册文字质量抽样</title>
  <style>
    :root {{
      --paper: #fbf7ee;
      --ink: #2b2118;
      --muted: #7c6f61;
      --line: #e5d8c7;
      --accent: #8f4d24;
      --card: #fffaf2;
      --warn: #b84a28;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at 15% 5%, #fff7df, var(--paper) 38%, #f3eadc); color: var(--ink); font-family: "Songti SC", "Noto Serif CJK SC", serif; }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 42px 24px 72px; }}
    .hero {{ border: 1px solid var(--line); background: rgba(255, 250, 242, .82); padding: 34px; border-radius: 28px; box-shadow: 0 24px 70px rgba(88, 58, 28, .12); }}
    .eyebrow {{ color: var(--accent); letter-spacing: .16em; font-size: 13px; }}
    h1 {{ margin: 12px 0; font-size: clamp(32px, 5vw, 58px); line-height: 1.05; }}
    .hero p {{ max-width: 760px; color: var(--muted); font-size: 18px; line-height: 1.8; }}
    .status {{ display: inline-flex; margin-top: 12px; padding: 9px 14px; border-radius: 999px; background: #fff0e7; color: var(--warn); font-weight: 700; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }}
    .metric {{ border: 1px solid var(--line); background: rgba(255, 250, 242, .86); padding: 18px; border-radius: 20px; }}
    .metric__label {{ color: var(--muted); font-size: 14px; }}
    .metric__value {{ font-size: 30px; margin: 8px 0; font-weight: 800; }}
    .metric__hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .note {{ border-left: 4px solid var(--accent); background: rgba(255,255,255,.55); padding: 16px 18px; line-height: 1.8; color: var(--muted); }}
    .board {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }}
    .sample-card {{ background: var(--card); border: 1px solid var(--line); border-radius: 24px; padding: 18px; box-shadow: 0 14px 40px rgba(83, 57, 31, .08); }}
    .sample-card__meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 13px; }}
    .sample-card__meta span {{ border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: #fffdf8; }}
    h3 {{ margin: 14px 0; font-size: 20px; }}
    .sample-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .label {{ margin: 0 0 6px; color: var(--accent); font-weight: 800; }}
    .hint {{ color: var(--muted); font-size: 13px; line-height: 1.55; }}
    img {{ margin-top: 14px; width: 100%; max-height: 460px; object-fit: contain; border: 1px solid var(--line); border-radius: 16px; background: white; }}
    .image-fallback {{ margin-top: 14px; padding: 12px; border: 1px dashed var(--line); border-radius: 16px; color: var(--muted); }}
    @media (max-width: 860px) {{ .metrics, .board, .sample-grid {{ grid-template-columns: 1fr; }} .shell {{ padding: 24px 14px 48px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 线上手册文字质量</div>
      <h1>先确认文字有没有读靠谱，再谈接进报价</h1>
      <p>{esc(model["summary"])}</p>
      <div class="status">{esc(verdict_label)} · {esc(model["candidate_layer"])}</div>
    </section>
    <section class="metrics">
      {render_metric("总页数", model["page_count"], "候选层里 PDF 页级记录数")}
      {render_metric("没读到文字页", model["unknown_page_count"], "这些页不能直接当作已完成提取")}
      {render_metric("图片较多页", model["image_heavy_count"], "图片或图示多，容易漏掉图中标注")}
      {render_metric("本轮 OCR 抽样", model["ocr_checked_count"], "只抽高风险页，不全量替换")}
    </section>
    <section class="metrics">
      {render_metric("PaddleOCR 成功", model["ocr_status_counts"].get("succeeded", 0), "抽样页里 OCR 读到文字")}
      {render_metric("OCR 空结果", model["ocr_status_counts"].get("empty", 0), "需要回看原文")}
      {render_metric("OCR 失败", model["ocr_status_counts"].get("failed", 0), "需要重跑或人工看 PDF")}
      {render_metric("看板样本", len(samples), "按风险挑，不是随机凑数")}
    </section>
    <section class="note">
      这个页面不是给程序看的底表，而是给人判断“这批手册能不能进入下一步”的抽样台。PaddleOCR 结果只用于交叉检查；真正激活规则前，仍然看人工在审核台上的选择。
    </section>
    <section class="board">
      {cards}
    </section>
  </main>
</body>
</html>
"""


def build_model(
    *,
    skill_dir: Path,
    candidate_layer: str,
    sample_size: int,
    run_ocr: bool,
    ocr_sample_size: int,
    render_sample_size: int,
    skip_render: bool,
    lang: str,
    device: str,
) -> dict[str, Any]:
    manifest = resolve_manifest(skill_dir, candidate_layer)
    report_dir = resolve_artifact_path(manifest, "rules_candidate_file").parent
    rules_candidate = load_json(resolve_artifact_path(manifest, "rules_candidate_file"), {"pages": []})
    pages = [page for page in rules_candidate.get("pages", []) if isinstance(page, dict)]
    samples = select_page_samples(pages, sample_size=sample_size)
    extract_module = load_module("extract_rules_candidate_for_quality", skill_dir / "scripts" / "extract_rules_candidate.py")
    enriched_samples = enrich_samples(
        samples=samples,
        extract_module=extract_module,
        report_dir=report_dir,
        run_ocr=run_ocr,
        ocr_sample_size=ocr_sample_size,
        render_sample_size=render_sample_size,
        skip_render=skip_render,
        lang=lang,
        device=device,
    )
    unknown_page_closure = load_unknown_page_closure(report_dir)
    verdict, summary = quality_verdict(enriched_samples, pages, unknown_page_closure)
    method_counts = Counter(str(page.get("extract_method")) for page in pages)
    ocr_status_counts = Counter(
        str(sample["ocr"].get("status"))
        for sample in enriched_samples
        if isinstance(sample.get("ocr"), dict)
    )
    html_path = report_dir / "quality-sample-board.html"
    return {
        "candidate_layer": manifest.get("layer_id", candidate_layer),
        "status": manifest.get("status", ""),
        "html_path": str(html_path),
        "verdict": verdict,
        "summary": summary,
        "page_count": len(pages),
        "unknown_page_count": method_counts.get("unknown", 0),
        "unknown_page_closure": unknown_page_closure,
        "image_heavy_count": sum(1 for page in pages if int(page.get("image_count") or 0) >= 3),
        "method_counts": dict(method_counts),
        "ocr_checked_count": sum(1 for sample in enriched_samples if isinstance(sample.get("ocr"), dict)),
        "ocr_status_counts": dict(ocr_status_counts),
        "samples": enriched_samples,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    model = build_model(
        skill_dir=skill_dir,
        candidate_layer=args.candidate_layer,
        sample_size=args.sample_size,
        run_ocr=args.run_ocr,
        ocr_sample_size=args.ocr_sample_size,
        render_sample_size=args.render_sample_size,
        skip_render=args.skip_render,
        lang=args.paddleocr_lang,
        device=args.paddleocr_device,
    )
    html_path = Path(model["html_path"])
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(model), encoding="utf-8")
    write_json(html_path.with_suffix(".json"), model)
    print(f"Wrote quality sample board to {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
