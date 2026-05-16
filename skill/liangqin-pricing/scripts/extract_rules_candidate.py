#!/usr/bin/env python3
"""Extract candidate rule sections from Liangqin rule sources."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

try:
    from PyPDF2 import PdfReader
except ModuleNotFoundError:
    PdfReader = None


W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s*(.+)$")
TABLE_RE = re.compile(r"^表\s*\d+$")
HTML_TAG_RE = re.compile(r"</?[^>]+>")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")

TEXT_TAGS: list[tuple[str, tuple[str, ...]]] = [
    ("柜体", ("柜体", "衣柜", "书柜", "电视柜", "餐边柜", "玄关柜")),
    ("超深", ("超深", "进深＞700", "进深>700", "加价15%", "加价 15%")),
    ("投影面积", ("投影面积", "㎡", "平方")),
    ("门型", ("门型", "拼框门", "玻璃门", "平板门", "格栅门", "流云", "飞瀑", "拉线", "藤编")),
    ("材质", ("材质", "黑胡桃", "樱桃木", "白橡木", "白蜡木", "玫瑰木")),
    ("公式", ("公式", "计算", "价格=", "单价=", "报价=")),
    ("表格", ("表1", "表2", "表3", "表4", "表5", "单价", "单位：元/投影面积")),
    ("尺寸阈值", ("≤", "≥", "＜", "＞", "mm", "m", "R")),
    ("折减", ("折减", "降低", "系数", "非见光面", "见光面")),
]

VISUAL_RULE_KEYWORDS = (
    "可选色样",
    "常规色",
    "示意图",
    "结构图",
    "尺寸图",
    "俯视图",
    "侧视图",
    "背视图",
    "产品编号 图片",
)

_PDF_RENDERER_BIN: Path | None = None
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def require_pypdf2() -> None:
    if PdfReader is None:
        raise RuntimeError("PyPDF2 is required to extract rules from PDF files.")

SWIFT_RENDER_SCRIPT = """\
import Foundation
import PDFKit
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count == 4 else {
    fputs("usage: render.swift <pdf-path> <page-number> <png-path>\\n", stderr)
    exit(2)
}

let pdfURL = URL(fileURLWithPath: args[1])
guard let doc = PDFDocument(url: pdfURL) else {
    fputs("failed to open pdf\\n", stderr)
    exit(3)
}

guard let pageNumber = Int(args[2]), pageNumber >= 1, pageNumber <= doc.pageCount else {
    fputs("invalid page number\\n", stderr)
    exit(4)
}

guard let page = doc.page(at: pageNumber - 1) else {
    fputs("missing page\\n", stderr)
    exit(5)
}

let bounds = page.bounds(for: .mediaBox)
let scale: CGFloat = 3.0
let width = max(Int(bounds.width * scale), 1)
let height = max(Int(bounds.height * scale), 1)

guard let context = CGContext(
    data: nil,
    width: width,
    height: height,
    bitsPerComponent: 8,
    bytesPerRow: 0,
    space: CGColorSpaceCreateDeviceRGB(),
    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
) else {
    fputs("failed to create graphics context\\n", stderr)
    exit(6)
}

context.setFillColor(CGColor(gray: 1.0, alpha: 1.0))
context.fill(CGRect(x: 0, y: 0, width: CGFloat(width), height: CGFloat(height)))
context.scaleBy(x: scale, y: scale)
context.translateBy(x: 0, y: bounds.height)
context.scaleBy(x: 1, y: -1)
page.draw(with: .mediaBox, to: context)

guard let image = context.makeImage() else {
    fputs("failed to render page\\n", stderr)
    exit(7)
}

let outputURL = URL(fileURLWithPath: args[3])
guard let destination = CGImageDestinationCreateWithURL(
    outputURL as CFURL,
    UTType.png.identifier as CFString,
    1,
    nil
) else {
    fputs("failed to create png destination\\n", stderr)
    exit(8)
}

