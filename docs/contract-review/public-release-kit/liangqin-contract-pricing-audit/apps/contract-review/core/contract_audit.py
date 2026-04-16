from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from job_models import ReviewJob


MONEY_PATTERN = r"([0-9][0-9,]*(?:\.[0-9]+)?\s*元)"
NUMBER_MONEY_PATTERN = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
TOTAL_LABEL_TOKEN_PATTERN = r"(?:费用合计|合同总\s*价|合同总\s*金额|总\s*价|总\s*金额|合计)"
TOTAL_LABEL_PATTERNS = (
    rf"{TOTAL_LABEL_TOKEN_PATTERN}(?:为人民币)?[:：\s]*{MONEY_PATTERN}",
)
LIST_PRICE_TOTAL_PATTERNS = (
    rf"(?:费用合计(?:（元）|\(元\)|元)?|折扣前合计)[:：\s]*{NUMBER_MONEY_PATTERN}",
    rf"(?:^|[\s，,。；;])合计[:：\s]*{NUMBER_MONEY_PATTERN}(?=\s*折扣)",
)
DISCOUNT_RATE_PATTERNS = (
    r"(?:折扣|折后系数)[:：\s]*([0-9]+(?:\.[0-9]+)?折)",
)
DISCOUNTED_TOTAL_PATTERNS = (
    rf"(?:折扣后合计|折后合计)[:：\s]*{NUMBER_MONEY_PATTERN}",
)
ADD_ON_PATTERNS = (
    rf"(?:增项费用|增项金额|另计费用|加项费用)[:：\s]*([^\n]*?){MONEY_PATTERN}",
)
NOTE_PREFIXES = ("备注", "特殊说明", "补充说明", "工艺说明", "安装说明")
FOLLOWUP_BOUNDARY = rf"(?=\s*(?:备注|特殊说明|补充说明|工艺说明|安装说明|增项费用|增项金额|另计费用|加项费用|{TOTAL_LABEL_TOKEN_PATTERN})[:：]|$)"
DIMENSION_VALUE_PATTERN = r"([0-9]+(?:\.[0-9]+)?\s*(?:mm|毫米|cm|厘米|m|米)?)"
TEXT_VALUE_PATTERN = r"([^\n，,。；;]+)"
CONFLICT_SPECS: dict[str, dict[str, Any]] = {
    "length": {
        "patterns": (
            rf"(?:^|[\s，,。；;])长度[:：\s]*{DIMENSION_VALUE_PATTERN}",
            rf"(?:床垫长度)[:：\s]*{DIMENSION_VALUE_PATTERN}",
        ),
        "normalizer": "dimension",
        "severity": "high",
    },
    "depth": {
        "patterns": (
            rf"(?:^|[\s，,。；;])进深[:：\s]*{DIMENSION_VALUE_PATTERN}",
            rf"(?:^|[\s，,。；;])深度[:：\s]*{DIMENSION_VALUE_PATTERN}",
        ),
        "normalizer": "dimension",
        "severity": "high",
    },
    "height": {
        "patterns": (
            rf"(?:^|[\s，,。；;])高度[:：\s]*{DIMENSION_VALUE_PATTERN}",
            rf"(?:^|[\s，,。；;])高[:：\s]*{DIMENSION_VALUE_PATTERN}",
        ),
        "normalizer": "dimension",
        "severity": "high",
    },
    "width": {
        "patterns": (
            rf"(?:^|[\s，,。；;])宽度[:：\s]*{DIMENSION_VALUE_PATTERN}",
            rf"(?:床垫宽度|床宽)[:：\s]*{DIMENSION_VALUE_PATTERN}",
        ),
        "normalizer": "dimension",
        "severity": "high",
    },
    "wood_material": {
        "patterns": (
            rf"(?:材质|木材|主材|木种)[:：\s]*{TEXT_VALUE_PATTERN}",
        ),
        "normalizer": "text",
        "severity": "critical",
    },
    "door_type": {
        "patterns": (
            rf"(?:门型|柜门类型|门板类型)[:：\s]*{TEXT_VALUE_PATTERN}",
        ),
        "normalizer": "text",
        "severity": "medium",
    },
    "bed_form": {
        "patterns": (
            rf"(?:床形态|床形式|床型|产品形态)[:：\s]*{TEXT_VALUE_PATTERN}",
        ),
        "normalizer": "text",
        "severity": "critical",
    },
    "front_cabinet_mode": {
        "patterns": (
            rf"(?:前排柜体结构|前排结构|前柜结构)[:：\s]*{TEXT_VALUE_PATTERN}",
        ),
        "normalizer": "text",
        "severity": "critical",
    },
    "rear_cabinet_mode": {
        "patterns": (
            rf"(?:后排柜体结构|后排结构|后柜结构)[:：\s]*{TEXT_VALUE_PATTERN}",
        ),
        "normalizer": "text",
        "severity": "critical",
    },
    "contract_total": {
        "patterns": TOTAL_LABEL_PATTERNS,
        "normalizer": "amount",
        "severity": "critical",
    },
}


