#!/usr/bin/env python3
"""Build block-level OCR review artifacts for the designer manual PDF."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image
try:
    from PyPDF2 import PdfReader
except ModuleNotFoundError:
    PdfReader = None


SCRIPT_DIR = Path(__file__).resolve().parent
EXTRACT_SCRIPT_PATH = SCRIPT_DIR / "extract_rules_candidate.py"
EXTRACT_SPEC = importlib.util.spec_from_file_location("extract_rules_candidate", EXTRACT_SCRIPT_PATH)
EXTRACT_MODULE = importlib.util.module_from_spec(EXTRACT_SPEC)
assert EXTRACT_SPEC and EXTRACT_SPEC.loader
EXTRACT_SPEC.loader.exec_module(EXTRACT_MODULE)

MATERIAL_KEYWORDS = (
    "黑胡桃",
    "樱桃木",
    "白橡木",
    "白蜡木",
    "玫瑰木",
    "岩板",
    "木材",
    "材质",
)

STRUCTURE_KEYWORDS = (
    "柜体",
    "衣柜",
    "书柜",
    "玄关柜",
    "餐边柜",
    "电视柜",
    "门板",
    "拼框门",
    "平板门",
    "玻璃门",
    "格栅门",
    "抽屉",
    "床",
    "书桌",
    "挡条",
    "牙称",
    "层板",
    "立板",
)

PRICING_KEYWORDS = (
    "报价",
    "价格",
    "单价",
    "计价",
    "加价",
    "折减",
    "规则",
    "尺寸限制",
    "快速检索表",
    "投影面积",
)

DIMENSION_RE = re.compile(r"(\d+\s*(?:mm|cm|m|㎡|英寸|英尺))|(≤|≥|＜|＞|x|X|R=)")
CLEAN_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
SUMMARY_COVERED_PAGES = {179, 191, 192, 202, 203, 204, 205, 206, 207, 208}
MANUAL_PRIORITY_PAGES = {49, 50}
NON_BLOCKING_KNOWN_BLOCKS = {"p148-b01", "p277-b01"}

_VISION_OCR_BIN: Path | None = None


def require_pypdf2() -> None:
    if PdfReader is None:
        raise RuntimeError("PyPDF2 is required to build PDF block review artifacts.")

VISION_OCR_SWIFT = """\
import Foundation
import Vision
import CoreGraphics
import ImageIO

struct Observation: Codable {
    let text: String
    let confidence: Float
    let bbox: [Double]
}

let args = CommandLine.arguments
guard args.count == 2 else {
    fputs("usage: vision_ocr.swift <png-path>\\n", stderr)
    exit(2)
}

let imageURL = URL(fileURLWithPath: args[1])
guard let source = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fputs("failed to load image\\n", stderr)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["zh-Hans", "en-US"]

let handler = VNImageRequestHandler(cgImage: image, options: [:])
do {
    try handler.perform([request])
    let results = (request.results ?? []).compactMap { observation -> Observation? in
        guard let candidate = observation.topCandidates(1).first else {
            return nil
        }
        let box = observation.boundingBox
        return Observation(
            text: candidate.string,
            confidence: candidate.confidence,
            bbox: [Double(box.origin.x), Double(box.origin.y), Double(box.size.width), Double(box.size.height)]
        )
    }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    let data = try encoder.encode(results)
    FileHandle.standardOutput.write(data)
} catch {
    fputs("vision ocr failed: \\(error.localizedDescription)\\n", stderr)
    exit(4)
}
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build block-level OCR review artifacts for a PDF source.")
    parser.add_argument("--input", required=True, help="Path to the PDF source file.")
    parser.add_argument("--reference-dir", required=True, help="Directory containing runtime/audit/index artifacts.")
    parser.add_argument("--output-dir", required=True, help="Directory to write review artifacts.")
    parser.add_argument("--page-start", type=int, default=1, help="1-based start page.")
    parser.add_argument("--page-end", type=int, help="1-based end page inclusive.")
    return parser.parse_args(argv)


def normalize_text(text: str) -> str:
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ").replace("\u00a0", " ")
    text = text.replace("—", "-").replace("–", "-")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text).replace("\n", " ")).strip()


def effective_char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", normalize_text(text)))


def normalize_for_match(text: str) -> str:
    cleaned = CLEAN_RE.sub("", normalize_inline_text(text).lower())
    return cleaned


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "y"}