CGImageDestinationAddImage(destination, image, nil)
guard CGImageDestinationFinalize(destination) else {
    fputs("failed to write png\\n", stderr)
    exit(9)
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract candidate rule sections from a docx or pdf file.")
    parser.add_argument("--input", required=True, help="Path to the source docx/pdf file.")
    parser.add_argument("--output", required=True, help="Path to write candidate JSON.")
    parser.add_argument("--markdown-output", help="Optional path to write a reviewable markdown source document.")
    parser.add_argument("--ocr-min-chars", type=int, default=50, help="Run OCR when extracted text is shorter than this threshold.")
    parser.add_argument(
        "--ocr-backend",
        choices=["tesseract", "paddleocr"],
        default="tesseract",
        help="OCR backend used when a PDF page needs visual text extraction.",
    )
    parser.add_argument("--paddleocr-lang", default="ch", help="Language hint passed to PaddleOCR when used.")
    parser.add_argument("--paddleocr-device", default="cpu", help="Device hint passed to PaddleOCR when used.")
    return parser.parse_args()


def normalize_text(text: str) -> str:
    text = MARKDOWN_IMAGE_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def effective_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def split_lines(text: str) -> list[str]:
    return [line for line in normalize_text(text).splitlines() if line]


def merge_text_sources(*texts: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for line in split_lines(text):
            if line not in seen:
                seen.add(line)
                merged.append(line)
    return "\n".join(merged)


def should_ocr_page(*, text_layer_text: str, image_count: int, ocr_min_chars: int) -> bool:
    if ocr_min_chars < 0:
        return False
    normalized_text = normalize_text(text_layer_text)
    if effective_char_count(normalized_text) < ocr_min_chars:
        return True
    if image_count >= 3 and any(keyword in normalized_text for keyword in VISUAL_RULE_KEYWORDS):
        return True
    return False


def infer_tags(text: str) -> list[str]:
    normalized = normalize_text(text)
    tags = [tag for tag, keywords in TEXT_TAGS if any(keyword in normalized for keyword in keywords)]
    return tags or ["待分类"]


def classify_rule_type(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return "empty"
    if TABLE_RE.search(normalized) or "单价" in normalized or "单位：元/投影面积" in normalized:
        return "table_pricing"
    if "公式" in normalized or "=" in normalized:
        return "formula"
    if any(keyword in normalized for keyword in ("加价", "折减", "降低", "上浮")):
        return "special_adjustment"
    if any(keyword in normalized for keyword in ("材质", "拼框门", "玻璃门", "平板门", "格栅门")):
        return "material_mapping"
    if any(keyword in normalized for keyword in ("≤", "≥", "＜", "＞", "mm", "m", "R")):
        return "dimension_threshold"
    if any(keyword in normalized for keyword in ("原则上", "不建议", "若坚持", "例外")):
        return "exception_condition"
    return "narrative_rule"


def confidence_for(method: str, text: str) -> float:
    base = {
        "docx_text": 0.99,
        "dingtalk_markdown": 0.99,
        "text_layer": 0.95,
        "hybrid": 0.86,
        "ocr_fallback": 0.72,
        "text_layer_ocr_unavailable": 0.68,
        "unknown": 0.6,
    }.get(method, 0.6)
    if effective_char_count(text) < 20:
        base -= 0.1
    return round(max(0.1, min(base, 0.99)), 2)


def summarize_text(text: str, *, tags: list[str], rule_type: str) -> str:
    lines = split_lines(text)
    if not lines:
        return "本页未抽取到可用文字，建议人工复核原 PDF。"

    prefix = {
        "table_pricing": "本段主要是价格表或单价矩阵，需要按材质、门型或结构组合取值。",
        "formula": "本段主要给出报价公式或计算关系，可作为程序规则表达式来源。",
        "special_adjustment": "本段主要描述加价、折减或特殊修正条件。",
        "material_mapping": "本段主要描述材质、门型或结构之间的映射关系。",
        "dimension_threshold": "本段主要定义尺寸阈值、适用区间或边界条件。",
        "exception_condition": "本段主要描述例外条件、限制或不建议场景。",
        "narrative_rule": "本段主要是业务说明，可作为规则注释或补充前提。",
        "empty": "本段未形成有效规则，需要人工复核。",
    }[rule_type]

    sample = "；".join(lines[:4])
    return f"{prefix} 识别标签：{', '.join(tags)}。关键信息：{sample}"


def extract_lines_from_docx(path: Path) -> list[str]:
    with ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    lines: list[str] = []
    for para in root.findall(".//w:p", W_NS):
        text = "".join(node.text or "" for node in para.findall(".//w:t", W_NS)).strip()
        if text:
            lines.append(text)
    return lines


def is_heading(line: str) -> bool:
    normalized = line.strip()
    if not normalized:
        return False
    if TABLE_RE.fullmatch(normalized):
        return True
    match = HEADING_RE.match(normalized)
    if not match:
        return False
    tail = match.group(2).strip()
    if not tail:
        return False
    if re.fullmatch(r"[\d./\\\-+%＜＞≤≥mM㎡元\s]+", tail):
        return False
    return True


def finalize_section(section: dict[str, object], *, extract_method: str) -> dict[str, object]:
    content = [str(item) for item in section.get("content", [])]
    page = int(section.get("page", 1))
    combined = "\n".join([str(section["heading"]), *content])
    tags = infer_tags(combined)
    rule_type = classify_rule_type(combined)
    section["page"] = page
    section["tags"] = tags
    section["rule_type"] = rule_type
    section["normalized_rule"] = summarize_text(combined, tags=tags, rule_type=rule_type)
    section["confidence"] = confidence_for(extract_method, combined)
    section["extract_method"] = extract_method
    return section


def sectionize_lines(lines: list[str], *, page: int = 1, extract_method: str = "docx_text") -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in lines:
        line = normalize_text(raw_line)
        if not line:
            continue
        if is_heading(line):
            current = {"heading": line, "content": [], "page": page}
            sections.append(current)
            continue
        if current is None:
            current = {"heading": "前言", "content": [], "page": page}
            sections.append(current)
        current["content"].append(line)
    return [finalize_section(section, extract_method=extract_method) for section in sections]


def ensure_pdf_renderer_binary(*, cache_dir: Path | None = None) -> Path:
    global _PDF_RENDERER_BIN

    if _PDF_RENDERER_BIN and _PDF_RENDERER_BIN.exists():
        return _PDF_RENDERER_BIN

    cache_dir = cache_dir or (Path(tempfile.gettempdir()) / "liangqin-pdf-renderer")
    cache_dir.mkdir(parents=True, exist_ok=True)
    script_path = cache_dir / "render_page.swift"
    binary_path = cache_dir / "render_page"

    if binary_path.exists():
        _PDF_RENDERER_BIN = binary_path
        return binary_path

    script_path.write_text(SWIFT_RENDER_SCRIPT, encoding="utf-8")
    result = subprocess.run(
        ["swiftc", str(script_path), "-o", str(binary_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "failed to compile pdf renderer"
        raise RuntimeError(stderr)

    _PDF_RENDERER_BIN = binary_path
    return binary_path


def render_pdf_page_to_png(pdf_path: Path, page_number: int, output_png: Path) -> None:
    renderer_binary = ensure_pdf_renderer_binary()
    result = subprocess.run(
        [str(renderer_binary), str(pdf_path), str(page_number), str(output_png)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or f"render failed for page {page_number}"
        raise RuntimeError(stderr)


def ocr_pdf_page(pdf_path: Path, page_number: int) -> str:
    with tempfile.TemporaryDirectory(prefix="liangqin-pdf-ocr-") as tmpdir:
        png_path = Path(tmpdir) / f"page-{page_number}.png"
        txt_base = Path(tmpdir) / f"page-{page_number}"
        render_pdf_page_to_png(pdf_path, page_number, png_path)
        result = subprocess.run(
            [
                "tesseract",
                str(png_path),
                str(txt_base),
                "-l",
                "chi_sim+eng",
                "--psm",
                "6",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or f"OCR failed for page {page_number}"
            raise RuntimeError(stderr)
        txt_path = txt_base.with_suffix(".txt")
        return txt_path.read_text(encoding="utf-8", errors="ignore")


def project_paddleocr_python() -> Path | None:
    candidates = [
        _PROJECT_ROOT / ".venv-paddleocr310-arm64" / "bin" / "python",
        _PROJECT_ROOT / ".venv-paddleocr310-arm64" / "bin" / "python3",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def ocr_pdf_document_with_paddleocr(
    pdf_path: Path,
    *,
    output_dir: Path,
    lang: str = "ch",
    device: str = "cpu",
) -> dict[int, str]:
    python_path = project_paddleocr_python()
    if python_path is None:
        raise RuntimeError("PaddleOCR project venv not found: .venv-paddleocr310-arm64")

    runner_path = _PROJECT_ROOT / "apps" / "contract-review" / "core" / "paddleocr_runner.py"
    if not runner_path.exists():
        raise RuntimeError(f"PaddleOCR runner not found: {runner_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    command = [
        str(python_path),
        str(runner_path),
        "--asset-id",
        pdf_path.stem,
        "--source-path",
        str(pdf_path),
        "--output-dir",
        str(output_dir),
        "--lang",
        lang,
        "--device",
        device,
        "--preview-limit-chars",
        "2000000",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "PaddleOCR failed"
        raise RuntimeError(stderr)

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PaddleOCR returned invalid JSON: {exc}") from exc

    summary_path = Path(str(payload.get("json_path") or output_dir / "summary.json"))
    if not summary_path.exists():
        raise RuntimeError(f"PaddleOCR summary missing: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    page_texts: dict[int, str] = {}
    for index, page in enumerate(summary.get("pages", []), start=1):
        if not isinstance(page, dict):
            continue
        page_no = int(page.get("page_no") or index)
        markdown_dir = Path(str(page.get("markdown_dir") or ""))
        page_text = read_paddleocr_page_markdown(markdown_dir)
        if page_text:
            page_texts[page_no] = page_text
    return page_texts


def read_paddleocr_page_markdown(markdown_dir: Path) -> str:
    if not markdown_dir.exists():
        return ""
    candidates = sorted(path for path in markdown_dir.glob("*.md") if path.is_file())
    texts: list[str] = []
    for candidate in candidates:
        if candidate.name == "combined.md":
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if text.strip():
            texts.append(text)
    return normalize_text("\n".join(texts))


def ocr_pdf_page_with_backend(
    pdf_path: Path,
    page_number: int,
    *,
    backend: str,
    paddleocr_page_texts: dict[int, str] | None = None,
) -> str:
    if backend == "paddleocr":
        return (paddleocr_page_texts or {}).get(page_number, "")
    return ocr_pdf_page(pdf_path, page_number)


def build_pdf_page_record(
    page_number: int,
    text_layer_text: str,
    ocr_text: str,
    *,
    ocr_min_chars: int,
    image_count: int = 0,
    ocr_backend: str = "tesseract",
    ocr_error: str = "",
) -> dict[str, object]:
    text_layer_text = normalize_text(text_layer_text)
    ocr_text = normalize_text(ocr_text)
    needs_ocr = should_ocr_page(text_layer_text=text_layer_text, image_count=image_count, ocr_min_chars=ocr_min_chars)

    if text_layer_text and not needs_ocr:
        extract_method = "text_layer"
        raw_text = text_layer_text
    elif ocr_text and text_layer_text:
        extract_method = "hybrid"
        raw_text = merge_text_sources(text_layer_text, ocr_text)
    elif ocr_text:
        extract_method = "ocr_fallback"
        raw_text = ocr_text
    else:
        extract_method = "text_layer_ocr_unavailable" if text_layer_text and needs_ocr else "text_layer" if text_layer_text else "unknown"
        raw_text = text_layer_text

    tags = infer_tags(raw_text)
    rule_type = classify_rule_type(raw_text)
    return {
        "page": page_number,
        "extract_method": extract_method,
        "raw_text": raw_text,
        "normalized_explanation": summarize_text(raw_text, tags=tags, rule_type=rule_type),
        "tags": tags,
        "rule_type": rule_type,
        "confidence": confidence_for(extract_method, raw_text),
        "image_count": image_count,
        "needs_ocr": needs_ocr,
        "ocr_backend": ocr_backend if needs_ocr else "",
        "ocr_error": ocr_error,
    }


def count_pdf_page_images(page: object) -> int:
    try:
        return len(list(page.images))  # type: ignore[attr-defined]
    except Exception:
        return 0


def extract_pdf_page_records(
    path: Path,
    *,
    ocr_min_chars: int,
    ocr_backend: str = "tesseract",
    paddleocr_lang: str = "ch",
    paddleocr_device: str = "cpu",
) -> list[dict[str, object]]:
    require_pypdf2()
    reader = PdfReader(str(path))
    page_inputs: list[tuple[int, object, str, int, bool]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text_layer_text = page.extract_text() or ""
        except Exception:
            text_layer_text = ""
        image_count = count_pdf_page_images(page)
        needs_ocr = should_ocr_page(text_layer_text=text_layer_text, image_count=image_count, ocr_min_chars=ocr_min_chars)
        page_inputs.append((page_number, page, text_layer_text, image_count, needs_ocr))

    paddleocr_page_texts: dict[int, str] = {}
    paddleocr_error = ""
    if ocr_backend == "paddleocr" and any(item[4] for item in page_inputs):
        try:
            with tempfile.TemporaryDirectory(prefix="liangqin-paddleocr-") as tmpdir:
                paddleocr_page_texts = ocr_pdf_document_with_paddleocr(
                    path,
                    output_dir=Path(tmpdir) / "ocr",
                    lang=paddleocr_lang,
                    device=paddleocr_device,
                )
        except Exception as exc:
            paddleocr_error = str(exc)

    records: list[dict[str, object]] = []
    for page_number, _page, text_layer_text, image_count, needs_ocr in page_inputs:
        ocr_text = ""
        ocr_error = ""
        if needs_ocr:
            try:
                ocr_text = ocr_pdf_page_with_backend(
                    path,
                    page_number,
                    backend=ocr_backend,
                    paddleocr_page_texts=paddleocr_page_texts,
                )
            except Exception as exc:
                ocr_text = ""
                ocr_error = str(exc)
            if ocr_backend == "paddleocr" and not ocr_text and paddleocr_error:
                ocr_error = paddleocr_error

        records.append(
            build_pdf_page_record(
                page_number,
                text_layer_text,
                ocr_text,
                ocr_min_chars=ocr_min_chars,
                image_count=image_count,
                ocr_backend=ocr_backend,
                ocr_error=ocr_error,
            )
        )
    return records


def sectionize_pdf_pages(page_records: list[dict[str, object]]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for record in page_records:
        page_number = int(record["page"])
        extract_method = str(record["extract_method"])
        for line in split_lines(str(record["raw_text"])):
            if is_heading(line):
                current = {"heading": line, "content": [], "page": page_number, "extract_method": extract_method}
                sections.append(current)
                continue
            if current is None:
                current = {"heading": "前言", "content": [], "page": page_number, "extract_method": extract_method}
                sections.append(current)
            current["content"].append(line)
    return [finalize_section(section, extract_method=str(section.get("extract_method", "unknown"))) for section in sections]


def write_markdown_output(output_path: Path, payload: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 规则源审阅稿",
        "",
        f"- source_file: {payload['source_file']}",
        f"- source_format: {payload['source_format']}",
    ]
    if "page_count" in payload:
        lines.append(f"- page_count: {payload['page_count']}")
    lines.append("")

    pages = payload.get("pages")
    if isinstance(pages, list):
        for page in pages:
            lines.extend(
                [
                    f"## Page {page['page']}",
                    "",
                    f"- extract_method: {page['extract_method']}",
                    f"- tags: {', '.join(page['tags'])}",
                    f"- rule_type: {page['rule_type']}",
                    f"- confidence: {page['confidence']}",
                    "",
                    "### raw_text",
                    "",
                    "```text",
                    str(page["raw_text"]),
                    "```",
                    "",
                    "### normalized_explanation",
                    "",
                    str(page["normalized_explanation"]),
                    "",
                ]
            )
    else:
        for section in payload["sections"]:
            lines.extend(
                [
                    f"## {section['heading']}",
                    "",
                    f"- page: {section.get('page', 1)}",
                    f"- extract_method: {section.get('extract_method', 'docx_text')}",
                    f"- tags: {', '.join(section['tags'])}",
                    f"- rule_type: {section['rule_type']}",
                    "",
                    "```text",
                    "\n".join([str(section["heading"]), *[str(item) for item in section["content"]]]),
                    "```",
                    "",
                    section["normalized_rule"],
                    "",
                ]
            )
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temp_path, output_path)


def build_candidate_payload(
    input_path: Path,
    markdown_output: Path | None = None,
    *,
    ocr_min_chars: int = 50,
    ocr_backend: str = "tesseract",
    paddleocr_lang: str = "ch",
    paddleocr_device: str = "cpu",
) -> dict[str, object]:
    input_path = input_path.expanduser().resolve()
    suffix = input_path.suffix.lower()

    if suffix == ".docx":
        lines = extract_lines_from_docx(input_path)
        payload: dict[str, object] = {
            "source_file": str(input_path),
            "source_format": "docx",
            "line_count": len(lines),
            "sections": sectionize_lines(lines),
        }
    elif suffix == ".pdf":
        page_records = extract_pdf_page_records(
            input_path,
            ocr_min_chars=ocr_min_chars,
            ocr_backend=ocr_backend,
            paddleocr_lang=paddleocr_lang,
            paddleocr_device=paddleocr_device,
        )
        payload = {
            "source_file": str(input_path),
            "source_format": "pdf",
            "page_count": len(page_records),
            "ocr_backend": ocr_backend if ocr_min_chars >= 0 else "disabled",
            "pages": page_records,
            "sections": sectionize_pdf_pages(page_records),
        }
    else:
        raise SystemExit(f"暂不支持的规则文件类型：{input_path.suffix}")

    if markdown_output is not None:
        write_markdown_output(markdown_output.expanduser().resolve(), payload)
    return payload


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output).expanduser().resolve()
    markdown_output = Path(args.markdown_output).expanduser().resolve() if args.markdown_output else None
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_candidate_payload(
        input_path,
        markdown_output=markdown_output,
        ocr_min_chars=args.ocr_min_chars,
        ocr_backend=args.ocr_backend,
        paddleocr_lang=args.paddleocr_lang,
        paddleocr_device=args.paddleocr_device,
    )
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, output_path)

    print(f"Wrote {len(payload['sections'])} candidate sections to {output_path}")
    if markdown_output is not None:
        print(f"Wrote review markdown to {markdown_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