def build_contract_audit_report(
    *,
    job: ReviewJob,
    normalized_fields_payload: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
) -> dict[str, Any]:
    text_sources = _collect_text_sources(job)
    aggregate_text = "\n".join(item["text"] for item in text_sources).strip()

    financials = _extract_financials(text_sources, aggregate_text)
    special_notes = _extract_special_notes(text_sources)
    pricing_alignment = _build_pricing_alignment(normalized_fields_payload, pricing_bridge_payload)
    field_evidence_overview = _build_field_evidence_overview(normalized_fields_payload)
    field_conflicts = _detect_field_conflicts(text_sources)
    conflict_resolution_suggestions = _build_conflict_resolution_suggestions(field_conflicts)

    risk_flags: list[str] = []
    if financials.get("contract_total"):
        risk_flags.append("contract_total_detected")
    if financials.get("list_price_total"):
        risk_flags.append("contract_list_price_detected")
    if financials.get("discounted_total"):
        risk_flags.append("contract_discounted_total_detected")
    if financials.get("discount_rate"):
        risk_flags.append("contract_discount_detected")
    if financials.get("add_on_items"):
        risk_flags.append("contract_add_on_detected")
    if special_notes:
        risk_flags.append("contract_special_notes_detected")
    if pricing_alignment["missing_for_pricing"]:
        risk_flags.append("pricing_fields_still_missing")
    if pricing_alignment["unmapped_high_confidence_fields"]:
        risk_flags.append("high_confidence_fields_not_consumed_by_pricing")
    for item in field_conflicts:
        risk_flags.append(f"{item['field_name']}_value_conflict_detected")
        if item["severity"] in {"high", "critical"}:
            risk_flags.append("high_severity_field_conflict_detected")
    if any(item.get("recommended_action") == "manual_review_required" for item in conflict_resolution_suggestions):
        risk_flags.append("manual_conflict_review_required")

    return {
        "job_id": job.job_id,
        "financials": financials,
        "special_notes": special_notes,
        "pricing_alignment": pricing_alignment,
        "field_evidence_overview": field_evidence_overview,
        "field_conflicts": field_conflicts,
        "conflict_resolution_suggestions": conflict_resolution_suggestions,
        "risk_flags": risk_flags,
    }


def _collect_text_sources(job: ReviewJob) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for asset in job.assets:
        metadata = asset.metadata or {}
        text = _read_preferred_asset_text(asset)
        if not text:
            continue
        sources.append(
            {
                "asset_id": asset.asset_id,
                "file_name": asset.file_name,
                "text": text,
                "text_extract_method": str(asset.text_extract_method or ""),
                "source_kind": _infer_source_kind(asset),
                "ocr_markdown_path": str(metadata.get("ocr_markdown_path") or ""),
            }
        )
    return sources


