#!/usr/bin/env python3
"""Build a human review board for blocking PDF pages in an addendum layer."""

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
    from PyPDF2 import PdfReader, PdfWriter
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    PdfReader = None
    PdfWriter = None


REVIEW_CHOICES = (
    "不影响规则",
    "OCR 可用",
    "必须看图",
    "暂缓激活",
)
HIGH_RISK_KEYWORDS = ("报价", "加价", "折减", "尺寸", "限制", "必须", "不可", "安全", "儿童", "岩板", "推拉门", "铰链")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a blocking-pages review board for a paused online addendum layer.")
    parser.add_argument("--candidate-layer", required=True, help="Candidate layer id or directory name.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--paddleocr-lang", default="ch", help="Language hint passed to PaddleOCR.")
    parser.add_argument("--paddleocr-device", default="cpu", help="Device hint passed to PaddleOCR.")
    parser.add_argument("--skip-ocr", action="store_true", help="Do not run PaddleOCR; reuse existing outputs when present.")
    parser.add_argument("--skip-render", action="store_true", help="Do not render PDF pages; reuse existing images when present.")
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


def excerpt(value: Any, limit: int = 220) -> str:
    text = normalize_inline(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def safe_name(value: Any) -> str:
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", str(value or "")).strip("_")
    return normalized[:80] or "page"


def page_key(page: dict[str, Any]) -> str:
    return f"{safe_name(page.get('source_title'))}__p{int(page.get('source_page') or 0):03d}"


def page_sort_key(page: dict[str, Any]) -> tuple[str, int]:
    return (str(page.get("source_title", "")), int(page.get("source_page") or page.get("page") or 0))


def resolve_manifest(skill_dir: Path, layer: str) -> dict[str, Any]:
    compare_module = load_module("compare_addendum_layers_for_blocking", skill_dir / "scripts" / "compare_addendum_layers.py")
    return compare_module.resolve_manifest(skill_dir / "references" / "addenda", layer)


def resolve_artifact_path(manifest: dict[str, Any], artifact_name: str) -> Path:
    artifacts = manifest.get("artifacts", {})
    raw_path = artifacts.get(artifact_name) if isinstance(artifacts, dict) else ""
    if not raw_path:
        raise SystemExit(f"Missing artifact in manifest: {artifact_name}")
    path = Path(str(raw_path))
    return path if path.is_absolute() else (Path(str(manifest["_manifest_dir"])) / path).resolve()


def collect_empty_ocr_samples(report_dir: Path) -> list[dict[str, Any]]:
    quality_path = report_dir / "quality-sample-board.json"
    quality = load_json(quality_path, {"samples": []})
    empty_samples: list[dict[str, Any]] = []
    for sample in quality.get("samples", []):
        if not isinstance(sample, dict):
            continue
        ocr = sample.get("ocr")
        if isinstance(ocr, dict) and str(ocr.get("status")) == "empty":
            copy = dict(sample)
            copy["_blocking_reason"] = "PaddleOCR 抽样为空"
            empty_samples.append(copy)
    return empty_samples


def collect_blocking_pages(rules_candidate: dict[str, Any], report_dir: Path) -> list[dict[str, Any]]:
    pages = [page for page in rules_candidate.get("pages", []) if isinstance(page, dict)]
    blocking: dict[tuple[str, int], dict[str, Any]] = {}
    for page in pages:
        if str(page.get("extract_method")) != "unknown":
            continue
        key = (str(page.get("source_local_path") or page.get("source_title") or ""), int(page.get("source_page") or 0))
        item = dict(page)
        item["_blocking_reason"] = "PDF 文字层为空"
        blocking[key] = item
    for page in collect_empty_ocr_samples(report_dir):
        key = (str(page.get("source_local_path") or page.get("source_title") or ""), int(page.get("source_page") or 0))
        if key in blocking:
            blocking[key]["_blocking_reason"] = "PDF 文字层为空；PaddleOCR 抽样为空"
        else:
            blocking[key] = page
    return sorted(blocking.values(), key=page_sort_key)


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


def run_page_ocr(
    *,
    extract_module: Any,
    page: dict[str, Any],
    output_root: Path,
    lang: str,
    device: str,
    skip_ocr: bool,
) -> dict[str, Any]:
    output_dir = output_root / page_key(page)
    one_page_pdf = output_dir / "source-page.pdf"
    combined_path = output_dir / "paddleocr" / "combined.md"
    if skip_ocr and combined_path.exists():
        text = combined_path.read_text(encoding="utf-8", errors="ignore")
        return {
            "status": "succeeded" if normalize_inline(text) else "empty",
            "text": normalize_inline(text),
            "char_count": char_count(text),
            "output_dir": str(output_dir),
            "one_page_pdf": str(one_page_pdf),
            "reused": True,
        }
    if skip_ocr:
        return {
            "status": "skipped",
            "text": "",
            "char_count": 0,
            "output_dir": str(output_dir),
            "one_page_pdf": str(one_page_pdf),
            "reused": False,
        }
    try:
        write_single_page_pdf(Path(str(page.get("source_local_path") or "")), int(page.get("source_page") or 0), one_page_pdf)
        page_texts = extract_module.ocr_pdf_document_with_paddleocr(
            one_page_pdf,
            output_dir=output_dir / "paddleocr",
            lang=lang,
            device=device,
        )
        text = normalize_inline(page_texts.get(1, ""))
        return {
            "status": "succeeded" if text else "empty",
            "text": text,
            "char_count": char_count(text),
            "output_dir": str(output_dir),
            "one_page_pdf": str(one_page_pdf),
            "reused": False,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "text": "",
            "char_count": 0,
            "output_dir": str(output_dir),
            "one_page_pdf": str(one_page_pdf),
            "reused": False,
        }


def render_page_image(
    *,
    extract_module: Any,
    page: dict[str, Any],
    image_root: Path,
    skip_render: bool,
) -> dict[str, Any]:
    png_path = image_root / f"{page_key(page)}.png"
    if skip_render and png_path.exists():
        return {"status": "succeeded", "path": str(png_path), "reused": True}
    if skip_render:
        return {"status": "skipped", "path": str(png_path), "reused": False}
    try:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        extract_module.render_pdf_page_to_png(
            Path(str(page.get("source_local_path") or "")),
            int(page.get("source_page") or 0),
            png_path,
        )
        return {"status": "succeeded", "path": str(png_path), "reused": False}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "path": str(png_path), "reused": False}


