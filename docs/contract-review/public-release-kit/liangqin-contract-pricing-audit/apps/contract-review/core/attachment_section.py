from __future__ import annotations

import re

from product_code_utils import extract_unique_product_codes


ATTACHMENT_PRICING_TITLE_PATTERN = re.compile(
    r"附件\s*[：:]\s*[《“\"]?\s*定制清单及设计图纸\s*[》”\"]?"
)
ATTACHMENT_TABLE_HEADER_PATTERN = re.compile(
    r"附件\s*[：:]\s*产品名称\s*产品编号\s*材质\s*数量\s*费用合计(?:（元）|\(元\)|元)?"
)
TABLE_HEADER_PATTERN = re.compile(
    r"产品名称\s*产品编号\s*材质\s*数量\s*费用合计(?:（元）|\(元\)|元)?"
)
FIRST_PAGE_MARKER_PATTERN = re.compile(r"第\s*1\s*页")
PAGE_CHUNK_PATTERN = re.compile(r"第\s*(\d+)\s*页(.*?)(?=第\s*\d+\s*页|$)", re.S)
ATTACHMENT_SECTION_MARKER_PATTERN = re.compile(r"附件\s*[：:]")


def extract_attachment_pricing_section(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""

    start = _resolve_attachment_start(normalized)
    if start is None:
        return normalized

    section = normalized[start:].strip()
    trimmed = _trim_repeated_contract_pages(section)
    return trimmed or section


def resolve_attachment_anchor_page(text: str) -> int | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    for match in PAGE_CHUNK_PATTERN.finditer(normalized):
        page_no = int(match.group(1))
        page_text = str(match.group(2) or "").strip()
        if _is_attachment_pricing_page(page_text):
            return page_no
    return None


def _resolve_attachment_start(text: str) -> int | None:
    for pattern in (
        ATTACHMENT_PRICING_TITLE_PATTERN,
        ATTACHMENT_TABLE_HEADER_PATTERN,
        TABLE_HEADER_PATTERN,
    ):
        match = pattern.search(text)
        if match:
            return match.start()
    return None


def _trim_repeated_contract_pages(section: str) -> str:
    header_match = TABLE_HEADER_PATTERN.search(section)
    if not header_match:
        return section.strip()

    first_page_match = FIRST_PAGE_MARKER_PATTERN.search(section, header_match.end())
    if not first_page_match:
        return section.strip()

    candidate = section[: first_page_match.start()].strip()
    if not extract_unique_product_codes(candidate):
        return section.strip()
    return candidate


def _is_attachment_pricing_page(page_text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(page_text or "")).strip()
    if not normalized:
        return False

    has_attachment_marker = bool(ATTACHMENT_SECTION_MARKER_PATTERN.search(normalized))
    has_attachment_title = bool(ATTACHMENT_PRICING_TITLE_PATTERN.search(normalized))
    has_table_header = bool(TABLE_HEADER_PATTERN.search(normalized))
    return has_attachment_marker and (has_attachment_title or has_table_header)