def _extract_financials(text_sources: list[dict[str, str]], aggregate_text: str) -> dict[str, Any]:
    contract_total = None
    for pattern in TOTAL_LABEL_PATTERNS:
        match = re.search(pattern, aggregate_text, flags=re.IGNORECASE)
        if match:
            source = _first_source_with_regex(text_sources, pattern)
            contract_total = {
                "value": _normalize_amount(match.group(1)),
                "evidence_text": match.group(0).strip(),
                "asset_id": source.get("asset_id", "") if source else "",
                "file_name": source.get("file_name", "") if source else "",
                "source_kind": source.get("source_kind", "") if source else "",
                "text_extract_method": source.get("text_extract_method", "") if source else "",
                "evidence_refs": [_build_evidence_ref(source, match.group(0))] if source else [],
            }
            break

    list_price_total = _extract_labeled_amount(
        text_sources,
        aggregate_text,
        LIST_PRICE_TOTAL_PATTERNS,
        label="list_price_total",
        value_normalizer=_normalize_numeric_amount,
    )
    discount_rate = _extract_labeled_text_value(
        text_sources,
        aggregate_text,
        DISCOUNT_RATE_PATTERNS,
        label="discount_rate",
    )
    discounted_total = _extract_labeled_amount(
        text_sources,
        aggregate_text,
        DISCOUNTED_TOTAL_PATTERNS,
        label="discounted_total",
        value_normalizer=_normalize_numeric_amount,
    )

    add_on_items: list[dict[str, str]] = []
    seen_signatures: set[tuple[str, str]] = set()
    for source in text_sources:
        for pattern in ADD_ON_PATTERNS:
            for match in re.finditer(pattern, source["text"], flags=re.IGNORECASE):
                description = str(match.group(1) or "").strip("：:，, ")
                amount = _normalize_amount(match.group(2))
                signature = (description, amount)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                add_on_items.append(
                    {
                        "description": description,
                        "amount": amount,
                        "evidence_text": match.group(0).strip(),
                        "asset_id": source["asset_id"],
                        "file_name": source["file_name"],
                        "source_kind": source.get("source_kind", ""),
                        "text_extract_method": source.get("text_extract_method", ""),
                        "evidence_refs": [_build_evidence_ref(source, match.group(0))],
                    }
                )

    return {
        "contract_total": contract_total,
        "list_price_total": list_price_total,
        "discount_rate": discount_rate,
        "discounted_total": discounted_total,
        "add_on_items": add_on_items,
    }


def _extract_special_notes(text_sources: list[dict[str, str]]) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in text_sources:
        for prefix in NOTE_PREFIXES:
            pattern = rf"{re.escape(prefix)}[:：]\s*([^\n]*?){FOLLOWUP_BOUNDARY}"
            for match in re.finditer(pattern, source["text"], flags=re.IGNORECASE):
                detail = str(match.group(1) or "").strip("，,；; ")
                text = f"{prefix}：{detail}" if detail else prefix
                if text in seen:
                    continue
                seen.add(text)
                notes.append(
                    {
                        "text": text,
                        "asset_id": source["asset_id"],
                        "file_name": source["file_name"],
                        "source_kind": source.get("source_kind", ""),
                        "text_extract_method": source.get("text_extract_method", ""),
                        "evidence_refs": [_build_evidence_ref(source, match.group(0))],
                    }
                )
    return notes


def _build_pricing_alignment(
    normalized_fields_payload: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
) -> dict[str, Any]:
    fields_payload = normalized_fields_payload.get("fields") or {}
    mapped_fields = pricing_bridge_payload.get("mapped_fields") or {}
    mapped_source_fields = {
        str(item.get("source_field") or "").strip()
        for item in mapped_fields.values()
        if isinstance(item, dict)
    }
    withheld_source_fields = [str(item).strip() for item in pricing_bridge_payload.get("withheld_source_fields") or [] if str(item).strip()]
    blocked_fields = [str(item).strip() for item in pricing_bridge_payload.get("blocked_fields") or [] if str(item).strip()]
    next_required_field = str((pricing_bridge_payload.get("precheck_result") or {}).get("next_required_field") or "").strip()

    unmapped_high_confidence_fields: list[str] = []
    for field_name, payload in fields_payload.items():
        if not isinstance(payload, dict):
            continue
        confidence = _to_confidence(payload.get("confidence"))
        if confidence < 0.9:
            continue
        if field_name in mapped_source_fields:
            continue
        unmapped_high_confidence_fields.append(str(field_name))

    return {
        "status": pricing_bridge_payload.get("status", ""),
        "reason": pricing_bridge_payload.get("reason", ""),
        "mapped_field_count": len(mapped_fields),
        "blocked_fields": sorted(set(blocked_fields)),
        "withheld_source_fields": sorted(set(withheld_source_fields)),
        "next_required_field": next_required_field,
        "missing_for_pricing": [next_required_field] if next_required_field else [],
        "unmapped_high_confidence_fields": sorted(set(unmapped_high_confidence_fields)),
    }