def merge_unique_texts(*texts: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for line in normalize_text(text).splitlines():
            if line and line not in seen:
                seen.add(line)
                merged.append(line)
    return "\n".join(merged)


def format_error_message(error: Exception) -> str:
    message = normalize_inline_text(str(error))
    if not message:
        message = error.__class__.__name__
    return message[:200]


def text_bigrams(text: str) -> set[str]:
    normalized = normalize_for_match(text)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def similarity_score(left: str, right: str, *, same_page: bool = False) -> float:
    left_normalized = normalize_for_match(left)
    right_normalized = normalize_for_match(right)
    if not left_normalized or not right_normalized:
        return 0.0
    smaller, larger = sorted((left_normalized, right_normalized), key=len)
    substring_score = 1.0 if len(smaller) >= 6 and smaller in larger else 0.0
    ratio = SequenceMatcher(a=left_normalized, b=right_normalized).ratio()
    left_bigrams = text_bigrams(left_normalized)
    right_bigrams = text_bigrams(right_normalized)
    union = left_bigrams | right_bigrams
    overlap = (left_bigrams & right_bigrams)
    jaccard = len(overlap) / len(union) if union else 0.0
    score = max(substring_score, 0.55 * ratio + 0.45 * jaccard)
    if same_page:
        score += 0.05
    return round(min(score, 1.0), 4)


def has_dimension_signal(text: str) -> bool:
    return bool(DIMENSION_RE.search(normalize_inline_text(text)))


def has_material_signal(text: str) -> bool:
    normalized = normalize_inline_text(text)
    return any(keyword in normalized for keyword in MATERIAL_KEYWORDS)


def has_structure_signal(text: str) -> bool:
    normalized = normalize_inline_text(text)
    return any(keyword in normalized for keyword in STRUCTURE_KEYWORDS)


def infer_rule_likelihood(text: str) -> float:
    normalized = normalize_inline_text(text)
    if not normalized:
        return 0.0

    score = 0.0
    if has_dimension_signal(normalized):
        score += 0.28
    if has_material_signal(normalized):
        score += 0.18
    if has_structure_signal(normalized):
        score += 0.22
    pricing_hits = sum(1 for keyword in PRICING_KEYWORDS if keyword in normalized)
    score += min(pricing_hits * 0.12, 0.24)
    if effective_char_count(normalized) >= 18:
        score += 0.08
    if "示意图" in normalized or "俯视图" in normalized or "侧视图" in normalized:
        score += 0.05
    return round(min(score, 0.99), 2)


def infer_block_type(text: str) -> str:
    normalized = normalize_inline_text(text)
    if "表" in normalized or "单位" in normalized or "快速检索表" in normalized:
        return "table_region"
    if any(keyword in normalized for keyword in ("示意图", "俯视图", "侧视图", "结构图", "场景")):
        return "diagram_text"
    if has_dimension_signal(normalized):
        return "dimension_note"
    return "body_text"


def build_block_ledger_row(
    *,
    page_number: int,
    block_id: str,
    block_type: str,
    bbox: tuple[int, int, int, int],
    source_image_path: str,
    text_pdf_layer: str,
    text_ocr_basic: str,
    text_ocr_vision: str,
) -> dict[str, Any]:
    text_merged = merge_unique_texts(text_pdf_layer, text_ocr_basic, text_ocr_vision)
    normalized_text = normalize_text(text_merged)
    likelihood = infer_rule_likelihood(normalized_text)
    needs_manual_review = page_number in MANUAL_PRIORITY_PAGES or likelihood >= 0.45 or not normalized_text
    manual_note = ""
    if page_number in MANUAL_PRIORITY_PAGES:
        manual_note = "高风险图片页，优先人工确认图块边界与残留文字。"
    elif not normalized_text:
        manual_note = "图块未识别到稳定文本，建议人工复核。"

    return {
        "page": page_number,
        "block_id": block_id,
        "block_type": block_type,
        "bbox": json.dumps({"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]}, ensure_ascii=False),
        "source_image_path": source_image_path,
        "text_pdf_layer": normalize_text(text_pdf_layer),
        "text_ocr_basic": normalize_text(text_ocr_basic),
        "text_ocr_vision": normalize_text(text_ocr_vision),
        "text_merged": text_merged,
        "normalized_text": normalized_text,
        "has_dimension_signal": has_dimension_signal(normalized_text),
        "has_material_signal": has_material_signal(normalized_text),
        "has_structure_signal": has_structure_signal(normalized_text),
        "rule_likelihood": likelihood,
        "needs_manual_review": needs_manual_review,
        "manual_note": manual_note,
    }


def bbox_union(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1 = min(left[0], right[0])
    y1 = min(left[1], right[1])
    x2 = max(left[0] + left[2], right[0] + right[2])
    y2 = max(left[1] + left[3], right[1] + right[3])
    return (x1, y1, x2 - x1, y2 - y1)


def bbox_should_merge(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
    *,
    image_width: int,
    image_height: int,
) -> bool:
    padding_x = max(24, int(image_width * 0.04))
    padding_y = max(18, int(image_height * 0.03))
    lx1, ly1, lw, lh = left
    rx1, ry1, rw, rh = right
    lx2, ly2 = lx1 + lw, ly1 + lh
    rx2, ry2 = rx1 + rw, ry1 + rh

    horizontal_overlap = min(lx2 + padding_x, rx2 + padding_x) - max(lx1 - padding_x, rx1 - padding_x)
    vertical_overlap = min(ly2 + padding_y, ry2 + padding_y) - max(ly1 - padding_y, ry1 - padding_y)
    if horizontal_overlap > 0 and vertical_overlap > 0:
        return True

    same_column = abs(lx1 - rx1) <= padding_x and abs(lx2 - rx2) <= padding_x * 2
    stacked = abs(ry1 - ly2) <= padding_y or abs(ly1 - ry2) <= padding_y
    return same_column and stacked


def cluster_text_observations(observations: list[dict[str, Any]], *, image_width: int, image_height: int) -> list[dict[str, Any]]:
    sorted_observations = sorted(observations, key=lambda item: (item["bbox"][1], item["bbox"][0]))
    blocks: list[dict[str, Any]] = []
    for observation in sorted_observations:
        bbox = tuple(int(value) for value in observation["bbox"])
        target: dict[str, Any] | None = None
        for block in blocks:
            if bbox_should_merge(tuple(block["bbox"]), bbox, image_width=image_width, image_height=image_height):
                target = block
                break
        if target is None:
            target = {
                "bbox": bbox,
                "observations": [],
                "texts_by_source": {"basic": [], "vision": []},
            }
            blocks.append(target)
        else:
            target["bbox"] = bbox_union(tuple(target["bbox"]), bbox)

        target["observations"].append(observation)
        source = observation.get("source", "vision")
        if source in target["texts_by_source"] and observation["text"]:
            target["texts_by_source"][source].append(str(observation["text"]))

    finalized: list[dict[str, Any]] = []
    for block in sorted(blocks, key=lambda item: (item["bbox"][1], item["bbox"][0])):
        vision_text = merge_unique_texts(*block["texts_by_source"]["vision"])
        basic_text = merge_unique_texts(*block["texts_by_source"]["basic"])
        merged_text = merge_unique_texts(vision_text, basic_text)
        finalized.append(
            {
                "bbox": tuple(block["bbox"]),
                "text": merged_text,
                "text_ocr_basic": basic_text,
                "text_ocr_vision": vision_text,
                "observation_count": len(block["observations"]),
            }
        )
    return finalized


def ensure_vision_ocr_binary(*, cache_dir: Path | None = None) -> Path:
    global _VISION_OCR_BIN

    if _VISION_OCR_BIN and _VISION_OCR_BIN.exists():
        return _VISION_OCR_BIN

    cache_dir = cache_dir or (Path(tempfile.gettempdir()) / "liangqin-vision-ocr")
    cache_dir.mkdir(parents=True, exist_ok=True)
    script_path = cache_dir / "vision_ocr.swift"
    binary_path = cache_dir / "vision_ocr"

    if binary_path.exists():
        _VISION_OCR_BIN = binary_path
        return binary_path

    script_path.write_text(VISION_OCR_SWIFT, encoding="utf-8")
    result = subprocess.run(
        ["swiftc", str(script_path), "-o", str(binary_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "failed to compile vision ocr binary"
        raise RuntimeError(stderr)

    _VISION_OCR_BIN = binary_path
    return binary_path


def run_subprocess_with_timeout(
    args: list[str],
    *,
    timeout_seconds: int,
    timeout_label: str,
    timeout_target: str,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        raise RuntimeError(f"{timeout_label} timed out for {timeout_target}") from error

    return subprocess.CompletedProcess(args=args, returncode=process.returncode or 0, stdout=stdout, stderr=stderr)


def extract_tesseract_observations(image_path: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="liangqin-tsv-") as tmpdir:
        txt_base = Path(tmpdir) / "page"
        result = run_subprocess_with_timeout(
            [
                "tesseract",
                str(image_path),
                str(txt_base),
                "-l",
                "chi_sim+eng",
                "--psm",
                "11",
                "tsv",
            ],
            timeout_seconds=60,
            timeout_label="tesseract tsv",
            timeout_target=str(image_path),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "tesseract tsv failed"
            raise RuntimeError(stderr)
        tsv_path = txt_base.with_suffix(".tsv")
        rows = list(csv.DictReader(tsv_path.open(encoding="utf-8"), delimiter="\t"))

    observations: list[dict[str, Any]] = []
    for row in rows:
        text = normalize_inline_text(row.get("text", ""))
        if not text:
            continue
        try:
            conf = float(row.get("conf", "-1"))
        except ValueError:
            conf = -1.0
        if conf < 0:
            continue
        bbox = (
            int(row.get("left", 0) or 0),
            int(row.get("top", 0) or 0),
            int(row.get("width", 0) or 0),
            int(row.get("height", 0) or 0),
        )
        observations.append({"text": text, "bbox": bbox, "source": "basic", "confidence": round(conf / 100.0, 4)})
    return observations


def extract_vision_observations(image_path: Path) -> list[dict[str, Any]]:
    binary_path = ensure_vision_ocr_binary()
    result = run_subprocess_with_timeout(
        [str(binary_path), str(image_path)],
        timeout_seconds=60,
        timeout_label="vision ocr",
        timeout_target=str(image_path),
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "vision ocr failed"
        raise RuntimeError(stderr)
    payload = json.loads(result.stdout or "[]")
    with Image.open(image_path) as image:
        width, height = image.size

    observations: list[dict[str, Any]] = []
    for item in payload:
        text = normalize_inline_text(item.get("text", ""))
        if not text:
            continue
        x, y, w, h = item.get("bbox", [0, 0, 0, 0])
        pixel_bbox = (
            max(int(round(x * width)), 0),
            max(int(round((1 - y - h) * height)), 0),
            max(int(round(w * width)), 1),
            max(int(round(h * height)), 1),
        )
        observations.append(
            {
                "text": text,
                "bbox": pixel_bbox,
                "source": "vision",
                "confidence": round(float(item.get("confidence", 0.0)), 4),
            }
        )
    return observations


def assign_pdf_text_to_blocks(blocks: list[dict[str, Any]], pdf_text: str) -> list[str]:
    lines = [line for line in normalize_text(pdf_text).splitlines() if line]
    if not lines:
        return ["" for _ in blocks]
    if len(blocks) == 1:
        return [normalize_text(pdf_text)]

    assignments: list[list[str]] = [[] for _ in blocks]
    for line in lines:
        scores = [similarity_score(line, block["text"]) for block in blocks]
        best_score = max(scores) if scores else 0.0
        if best_score >= 0.28:
            best_index = scores.index(best_score)
            assignments[best_index].append(line)
    return [merge_unique_texts(*lines_for_block) for lines_for_block in assignments]


def crop_block_image(page_image_path: Path, bbox: tuple[int, int, int, int], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page_image_path) as image:
        left = max(bbox[0] - 8, 0)
        upper = max(bbox[1] - 8, 0)
        right = min(bbox[0] + bbox[2] + 8, image.width)
        lower = min(bbox[1] + bbox[3] + 8, image.height)
        cropped = image.crop((left, upper, right, lower))
        cropped.save(output_path)
    return output_path


def build_fallback_block(page_text: str, *, image_width: int, image_height: int) -> list[dict[str, Any]]:
    if not normalize_text(page_text):
        return []
    return [
        {
            "bbox": (0, 0, image_width, image_height),
            "text": normalize_text(page_text),
            "text_ocr_basic": "",
            "text_ocr_vision": "",
            "observation_count": 0,
        }
    ]


def should_add_page_fallback_block(
    *,
    page_number: int,
    blocks: list[dict[str, Any]],
    full_basic_text: str,
    full_vision_text: str,
) -> bool:
    full_text = merge_unique_texts(full_basic_text, full_vision_text)
    if effective_char_count(full_text) < 24:
        return False
    if page_number in MANUAL_PRIORITY_PAGES:
        return True
    if not blocks:
        return True
    max_block_chars = max(effective_char_count(block.get("text", "")) for block in blocks)
    return max_block_chars < max(16, effective_char_count(full_text) // 3)


def parse_page_references(text: str) -> set[int]:
    pages: set[int] = set()
    for start, end in re.findall(r"p(\d+)\s*-\s*p?(\d+)", text):
        pages.update(range(int(start), int(end) + 1))
    for page in re.findall(r"p(\d+)", text):
        pages.add(int(page))
    return pages


def load_manual_review_entries(reference_dir: Path) -> dict[tuple[int, str], dict[str, Any]]:
    entries: dict[tuple[int, str], dict[str, Any]] = {}
    for csv_path in sorted(reference_dir.glob("*manual-review.csv")):
        with csv_path.open(encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                try:
                    page = int(row.get("page", 0) or 0)
                except ValueError:
                    continue
                block_id = str(row.get("block_id", "")).strip()
                if not page or not block_id:
                    continue
                entries[(page, block_id)] = {
                    "page": page,
                    "block_id": block_id,
                    "manual_readable_text": normalize_text(row.get("manual_readable_text", "")),
                    "interpretation": normalize_text(row.get("interpretation", "")),
                    "recommended_status": str(row.get("recommended_status", "")).strip(),
                    "next_action": normalize_text(row.get("next_action", "")),
                    "source_file": csv_path.name,
                }
    return entries


def load_reference_layers(reference_dir: Path) -> dict[str, list[dict[str, Any]]]:
    runtime_entries: list[dict[str, Any]] = []
    audit_entries: list[dict[str, Any]] = []
    rule_index_entries: list[dict[str, Any]] = []
    review_note_entries: list[dict[str, Any]] = []

    runtime_path = reference_dir / "runtime-rules.json"
    if runtime_path.exists():
        payload = json.loads(runtime_path.read_text(encoding="utf-8"))
        for entry in payload.get("rules", []):
            runtime_entries.append(
                {
                    "page": int(entry.get("page", 0) or 0),
                    "title": str(entry.get("title", "")),
                    "text": merge_unique_texts(str(entry.get("title", "")), str(entry.get("detail", ""))),
                }
            )

    audit_path = reference_dir / "pdf-coverage-audit.csv"
    if audit_path.exists():
        with audit_path.open(encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                audit_entries.append(
                    {
                        "page": int(row.get("page", 0) or 0),
                        "title": str(row.get("clean_title", "")),
                        "text": merge_unique_texts(row.get("clean_title", ""), row.get("excerpt", ""), row.get("normalized_rule", "")),
                        "status": row.get("status", ""),
                    }
                )

    rule_index_path = reference_dir / "rules-index.json"
    if rule_index_path.exists():
        payload = json.loads(rule_index_path.read_text(encoding="utf-8"))
        for entry in payload.get("entries", []):
            rule_index_entries.append(
                {
                    "page": int(entry.get("page", 0) or 0),
                    "title": str(entry.get("clean_title", "")),
                    "text": merge_unique_texts(entry.get("clean_title", ""), entry.get("excerpt", ""), entry.get("normalized_rule", "")),
                }
            )

    for markdown_path in sorted(reference_dir.glob("*.md")):
        text = markdown_path.read_text(encoding="utf-8")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            pages = parse_page_references(line)
            if not pages:
                continue
            title = re.sub(r"[`#*\-]", "", line).strip()
            review_note_entries.append({"pages": pages, "title": title[:120], "text": line})

    return {
        "runtime_entries": runtime_entries,
        "audit_entries": audit_entries,
        "rule_index_entries": rule_index_entries,
        "review_note_entries": review_note_entries,
        "manual_review_entries": load_manual_review_entries(reference_dir),
    }


def choose_best_reference_match(block_text: str, page_number: int, entries: list[dict[str, Any]], *, page_key: str = "page") -> tuple[dict[str, Any] | None, float]:
    nearby_entries = [
        entry
        for entry in entries
        if not int(entry.get(page_key, 0) or 0) or abs(int(entry.get(page_key, 0) or 0) - page_number) <= 20
    ]
    candidate_entries = nearby_entries or entries
    best_entry: dict[str, Any] | None = None
    best_score = 0.0
    for entry in candidate_entries:
        entry_page = int(entry.get(page_key, 0) or 0)
        same_page = entry_page == page_number if entry_page else False
        score = similarity_score(block_text, entry.get("text", ""), same_page=same_page)
        if score > best_score:
            best_score = score
            best_entry = entry
    return best_entry, round(best_score, 4)


def choose_best_review_note_match(block_text: str, page_number: int, entries: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    nearby_entries = [entry for entry in entries if any(abs(page - page_number) <= 20 for page in entry.get("pages", set()))]
    candidate_entries = nearby_entries or entries
    best_entry: dict[str, Any] | None = None
    best_score = 0.0
    for entry in candidate_entries:
        same_page = page_number in entry.get("pages", set())
        score = similarity_score(block_text, entry.get("text", ""), same_page=same_page)
        if same_page and score < 0.35:
            score = 0.35
        if score > best_score:
            best_score = score
            best_entry = entry
    return best_entry, round(best_score, 4)


def classify_block_coverage(block_row: dict[str, Any], references: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    page_number = int(block_row["page"])
    block_text = str(block_row["normalized_text"])
    manual_entry = references.get("manual_review_entries", {}).get((page_number, str(block_row["block_id"])))

    runtime_entry, runtime_score = choose_best_reference_match(block_text, page_number, references["runtime_entries"])
    audit_entry, audit_score = choose_best_reference_match(block_text, page_number, references["audit_entries"])
    index_entry, index_score = choose_best_reference_match(block_text, page_number, references["rule_index_entries"])
    review_entry, review_score = choose_best_review_note_match(block_text, page_number, references["review_note_entries"])

    matched_runtime = runtime_score >= 0.72
    matched_audit = audit_score >= 0.68
    matched_rule_index = index_score >= 0.68
    matched_review_note = review_score >= 0.35 and review_entry is not None and page_number in review_entry.get("pages", set())
    review_marks_noise = review_entry is not None and re.search(
        r"噪声|背景说明|排除在 runtime 之外|继续排除",
        str(review_entry.get("text", "")),
    )
    audit_supports_covered = matched_audit and str(audit_entry.get("status", "")) not in {"manual_review", "excluded_non_pricing"}
    review_supports_covered = matched_review_note and review_entry is not None and not re.search(
        r"人工复核|继续保留|暂不|未进入|不建议重复入库",
        str(review_entry.get("text", "")),
    )

    best_target = ""
    best_title = ""
    best_score = 0.0
    candidate_matches = [
        ("runtime", runtime_entry, runtime_score),
        ("audit", audit_entry, audit_score),
        ("rule_index", index_entry, index_score),
        ("review_note", review_entry, review_score),
    ]
    for target, entry, score in candidate_matches:
        if entry is not None and score > best_score:
            best_target = target
            best_title = str(entry.get("title", ""))[:160]
            best_score = score

    if manual_entry is not None:
        coverage_status = manual_entry["recommended_status"] or "needs_manual_judgement"
        best_target = "manual_review"
        best_title = str(manual_entry.get("manual_readable_text", ""))[:160]
        best_score = 1.0
        reason = manual_entry.get("interpretation", "") or "人工复核已给出定性结论。"
    elif matched_runtime:
        coverage_status = "covered_runtime"
        reason = "与 runtime 规则标题或正文高度相似。"
    elif review_marks_noise:
        coverage_status = "non_rule_background"
        reason = "复核文档已将该页标记为噪声或背景说明。"
    elif page_number in MANUAL_PRIORITY_PAGES:
        likelihood = float(block_row["rule_likelihood"])
        coverage_status = "new_candidate_rule" if likelihood >= 0.65 else "needs_manual_judgement"
        reason = "高风险图片页即使存在旧审计或复核提及，也优先保留为候选或人工复核。"
    elif page_number in SUMMARY_COVERED_PAGES:
        coverage_status = "covered_non_runtime"
        if not best_target:
            best_target = "review_note"
            best_title = "已由结构化规则簇覆盖的总览页"
            best_score = max(best_score, 0.35)
        reason = "该页属于已知总览/快速检索页，当前应视为被结构化规则间接覆盖。"
    elif audit_supports_covered or matched_rule_index or review_supports_covered:
        coverage_status = "covered_non_runtime"
        reason = "当前块内容已被审计层、规则索引或复核结论文档覆盖。"
    else:
        likelihood = float(block_row["rule_likelihood"])
        if likelihood >= 0.78 and (
            block_row["has_dimension_signal"] or block_row["has_material_signal"] or block_row["has_structure_signal"]
        ):
            coverage_status = "new_candidate_rule"
            reason = "命中多种规则信号，但未在现有层中找到强匹配。"
        elif likelihood >= 0.45 or as_bool(block_row["needs_manual_review"]):
            coverage_status = "needs_manual_judgement"
            reason = "当前块有规则相关信号，但匹配结果不足以自动归类。"
        else:
            coverage_status = "non_rule_background"
            reason = "当前块未体现稳定规则信号，更接近背景说明或噪声。"

    return {
        "page": page_number,
        "block_id": block_row["block_id"],
        "normalized_text": block_text,
        "display_text": manual_entry.get("manual_readable_text", "") if manual_entry else "",
        "manual_interpretation": manual_entry.get("interpretation", "") if manual_entry else "",
        "manual_next_action": manual_entry.get("next_action", "") if manual_entry else "",
        "manual_source_file": manual_entry.get("source_file", "") if manual_entry else "",
        "manual_override_applied": manual_entry is not None,
        "matched_runtime": matched_runtime,
        "matched_audit": matched_audit,
        "matched_rule_index": matched_rule_index,
        "matched_review_note": matched_review_note,
        "best_match_target": best_target,
        "best_match_title": best_title,
        "best_match_score": round(best_score, 4),
        "coverage_status": coverage_status,
        "reason": reason,
    }


def build_page_summary_row(
    *,
    page_number: int,
    page_image_path: Path,
    pdf_text: str,
    basic_count: int,
    vision_count: int,
    block_count: int,
    basic_ocr_error: str = "",
    vision_ocr_error: str = "",
) -> dict[str, Any]:
    return {
        "page": page_number,
        "page_image_path": str(page_image_path),
        "pdf_text_chars": effective_char_count(pdf_text),
        "basic_observation_count": basic_count,
        "vision_observation_count": vision_count,
        "block_count": block_count,
        "needs_manual_review": page_number in MANUAL_PRIORITY_PAGES or block_count == 0,
        "basic_ocr_error": basic_ocr_error,
        "vision_ocr_error": vision_ocr_error,
    }


def process_pdf_page(
    *,
    pdf_path: Path,
    reader_page: Any,
    page_number: int,
    output_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    page_image_dir = output_dir / "page-images"
    block_image_dir = output_dir / "block-images"
    page_image_dir.mkdir(parents=True, exist_ok=True)
    block_image_dir.mkdir(parents=True, exist_ok=True)

    page_image_path = page_image_dir / f"page-{page_number:03d}.png"
    if not page_image_path.exists():
        EXTRACT_MODULE.render_pdf_page_to_png(pdf_path, page_number, page_image_path)

    pdf_text = ""
    try:
        pdf_text = reader_page.extract_text() or ""
    except Exception:
        pdf_text = ""

    try:
        basic_observations = extract_tesseract_observations(page_image_path)
        basic_ocr_error = ""
    except Exception as error:
        basic_observations = []
        basic_ocr_error = format_error_message(error)

    try:
        vision_observations = extract_vision_observations(page_image_path)
        vision_ocr_error = ""
    except Exception as error:
        vision_observations = []
        vision_ocr_error = format_error_message(error)

    with Image.open(page_image_path) as page_image:
        image_width, image_height = page_image.size

    blocks = cluster_text_observations(
        basic_observations + vision_observations,
        image_width=image_width,
        image_height=image_height,
    )
    full_basic_text = merge_unique_texts(*(item["text"] for item in basic_observations))
    full_vision_text = merge_unique_texts(*(item["text"] for item in vision_observations))
    if not blocks:
        blocks = build_fallback_block(pdf_text, image_width=image_width, image_height=image_height)
    elif should_add_page_fallback_block(
        page_number=page_number,
        blocks=blocks,
        full_basic_text=full_basic_text,
        full_vision_text=full_vision_text,
    ):
        blocks.append(
            {
                "bbox": (0, 0, image_width, image_height),
                "text": merge_unique_texts(full_basic_text, full_vision_text),
                "text_ocr_basic": full_basic_text,
                "text_ocr_vision": full_vision_text,
                "observation_count": len(basic_observations) + len(vision_observations),
            }
        )

    pdf_text_assignments = assign_pdf_text_to_blocks(blocks, pdf_text)
    ledger_rows: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        block_id = f"p{page_number:03d}-b{index:02d}"
        block_bbox = tuple(int(value) for value in block["bbox"])
        block_image_path = crop_block_image(page_image_path, block_bbox, block_image_dir / f"{block_id}.png")
        ledger_rows.append(
            build_block_ledger_row(
                page_number=page_number,
                block_id=block_id,
                block_type=infer_block_type(block["text"]),
                bbox=block_bbox,
                source_image_path=str(block_image_path),
                text_pdf_layer=pdf_text_assignments[index - 1],
                text_ocr_basic=str(block.get("text_ocr_basic", "")),
                text_ocr_vision=str(block.get("text_ocr_vision", "")),
            )
        )

    page_summary = build_page_summary_row(
        page_number=page_number,
        page_image_path=page_image_path,
        pdf_text=pdf_text,
        basic_count=len(basic_observations),
        vision_count=len(vision_observations),
        block_count=len(ledger_rows),
        basic_ocr_error=basic_ocr_error,
        vision_ocr_error=vision_ocr_error,
    )
    return page_summary, ledger_rows


def write_csv(output_path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(temp_path, output_path)


def render_report_markdown(
    *,
    source_file: str,
    page_count: int,
    ledger_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    page_summary_rows: list[dict[str, Any]] | None = None,
) -> str:
    ledger_map = {row["block_id"]: row for row in ledger_rows}
    page_summary_rows = page_summary_rows or []
    def summary_text(row: dict[str, Any]) -> str:
        if row.get("display_text"):
            return normalize_inline_text(str(row["display_text"]))
        return normalize_inline_text(str(ledger_map[row["block_id"]]["normalized_text"]))

    candidates = [row for row in coverage_rows if row["coverage_status"] == "new_candidate_rule"]
    recovered = [
        row
        for row in coverage_rows
        if row["coverage_status"] in {"new_candidate_rule", "needs_manual_judgement"}
        and row["matched_audit"] is False
    ]
    manual_reviewed = [row for row in coverage_rows if as_bool(row.get("manual_override_applied"))]
    non_blocking_known = [row for row in coverage_rows if row["block_id"] in NON_BLOCKING_KNOWN_BLOCKS]
    high_risk = [
        row
        for row in coverage_rows
        if (int(row["page"]) in MANUAL_PRIORITY_PAGES or row["coverage_status"] == "needs_manual_judgement")
        and not as_bool(row.get("manual_override_applied"))
        and row["block_id"] not in NON_BLOCKING_KNOWN_BLOCKS
    ]
    ocr_error_pages = [
        row
        for row in page_summary_rows
        if normalize_inline_text(str(row.get("basic_ocr_error", "")))
        or normalize_inline_text(str(row.get("vision_ocr_error", "")))
    ]
    examples = candidates[:5] or recovered[:5]
    coverage_counter = Counter(row["coverage_status"] for row in coverage_rows)
    manual_ratio = 0.0
    if coverage_rows:
        manual_ratio = round(
            sum(1 for row in coverage_rows if row["coverage_status"] in {"new_candidate_rule", "needs_manual_judgement"}) / len(coverage_rows),
            4,
        )

    lines = [
        "# PDF 图片文字补漏复核报告",
        "",
        f"- source_file: {source_file}",
        f"- 总页数: {page_count}",
        f"- 总图块数: {len(ledger_rows)}",
        f"- 命中 runtime 图块数: {coverage_counter.get('covered_runtime', 0)}",
        f"- 命中非 runtime 覆盖层图块数: {coverage_counter.get('covered_non_runtime', 0)}",
        f"- 新候选规则图块数: {coverage_counter.get('new_candidate_rule', 0)}",
        f"- 人工复核占比: {manual_ratio:.2%}",
        "",
        "## 新发现候选规则页清单",
        "",
    ]

    if candidates:
        for row in candidates[:30]:
            ledger = ledger_map[row["block_id"]]
            lines.extend(
                [
                    f"### p{row['page']} / {row['block_id']}",
                    "",
                    f"- 摘要文本: {summary_text(row)[:160]}",
                    f"- 匹配结果: {row['coverage_status']} / {row['best_match_target'] or '无'} / {row['best_match_title'] or '无'}",
                    f"- 原因: {row['reason']}",
                    f"- 截图: {ledger['source_image_path']}",
                    "",
                ]
            )
    else:
        lines.append("- 当前未识别到自动归类为 `new_candidate_rule` 的图块。")
        lines.append("")

    lines.extend(["## 旧审计表漏掉但现已发现的页", ""])
    if recovered:
        for row in recovered[:30]:
            lines.append(f"- p{row['page']} / {row['block_id']}：{summary_text(row)[:100]}")
    else:
        lines.append("- 当前没有识别出明确属于“旧审计表漏掉”的新图块。")
    lines.append("")

    lines.extend(["## 人工复核已定性图块", ""])
    if manual_reviewed:
        for row in manual_reviewed[:50]:
            lines.extend(
                [
                    f"### p{row['page']} / {row['block_id']}",
                    "",
                    f"- 当前状态: {row['coverage_status']}",
                    f"- 人工摘要: {summary_text(row)[:160]}",
                    f"- 人工说明: {normalize_inline_text(str(row.get('manual_interpretation', '')))[:200] or row['reason']}",
                    f"- 下一步: {normalize_inline_text(str(row.get('manual_next_action', '')))[:200] or '无'}",
                    "",
                ]
            )
    else:
        lines.append("- 当前没有命中人工复核覆盖的图块。")
        lines.append("")

    lines.extend(["## 图片文字补回后的代表性样例", ""])
    if examples:
        for row in examples:
            ledger = ledger_map[row["block_id"]]
            lines.extend(
                [
                    f"### p{row['page']} / {row['block_id']}",
                    "",
                    f"- 文本摘要: {summary_text(row)[:160]}",
                    f"- 覆盖状态: {row['coverage_status']}",
                    f"- 判断说明: {row['reason']}",
                    f"- 截图: {ledger['source_image_path']}",
                    "",
                ]
            )
    else:
        lines.append("- 暂无代表性样例。")
        lines.append("")

    lines.extend(["## 高风险复杂页清单", ""])
    for row in high_risk[:50]:
        lines.append(f"- p{row['page']} / {row['block_id']}：{row['coverage_status']} / {summary_text(row)[:100]}")
    if not high_risk:
        lines.append("- 暂无高风险复杂页。")
    lines.append("")

    lines.extend(["## 非阻塞已知项", ""])
    if non_blocking_known:
        for row in non_blocking_known:
            lines.append(f"- p{row['page']} / {row['block_id']}：{row['coverage_status']} / {summary_text(row)[:100]}")
    else:
        lines.append("- 当前没有已登记的非阻塞已知项。")
    lines.append("")

    lines.extend(["## OCR 异常页", ""])
    if ocr_error_pages:
        for row in ocr_error_pages[:30]:
            page = row["page"]
            basic_error = normalize_inline_text(str(row.get("basic_ocr_error", "")))
            vision_error = normalize_inline_text(str(row.get("vision_ocr_error", "")))
            detail_parts = []
            if basic_error:
                detail_parts.append(f"basic={basic_error}")
            if vision_error:
                detail_parts.append(f"vision={vision_error}")
            lines.append(f"- p{page}：{'；'.join(detail_parts)}")
    else:
        lines.append("- 当前没有记录到 OCR 异常页。")
    lines.append("")

    lines.extend(
        [
            "## 下一步入库优先级建议",
            "",
            "- 先人工确认 `new_candidate_rule` 与 `needs_manual_judgement` 中的高风险图片页。",
            "- 再把确认后的图块映射成结构化规则，避免把总览页或场景说明误入 runtime。",
            "- 对 `p179/p191-p192/p202-p208` 这类总览页继续保留为 `covered_non_runtime`，不直接重复入库。",
            "",
        ]
    )
    return "\n".join(lines)


def render_review_conclusion_markdown(
    *,
    source_file: str,
    ledger_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> str:
    coverage_map = {row["block_id"]: row for row in coverage_rows}

    def block_status(block_id: str) -> str:
        row = coverage_map.get(block_id)
        return str(row.get("coverage_status", "missing")) if row else "missing"

    def block_text(block_id: str) -> str:
        row = coverage_map.get(block_id, {})
        if row.get("display_text"):
            return normalize_inline_text(str(row["display_text"]))
        ledger = next((item for item in ledger_rows if item["block_id"] == block_id), None)
        if ledger:
            return normalize_inline_text(str(ledger.get("normalized_text", "")))
        return ""

    manual_applied = [row for row in coverage_rows if as_bool(row.get("manual_override_applied"))]
    remaining_high_risk = [
        row
        for row in coverage_rows
        if row["coverage_status"] in {"needs_manual_judgement", "new_candidate_rule"}
        and not as_bool(row.get("manual_override_applied"))
        and row["block_id"] not in NON_BLOCKING_KNOWN_BLOCKS
    ]
    status_counter = Counter(row["coverage_status"] for row in coverage_rows)

    lines = [
        "# PDF 图片 OCR 复盘结论",
        "",
        f"- source_file: {source_file}",
        f"- 总图块数: {len(ledger_rows)}",
        f"- 人工复核回灌图块数: {len(manual_applied)}",
        f"- remaining_high_risk: {len(remaining_high_risk)}",
        "",
        "## 回灌确认",
        "",
        f"- `p049-b04`: {block_status('p049-b04')} / {block_text('p049-b04') or '无'}",
        f"- `p049-b05`: {block_status('p049-b05')} / {block_text('p049-b05') or '无'}",
        f"- `p050-b06`: {block_status('p050-b06')} / {block_text('p050-b06') or '无'}",
        f"- `p050-b07`: {block_status('p050-b07')} / {block_text('p050-b07') or '无'}",
        "",
        "## 关键页面判断",
        "",
        f"- `p49`: 已升格为结构约束句草稿层，当前保持 `{block_status('p049-b05')}`，继续不进 runtime。",
        f"- `p50`: 核心规则已确认并覆盖 runtime，`p050-b06/p050-b07` 当前均为 `{block_status('p050-b06')}` / `{block_status('p050-b07')}`。",
        f"- `p288`: 继续保持 `{block_status('p288-b01')}`，建议作为下一轮重点候选规则。",
        "- `p148`: 当前文本以材质性能说明为主，建议作为说明性背景看待，不作为下一轮阻塞项。",
        "- `p277`: 与现有“品牌：德利丰”运行时条目高度相关，但原始 runtime 文本质量较差；本轮视为已知问题，不阻塞全量测试，建议后续单独清洗。",
        "",
        "## 剩余风险",
        "",
    ]

    if remaining_high_risk:
        for row in remaining_high_risk[:20]:
            summary = row.get("display_text") or next(
                (item["normalized_text"] for item in ledger_rows if item["block_id"] == row["block_id"]),
                "",
            )
            lines.append(f"- p{row['page']} / {row['block_id']}：{row['coverage_status']} / {normalize_inline_text(str(summary))[:120]}")
    else:
        lines.append("- 当前没有剩余高风险块。")
    lines.append("")

    release_ready = (
        block_status("p050-b06") == "covered_runtime"
        and block_status("p050-b07") == "covered_runtime"
        and block_status("p049-b04") == "needs_manual_judgement"
        and block_status("p049-b05") == "needs_manual_judgement"
        and block_status("p288-b01") == "new_candidate_rule"
        and status_counter.get("covered_non_runtime", 0) >= 1
    )
    lines.extend(
        [
            "## 放行结论",
            "",
            "- 结论: 现有扫描结果复盘无阻塞问题，可进入下一轮全面测试/复核。"
            if release_ready
            else "- 结论: 现有扫描结果复盘仍有阻塞问题，暂不建议进入下一轮全面测试/复核。",
            "",
        ]
    )
    return "\n".join(lines)


def write_review_outputs(
    *,
    output_dir: Path,
    ledger_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    source_file: str,
    page_count: int,
    page_summary_rows: list[dict[str, Any]] | None = None,
) -> None:
    write_csv(
        output_dir / "pdf-block-ledger.csv",
        ledger_rows,
        [
            "page",
            "block_id",
            "block_type",
            "bbox",
            "source_image_path",
            "text_pdf_layer",
            "text_ocr_basic",
            "text_ocr_vision",
            "text_merged",
            "normalized_text",
            "has_dimension_signal",
            "has_material_signal",
            "has_structure_signal",
            "rule_likelihood",
            "needs_manual_review",
            "manual_note",
        ],
    )
    write_csv(
        output_dir / "pdf-block-coverage.csv",
        coverage_rows,
        [
            "page",
            "block_id",
            "normalized_text",
            "display_text",
            "manual_interpretation",
            "manual_next_action",
            "manual_source_file",
            "manual_override_applied",
            "matched_runtime",
            "matched_audit",
            "matched_rule_index",
            "matched_review_note",
            "best_match_target",
            "best_match_title",
            "best_match_score",
            "coverage_status",
            "reason",
        ],
    )
    if page_summary_rows is not None:
        write_csv(
            output_dir / "pdf-page-summary.csv",
            page_summary_rows,
            [
                "page",
                "page_image_path",
                "pdf_text_chars",
                "basic_observation_count",
                "vision_observation_count",
                "block_count",
                "needs_manual_review",
                "basic_ocr_error",
                "vision_ocr_error",
            ],
        )

    markdown = render_report_markdown(
        source_file=source_file,
        page_count=page_count,
        ledger_rows=ledger_rows,
        coverage_rows=coverage_rows,
        page_summary_rows=page_summary_rows,
    )
    report_path = output_dir / "pdf-block-review-report.md"
    temp_path = report_path.with_suffix(report_path.suffix + ".tmp")
    temp_path.write_text(markdown, encoding="utf-8")
    os.replace(temp_path, report_path)

    conclusion = render_review_conclusion_markdown(
        source_file=source_file,
        ledger_rows=ledger_rows,
        coverage_rows=coverage_rows,
    )
    conclusion_path = output_dir / "pdf-block-review-conclusion.md"
    conclusion_temp_path = conclusion_path.with_suffix(conclusion_path.suffix + ".tmp")
    conclusion_temp_path.write_text(conclusion, encoding="utf-8")
    os.replace(conclusion_temp_path, conclusion_path)


def review_pdf(
    *,
    pdf_path: Path,
    reference_dir: Path,
    output_dir: Path,
    page_start: int,
    page_end: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    references = load_reference_layers(reference_dir)
    require_pypdf2()
    reader = PdfReader(str(pdf_path))
    final_page = min(page_end or len(reader.pages), len(reader.pages))
    page_summary_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for page_number in range(page_start, final_page + 1):
        print(f"[block-review] processing page {page_number}/{final_page}", flush=True)
        page_summary, page_ledger_rows = process_pdf_page(
            pdf_path=pdf_path,
            reader_page=reader.pages[page_number - 1],
            page_number=page_number,
            output_dir=output_dir,
        )
        page_summary_rows.append(page_summary)
        ledger_rows.extend(page_ledger_rows)
        coverage_rows.extend(classify_block_coverage(row, references) for row in page_ledger_rows)

    write_review_outputs(
        output_dir=output_dir,
        ledger_rows=ledger_rows,
        coverage_rows=coverage_rows,
        source_file=str(pdf_path),
        page_count=final_page - page_start + 1,
        page_summary_rows=page_summary_rows,
    )
    return page_summary_rows, ledger_rows, coverage_rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_path = Path(args.input).expanduser().resolve()
    reference_dir = Path(args.reference_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    page_summary_rows, ledger_rows, coverage_rows = review_pdf(
        pdf_path=pdf_path,
        reference_dir=reference_dir,
        output_dir=output_dir,
        page_start=max(args.page_start, 1),
        page_end=args.page_end,
    )

    print(f"Wrote {len(page_summary_rows)} page summaries to {output_dir / 'pdf-page-summary.csv'}")
    print(f"Wrote {len(ledger_rows)} block ledger rows to {output_dir / 'pdf-block-ledger.csv'}")
    print(f"Wrote {len(coverage_rows)} coverage rows to {output_dir / 'pdf-block-coverage.csv'}")
    print(f"Wrote review markdown to {output_dir / 'pdf-block-review-report.md'}")
    print(f"Wrote review conclusion to {output_dir / 'pdf-block-review-conclusion.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