def infer_default_decision(page: dict[str, Any]) -> tuple[str, str]:
    ocr = page.get("ocr") if isinstance(page.get("ocr"), dict) else {}
    text = normalize_inline(ocr.get("text"))
    joined = f"{page.get('source_title', '')} {text}"
    if str(ocr.get("status")) == "succeeded" and char_count(text) >= 80 and any(keyword in joined for keyword in HIGH_RISK_KEYWORDS):
        return "暂缓激活", "OCR 补到了较多文字，而且涉及规则/尺寸/安全等关键词，需要人工确认后再进规则。"
    if str(ocr.get("status")) == "succeeded" and char_count(text) >= 20:
        return "OCR 可用", "OCR 已补回主要文字，可作为候选证据，但仍建议抽看截图。"
    if int(page.get("image_count") or 0) >= 3:
        return "必须看图", "图片较多且 OCR 不充分，可能有图示、尺寸或表格需要人工看截图。"
    return "不影响规则", "当前未读到可用文字，且图片数较少；优先判断是否为空白、封面或纯装饰页。"


def enrich_blocking_pages(
    *,
    pages: list[dict[str, Any]],
    extract_module: Any,
    report_dir: Path,
    lang: str,
    device: str,
    skip_ocr: bool,
    skip_render: bool,
) -> list[dict[str, Any]]:
    output_root = report_dir / "blocking-pages" / "ocr"
    image_root = report_dir / "blocking-pages" / "images"
    enriched: list[dict[str, Any]] = []
    for page in pages:
        item = dict(page)
        item["image"] = render_page_image(
            extract_module=extract_module,
            page=item,
            image_root=image_root,
            skip_render=skip_render,
        )
        item["ocr"] = run_page_ocr(
            extract_module=extract_module,
            page=item,
            output_root=output_root,
            lang=lang,
            device=device,
            skip_ocr=skip_ocr,
        )
        decision, reason = infer_default_decision(item)
        item["default_decision"] = decision
        item["default_decision_reason"] = reason
        enriched.append(item)
    return enriched