def _build_field_evidence_overview(normalized_fields_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields_payload = normalized_fields_payload.get("fields") or {}
    overview: dict[str, dict[str, Any]] = {}
    for field_name, payload in fields_payload.items():
        if not isinstance(payload, dict):
            continue
        evidence_refs = payload.get("evidence_refs") or []
        source_kinds = sorted(
            {
                str(item.get("source_kind") or "").strip()
                for item in evidence_refs
                if isinstance(item, dict) and str(item.get("source_kind") or "").strip()
            }
        )
        asset_ids = sorted(
            {
                str(item.get("asset_id") or "").strip()
                for item in evidence_refs
                if isinstance(item, dict) and str(item.get("asset_id") or "").strip()
            }
        )
        overview[str(field_name)] = {
            "value": payload.get("value"),
            "confidence": _to_confidence(payload.get("confidence")),
            "evidence_ref_count": len(evidence_refs),
            "source_kinds": source_kinds,
            "asset_ids": asset_ids,
        }
    return overview


def _detect_field_conflicts(text_sources: list[dict[str, str]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for field_name, spec in CONFLICT_SPECS.items():
        patterns = tuple(spec.get("patterns") or ())
        normalizer = str(spec.get("normalizer") or "text")
        severity = str(spec.get("severity") or "medium")
        observations: list[dict[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for source in text_sources:
            for pattern in patterns:
                for match in re.finditer(pattern, source["text"], flags=re.IGNORECASE):
                    raw_value = match.group(1)
                    if normalizer == "dimension":
                        value = _normalize_dimension(raw_value)
                    elif normalizer == "amount":
                        value = _normalize_amount(raw_value)
                    else:
                        value = _normalize_text_value(raw_value)
                    if not value:
                        continue
                    signature = (str(source.get("asset_id") or ""), value)
                    if signature in seen_pairs:
                        continue
                    seen_pairs.add(signature)
                    observations.append(
                        {
                            "value": value,
                            "asset_id": str(source.get("asset_id") or ""),
                            "file_name": str(source.get("file_name") or ""),
                            "source_kind": str(source.get("source_kind") or ""),
                            "text_extract_method": str(source.get("text_extract_method") or ""),
                            "snippet": match.group(0).strip(),
                            "ocr_markdown_path": str(source.get("ocr_markdown_path") or ""),
                        }
                    )
                    break
        detected_values = sorted({item["value"] for item in observations if item["value"]})
        if len(detected_values) <= 1:
            continue
        conflicts.append(
            {
                "field_name": field_name,
                "severity": severity,
                "detected_values": detected_values,
                "evidence_refs": observations,
            }
        )
    return conflicts


def _build_conflict_resolution_suggestions(field_conflicts: list[dict[str, Any]]) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for item in field_conflicts:
        field_name = str(item.get("field_name") or "").strip()
        severity = str(item.get("severity") or "medium").strip()
        evidence_refs = item.get("evidence_refs") or []
        source_kinds = {
            str(ref.get("source_kind") or "").strip()
            for ref in evidence_refs
            if isinstance(ref, dict) and str(ref.get("source_kind") or "").strip()
        }

        if severity == "critical":
            suggestions.append(
                {
                    "field_name": field_name,
                    "priority": "p0",
                    "recommended_action": "manual_review_required",
                    "preferred_source_kind": "native_preview" if "native_preview" in source_kinds else "",
                    "rationale": "关键字段出现冲突，当前不应自动信任任一来源，必须人工复核后再继续。",
                }
            )
            continue

        if field_name in {"length", "depth", "height", "width"} and source_kinds & {"ocr_markdown", "ocr_preview"}:
            suggestions.append(
                {
                    "field_name": field_name,
                    "priority": "p1",
                    "recommended_action": "prefer_ocr_drawing",
                    "preferred_source_kind": "ocr_markdown" if "ocr_markdown" in source_kinds else "ocr_preview",
                    "rationale": "尺寸冲突优先参考图纸/OCR证据，但仍建议人工快速确认后再进入正式报价。",
                }
            )
            continue

        if field_name in {"door_type"} and "native_preview" in source_kinds:
            suggestions.append(
                {
                    "field_name": field_name,
                    "priority": "p2",
                    "recommended_action": "prefer_primary_contract",
                    "preferred_source_kind": "native_preview",
                    "rationale": "文本型门型冲突默认优先参考主合同正文描述。",
                }
            )
            continue

        preferred_source_kind = "native_preview" if "native_preview" in source_kinds else ""
        suggestions.append(
            {
                "field_name": field_name,
                "priority": "p1" if severity == "high" else "p2",
                "recommended_action": "prefer_primary_contract" if preferred_source_kind else "manual_review_required",
                "preferred_source_kind": preferred_source_kind,
                "rationale": "当前冲突建议优先参考主合同正文；若正文不完整，再转人工复核。",
            }
        )

    priority_order = {"p0": 0, "p1": 1, "p2": 2}
    return sorted(
        suggestions,
        key=lambda item: (priority_order.get(str(item.get("priority") or "p9"), 9), str(item.get("field_name") or "")),
    )


def _first_source_with_regex(text_sources: list[dict[str, str]], pattern: str) -> dict[str, str] | None:
    for source in text_sources:
        if re.search(pattern, source["text"], flags=re.IGNORECASE):
            return source
    return text_sources[0] if text_sources else None


def _extract_labeled_amount(
    text_sources: list[dict[str, str]],
    aggregate_text: str,
    patterns: tuple[str, ...],
    *,
    label: str,
    value_normalizer,
) -> dict[str, Any] | None:
    for pattern in patterns:
        match = re.search(pattern, aggregate_text, flags=re.IGNORECASE)
        if not match:
            continue
        source = _first_source_with_regex(text_sources, pattern)
        value = value_normalizer(match.group(1))
        return {
            "label": label,
            "value": value,
            "evidence_text": match.group(0).strip(),
            "asset_id": source.get("asset_id", "") if source else "",
            "file_name": source.get("file_name", "") if source else "",
            "source_kind": source.get("source_kind", "") if source else "",
            "text_extract_method": source.get("text_extract_method", "") if source else "",
            "evidence_refs": [_build_evidence_ref(source, match.group(0))] if source else [],
        }
    return None


def _extract_labeled_text_value(
    text_sources: list[dict[str, str]],
    aggregate_text: str,
    patterns: tuple[str, ...],
    *,
    label: str,
) -> dict[str, Any] | None:
    for pattern in patterns:
        match = re.search(pattern, aggregate_text, flags=re.IGNORECASE)
        if not match:
            continue
        source = _first_source_with_regex(text_sources, pattern)
        return {
            "label": label,
            "value": str(match.group(1) or "").strip(),
            "evidence_text": match.group(0).strip(),
            "asset_id": source.get("asset_id", "") if source else "",
            "file_name": source.get("file_name", "") if source else "",
            "source_kind": source.get("source_kind", "") if source else "",
            "text_extract_method": source.get("text_extract_method", "") if source else "",
            "evidence_refs": [_build_evidence_ref(source, match.group(0))] if source else [],
        }
    return None


def _build_evidence_ref(source: dict[str, str], snippet: str) -> dict[str, str]:
    return {
        "asset_id": str(source.get("asset_id") or ""),
        "file_name": str(source.get("file_name") or ""),
        "source_kind": str(source.get("source_kind") or ""),
        "text_extract_method": str(source.get("text_extract_method") or ""),
        "snippet": str(snippet or "").strip(),
        "ocr_markdown_path": str(source.get("ocr_markdown_path") or ""),
    }


def _read_preferred_asset_text(asset: Any) -> str:
    preview_text = str(asset.text_preview or "").strip()
    metadata = asset.metadata or {}
    markdown_path = str(metadata.get("ocr_markdown_path") or "").strip()
    if markdown_path:
        path = Path(markdown_path)
        if path.exists():
            try:
                markdown_text = path.read_text(encoding="utf-8").strip()
                if markdown_text and preview_text:
                    if markdown_text in preview_text:
                        return preview_text
                    if preview_text in markdown_text:
                        return markdown_text
                    return f"{preview_text}\n\n[OCR Markdown]\n{markdown_text}"
                if markdown_text:
                    return markdown_text
            except OSError:
                pass
    return preview_text


def _infer_source_kind(asset: Any) -> str:
    metadata = asset.metadata or {}
    markdown_path = str(metadata.get("ocr_markdown_path") or "").strip()
    if markdown_path:
        return "ocr_markdown"
    if str(metadata.get("ocr_status") or "").strip() == "succeeded":
        return "ocr_preview"
    return "native_preview"


def _normalize_amount(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _normalize_numeric_amount(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or "").strip())
    if not normalized:
        return ""
    return normalized if normalized.endswith("元") else f"{normalized}元"


def _normalize_dimension(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _normalize_text_value(value: str) -> str:
    return str(value or "").strip()


def _to_confidence(value: Any) -> float:
    try:
        if value is None or value == "":
            return 1.0
        return float(value)
    except (TypeError, ValueError):
        return 1.0
