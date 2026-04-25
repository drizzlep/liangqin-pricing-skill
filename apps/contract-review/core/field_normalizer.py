from __future__ import annotations

import html
import importlib
import math
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image

from attachment_section import extract_attachment_pricing_section
from product_code_utils import count_unique_product_codes
from job_models import ReviewJob, SourceAsset
from liangqin_paths import resolve_pricing_scripts_dir
from ocr_layout_parser import load_ocr_layout_analysis
from template_learning import find_template_profile


DIMENSION_VALUE_PATTERN = r"([0-9]+(?:\.[0-9]+)?\s*(?:mm|毫米|cm|厘米|m|米)?)"
FIELD_FOLLOWUP_BOUNDARY = r"(?=\s+(?:前排|后排|床垫|围栏|护栏|梯柜|材质|门型|柜体形式|床形态|上层出入方式|下层结构|产品名称|产品编号|数量|费用合计|折扣后合计|本单按)[^:：]*[:：]|\s+(?:数量|费用合计|折扣后合计)\b|$)"
LABELED_PATTERNS = {
    "length": (
        rf"(?:床垫长度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])长度[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])长[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "depth": (
        rf"(?:^|[\s，,。；;])进深[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])深度[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])柜深[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])深[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "height": (
        rf"(?:^|[\s，,。；;])高度[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])总高[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])高[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "width": (
        rf"(?:床垫宽度|床宽)[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])宽度[:：\s]*{DIMENSION_VALUE_PATTERN}",
        rf"(?:^|[\s，,。；;])宽[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "guardrail_length": (
        rf"(?:围栏长度|护栏长度|围栏总长度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "guardrail_height": (
        rf"(?:围栏高度|护栏高度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "access_height": (
        rf"(?:垂直高度|梯子高度|上下床间距|上层高度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "stair_width": (
        rf"(?:梯柜踏步宽度|梯柜宽度|踏步宽度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "stair_depth": (
        rf"(?:梯柜进深|梯柜深度|梯柜踏步深度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "front_cabinet_length": (
        rf"(?:前排柜体长度|前排长度|前柜长度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "front_cabinet_height": (
        rf"(?:前排柜体高度|前排高度|前柜高度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "front_cabinet_depth": (
        rf"(?:前排柜体进深|前排进深|前柜进深)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "rear_cabinet_length": (
        rf"(?:后排柜体长度|后排长度|后柜长度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "rear_cabinet_height": (
        rf"(?:后排柜体高度|后排高度|后柜高度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
    "rear_cabinet_depth": (
        rf"(?:后排柜体进深|后排进深|后柜进深)[:：\s]*{DIMENSION_VALUE_PATTERN}",
    ),
}
PRODUCT_LABEL_PATTERNS = (
    rf"(?:产品名称|品名|产品|床型|柜体类型)[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}",
)
MATERIAL_LABEL_PATTERNS = (
    rf"(?:材质|木材|主材|木种)[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}",
)
DOOR_TYPE_LABEL_PATTERNS = (
    rf"(?:门型|柜门类型|门板类型)[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}",
)
CABINET_MODE_LABEL_PATTERNS = {
    "front_cabinet_mode": (rf"(?:前排柜体结构|前排结构|前柜结构)[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}",),
    "rear_cabinet_mode": (rf"(?:后排柜体结构|后排结构|后柜结构)[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}",),
}
QUOTE_KIND_PATTERNS = {
    "custom": (r"定制", r"订制", r"定做", r"订做", r"非标"),
    "standard": (r"成品", r"标品", r"标准品", r"现成"),
}
DOOR_TYPE_PATTERNS = {
    "yes": (r"带门",),
    "no": (r"不带门", r"开放柜", r"开放式"),
}


GENERIC_CATEGORY_VALUES = {"床", "桌", "柜", "柜体", "书柜", "衣柜", "玄关柜", "餐边柜", "架式床", "箱体床"}
CHILD_BED_KEYWORDS = ("儿童床", "上下床", "子母床", "高架床", "半高床", "错层床")
CHILD_BED_DRAWING_HINTS = ("尺寸图", "大尺寸图", "图纸", "设计图", "大样", "立面", "剖面", "正视", "侧视", "主视")
CHILD_BED_DRAWING_PENALTIES = ("效果图", "渲染图", "场景图", "透视图")
CHILD_BED_STRUCTURE_KEYWORDS = (
    "上下床",
    "高架床",
    "半高床",
    "错层床",
    "梯柜",
    "直梯",
    "斜梯",
    "围栏",
    "护栏",
    "前排",
    "后排",
    "床下",
    "互通",
)
CHILD_BED_PRIMARY_DRAWING_MIN_SCORE = 18
CHILD_BED_PRIMARY_DRAWING_MIN_GAP = 4
CHILD_BED_PRIMARY_DRAWING_KEY_FIELDS = (
    "bed_form",
    "access_style",
    "width",
    "length",
    "guardrail_style",
    "guardrail_length",
    "guardrail_height",
    "access_height",
    "stair_width",
    "stair_depth",
    "front_cabinet_length",
    "front_cabinet_height",
    "front_cabinet_depth",
    "rear_cabinet_length",
    "rear_cabinet_height",
    "rear_cabinet_depth",
)
UNDERBED_COMBO_SIGNAL_PATTERNS = (
    ("双面柜", (r"床下柜子为双面柜", r"双面柜")),
    ("活动层板", (r"活动层板", r"可调(?:节)?层板", r"层板可调")),
    ("朝外柜", (r"朝外柜", r"该面朝外", r"面朝外")),
    ("朝下床柜", (r"朝下床", r"该面朝下床", r"面朝下床")),
    ("柜体互通", (r"前后双排互通", r"双排互通", r"前后互通", r"柜体互通", r"互通", r"连通")),
)
STAIR_STORAGE_OPEN_SIGNAL_PATTERNS = (
    ("开放格", (r"开放格梯柜", r"梯柜.*开放格", r"左侧开放格", r"右侧开放格", r"开放格")),
    ("无抽屉", (r"无抽屉梯柜", r"梯柜.*无抽屉", r"无抽屉", r"不带抽屉")),
    ("书格式", (r"书架梯柜", r"书格式梯柜", r"书架式梯柜")),
)
STAIR_STORAGE_STANDARD_SIGNAL_PATTERNS = (
    ("抽屉", (r"梯柜.*(?:带|有)抽屉", r"(?:带|有)抽屉.*梯柜", r"踏步.*(?:带|有)抽屉", r"台阶.*(?:带|有)抽屉")),
)
CABINET_ROUTE_SIGNAL_PATTERNS = (
    ("开放书柜", (r"开放书柜", r"开放式书柜", r"无门书柜")),
    ("开放柜", (r"开放柜", r"开放式", r"无门", r"不带门")),
    ("带门", (r"带门",)),
)


def normalize_job_fields(job: ReviewJob, *, template_runtime_root: Path | None = None) -> dict[str, Any]:
    template_profile = (
        find_template_profile(job=job, runtime_root=template_runtime_root)
        if template_runtime_root is not None
        else None
    )
    preferred_evidence_order = list((template_profile or {}).get("preferred_evidence_order") or [])
    raw_text_sources = _build_text_sources(job.assets)
    child_bed_analysis = _analyze_child_bed_drawing_sources(raw_text_sources)
    text_sources = _sort_text_sources(
        raw_text_sources,
        preferred_evidence_order=preferred_evidence_order,
        child_bed_analysis=child_bed_analysis,
    )
    aggregate_text = "\n".join(item["text"] for item in text_sources).strip()
    inferred_fields = _infer_fields_from_pricing_text(text_sources, aggregate_text)

    fields: dict[str, Any] = {}
    _merge_field(fields, _extract_product_category(text_sources, aggregate_text))
    _merge_field(fields, _extract_bed_form(text_sources, aggregate_text))
    _merge_field(fields, _extract_access_style(text_sources, aggregate_text))
    _merge_field(fields, _extract_lower_bed_type(text_sources, aggregate_text))
    _merge_field(fields, _extract_guardrail_style(text_sources, aggregate_text))
    _merge_field(fields, _extract_material(text_sources, aggregate_text))
    _merge_field(fields, _extract_quote_kind(text_sources, aggregate_text))
    _merge_field(fields, _extract_has_door(text_sources, aggregate_text))
    _merge_field(fields, _extract_door_type(text_sources, aggregate_text))
    _merge_field(fields, _extract_underbed_cabinet_mode(text_sources, aggregate_text))
    _merge_field(fields, _extract_cabinet_mode("front_cabinet_mode", text_sources, aggregate_text))
    _merge_field(fields, _extract_cabinet_mode("rear_cabinet_mode", text_sources, aggregate_text))
    _merge_field(fields, _extract_interconnected_rows(text_sources, aggregate_text))
    for target_field in (
        "length",
        "depth",
        "height",
        "width",
        "guardrail_length",
        "guardrail_height",
        "access_height",
        "stair_width",
        "stair_depth",
        "front_cabinet_length",
        "front_cabinet_height",
        "front_cabinet_depth",
        "rear_cabinet_length",
        "rear_cabinet_height",
        "rear_cabinet_depth",
    ):
        _merge_field(fields, _extract_dimension(target_field, text_sources, aggregate_text))
    _merge_combo_row_segment_dimensions(fields, text_sources, aggregate_text)
    _merge_inferred_field_candidates(fields, inferred_fields)
    _apply_template_profile(fields, text_sources, template_profile)
    child_bed_analysis = _finalize_child_bed_analysis(
        child_bed_analysis,
        fields=fields,
        aggregate_text=aggregate_text,
        text_sources=text_sources,
    )
    route_evidence = _build_route_evidence(
        text_sources=text_sources,
        fields=fields,
        aggregate_text=aggregate_text,
        child_bed_analysis=child_bed_analysis,
    )

    payload = {
        "job_id": job.job_id,
        "field_count": len(fields),
        "fields": fields,
        "source_assets": [
            {
                "asset_id": item["asset_id"],
                "file_name": item["file_name"],
                "text_extract_method": item["text_extract_method"],
            }
            for item in text_sources
        ],
        "aggregate_text_preview": aggregate_text[:1200],
    }
    if route_evidence:
        payload["route_evidence"] = route_evidence
    if child_bed_analysis.get("is_child_bed"):
        payload["child_bed_analysis"] = child_bed_analysis
    if template_profile:
        payload["template_profile"] = {
            "template_id": str(template_profile.get("template_id") or "").strip(),
            "template_fingerprint": str(template_profile.get("template_fingerprint") or "").strip(),
            "template_lookup_fingerprint": str(template_profile.get("template_lookup_fingerprint") or "").strip(),
            "trust_score": template_profile.get("trust_score"),
        }
    return payload


def _build_text_sources(assets: list[SourceAsset]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for asset in assets:
        ocr_layout = load_ocr_layout_analysis((asset.metadata or {}).get("ocr_json_path"))
        raw_text = str(asset.text_preview or "").strip()
        if not raw_text and ocr_layout.get("combined_text"):
            raw_text = str(ocr_layout.get("combined_text") or "").strip()
        if not raw_text:
            continue
        normalized_text = extract_attachment_pricing_section(raw_text)
        sources.append(
            {
                "asset_id": asset.asset_id,
                "file_name": asset.file_name,
                "source_path": str(asset.source_path or "").strip(),
                "text": normalized_text,
                "text_extract_method": asset.text_extract_method,
                "source_kind": _infer_source_kind(asset),
                "media_kind": str(asset.media_kind or "").strip(),
                "role_hint": str(asset.role_hint or "").strip(),
                "ocr_layout": ocr_layout,
                "ocr_output_dir": str((asset.metadata or {}).get("ocr_output_dir") or "").strip(),
                "ocr_markdown_path": str((asset.metadata or {}).get("ocr_markdown_path") or "").strip(),
            }
        )
    return sources


def _sort_text_sources(
    text_sources: list[dict[str, Any]],
    *,
    preferred_evidence_order: list[str] | None = None,
    child_bed_analysis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sorted_sources = list(text_sources)
    order = {value: index for index, value in enumerate(preferred_evidence_order or [])}
    primary_asset_id = str((child_bed_analysis or {}).get("primary_drawing_asset_id") or "").strip()

    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        child_bed_rank = 0 if primary_asset_id and str(item.get("asset_id") or "").strip() == primary_asset_id else 1
        source_rank = order.get(str(item.get("source_kind") or ""), len(order))
        return (child_bed_rank, source_rank, str(item.get("asset_id") or ""))

    sorted_sources.sort(key=sort_key)
    return sorted_sources


def _analyze_child_bed_drawing_sources(text_sources: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate_text = "\n".join(str(item.get("text") or "") for item in text_sources).strip()
    is_child_bed = _looks_like_child_bed_request(aggregate_text)
    visual_source_count = sum(1 for item in text_sources if str(item.get("role_hint") or "") == "visual_attachment")
    analysis: dict[str, Any] = {
        "is_child_bed": is_child_bed,
        "visual_source_count": visual_source_count,
        "primary_drawing_asset_id": "",
        "primary_drawing_file_name": "",
        "primary_drawing_score": 0,
        "primary_drawing_confidence": "none",
        "requires_primary_drawing_review": False,
        "review_reason": "",
        "review_block_fields": [],
        "main_drawing_field_hits": [],
        "combo_candidate_signals": [],
        "suggested_pricing_route": "",
    }
    if not is_child_bed:
        return analysis

    candidate_scores = [_score_child_bed_drawing_source(item) for item in text_sources]
    drawing_candidates = [item for item in candidate_scores if item["is_candidate"]]
    if not drawing_candidates:
        if visual_source_count:
            analysis["requires_primary_drawing_review"] = True
            analysis["review_reason"] = "child_bed_visual_drawing_not_identified"
            analysis["review_block_fields"] = ["bed_form", "width", "length", "access_style"]
        return analysis

    drawing_candidates.sort(
        key=lambda item: (
            int(item["score"]),
            int(item["dimension_count"]),
            int(item["structure_hit_count"]),
            str(item["asset_id"] or ""),
        ),
        reverse=True,
    )
    top = drawing_candidates[0]
    second_score = int(drawing_candidates[1]["score"]) if len(drawing_candidates) > 1 else 0
    score_gap = int(top["score"]) - second_score
    confidence = (
        "high"
        if int(top["score"]) >= CHILD_BED_PRIMARY_DRAWING_MIN_SCORE and score_gap >= CHILD_BED_PRIMARY_DRAWING_MIN_GAP
        else "medium"
        if int(top["score"]) >= CHILD_BED_PRIMARY_DRAWING_MIN_SCORE
        else "low"
    )
    analysis.update(
        {
            "primary_drawing_asset_id": str(top["asset_id"] or "").strip(),
            "primary_drawing_file_name": str(top["file_name"] or "").strip(),
            "primary_drawing_score": int(top["score"]),
            "primary_drawing_confidence": confidence,
            "drawing_candidates": [
                {
                    "asset_id": str(item["asset_id"] or "").strip(),
                    "file_name": str(item["file_name"] or "").strip(),
                    "score": int(item["score"]),
                    "dimension_count": int(item["dimension_count"]),
                    "structure_hit_count": int(item["structure_hit_count"]),
                }
                for item in drawing_candidates[:3]
            ],
        }
    )
    if confidence != "high":
        analysis["requires_primary_drawing_review"] = True
        analysis["review_reason"] = "child_bed_primary_drawing_not_stable"
        analysis["review_block_fields"] = ["bed_form", "width", "length", "access_style"]
    return analysis


def _score_child_bed_drawing_source(source: dict[str, Any]) -> dict[str, Any]:
    text = str(source.get("text") or "")
    normalized_text = _normalize_text(text)
    file_name = str(source.get("file_name") or "")
    normalized_file_name = _normalize_text(file_name)
    ocr_layout = source.get("ocr_layout") or {}
    mm_values = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(?:mm|毫米)", text, flags=re.IGNORECASE)
    layout_dimension_count = int(ocr_layout.get("dimension_count") or 0)
    layout_field_count = len(ocr_layout.get("field_candidates") or {})
    dimension_count = max(len(mm_values), layout_dimension_count)
    structure_hit_count = sum(
        1 for keyword in CHILD_BED_STRUCTURE_KEYWORDS if keyword and keyword in normalized_text
    )
    score = min(dimension_count, 12) * 2 + min(structure_hit_count, 4) * 3
    score += min(layout_field_count, 6) * 2
    if str(source.get("role_hint") or "").strip() == "visual_attachment":
        score += 5
    if str(source.get("source_kind") or "").strip().startswith("ocr"):
        score += 2
    if any(hint in normalized_file_name or hint in normalized_text for hint in CHILD_BED_DRAWING_HINTS):
        score += 6
    if "大尺寸图" in normalized_text or "注" in normalized_text:
        score += 4
    if any(penalty in normalized_file_name or penalty in normalized_text for penalty in CHILD_BED_DRAWING_PENALTIES):
        score -= 6

    is_candidate = dimension_count >= 4 or score >= CHILD_BED_PRIMARY_DRAWING_MIN_SCORE
    return {
        "asset_id": str(source.get("asset_id") or "").strip(),
        "file_name": file_name,
        "score": score,
        "dimension_count": dimension_count,
        "structure_hit_count": structure_hit_count,
        "is_candidate": is_candidate,
    }


def _finalize_child_bed_analysis(
    child_bed_analysis: dict[str, Any],
    *,
    fields: dict[str, Any],
    aggregate_text: str,
    text_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    analysis = dict(child_bed_analysis or {})
    if not analysis.get("is_child_bed"):
        return analysis

    combo_candidate_signals = _collect_underbed_combo_candidate_signals(
        aggregate_text=aggregate_text,
        fields=fields,
    )
    analysis["combo_candidate_signals"] = combo_candidate_signals
    analysis["suggested_pricing_route"] = (
        "modular_child_bed_combo" if combo_candidate_signals else ""
    )
    analysis.update(
        _collect_child_bed_stair_storage_context(
            text_sources=text_sources,
            aggregate_text=aggregate_text,
            fields=fields,
        )
    )

    primary_asset_id = str(analysis.get("primary_drawing_asset_id") or "").strip()
    if not primary_asset_id:
        return analysis

    main_drawing_field_hits: list[str] = []
    for field_name in CHILD_BED_PRIMARY_DRAWING_KEY_FIELDS:
        payload = fields.get(field_name)
        if not isinstance(payload, dict):
            continue
        evidence_refs = [item for item in list(payload.get("evidence_refs") or []) if isinstance(item, dict)]
        if not evidence_refs:
            continue
        if str(evidence_refs[0].get("asset_id") or "").strip() == primary_asset_id:
            main_drawing_field_hits.append(field_name)

    analysis["main_drawing_field_hits"] = sorted(main_drawing_field_hits)
    if analysis.get("requires_primary_drawing_review"):
        return analysis

    missing_core_fields = [
        field_name
        for field_name in ("bed_form", "width", "length")
        if field_name not in main_drawing_field_hits
    ]
    if len(main_drawing_field_hits) < 3 or missing_core_fields:
        analysis["requires_primary_drawing_review"] = True
        analysis["review_reason"] = "child_bed_primary_drawing_fields_incomplete"
        analysis["review_block_fields"] = missing_core_fields or ["bed_form", "width", "length"]
    return analysis


def _collect_underbed_combo_candidate_signals(
    *,
    aggregate_text: str,
    fields: dict[str, Any],
) -> list[str]:
    signals: list[str] = []
    normalized_text = _normalize_text(aggregate_text)
    for label, patterns in UNDERBED_COMBO_SIGNAL_PATTERNS:
        if any(re.search(pattern, normalized_text, flags=re.IGNORECASE) for pattern in patterns):
            signals.append(label)

    if _has_underbed_combo_fields(fields):
        signals.append("床下柜体尺寸")

    deduped: list[str] = []
    for label in signals:
        if label and label not in deduped:
            deduped.append(label)
    return deduped


def _collect_child_bed_stair_storage_context(
    *,
    text_sources: list[dict[str, Any]],
    aggregate_text: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    access_style = str((fields.get("access_style") or {}).get("value") or "").strip()
    normalized_text = _normalize_text(aggregate_text)
    allow_text_signal_scan = access_style == "梯柜" or "梯柜" in normalized_text

    open_signals: list[str] = []
    standard_signals: list[str] = []
    evidence_snippets: list[str] = []
    source_asset_ids: list[str] = []

    if allow_text_signal_scan:
        for label, patterns in STAIR_STORAGE_OPEN_SIGNAL_PATTERNS:
            source_id, snippet = _find_first_signal_snippet(text_sources, patterns)
            if not snippet:
                continue
            open_signals.append(label)
            if snippet not in evidence_snippets:
                evidence_snippets.append(snippet)
            if source_id and source_id not in source_asset_ids:
                source_asset_ids.append(source_id)

        for label, patterns in STAIR_STORAGE_STANDARD_SIGNAL_PATTERNS:
            source_id, snippet = _find_first_signal_snippet(text_sources, patterns)
            if not snippet:
                continue
            standard_signals.append(label)
            if snippet not in evidence_snippets:
                evidence_snippets.append(snippet)
            if source_id and source_id not in source_asset_ids:
                source_asset_ids.append(source_id)

    mode = ""
    if open_signals and standard_signals:
        mode = "mixed"
    elif open_signals:
        mode = "open_grid"
    elif standard_signals:
        mode = "standard"
    if mode:
        signals = open_signals + [item for item in standard_signals if item not in open_signals]
        return {
            "stair_storage_mode": mode,
            "stair_storage_signals": signals,
            "stair_storage_evidence_snippets": evidence_snippets[:4],
            "stair_storage_source_asset_ids": source_asset_ids,
        }

    return _collect_child_bed_stair_storage_from_effect_images(
        text_sources=text_sources,
        aggregate_text=aggregate_text,
    )


def _collect_child_bed_stair_storage_from_effect_images(
    *,
    text_sources: list[dict[str, Any]],
    aggregate_text: str,
) -> dict[str, Any]:
    best_result: dict[str, Any] | None = None
    for source in text_sources:
        for candidate in _iter_child_bed_effect_image_candidates(source, aggregate_text=aggregate_text):
            image_path = Path(str(candidate.get("image_path") or "")).expanduser()
            analysis = _infer_stair_storage_mode_from_effect_image(image_path)
            if str(analysis.get("mode") or "").strip() != "open_grid":
                continue
            if best_result is None or float(analysis.get("confidence_score") or 0.0) > float(best_result["analysis"].get("confidence_score") or 0.0):
                best_result = {
                    "analysis": analysis,
                    "candidate": candidate,
                    "source": source,
                }

    if best_result is None:
        return {}

    analysis = best_result["analysis"]
    candidate = best_result["candidate"]
    source = best_result["source"]
    evidence_snippet = (
        f"视觉命中开放格梯柜：{Path(str(candidate.get('image_path') or '')).name} "
        f"(score={float(analysis.get('confidence_score') or 0.0):.2f})"
    )
    return {
        "stair_storage_mode": "open_grid",
        "stair_storage_signals": [
            str(item).strip()
            for item in list(analysis.get("signals") or [])
            if str(item).strip()
        ],
        "stair_storage_evidence_snippets": [evidence_snippet],
        "stair_storage_source_asset_ids": [str(source.get("asset_id") or "").strip()],
    }


def _iter_child_bed_effect_image_candidates(
    source: dict[str, Any],
    *,
    aggregate_text: str,
) -> list[dict[str, Any]]:
    ocr_output_dir = Path(str(source.get("ocr_output_dir") or "")).expanduser()
    if not ocr_output_dir.exists():
        return []

    candidates: list[dict[str, Any]] = []
    child_bed_page_signals = ("儿童床", "上下床", "高架床", "半高床", "错层床", "下床床垫建议尺寸")
    for markdown_path in sorted(ocr_output_dir.glob("page-*/*.md")):
        page_text = html.unescape(markdown_path.read_text(encoding="utf-8", errors="ignore"))
        if "效果图" not in page_text:
            continue
        if not any(signal in page_text for signal in child_bed_page_signals) and not any(
            signal in aggregate_text for signal in child_bed_page_signals
        ):
            continue

        for image_path in _extract_markdown_image_paths(markdown_path):
            if not image_path.exists():
                continue
            try:
                with Image.open(image_path) as image:
                    width, height = image.size
            except OSError:
                continue
            candidates.append(
                {
                    "image_path": str(image_path),
                    "markdown_path": str(markdown_path),
                    "area": width * height,
                }
            )

    candidates.sort(key=lambda item: int(item.get("area") or 0), reverse=True)
    return candidates[:3]


def _extract_markdown_image_paths(markdown_path: Path) -> list[Path]:
    content = markdown_path.read_text(encoding="utf-8", errors="ignore")
    paths: list[Path] = []
    for raw_path in re.findall(r'<img\s+src="([^"]+)"', content, flags=re.IGNORECASE):
        candidate = (markdown_path.parent / raw_path).resolve()
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _infer_stair_storage_mode_from_effect_image(image_path: Path) -> dict[str, Any]:
    try:
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            crop = rgb.crop(
                (
                    int(width * 0.00),
                    int(height * 0.45),
                    int(width * 0.22),
                    int(height * 0.95),
                )
            )
            arr = np.asarray(crop, dtype=np.float32) / 255.0
    except OSError:
        return {"mode": "", "confidence_score": 0.0, "signals": []}

    if arr.size == 0:
        return {"mode": "", "confidence_score": 0.0, "signals": []}

    red = arr[:, :, 0]
    green = arr[:, :, 1]
    blue = arr[:, :, 2]
    gray = arr.mean(axis=2)

    wood_mask = (
        (red > green)
        & (green > blue * 0.8)
        & ((red - green) > 0.04)
        & ((red - green) < 0.35)
        & (red > 0.24)
        & (red < 0.9)
    )
    non_wood_ratio = 1.0 - float(np.mean(wood_mask))
    gray_std = float(np.std(gray))
    channel_diff = np.max(arr, axis=2) - np.min(arr, axis=2)
    neutral_content_ratio = float(np.mean((channel_diff < 0.12) & (gray > 0.25) & (gray < 0.92)))

    signals: list[str] = []
    score = 0.0
    if non_wood_ratio >= 0.40:
        score += 1.8
        signals.append("visual_open_cells")
    if neutral_content_ratio >= 0.38:
        score += 1.2
        signals.append("visual_neutral_contents")
    if gray_std >= 0.13:
        score += 0.4
        signals.append("visual_contents_variance")

    return {
        "mode": "open_grid" if score >= 3.0 else "",
        "confidence_score": round(score, 2),
        "signals": signals,
        "metrics": {
            "non_wood_ratio": round(non_wood_ratio, 3),
            "gray_std": round(gray_std, 3),
            "neutral_content_ratio": round(neutral_content_ratio, 3),
        },
    }


def _has_underbed_combo_fields(fields: dict[str, Any]) -> bool:
    combo_field_names = (
        "underbed_cabinet_mode",
        "front_cabinet_length",
        "front_cabinet_height",
        "front_cabinet_depth",
        "front_cabinet_mode",
        "rear_cabinet_length",
        "rear_cabinet_height",
        "rear_cabinet_depth",
        "rear_cabinet_mode",
        "interconnected_rows",
    )
    return any(field_name in fields for field_name in combo_field_names)


def _build_route_evidence(
    *,
    text_sources: list[dict[str, Any]],
    fields: dict[str, Any],
    aggregate_text: str,
    child_bed_analysis: dict[str, Any],
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    child_bed_candidate = _build_child_bed_route_candidate(
        text_sources=text_sources,
        fields=fields,
        child_bed_analysis=child_bed_analysis,
    )
    if child_bed_candidate:
        candidates.append(child_bed_candidate)

    cabinet_candidate = _build_cabinet_route_candidate(
        text_sources=text_sources,
        fields=fields,
        aggregate_text=aggregate_text,
    )
    if cabinet_candidate:
        candidates.append(cabinet_candidate)

    if not candidates:
        return None
    candidates.sort(key=lambda item: (int(item.get("score") or 0), str(item.get("route") or "")), reverse=True)
    return {
        "recommended_route": str(candidates[0].get("route") or "").strip(),
        "candidates": candidates,
    }


def _build_child_bed_route_candidate(
    *,
    text_sources: list[dict[str, Any]],
    fields: dict[str, Any],
    child_bed_analysis: dict[str, Any],
) -> dict[str, Any] | None:
    if not child_bed_analysis.get("is_child_bed"):
        return None

    signals = [
        str(item).strip()
        for item in list(child_bed_analysis.get("combo_candidate_signals") or [])
        if str(item).strip()
    ]
    if not signals:
        return None

    evidence_snippets: list[str] = []
    source_asset_ids: list[str] = []
    for label, patterns in UNDERBED_COMBO_SIGNAL_PATTERNS:
        if label not in signals:
            continue
        source_id, snippet = _find_first_signal_snippet(text_sources, patterns)
        if snippet and snippet not in evidence_snippets:
            evidence_snippets.append(snippet)
        if source_id and source_id not in source_asset_ids:
            source_asset_ids.append(source_id)

    if "床下柜体尺寸" in signals:
        snippet = _summarize_underbed_combo_fields(fields)
        if snippet and snippet not in evidence_snippets:
            evidence_snippets.append(snippet)

    primary_asset_id = str(child_bed_analysis.get("primary_drawing_asset_id") or "").strip()
    if primary_asset_id and primary_asset_id not in source_asset_ids:
        source_asset_ids.append(primary_asset_id)

    return {
        "route": "modular_child_bed_combo",
        "score": 10 + len(signals) * 3,
        "signals": signals,
        "evidence_snippets": evidence_snippets[:4],
        "source_asset_ids": source_asset_ids,
        "inferred_overrides": {},
    }


def _build_cabinet_route_candidate(
    *,
    text_sources: list[dict[str, Any]],
    fields: dict[str, Any],
    aggregate_text: str,
) -> dict[str, Any] | None:
    inferred_overrides: dict[str, str] = {}
    signals: list[str] = []
    evidence_snippets: list[str] = []
    source_asset_ids: list[str] = []

    precheck_quote = _precheck_quote_module()
    known_profiles = precheck_quote.DEFAULT_CABINET_PROFILES
    current_category = str((fields.get("product_category") or {}).get("value") or "").strip()
    category = current_category if current_category in known_profiles else ""
    if not category:
        for candidate in known_profiles:
            source_id, snippet = _find_first_signal_snippet(text_sources, (candidate,))
            if snippet:
                category = candidate
                inferred_overrides["category"] = candidate
                signals.append(snippet.replace("图下注：", "").strip())
                evidence_snippets.append(snippet)
                if source_id:
                    source_asset_ids.append(source_id)
                break

    for label, patterns in CABINET_ROUTE_SIGNAL_PATTERNS:
        source_id, snippet = _find_first_signal_snippet(text_sources, patterns)
        if not snippet:
            continue
        if label not in signals:
            signals.append(label if label != "开放柜" else snippet.replace("图下注：", "").strip())
        if snippet not in evidence_snippets:
            evidence_snippets.append(snippet)
        if source_id and source_id not in source_asset_ids:
            source_asset_ids.append(source_id)
        if label in {"开放书柜", "开放柜"} and not (fields.get("has_door") or {}).get("value"):
            inferred_overrides["has_door"] = "no"
        if label == "带门" and not (fields.get("has_door") or {}).get("value"):
            inferred_overrides["has_door"] = "yes"

    if not inferred_overrides.get("has_door"):
        door_type = str((fields.get("door_type") or {}).get("value") or "").strip()
        if door_type:
            inferred_overrides["has_door"] = "yes"
            inferred_overrides["door_type"] = door_type
        else:
            for door_type_candidate in _known_door_types():
                source_id, snippet = _find_first_signal_snippet(text_sources, (door_type_candidate,))
                if not snippet:
                    continue
                inferred_overrides["has_door"] = "yes"
                inferred_overrides["door_type"] = door_type_candidate
                if door_type_candidate not in signals:
                    signals.append(door_type_candidate)
                if snippet not in evidence_snippets:
                    evidence_snippets.append(snippet)
                if source_id and source_id not in source_asset_ids:
                    source_asset_ids.append(source_id)
                break

    has_core_dimensions = bool(fields.get("length")) and bool(fields.get("height"))
    has_material = bool(fields.get("wood_material"))
    if not category and "category" not in inferred_overrides:
        return None
    if not has_core_dimensions or not has_material:
        return None

    return {
        "route": "cabinet",
        "score": 8 + len(signals) * 2 + int(bool(inferred_overrides)),
        "signals": signals[:4],
        "evidence_snippets": evidence_snippets[:4],
        "source_asset_ids": source_asset_ids,
        "inferred_overrides": inferred_overrides,
    }


def _find_first_signal_snippet(
    text_sources: list[dict[str, Any]],
    patterns: tuple[str, ...],
) -> tuple[str, str]:
    for source in text_sources:
        text = str(source.get("text") or "")
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            return str(source.get("asset_id") or "").strip(), _extract_match_snippet(text, match)
    return "", ""


def _extract_match_snippet(text: str, match: re.Match[str]) -> str:
    start = max(match.start() - 8, 0)
    end = min(match.end() + 20, len(text))
    return re.sub(r"\s+", " ", text[start:end]).strip(" ，,。；;\n")


def _summarize_underbed_combo_fields(fields: dict[str, Any]) -> str:
    parts: list[str] = []
    for field_name in (
        "front_cabinet_length",
        "front_cabinet_height",
        "front_cabinet_depth",
        "rear_cabinet_length",
        "rear_cabinet_height",
        "rear_cabinet_depth",
    ):
        value = str((fields.get(field_name) or {}).get("value") or "").strip()
        if value:
            parts.append(f"{field_name}={value}")
    return "；".join(parts[:3])


def _infer_fields_from_pricing_text(
    text_sources: list[dict[str, str]],
    aggregate_text: str,
) -> dict[str, dict[str, Any]]:
    if not aggregate_text or count_unique_product_codes(aggregate_text) > 1:
        return {}

    compact_text = re.sub(r"\s+", "", aggregate_text)
    if not compact_text:
        return {}

    inferred = _handle_quote_message_module()._infer_precheck_args_from_text(compact_text)
    if not isinstance(inferred, dict):
        return {}

    inferred_fields: dict[str, dict[str, Any]] = {}
    category = str(inferred.get("category") or "").strip()
    if category:
        inferred_fields["product_category"] = _build_field_payload(
            key="product_category",
            value=category,
            confidence=0.9,
            source=text_sources[0] if text_sources else None,
            evidence_text=category,
        )
    return inferred_fields


def _merge_inferred_field_candidates(
    fields: dict[str, Any],
    inferred_fields: dict[str, dict[str, Any]],
) -> None:
    inferred_category = inferred_fields.get("product_category")
    if not inferred_category:
        return

    current = fields.get("product_category") or {}
    current_value = str(current.get("value") or "").strip()
    candidate_value = str(inferred_category.get("value") or "").strip()
    if not candidate_value:
        return

    if not current_value or _should_prefer_inferred_category(current_value, candidate_value):
        _merge_field(fields, inferred_category)


def _should_prefer_inferred_category(current_value: str, candidate_value: str) -> bool:
    if current_value == candidate_value:
        return False
    if current_value in {"床", "桌", "箱体床", "架式床"} and len(candidate_value) >= len(current_value):
        return True
    if current_value in {"书柜", "衣柜", "玄关柜", "餐边柜"} and len(candidate_value) > len(current_value):
        return True
    return False


def _extract_product_category(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    explicit_value, source = _find_labeled_text(text_sources, PRODUCT_LABEL_PATTERNS)
    categories = _known_categories()
    if explicit_value:
        candidate = _match_category(explicit_value, categories)
        if candidate:
            return _build_field_payload(
                key="product_category",
                value=candidate,
                confidence=0.96,
                source=source,
                evidence_text=explicit_value,
            )
    candidate = _match_category(aggregate_text, categories)
    if candidate:
        source = _first_source_with_match(text_sources, candidate)
        return _build_field_payload(
            key="product_category",
            value=candidate,
            confidence=0.88,
            source=source,
            evidence_text=candidate,
        )
    return None


def _extract_material(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    material_module = _material_names_module()
    explicit_value, source = _find_labeled_text(text_sources, MATERIAL_LABEL_PATTERNS)
    known_formal_materials = {str(spec["formal"]).strip() for spec in material_module.MATERIAL_SPECS}
    if explicit_value:
        formalized = material_module.formalize_material_name(
            material_module.normalize_material_for_query(explicit_value)
        )
        if formalized in known_formal_materials:
            return _build_field_payload(
                key="wood_material",
                value=formalized,
                confidence=0.95,
                source=source,
                evidence_text=explicit_value,
            )

    formalized_text = material_module.formalize_text(aggregate_text) or aggregate_text
    for spec in material_module.MATERIAL_SPECS:
        formal_name = str(spec["formal"]).strip()
        if formal_name and formal_name in formalized_text:
            source = _first_source_with_match(text_sources, formal_name)
            return _build_field_payload(
                key="wood_material",
                value=formal_name,
                confidence=0.9,
                source=source,
                evidence_text=formal_name,
            )
    return None


def _extract_bed_form(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    return _extract_from_known_values(
        key="bed_form",
        text_sources=text_sources,
        aggregate_text=aggregate_text,
        known_values=_modular_child_bed_forms(),
        label_patterns=(r"(?:床形态|床形式|床型|产品形态)[:：\s]*([^\n，,。；;]+)",),
        labeled_confidence=0.95,
        aggregate_confidence=0.9,
    )


def _extract_access_style(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    return _extract_from_known_values(
        key="access_style",
        text_sources=text_sources,
        aggregate_text=aggregate_text,
        known_values=["梯柜", "斜梯", "直梯"],
        label_patterns=(r"(?:上层出入方式|出入方式|爬梯方式|梯型)[:：\s]*([^\n，,。；;]+)",),
        labeled_confidence=0.95,
        aggregate_confidence=0.9,
    )


def _extract_lower_bed_type(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    return _extract_from_known_values(
        key="lower_bed_type",
        text_sources=text_sources,
        aggregate_text=aggregate_text,
        known_values=["架式床", "箱体床", "抽屉床"],
        label_patterns=(r"(?:下层结构|下床结构|下层床型|下层形式)[:：\s]*([^\n，,。；;]+)",),
        labeled_confidence=0.95,
        aggregate_confidence=0.9,
    )


def _extract_guardrail_style(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    return _extract_from_known_values(
        key="guardrail_style",
        text_sources=text_sources,
        aggregate_text=aggregate_text,
        known_values=_guardrail_styles(),
        label_patterns=(r"(?:围栏样式|围栏款式|护栏样式|护栏款式)[:：\s]*([^\n，,。；;]+)",),
        labeled_confidence=0.95,
        aggregate_confidence=0.9,
    )


def _extract_quote_kind(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    for quote_kind, patterns in QUOTE_KIND_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, aggregate_text)
            if match:
                source = _first_source_with_regex(text_sources, pattern)
                return _build_field_payload(
                    key="quote_kind",
                    value=quote_kind,
                    confidence=0.87,
                    source=source,
                    evidence_text=match.group(0),
                )
    return None


def _extract_has_door(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    for door_flag, patterns in DOOR_TYPE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, aggregate_text)
            if match:
                source = _first_source_with_regex(text_sources, pattern)
                return _build_field_payload(
                    key="has_door",
                    value=door_flag,
                    confidence=0.87,
                    source=source,
                    evidence_text=match.group(0),
                )
    return None


def _extract_door_type(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    explicit_value, source = _find_labeled_text(text_sources, DOOR_TYPE_LABEL_PATTERNS)
    if explicit_value:
        candidate = _match_known_value(explicit_value, _known_door_types())
        if candidate:
            return _build_field_payload(
                key="door_type",
                value=candidate,
                confidence=0.94,
                source=source,
                evidence_text=explicit_value,
            )

    candidate = _match_known_value(aggregate_text, _known_door_types())
    if candidate:
        source = _first_source_with_match(text_sources, candidate)
        return _build_field_payload(
            key="door_type",
            value=candidate,
            confidence=0.86,
            source=source,
            evidence_text=candidate,
        )
    return None


def _extract_underbed_cabinet_mode(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    known_values = ["有门无背板", "无门有背板", "无门无背板"]
    return _extract_from_known_values(
        key="underbed_cabinet_mode",
        text_sources=text_sources,
        aggregate_text=aggregate_text,
        known_values=known_values,
        label_patterns=(rf"(?:床下柜体结构|床下柜结构|下柜结构)[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}",),
        labeled_confidence=0.93,
        aggregate_confidence=0.86,
    )


def _extract_cabinet_mode(
    key: str,
    text_sources: list[dict[str, str]],
    aggregate_text: str,
) -> dict[str, Any] | None:
    known_values = ["有门无背板", "无门有背板", "无门无背板"]
    return _extract_from_known_values(
        key=key,
        text_sources=text_sources,
        aggregate_text=aggregate_text,
        known_values=known_values,
        label_patterns=CABINET_MODE_LABEL_PATTERNS[key],
        labeled_confidence=0.94,
        aggregate_confidence=0.86,
        allow_aggregate=False,
    )


def _extract_interconnected_rows(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any] | None:
    for pattern in (r"前后双排互通", r"双排互通", r"前后互通", r"互通", r"连通"):
        match = re.search(pattern, aggregate_text)
        if match:
            source = _first_source_with_regex(text_sources, pattern)
            return _build_field_payload(
                key="interconnected_rows",
                value=True,
                confidence=0.93,
                source=source,
                evidence_text=match.group(0),
            )
    return None


def _extract_dimension(
    target_field: str,
    text_sources: list[dict[str, str]],
    aggregate_text: str,
) -> dict[str, Any] | None:
    layout_candidate = _find_dimension_from_ocr_layout(target_field, text_sources)
    if layout_candidate is not None:
        return layout_candidate

    for pattern in LABELED_PATTERNS.get(target_field, ()):
        match = re.search(pattern, aggregate_text, flags=re.IGNORECASE)
        if match:
            source = _first_source_with_regex(text_sources, pattern)
            return _build_field_payload(
                key=target_field,
                value=match.group(1).strip(),
                confidence=0.95,
                source=source,
                evidence_text=match.group(0),
            )
    return None


def _merge_combo_row_segment_dimensions(
    fields: dict[str, Any],
    text_sources: list[dict[str, str]],
    aggregate_text: str,
) -> None:
    if not _looks_like_bed_combo_request(aggregate_text):
        return

    for row_prefix in ("front", "rear"):
        updates = _extract_combo_row_segment_fields(row_prefix, text_sources)
        for payload in updates:
            if payload["key"] not in fields:
                _merge_field(fields, payload)


def _extract_combo_row_segment_fields(
    row_prefix: str,
    text_sources: list[dict[str, str]],
) -> list[dict[str, Any]]:
    prefixes = ("前排", "前面", "前方") if row_prefix == "front" else ("后排", "后面", "后方")
    stop_prefixes = ("后排", "后面", "后方") if row_prefix == "front" else ()
    fields: list[dict[str, Any]] = []

    for source in text_sources:
        segment = _extract_row_segment(
            source["text"],
            prefixes=prefixes,
            stop_prefixes=stop_prefixes,
        )
        if not segment:
            continue

        dimension_map = {
            f"{row_prefix}_cabinet_length": ("长度", "长"),
            f"{row_prefix}_cabinet_height": ("高度", "高"),
            f"{row_prefix}_cabinet_depth": ("进深", "深度", "深"),
        }
        for key, labels in dimension_map.items():
            value = _extract_segment_dimension(segment, labels)
            if value:
                fields.append(
                    _build_field_payload(
                        key=key,
                        value=value,
                        confidence=0.92,
                        source=source,
                        evidence_text=segment,
                    )
                )

        mode = _match_known_value(segment, ["有门无背板", "无门有背板", "无门无背板"])
        if mode:
            fields.append(
                _build_field_payload(
                    key=f"{row_prefix}_cabinet_mode",
                    value=mode,
                    confidence=0.92,
                    source=source,
                    evidence_text=segment,
                )
            )
        break

    return fields


def _find_labeled_text(
    text_sources: list[dict[str, str]],
    patterns: tuple[str, ...],
) -> tuple[str | None, dict[str, str] | None]:
    for source in text_sources:
        for pattern in patterns:
            match = re.search(pattern, source["text"], flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(), source
    return None, None


def _extract_from_known_values(
    *,
    key: str,
    text_sources: list[dict[str, str]],
    aggregate_text: str,
    known_values: list[str],
    label_patterns: tuple[str, ...],
    labeled_confidence: float,
    aggregate_confidence: float,
    allow_aggregate: bool = True,
) -> dict[str, Any] | None:
    explicit_value, source = _find_labeled_text(text_sources, label_patterns)
    if explicit_value:
        candidate = _match_known_value(explicit_value, known_values)
        if candidate:
            return _build_field_payload(
                key=key,
                value=candidate,
                confidence=labeled_confidence,
                source=source,
                evidence_text=explicit_value,
            )

    candidate = _match_known_value(aggregate_text, known_values) if allow_aggregate else None
    if candidate:
        source = _first_source_with_match(text_sources, candidate)
        return _build_field_payload(
            key=key,
            value=candidate,
            confidence=aggregate_confidence,
            source=source,
            evidence_text=candidate,
        )
    return None


def _build_field_payload(
    *,
    key: str,
    value: Any,
    confidence: float,
    source: dict[str, str] | None,
    evidence_text: str,
    evidence_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "key": key,
        "value": value,
        "confidence": confidence,
        "evidence_refs": [],
    }
    if source is not None:
        evidence_ref = {
            "asset_id": source["asset_id"],
            "file_name": source["file_name"],
            "text_extract_method": source["text_extract_method"],
            "source_kind": source.get("source_kind", ""),
            "snippet": evidence_text,
        }
        if evidence_meta:
            evidence_ref.update(evidence_meta)
        payload["evidence_refs"].append(evidence_ref)
    return payload


def _find_dimension_from_ocr_layout(
    target_field: str,
    text_sources: list[dict[str, str]],
) -> dict[str, Any] | None:
    best_source: dict[str, Any] | None = None
    best_candidate: dict[str, Any] | None = None
    for source in text_sources:
        ocr_layout = source.get("ocr_layout") or {}
        field_candidates = ocr_layout.get("field_candidates") or {}
        candidate = field_candidates.get(target_field)
        if not isinstance(candidate, dict):
            continue
        if best_candidate is None or float(candidate.get("score") or 0.0) > float(best_candidate.get("score") or 0.0):
            best_source = source
            best_candidate = candidate

    if best_source is None or best_candidate is None:
        return None

    label = str(best_candidate.get("label") or "").strip()
    value = str(best_candidate.get("value") or "").strip()
    evidence_text = " ".join(item for item in (label, value) if item).strip() or value
    return _build_field_payload(
        key=target_field,
        value=value,
        confidence=0.97 if str(best_candidate.get("match_type") or "") == "inline_label" else 0.95,
        source=best_source,
        evidence_text=evidence_text,
        evidence_meta={
            "evidence_type": "ocr_layout",
            "page_no": best_candidate.get("page_no"),
            "bbox": best_candidate.get("bbox"),
            "label_text": best_candidate.get("label_text"),
            "layout_match_type": best_candidate.get("match_type"),
        },
    )


def _merge_field(fields: dict[str, Any], payload: dict[str, Any] | None) -> None:
    if payload is None:
        return
    key = str(payload["key"])
    fields[key] = {field_key: field_value for field_key, field_value in payload.items() if field_key != "key"}


def _first_source_with_match(text_sources: list[dict[str, str]], text: str) -> dict[str, str] | None:
    for source in text_sources:
        if text and text in source["text"]:
            return source
    return text_sources[0] if text_sources else None


def _first_source_with_regex(text_sources: list[dict[str, str]], pattern: str) -> dict[str, str] | None:
    for source in text_sources:
        if re.search(pattern, source["text"], flags=re.IGNORECASE):
            return source
    return text_sources[0] if text_sources else None


def _match_category(text: str, categories: list[str]) -> str | None:
    for category in categories:
        if category and category in text:
            return category
    return None


def _match_known_value(text: str, values: list[str]) -> str | None:
    for value in values:
        if value and value in text:
            return value
    return None


def _looks_like_child_bed_request(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(keyword in normalized for keyword in CHILD_BED_KEYWORDS)


def _looks_like_bed_combo_request(text: str) -> bool:
    has_bed_signal = "床" in text or any(keyword in text for keyword in ("上铺床", "床下"))
    has_combo_signal = any(
        keyword in text
        for keyword in ("床下", "前排", "后排", "前面", "后面", "前方", "后方", "前后双排", "互通")
    )
    return has_bed_signal and has_combo_signal


def _extract_row_segment(text: str, *, prefixes: tuple[str, ...], stop_prefixes: tuple[str, ...] = ()) -> str:
    prefix_pattern = "|".join(re.escape(item) for item in prefixes)
    stop_pattern = "|".join(re.escape(item) for item in stop_prefixes)
    lookahead = rf"(?:(?:{stop_pattern})|[。；;\n]|$)" if stop_pattern else r"(?=[。；;\n]|$)"
    pattern = rf"((?:{prefix_pattern})[^。；;\n]*?){lookahead}"
    match = re.search(pattern, text)
    if not match:
        return ""
    return str(match.group(1)).strip("，, ")


def _extract_segment_dimension(segment: str, labels: tuple[str, ...]) -> str:
    labels_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{labels_pattern})[:：\s]*{DIMENSION_VALUE_PATTERN}", segment, flags=re.IGNORECASE)
    if not match:
        return ""
    return str(match.group(1)).strip()


def _apply_template_profile(
    fields: dict[str, Any],
    text_sources: list[dict[str, str]],
    template_profile: dict[str, Any] | None,
) -> None:
    if not template_profile:
        return
    field_aliases = template_profile.get("field_aliases") or {}
    for field_name, alias_entry in field_aliases.items():
        labels = [str(label).strip() for label in list(alias_entry.get("labels") or []) if str(label).strip()]
        confirmed_values = [str(value).strip() for value in list(alias_entry.get("confirmed_values") or []) if str(value).strip()]
        if not labels or not confirmed_values:
            continue

        current = fields.get(field_name)
        if current is not None:
            confirmed = _match_confirmed_value(
                field_name=field_name,
                current_value=str(current.get("value") or "").strip(),
                confirmed_values=confirmed_values,
            )
            if confirmed and str(current.get("value") or "").strip() == confirmed:
                current["confidence"] = round(max(float(current.get("confidence") or 0.0), 0.97), 2)
                current["template_hint"] = {
                    "template_id": str(template_profile.get("template_id") or "").strip(),
                    "strategy": "confidence_boost",
                }
            elif confirmed_values and _is_generic_field_value(field_name, str(current.get("value") or "").strip()):
                explicit_value, source = _find_labeled_text(text_sources, _label_patterns_from_aliases(labels))
                confirmed = _match_confirmed_value(
                    field_name=field_name,
                    current_value=str(explicit_value or "").strip(),
                    confirmed_values=confirmed_values,
                )
                if confirmed:
                    _merge_field(
                        fields,
                        {
                            **_build_field_payload(
                                key=field_name,
                                value=confirmed,
                                confidence=max(float(current.get("confidence") or 0.0), 0.91),
                                source=source,
                                evidence_text=explicit_value or confirmed,
                            ),
                            "template_hint": {
                                "template_id": str(template_profile.get("template_id") or "").strip(),
                                "strategy": "replace_generic_value",
                            },
                        },
                    )
            continue

        explicit_value, source = _find_labeled_text(text_sources, _label_patterns_from_aliases(labels))
        if not explicit_value:
            continue
        confirmed = _match_confirmed_value(
            field_name=field_name,
            current_value=str(explicit_value or "").strip(),
            confirmed_values=confirmed_values,
        )
        if not confirmed:
            continue
        _merge_field(
            fields,
            {
                **_build_field_payload(
                    key=field_name,
                    value=confirmed,
                    confidence=0.84,
                    source=source,
                    evidence_text=explicit_value,
                ),
                "template_hint": {
                    "template_id": str(template_profile.get("template_id") or "").strip(),
                    "strategy": "alias_fill",
                },
            },
        )


def _label_patterns_from_aliases(labels: list[str]) -> tuple[str, ...]:
    return tuple(
        rf"(?:{re.escape(label)})[:：\s]*([^\n，,。；;]+?){FIELD_FOLLOWUP_BOUNDARY}"
        for label in labels
    )


def _match_confirmed_value(*, field_name: str, current_value: str, confirmed_values: list[str]) -> str:
    if not current_value and len(confirmed_values) == 1:
        return confirmed_values[0]
    for value in confirmed_values:
        if value == current_value:
            return value
        if value and current_value and (value in current_value or current_value in value):
            return value
        if field_name == "product_category" and value and current_value and _normalize_text(value) == _normalize_text(current_value):
            return value
    return ""


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _is_generic_field_value(field_name: str, value: str) -> bool:
    if field_name != "product_category":
        return False
    return value in GENERIC_CATEGORY_VALUES


def _infer_source_kind(asset: SourceAsset) -> str:
    method = str(asset.text_extract_method or "").strip()
    metadata = asset.metadata or {}
    if metadata.get("ocr_markdown_path"):
        return "ocr_markdown"
    if method in {"docx_text", "pdf_text_layer", "native_plus_ocr"}:
        return "native_preview"
    if "ocr" in method.lower():
        return "ocr_preview"
    return "ocr_unknown"


@lru_cache(maxsize=1)
def _known_categories() -> list[str]:
    precheck_quote = _precheck_quote_module()
    categories = {
        *precheck_quote.CABINET_CATEGORIES,
        *precheck_quote.BED_CATEGORIES,
        *precheck_quote.TATAMI_CATEGORIES,
        *precheck_quote.TABLE_CATEGORIES,
    }
    return sorted(categories, key=len, reverse=True)


@lru_cache(maxsize=1)
def _modular_child_bed_forms() -> list[str]:
    precheck_quote = _precheck_quote_module()
    return sorted(precheck_quote.MODULAR_CHILD_BED_FORMS, key=len, reverse=True)


@lru_cache(maxsize=1)
def _guardrail_styles() -> list[str]:
    precheck_quote = _precheck_quote_module()
    return sorted(precheck_quote.MODULAR_CHILD_BED_GUARDRAIL_STYLES, key=len, reverse=True)


@lru_cache(maxsize=1)
def _known_door_types() -> list[str]:
    return ["真格栅门", "格栅门", "铝框门", "拼框门", "平板门", "带门"]


@lru_cache(maxsize=1)
def _precheck_quote_module():
    scripts_dir = resolve_pricing_scripts_dir(Path(__file__))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("precheck_quote")


@lru_cache(maxsize=1)
def _handle_quote_message_module():
    scripts_dir = resolve_pricing_scripts_dir(Path(__file__))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("handle_quote_message")


@lru_cache(maxsize=1)
def _material_names_module():
    scripts_dir = resolve_pricing_scripts_dir(Path(__file__))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("material_names")
