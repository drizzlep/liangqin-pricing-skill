#!/usr/bin/env python3
"""Build a higher-signal rules index from extracted candidate sections."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


DOMAIN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cabinet", ("柜体", "衣柜", "书柜", "餐边柜", "玄关柜", "电视柜", "投影面积", "进深")),
    ("bed", ("床", "箱体床", "架式床", "高架床", "上下床", "伴床", "床头")),
    ("table", ("桌", "书桌", "餐桌", "边几", "岛台", "茶几")),
    ("door_panel", ("门板", "拼框门", "平板门", "玻璃门", "格栅门", "流云", "飞瀑")),
    ("accessory", ("配件", "拉手", "抽屉", "气压杆", "灯带", "开关", "插座")),
    ("material", ("材质", "黑胡桃", "樱桃木", "白橡木", "白蜡木", "玫瑰木", "木材", "NHLA")),
    ("child_room", ("儿童床", "儿童房", "挂梯", "梯柜", "榻榻米")),
]

PRICING_KEYWORDS = (
    "报价",
    "价格",
    "单价",
    "计价",
    "加价",
    "折减",
    "投影面积",
    "尺寸",
    "材质",
    "门型",
    "公式",
    "规则",
)

CATALOG_OPTION_KEYWORDS = (
    "可选色样",
    "常规色",
    "颜色可选",
    "颜色有两种",
    "可选颜色",
)

ROCK_SLAB_COLOR_NAMES = (
    "圣勃朗鱼肚白",
    "保加利亚浅灰",
    "劳伦特黑金",
    "极光黑",
    "极光白",
    "阿勒山闪电黑",
    "莱姆石中灰",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a high-signal rules index from candidate JSON.")
    parser.add_argument("--input", required=True, help="Path to rules-candidate JSON.")
    parser.add_argument("--output", required=True, help="Path to write rules-index JSON.")
    parser.add_argument("--markdown-output", help="Optional path to write markdown overview.")
    return parser.parse_args(argv)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\r", "\n").replace("\n", " ")).strip()


def effective_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def is_noisy_heading(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    if effective_char_count(normalized) < 4:
        return True
    if len(normalized) <= 20 and not any(keyword in normalized for keyword in PRICING_KEYWORDS):
        cjk_count = sum(1 for char in normalized if "\u4e00" <= char <= "\u9fff")
        if cjk_count < 3:
            return True
    visible = [char for char in normalized if not char.isspace()]
    useful = [char for char in visible if ("\u4e00" <= char <= "\u9fff") or char.isalnum()]
    if not useful:
        return True
    return len(useful) / max(len(visible), 1) < 0.55


def choose_clean_title(heading: str, content: list[str], tags: list[str]) -> str:
    if not is_noisy_heading(heading):
        return normalize_text(heading)[:120]

    for line in content:
        candidate = normalize_text(line)
        if candidate and not is_noisy_heading(candidate):
            return candidate[:120]

    if tags:
        return f"{' / '.join(tags)} 规则"
    return "待人工复核规则"


def classify_domain(text: str, tags: list[str]) -> str:
    normalized = normalize_text(text)
    for domain, keywords in DOMAIN_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return domain
    if "材质" in tags:
        return "material"
    return "general"


def compute_relevance_score(text: str, tags: list[str], rule_type: str, confidence: float) -> int:
    score = 0
    normalized = normalize_text(text)

    keyword_hits = sum(1 for keyword in PRICING_KEYWORDS if keyword in normalized)
    score += min(keyword_hits, 4)
    score += min(len(tags), 2)
    if rule_type in {"table_pricing", "formula", "special_adjustment", "dimension_threshold", "material_mapping"}:
        score += 2
    if confidence >= 0.9:
        score += 1
    if "柜体" in tags or "材质" in tags or "门型" in tags or "公式" in tags:
        score += 1
    return score


def classify_response_kind(text: str) -> str:
    normalized = normalize_text(text)
    if any(keyword in normalized for keyword in CATALOG_OPTION_KEYWORDS):
        return "catalog_option"
    return "pricing_rule"


def build_entry(section: dict[str, object]) -> dict[str, object]:
    heading = str(section.get("heading", ""))
    content = [str(item) for item in section.get("content", [])]
    tags = [str(item) for item in section.get("tags", [])]
    rule_type = str(section.get("rule_type", "narrative_rule"))
    confidence = float(section.get("confidence", 0.0))
    full_text = "\n".join([heading, *content]).strip()
    clean_title = choose_clean_title(heading, content, tags)
    domain = classify_domain(full_text, tags)
    score = compute_relevance_score(full_text, tags, rule_type, confidence)
    excerpt = normalize_text(full_text)[:240]
    response_kind = classify_response_kind(full_text)
    pricing_relevant = score >= 5
    runtime_relevant = pricing_relevant or response_kind == "catalog_option"

    return {
        "page": int(section.get("page", 1)),
        "domain": domain,
        "clean_title": clean_title,
        "heading": heading,
        "excerpt": excerpt,
        "tags": tags,
        "rule_type": rule_type,
        "confidence": confidence,
        "extract_method": section.get("extract_method", "unknown"),
        "normalized_rule": section.get("normalized_rule", ""),
        "relevance_score": score,
        "pricing_relevant": pricing_relevant,
        "runtime_relevant": runtime_relevant,
        "response_kind": response_kind,
    }


def build_page_entry(page: dict[str, object]) -> dict[str, object] | None:
    raw_text = str(page.get("raw_text", "")).strip()
    if not raw_text:
        return None
    response_kind = classify_response_kind(raw_text)
    image_count = int(page.get("image_count", 0) or 0)
    if response_kind != "catalog_option" and image_count < 3:
        return None

    tags = [str(item) for item in page.get("tags", [])]
    domain = classify_domain(raw_text, tags)
    score = compute_relevance_score(raw_text, tags, str(page.get("rule_type", "narrative_rule")), float(page.get("confidence", 0.0)))
    lines = split_lines(raw_text)
    clean_title = choose_clean_title(lines[0] if lines else "", lines[1:], tags)
    if response_kind == "catalog_option" and any(color_name in raw_text for color_name in ROCK_SLAB_COLOR_NAMES):
        if "岩板" not in tags:
            tags.append("岩板")
    if response_kind == "catalog_option" and ("保加利亚浅灰" in raw_text or "劳伦特黑金" in raw_text):
        clean_title = "岩板餐桌可选色样"
        domain = "table"
        if "餐桌" not in tags:
            tags.append("餐桌")
    elif response_kind == "catalog_option" and "岩板" in raw_text:
        clean_title = "岩板可选色样"

    return {
        "page": int(page.get("page", 1)),
        "domain": domain,
        "clean_title": clean_title,
        "heading": lines[0] if lines else "",
        "excerpt": normalize_text(raw_text)[:240],
        "tags": tags,
        "rule_type": str(page.get("rule_type", "narrative_rule")),
        "confidence": float(page.get("confidence", 0.0)),
        "extract_method": str(page.get("extract_method", "unknown")),
        "normalized_rule": str(page.get("normalized_explanation", "")),
        "relevance_score": max(score, 6 if response_kind == "catalog_option" else score),
        "pricing_relevant": False,
        "runtime_relevant": True,
        "response_kind": response_kind,
    }


def deduplicate_entries(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    deduplicated: list[dict[str, object]] = []
    seen: set[tuple[int, str, str]] = set()
    for entry in entries:
        key = (
            int(entry.get("page", 0)),
            str(entry.get("clean_title", "")).strip(),
            str(entry.get("response_kind", "")).strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(entry)
    return deduplicated


def build_rules_index(payload: dict[str, object]) -> dict[str, object]:
    sections = payload.get("sections", [])
    entries = [build_entry(section) for section in sections if isinstance(section, dict)]
    pages = payload.get("pages", [])
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        page_entry = build_page_entry(page)
        if page_entry is not None:
            entries.append(page_entry)
    entries = deduplicate_entries(entries)
    entries.sort(key=lambda item: (-item["relevance_score"], item["page"], item["clean_title"]))

    domain_counts = Counter(entry["domain"] for entry in entries)
    relevant_counts = Counter(entry["domain"] for entry in entries if entry["pricing_relevant"])

    return {
        "source_file": payload.get("source_file"),
        "source_format": payload.get("source_format"),
        "page_count": payload.get("page_count"),
        "entry_count": len(entries),
        "pricing_relevant_count": sum(1 for entry in entries if entry["pricing_relevant"]),
        "domain_counts": dict(domain_counts),
        "pricing_relevant_domain_counts": dict(relevant_counts),
        "entries": entries,
    }


def write_markdown(output_path: Path, index: dict[str, object]) -> None:
    lines = [
        "# 规则索引概览",
        "",
        f"- source_file: {index.get('source_file')}",
        f"- source_format: {index.get('source_format')}",
        f"- entry_count: {index.get('entry_count')}",
        f"- pricing_relevant_count: {index.get('pricing_relevant_count')}",
        "",
    ]
    entries = index.get("entries", [])
    if isinstance(entries, list):
        grouped: dict[str, list[dict[str, object]]] = {}
        for entry in entries:
            grouped.setdefault(str(entry["domain"]), []).append(entry)
        for domain, domain_entries in grouped.items():
            lines.append(f"## {domain}")
            lines.append("")
            for entry in domain_entries[:20]:
                lines.extend(
                    [
                        f"### p{entry['page']} · {entry['clean_title']}",
                        "",
                        f"- rule_type: {entry['rule_type']}",
                        f"- relevance_score: {entry['relevance_score']}",
                        f"- pricing_relevant: {entry['pricing_relevant']}",
                        f"- tags: {', '.join(entry['tags'])}",
                        "",
                        entry["excerpt"],
                        "",
                    ]
                )
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temp_path, output_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    markdown_output = Path(args.markdown_output).expanduser().resolve() if args.markdown_output else None

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    index = build_rules_index(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, output_path)

    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(markdown_output, index)

    print(f"Wrote {index['entry_count']} indexed rules to {output_path}")
    if markdown_output is not None:
        print(f"Wrote rules index overview to {markdown_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