def relative_url(path: str, *, from_dir: Path) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(from_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_uri()


def render_metric(label: str, value: Any, hint: str = "") -> str:
    return f"""
      <section class="metric">
        <div class="metric__label">{esc(label)}</div>
        <div class="metric__value">{esc(value)}</div>
        <div class="metric__hint">{esc(hint)}</div>
      </section>
    """


def render_choice_chips(default_decision: str) -> str:
    chips = []
    for choice in REVIEW_CHOICES:
        selected = " is-selected" if choice == default_decision else ""
        chips.append(f'<span class="choice{selected}">{esc(choice)}</span>')
    return "\n".join(chips)


def render_page_card(page: dict[str, Any], *, html_dir: Path) -> str:
    ocr = page.get("ocr") if isinstance(page.get("ocr"), dict) else {}
    image = page.get("image") if isinstance(page.get("image"), dict) else {}
    image_html = ""
    if image.get("status") == "succeeded":
        image_html = f'<img src="{esc(relative_url(str(image.get("path")), from_dir=html_dir))}" alt="页面截图">'
    elif image:
        image_html = f'<div class="image-fallback">截图不可用：{esc(image.get("error") or image.get("status"))}</div>'
    ocr_status = str(ocr.get("status") or "unknown")
    ocr_text = excerpt(ocr.get("text"), 280)
    if not ocr_text:
        ocr_text = {
            "empty": "PaddleOCR 没补到文字。",
            "failed": "PaddleOCR 执行失败。",
            "skipped": "本次未执行 PaddleOCR。",
        }.get(ocr_status, "没有 OCR 文本。")
    return f"""
      <article class="page-card" data-decision="{esc(page.get('default_decision'))}" data-ocr-status="{esc(ocr_status)}">
        <div class="page-card__meta">
          <span>{esc(page.get('source_title'))}</span>
          <span>源页 {esc(page.get('source_page'))}</span>
          <span>{esc(page.get('_blocking_reason'))}</span>
        </div>
        <h3>{esc(page.get('default_decision'))}</h3>
        <p class="reason">{esc(page.get('default_decision_reason'))}</p>
        <div class="choices">{render_choice_chips(str(page.get('default_decision')))}</div>
        <div class="page-grid">
          <section>
            <p class="label">PaddleOCR 读到什么</p>
            <p>{esc(ocr_text)}</p>
            <p class="hint">状态：{esc(ocr_status)}；字数：{esc(ocr.get('char_count', 0))}；图片数：{esc(page.get('image_count', 0))}</p>
          </section>
          <section>
            <p class="label">给人的备注建议</p>
            <p>{esc(suggest_human_note(page))}</p>
            <p class="hint">人工只需要确认这页属于哪一类，必要时补一句短备注。</p>
          </section>
        </div>
        {image_html}
      </article>
    """


def suggest_human_note(page: dict[str, Any]) -> str:
    decision = str(page.get("default_decision") or "")
    source = str(page.get("source_title") or "")
    if decision == "暂缓激活":
        return f"请确认《{source}》这页是否包含报价、尺寸、安全或工艺限制。"
    if decision == "必须看图":
        return "请看截图判断是否有尺寸标注、表格、结构说明或设计限制。"
    if decision == "OCR 可用":
        return "建议对照截图快速确认 OCR 文字是否覆盖主要信息。"
    return "如果截图是空白、封面、纯图片或无规则内容，可以标为不影响规则。"


def render_html(model: dict[str, Any]) -> str:
    pages = model["pages"]
    html_path = Path(model["html_path"])
    html_dir = html_path.parent
    cards = "\n".join(render_page_card(page, html_dir=html_dir) for page in pages)
    decision_counts = Counter(str(page.get("default_decision")) for page in pages)
    ocr_counts = model["ocr_status_counts"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>阻断页复核包</title>
  <style>
    :root {{
      --paper: #f7f1e6;
      --card: #fffaf2;
      --ink: #2a2119;
      --muted: #756858;
      --line: #e3d4bf;
      --accent: #8c4b25;
      --danger: #a33b24;
      --ok: #436f4d;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: linear-gradient(135deg, #fff9ef 0%, var(--paper) 52%, #eee2d0 100%); color: var(--ink); font-family: "Songti SC", "Noto Serif CJK SC", serif; }}
    .shell {{ max-width: 1220px; margin: 0 auto; padding: 42px 24px 80px; }}
    .hero {{ border: 1px solid var(--line); border-radius: 30px; background: rgba(255, 250, 242, .9); padding: 34px; box-shadow: 0 28px 80px rgba(69, 43, 19, .13); }}
    .eyebrow {{ color: var(--accent); letter-spacing: .16em; font-size: 13px; }}
    h1 {{ margin: 12px 0; font-size: clamp(32px, 5vw, 60px); line-height: 1.05; }}
    .hero p {{ max-width: 780px; color: var(--muted); font-size: 18px; line-height: 1.8; }}
    .status {{ display: inline-flex; padding: 9px 14px; border-radius: 999px; background: #fff0e8; color: var(--danger); font-weight: 800; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }}
    .metric {{ border: 1px solid var(--line); border-radius: 20px; background: rgba(255, 250, 242, .85); padding: 17px; }}
    .metric__label {{ color: var(--muted); font-size: 14px; }}
    .metric__value {{ font-size: 30px; font-weight: 900; margin: 8px 0; }}
    .metric__hint {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0; }}
    .filter {{ border: 1px solid var(--line); background: #fffaf2; color: var(--ink); padding: 10px 13px; border-radius: 999px; cursor: pointer; }}
    .filter.is-active {{ background: var(--accent); color: white; border-color: var(--accent); }}
    .board {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .page-card {{ border: 1px solid var(--line); border-radius: 24px; background: var(--card); padding: 18px; box-shadow: 0 16px 44px rgba(70, 46, 23, .09); }}
    .page-card__meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 13px; }}
    .page-card__meta span, .choice {{ border: 1px solid var(--line); border-radius: 999px; background: #fffdf8; padding: 5px 9px; }}
    h3 {{ margin: 14px 0 8px; font-size: 22px; }}
    .reason {{ color: var(--muted); line-height: 1.7; }}
    .choices {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
    .choice.is-selected {{ background: #eff6ed; color: var(--ok); border-color: #bdd0b8; font-weight: 800; }}
    .page-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .label {{ margin: 0 0 6px; color: var(--accent); font-weight: 900; }}
    .hint {{ color: var(--muted); font-size: 13px; line-height: 1.55; }}
    img {{ margin-top: 14px; width: 100%; max-height: 560px; object-fit: contain; border: 1px solid var(--line); border-radius: 16px; background: white; }}
    .image-fallback {{ margin-top: 14px; padding: 12px; border: 1px dashed var(--line); border-radius: 16px; color: var(--muted); }}
    .empty {{ display:none; color: var(--muted); padding: 30px; text-align: center; }}
    @media (max-width: 900px) {{ .metrics, .board, .page-grid {{ grid-template-columns: 1fr; }} .shell {{ padding: 24px 14px 52px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">良禽佳木 · 设计师手册阻断页</div>
      <h1>这些页先看完，再决定能不能激活线上版</h1>
      <p>{esc(model["summary"])}</p>
      <div class="status">候选层仍是 {esc(model["candidate_status"])} · {esc(model["candidate_layer"])}</div>
    </section>
    <section class="metrics">
      {render_metric("阻断页", model["blocking_page_count"], "PDF 文字层为空或 OCR 抽样为空")}
      {render_metric("截图成功", model["image_status_counts"].get("succeeded", 0), "每页都应有可看截图")}
      {render_metric("OCR 成功", ocr_counts.get("succeeded", 0), "PaddleOCR 读到文字")}
      {render_metric("仍为空/失败", ocr_counts.get("empty", 0) + ocr_counts.get("failed", 0), "需要人工看截图")}
    </section>
    <section class="metrics">
      {render_metric("不影响规则", decision_counts.get("不影响规则", 0), "默认建议，可人工改")}
      {render_metric("OCR 可用", decision_counts.get("OCR 可用", 0), "可作为候选证据")}
      {render_metric("必须看图", decision_counts.get("必须看图", 0), "图示或尺寸要看截图")}
      {render_metric("暂缓激活", decision_counts.get("暂缓激活", 0), "先不要进规则")}
    </section>
    <section class="toolbar">
      <button class="filter is-active" data-filter="all">全部</button>
      <button class="filter" data-filter="暂缓激活">暂缓激活</button>
      <button class="filter" data-filter="必须看图">必须看图</button>
      <button class="filter" data-filter="OCR 可用">OCR 可用</button>
      <button class="filter" data-filter="不影响规则">不影响规则</button>
    </section>
    <section id="board" class="board">{cards}</section>
    <section id="empty" class="empty">没有这个分类的阻断页。</section>
  </main>
  <script>
    const buttons = [...document.querySelectorAll('.filter')];
    const cards = [...document.querySelectorAll('.page-card')];
    const empty = document.querySelector('#empty');
    function applyFilter(value) {{
      let visible = 0;
      cards.forEach(card => {{
        const show = value === 'all' || card.dataset.decision === value;
        card.style.display = show ? '' : 'none';
        if (show) visible += 1;
      }});
      empty.style.display = visible ? 'none' : 'block';
    }}
    buttons.forEach(button => button.addEventListener('click', () => {{
      buttons.forEach(item => item.classList.remove('is-active'));
      button.classList.add('is-active');
      applyFilter(button.dataset.filter);
    }}));
  </script>
</body>
</html>
"""


def build_model(
    *,
    skill_dir: Path,
    candidate_layer: str,
    lang: str,
    device: str,
    skip_ocr: bool,
    skip_render: bool,
) -> dict[str, Any]:
    manifest = resolve_manifest(skill_dir, candidate_layer)
    report_dir = resolve_artifact_path(manifest, "rules_candidate_file").parent
    rules_candidate = load_json(resolve_artifact_path(manifest, "rules_candidate_file"), {"pages": []})
    pages = collect_blocking_pages(rules_candidate, report_dir)
    extract_module = load_module("extract_rules_candidate_for_blocking", skill_dir / "scripts" / "extract_rules_candidate.py")
    enriched = enrich_blocking_pages(
        pages=pages,
        extract_module=extract_module,
        report_dir=report_dir,
        lang=lang,
        device=device,
        skip_ocr=skip_ocr,
        skip_render=skip_render,
    )
    ocr_status_counts = Counter(str(page.get("ocr", {}).get("status")) for page in enriched if isinstance(page.get("ocr"), dict))
    image_status_counts = Counter(str(page.get("image", {}).get("status")) for page in enriched if isinstance(page.get("image"), dict))
    html_path = report_dir / "blocking-pages-review-board.html"
    still_blocking = ocr_status_counts.get("empty", 0) + ocr_status_counts.get("failed", 0)
    return {
        "candidate_layer": manifest.get("layer_id", candidate_layer),
        "candidate_status": manifest.get("status", ""),
        "html_path": str(html_path),
        "blocking_page_count": len(enriched),
        "ocr_status_counts": dict(ocr_status_counts),
        "image_status_counts": dict(image_status_counts),
        "summary": (
            f"本复核包聚焦 {len(enriched)} 个阻断页：PDF 文字层为空，或此前 OCR 抽样为空。"
            f"本轮 PaddleOCR 后仍有 {still_blocking} 页为空或失败，需要人工看截图；候选层不得激活。"
        ),
        "pages": enriched,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    model = build_model(
        skill_dir=skill_dir,
        candidate_layer=args.candidate_layer,
        lang=args.paddleocr_lang,
        device=args.paddleocr_device,
        skip_ocr=args.skip_ocr,
        skip_render=args.skip_render,
    )
    html_path = Path(model["html_path"])
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(model), encoding="utf-8")
    write_json(html_path.with_suffix(".json"), model)
    print(f"Wrote blocking pages review board to {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
