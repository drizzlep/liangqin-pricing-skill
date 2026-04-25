from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

try:
    from PyPDF2 import PdfReader
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    PdfReader = None


W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PDF_PRIORITY_KEYWORDS = (
    "产品名称",
    "材质",
    "尺寸",
    "长度",
    "进深",
    "高度",
    "长：",
    "宽：",
    "高：",
    "费用合计",
    "折扣后合计",
    "合同总金额",
    "合同总 金额",
    "门型",
    "柜体形式",
    "床形态",
)


def normalize_preview(text: str, *, limit_chars: int) -> str:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if len(normalized) <= limit_chars:
        return normalized
    return normalized[:limit_chars].rstrip() + "..."


def extract_docx_preview(path: Path, *, limit_chars: int = 600) -> tuple[str, str]:
    with ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    parts: list[str] = []
    for para in root.findall(".//w:p", W_NS):
        text = "".join(node.text or "" for node in para.findall(".//w:t", W_NS)).strip()
        if text:
            parts.append(text)
        if sum(len(part) for part in parts) >= limit_chars:
            break
    return normalize_preview("\n".join(parts), limit_chars=limit_chars), "docx_text"


def extract_pdf_preview(path: Path, *, limit_chars: int = 600, page_limit: int = 3) -> tuple[str, str]:
    if PdfReader is None:
        return "", ""

    reader = PdfReader(str(path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    full_text = _compose_pdf_text(page_texts)
    if full_text:
        return full_text, "pdf_text_layer"
    preview_text = _select_pdf_preview_text(page_texts, limit_chars=limit_chars, page_limit=page_limit)
    return preview_text, "pdf_text_layer"


def _select_pdf_preview_text(page_texts: list[str], *, limit_chars: int, page_limit: int) -> str:
    cleaned_pages = [(index, text.strip()) for index, text in enumerate(page_texts) if str(text or "").strip()]
    if not cleaned_pages:
        return ""

    ranked_pages = sorted(
        (
            (_score_pdf_page(text), index, text)
            for index, text in cleaned_pages
        ),
        key=lambda item: (-item[0], item[1]),
    )

    selected_pages: list[tuple[int, str]] = []
    selected_indexes: set[int] = set()
    priority_pages = [(index, text) for score, index, text in ranked_pages if score > 0]

    if priority_pages:
        for index, text in priority_pages[: max(page_limit, 1)]:
            selected_pages.append((index, text))
            selected_indexes.add(index)
    else:
        for index, text in cleaned_pages[: max(page_limit, 1)]:
            selected_pages.append((index, text))
            selected_indexes.add(index)

    if len(" ".join(text for _, text in selected_pages)) < limit_chars:
        for index, text in cleaned_pages[: max(page_limit, 1)]:
            if index in selected_indexes:
                continue
            selected_pages.append((index, text))
            selected_indexes.add(index)
            if len(" ".join(item for _, item in selected_pages)) >= limit_chars:
                break

    preview_parts = [f"第{index + 1}页 {text}" for index, text in selected_pages]
    return normalize_preview("\n".join(preview_parts), limit_chars=limit_chars)


def _compose_pdf_text(page_texts: list[str]) -> str:
    cleaned_pages: list[tuple[int, str]] = []
    for index, text in enumerate(page_texts):
        normalized = _normalize_page_text(text)
        if normalized:
            cleaned_pages.append((index, normalized))
    if not cleaned_pages:
        return ""
    return "\n".join(f"第{index + 1}页 {text}" for index, text in cleaned_pages)


def _normalize_page_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _score_pdf_page(text: str) -> int:
    return sum(1 for keyword in PDF_PRIORITY_KEYWORDS if keyword in text)


def extract_text_preview(path: Path, *, limit_chars: int = 600) -> tuple[str, str]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            return extract_docx_preview(path, limit_chars=limit_chars)
        if suffix == ".pdf":
            return extract_pdf_preview(path, limit_chars=max(limit_chars, 1600))
    except Exception:
        return "", ""
    return "", ""
