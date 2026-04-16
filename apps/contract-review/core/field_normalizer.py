from __future__ import annotations

import importlib
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from attachment_section import extract_attachment_pricing_section
from product_code_utils import count_unique_product_codes
from job_models import ReviewJob, SourceAsset
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


def normalize_job_fields(job: ReviewJob, *, template_runtime_root: Path | None = None) -> dict[str, Any]:
    template_profile = (
        find_template_profile(job=job, runtime_root=template_runtime_root)
        if template_runtime_root is not None
        else None
    )
    preferred_evidence_order = list((template_profile or {}).get("preferred_evidence_order") or [])
    text_sources = _collect_text_sources(job.assets, preferred_evidence_order=preferred_evidence_order)
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
    if template_profile:
        payload["template_profile"] = {
            "template_id": str(template_profile.get("template_id") or "").strip(),
            "template_fingerprint": str(template_profile.get("template_fingerprint") or "").strip(),
            "template_lookup_fingerprint": str(template_profile.get("template_lookup_fingerprint") or "").strip(),
            "trust_score": template_profile.get("trust_score"),
        }
    return payload


def _collect_text_sources(
    assets: list[SourceAsset],
    *,
    preferred_evidence_order: list[str] | None = None,
) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for asset in assets:
        if not str(asset.text_preview or "").strip():
            continue
        normalized_text = extract_attachment_pricing_section(str(asset.text_preview).strip())
        sources.append(
            {
                "asset_id": asset.asset_id,
                "file_name": asset.file_name,
                "text": normalized_text,
                "text_extract_method": asset.text_extract_method,
                "source_kind": _infer_source_kind(asset),
            }
        )
    if preferred_evidence_order:
        order = {value: index for index, value in enumerate(preferred_evidence_order)}
        sources.sort(key=lambda item: (order.get(str(item.get("source_kind") or ""), len(order)), str(item.get("asset_id") or "")))
    return sources


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
) -> dict[str, Any]:
    payload = {
        "key": key,
        "value": value,
        "confidence": confidence,
        "evidence_refs": [],
    }
    if source is not None:
        payload["evidence_refs"].append(
            {
                "asset_id": source["asset_id"],
                "file_name": source["file_name"],
                "text_extract_method": source["text_extract_method"],
                "source_kind": source.get("source_kind", ""),
                "snippet": evidence_text,
            }
        )
    return payload


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
    scripts_dir = Path(__file__).resolve().parents[3] / "skill" / "liangqin-pricing" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("precheck_quote")


@lru_cache(maxsize=1)
def _handle_quote_message_module():
    scripts_dir = Path(__file__).resolve().parents[3] / "skill" / "liangqin-pricing" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("handle_quote_message")


@lru_cache(maxsize=1)
def _material_names_module():
    scripts_dir = Path(__file__).resolve().parents[3] / "skill" / "liangqin-pricing" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("material_names")
