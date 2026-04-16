from __future__ import annotations

import argparse
import importlib
import itertools
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from attachment_section import extract_attachment_pricing_section
from job_models import ReviewJob, SourceAsset
from field_normalizer import normalize_job_fields
from pricing_bridge import bridge_contract_to_pricing_precheck
import pricing_compare
from product_code_utils import extract_unique_product_codes


TABLE_HEADER_PATTERN = re.compile(r"产品名称\s*产品编号\s*材质\s*数量\s*费用合计(?:（元）|\(元\)|元)?")
TABLE_TOTAL_PATTERN = re.compile(r"\s合计\s*\d")
PRODUCT_ROW_PATTERN = re.compile(
    r"(?P<name>[\u4e00-\u9fa5A-Za-z（）()·\-\s]{1,40}?)\s*"
    r"(?P<code>\d[\d\s]{13,17})\s*"
    r"(?P<material>[\u4e00-\u9fa5A-Za-z]+木)\s*"
    r"(?P<qty>\d+)\s*"
    r"(?P<amount>\d+(?:\.\d+)?)"
)
DETAIL_KEYWORDS = ("尺寸", "长：", "宽：", "高：", "注明", "材质", "主卧", "客厅", "儿童房")
DETAIL_SIGNAL_KEYWORDS = ("尺寸", "长：", "宽：", "高：", "注明", "主卧", "客厅", "儿童房")
PAGE_MARKER_PATTERN = re.compile(r"第\d+页")
GENERIC_CATEGORY_TERMS = {
    "床",
    "柜",
    "桌",
    "椅",
    "凳",
    "床头柜",
    "书柜",
    "衣柜",
    "斗柜",
    "玄关柜",
    "电视柜",
    "餐边柜",
    "书桌",
    "其他床",
    "其他柜",
    "其他斗柜",
}
STANDARD_QUOTE_TOKENS = ("标准件", "标准款", "标准品", "标件", "标品", "现货", "现成")
CUSTOM_QUOTE_TOKENS = ("定制", "订制", "定做", "订做", "非标")
EXPLICIT_STANDARD_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,5}-\d{2}(?:-\d+)?)(?![A-Za-z0-9])", re.IGNORECASE)


def build_multi_product_split_review(
    job: ReviewJob,
    *,
    runtime_root: Path,
) -> dict[str, Any]:
    aggregate_text = _collect_primary_contract_text(job)
    catalog_text = _extract_catalog_section(aggregate_text)
    line_items = extract_product_line_items(catalog_text)
    split_items: list[dict[str, Any]] = []
    status_breakdown: dict[str, int] = {}

    for index, line_item in enumerate(line_items, start=1):
        synthetic_text = _build_synthetic_product_text(
            aggregate_text=catalog_text,
            line_item=line_item,
        )
        split_job = _build_split_job(job, line_item=line_item, synthetic_text=synthetic_text, index=index)
        normalized_fields = normalize_job_fields(split_job)
        _force_line_item_fields(
            normalized_fields,
            product_name=line_item["product_name"],
            material=line_item["material"],
            quote_kind=_infer_quote_kind(line_item["detail_snippet"] or catalog_text),
            detail_snippet=line_item["detail_snippet"],
        )
        pricing_bridge_payload = bridge_contract_to_pricing_precheck(normalized_fields)
        quote_runtime_root = runtime_root / "split-items" / line_item["product_code"]
        if pricing_bridge_payload["status"] == "ready_for_formal_quote":
            formal_quote_payload = pricing_compare.execute_formal_quote(
                pricing_bridge_payload.get("precheck_args") or {},
                job_id=f"{job.job_id}-{line_item['product_code']}",
                runtime_root=quote_runtime_root,
            )
            refined_quote_payload = _retry_with_nearest_catalog_variant(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                line_total=line_item["line_total"],
                job_id=f"{job.job_id}-{line_item['product_code']}",
                runtime_root=quote_runtime_root,
            )
            if refined_quote_payload is not None:
                formal_quote_payload = refined_quote_payload
            inferred_stool_quote_payload = _retry_generic_stool_with_catalog_candidate(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
            )
            if inferred_stool_quote_payload is not None:
                formal_quote_payload = inferred_stool_quote_payload
            inferred_cabinet_quote_payload = _retry_generic_cabinet_with_projection_fallback(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
            )
            if inferred_cabinet_quote_payload is not None:
                formal_quote_payload = inferred_cabinet_quote_payload
            inferred_cabinet_unit_quote_payload = _retry_generic_cabinet_with_unit_candidate(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
            )
            if inferred_cabinet_unit_quote_payload is not None:
                formal_quote_payload = inferred_cabinet_unit_quote_payload
            inferred_dining_cabinet_combo_quote_payload = _retry_dining_cabinet_combo_with_unit_candidates(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
            )
            if inferred_dining_cabinet_combo_quote_payload is not None:
                formal_quote_payload = inferred_dining_cabinet_combo_quote_payload
            inferred_desk_quote_payload = _retry_generic_desk_with_catalog_candidate(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
            )
            if inferred_desk_quote_payload is not None:
                formal_quote_payload = inferred_desk_quote_payload
            inferred_explicit_code_quote_payload = _retry_with_explicit_catalog_code(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
            )
            if inferred_explicit_code_quote_payload is not None:
                formal_quote_payload = inferred_explicit_code_quote_payload
        else:
            formal_quote_payload = {
                "status": "skipped",
                "reason": "formal_quote_not_ready",
                "pricing_route": "",
                "pricing_total": "",
                "pricing_total_value": None,
                "prepared_payload": {},
                "raw_result": None,
            }
            inferred_bed_quote_payload = _retry_generic_bed_with_standard_candidate(
                pricing_bridge_payload=pricing_bridge_payload,
                detail_snippet=line_item["detail_snippet"],
                line_total=line_item["line_total"],
                job_id=f"{job.job_id}-{line_item['product_code']}",
                runtime_root=quote_runtime_root,
            )
            if inferred_bed_quote_payload is not None:
                formal_quote_payload = inferred_bed_quote_payload
        inferred_named_bed_quote_payload = _retry_standard_bed_with_mattress_candidate(
            pricing_bridge_payload=pricing_bridge_payload,
            formal_quote_payload=formal_quote_payload,
            detail_snippet=line_item["detail_snippet"],
            line_total=line_item["line_total"],
        )
        if inferred_named_bed_quote_payload is not None:
            formal_quote_payload = inferred_named_bed_quote_payload
        formal_quote_payload = _scale_quote_payload_for_quantity(
            formal_quote_payload,
            quantity=line_item["quantity"],
        )
        pricing_compare_payload = pricing_compare.build_pricing_comparison(
            contract_audit_payload={
                "financials": {
                    "contract_total": {"value": line_item["line_total"]},
                    "list_price_total": {"value": line_item["line_total"]},
                    "discounted_total": {"value": line_item["line_total"]},
                }
            },
            pricing_bridge_payload=pricing_bridge_payload,
            quote_payload=formal_quote_payload,
        )
        split_status = _derive_split_status(
            pricing_compare_status=str(pricing_compare_payload.get("status") or "").strip(),
            pricing_bridge_status=str(pricing_bridge_payload.get("status") or "").strip(),
            formal_quote_status=str(formal_quote_payload.get("status") or "").strip(),
        )
        status_breakdown[split_status] = status_breakdown.get(split_status, 0) + 1
        split_items.append(
            {
                "product_index": index,
                "product_name": line_item["product_name"],
                "product_code": line_item["product_code"],
                "material": line_item["material"],
                "quantity": line_item["quantity"],
                "line_total": line_item["line_total"],
                "detail_snippet": line_item["detail_snippet"],
                "detail_resolution": line_item.get("detail_resolution") or {},
                "normalized_fields": normalized_fields,
                "pricing_precheck": pricing_bridge_payload,
                "formal_quote": formal_quote_payload,
                "pricing_compare": pricing_compare_payload,
                "split_status": split_status,
            }
        )

    return {
        "job_id": job.job_id,
        "item_count": len(split_items),
        "status_breakdown": status_breakdown,
        "items": split_items,
    }


def extract_product_line_items(aggregate_text: str) -> list[dict[str, str]]:
    section_text = _extract_catalog_section(aggregate_text)
    header_match = TABLE_HEADER_PATTERN.search(section_text)
    if not header_match:
        return []

    table_text = section_text[header_match.start() :]
    total_match = TABLE_TOTAL_PATTERN.search(table_text)
    if total_match:
        table_text = table_text[: total_match.start()]

    items: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    for match in PRODUCT_ROW_PATTERN.finditer(table_text):
        raw_name = _normalize_inline_text(match.group("name"))
        product_name = raw_name.replace("产品名称产品编号材质数量费用合计（元）", "").strip()
        product_code = _normalize_product_code(match.group("code"))
        if not product_name or not product_code or product_code in seen_codes:
            continue
        seen_codes.add(product_code)
        detail_snippet = _extract_best_detail_snippet(
            section_text,
            product_code,
            product_name=product_name,
        )
        items.append(
            {
                "product_name": product_name,
                "product_code": product_code,
                "material": _normalize_inline_text(match.group("material")),
                "quantity": _normalize_inline_text(match.group("qty")),
                "line_total": _normalize_amount(match.group("amount")),
                "detail_snippet": detail_snippet,
                "detail_resolution": _build_detail_resolution(section_text, product_code, detail_snippet),
            }
        )
    return items


def _collect_primary_contract_text(job: ReviewJob) -> str:
    return "\n".join(str(asset.text_preview or "").strip() for asset in job.primary_contract_assets() if str(asset.text_preview or "").strip()).strip()


def _normalize_inline_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _normalize_product_code(value: str) -> str:
    codes = extract_unique_product_codes(value)
    if codes:
        return codes[-1]
    return _normalize_inline_text(value)


def _normalize_amount(value: str) -> str:
    normalized = str(value or "").replace(",", "").replace("，", "").strip()
    return f"{normalized}元" if normalized else ""


def _extract_catalog_section(aggregate_text: str) -> str:
    return extract_attachment_pricing_section(aggregate_text)


def _extract_best_detail_snippet(aggregate_text: str, product_code: str, *, product_name: str = "") -> str:
    if not aggregate_text or not product_code:
        return ""
    code_pattern = r"\s*".join(map(re.escape, product_code))
    page_markers = [match.start() for match in PAGE_MARKER_PATTERN.finditer(aggregate_text)]
    best_snippet = ""
    best_score = -1
    for match in re.finditer(code_pattern, aggregate_text):
        start, end = _resolve_page_boundaries(aggregate_text, page_markers, match.start(), match.end())
        candidate_snippets = [
            _extract_local_detail_table_block(aggregate_text, match.start(), match.end()),
            aggregate_text[start:end].strip(),
        ]
        for snippet in candidate_snippets:
            normalized_snippet = str(snippet or "").strip()
            if not normalized_snippet:
                continue
            score = _detail_snippet_score(normalized_snippet, product_name=product_name)
            if score > best_score:
                best_score = score
                best_snippet = normalized_snippet
    if TABLE_HEADER_PATTERN.search(best_snippet) and not any(keyword in best_snippet for keyword in DETAIL_SIGNAL_KEYWORDS):
        return ""
    return best_snippet


def _extract_local_detail_table_block(text: str, start: int, end: int) -> str:
    search_start = max(0, start - 2500)
    search_end = min(len(text), end + 2500)
    window = text[search_start:search_end]
    relative_start = start - search_start
    relative_end = end - search_start

    table_start = window.rfind("<table", 0, relative_start)
    table_end = window.find("</table>", relative_end)
    if table_start == -1 or table_end == -1:
        return ""

    table_end += len("</table>")
    return window[table_start:table_end].strip()


def _detail_snippet_score(snippet: str, *, product_name: str) -> int:
    score = sum(1 for keyword in DETAIL_KEYWORDS if keyword in snippet)
    normalized_snippet = _normalize_inline_text(snippet)
    normalized_name = _normalize_inline_text(product_name)
    if normalized_name and normalized_name in normalized_snippet:
        score += 4

    product_code_hits = len(extract_unique_product_codes(snippet))
    if product_code_hits > 1:
        score -= (product_code_hits - 1) * 3
    if "附件" in snippet and "产品名称" in snippet:
        score -= 2
    return score


def _build_detail_resolution(aggregate_text: str, product_code: str, detail_snippet: str) -> dict[str, Any]:
    occurrences = len(list(re.finditer(r"\s*".join(map(re.escape, product_code)), str(aggregate_text or ""))))
    if detail_snippet:
        return {
            "status": "detail_page_linked",
            "reason": "linked_from_product_code_occurrence",
            "product_code_occurrence_count": occurrences,
        }
    if occurrences <= 1:
        return {
            "status": "missing_detail_in_source_text",
            "reason": "product_code_only_seen_in_catalog_table",
            "product_code_occurrence_count": occurrences,
        }
    return {
        "status": "detail_not_resolved",
        "reason": "product_code_seen_multiple_times_but_no_detail_page_selected",
        "product_code_occurrence_count": occurrences,
    }


def _resolve_page_boundaries(text: str, page_markers: list[int], start: int, end: int) -> tuple[int, int]:
    if not page_markers:
        return max(0, start - 80), min(len(text), end + 260)

    page_start = 0
    page_end = len(text)
    for marker in page_markers:
        if marker <= start:
            page_start = marker
        elif marker > start:
            page_end = marker
            break
    return page_start, page_end


def _build_synthetic_product_text(*, aggregate_text: str, line_item: dict[str, str]) -> str:
    parts = [
        f"产品名称：{line_item['product_name']}",
        f"产品编号：{line_item['product_code']}",
        f"材质：{line_item['material']}",
        f"费用合计：{line_item['line_total']}",
    ]
    quote_kind = _infer_quote_kind(aggregate_text)
    if quote_kind == "custom":
        parts.append("本单按定制执行")
    detail_snippet = str(line_item.get("detail_snippet") or "").strip()
    if detail_snippet:
        parts.append(detail_snippet)
    return "\n".join(parts)


def _build_split_job(job: ReviewJob, *, line_item: dict[str, str], synthetic_text: str, index: int) -> ReviewJob:
    return ReviewJob(
        job_id=f"{job.job_id}-split-{index:02d}",
        batch_id=job.batch_id,
        group_key=f"{job.group_key}::{line_item['product_code']}",
        source_type=job.source_type,
        source_channel=job.source_channel,
        requested_actions=list(job.requested_actions),
        assets=[
            SourceAsset(
                asset_id=f"split-asset-{index:02d}",
                source_path=str(job.primary_contract_assets()[0].source_path if job.primary_contract_assets() else ""),
                relative_path=str(job.primary_contract_assets()[0].relative_path if job.primary_contract_assets() else ""),
                file_name=str(job.primary_contract_assets()[0].file_name if job.primary_contract_assets() else ""),
                extension=str(job.primary_contract_assets()[0].extension if job.primary_contract_assets() else ".pdf"),
                media_kind="document",
                role_hint="primary_contract",
                text_preview=synthetic_text,
                text_extract_method="synthetic_multi_product_split",
                metadata={"split_product_code": line_item["product_code"]},
            )
        ],
        metadata={"split_from_job_id": job.job_id, "split_product_code": line_item["product_code"]},
    )


def _force_line_item_fields(
    normalized_fields: dict[str, Any],
    *,
    product_name: str,
    material: str,
    quote_kind: str,
    detail_snippet: str,
) -> None:
    fields = normalized_fields.setdefault("fields", {})
    current_category = str((fields.get("product_category") or {}).get("value") or "").strip()
    resolved_category = _resolve_split_product_category(
        current_category=current_category,
        product_name=product_name,
        detail_snippet=detail_snippet,
    )
    if resolved_category and _should_override_product_category(current_category, resolved_category):
        fields["product_category"] = {
            "value": resolved_category,
            "confidence": 0.99,
            "evidence_refs": [{"asset_id": "split", "file_name": "split", "text_extract_method": "synthetic_multi_product_split", "snippet": resolved_category}],
        }
    if material:
        fields["wood_material"] = {
            "value": material,
            "confidence": 0.99,
            "evidence_refs": [{"asset_id": "split", "file_name": "split", "text_extract_method": "synthetic_multi_product_split", "snippet": material}],
        }
    if quote_kind and "quote_kind" not in fields:
        fields["quote_kind"] = {
            "value": quote_kind,
            "confidence": 0.95,
            "evidence_refs": [{"asset_id": "split", "file_name": "split", "text_extract_method": "synthetic_multi_product_split", "snippet": quote_kind}],
        }


def _infer_quote_kind(aggregate_text: str) -> str:
    text = str(aggregate_text or "")
    if any(token in text for token in CUSTOM_QUOTE_TOKENS):
        return "custom"
    if any(token in text for token in STANDARD_QUOTE_TOKENS):
        return "standard"
    return ""


def _should_override_product_category(current_value: str, product_name: str) -> bool:
    current = str(current_value or "").strip()
    candidate = str(product_name or "").strip()
    if not candidate:
        return False
    if not current:
        return True
    if current == candidate:
        return False
    if _canonicalize_generic_cabinet_category(current) == candidate:
        return True
    if _is_more_specific_category(current, candidate):
        return False
    if _is_generic_category(current):
        return True
    return len(candidate) > len(current)


def _resolve_split_product_category(*, current_category: str, product_name: str, detail_snippet: str) -> str:
    current = str(current_category or "").strip()
    line_name = str(product_name or "").strip()
    detail = str(detail_snippet or "").strip()

    for candidate in (line_name, current):
        refined = _refine_category_from_detail(candidate, detail)
        if refined:
            return refined
    if line_name and current and line_name != current:
        if line_name in current and len(current) > len(line_name):
            return current
        if current in line_name and len(line_name) > len(current):
            return line_name
    if current and not _is_generic_category(current):
        return _canonicalize_generic_cabinet_category(current)
    return _canonicalize_generic_cabinet_category(line_name)


def _refine_category_from_detail(category: str, detail_snippet: str) -> str:
    normalized_category = str(category or "").strip()
    detail = str(detail_snippet or "")
    if "床头柜" in normalized_category or "床头柜" in detail:
        bedstand_match = re.search(r"经典床头柜\s*([13])", detail)
        if bedstand_match:
            return f"经典床头柜{bedstand_match.group(1)}"

    if normalized_category in {"床", "其他床", "经典床", "架式床", "支腿架式床"} or "床" in normalized_category:
        for candidate in (
            "支腿架式床",
            "悬浮架式床",
            "抛物线架式床",
            "梳背架式床",
            "经典架式床01",
            "经典箱体床",
            "悬浮箱体床",
            "支腿箱体床",
            "华夫格软包架式床",
            "华夫格软包箱体床",
            "公主床",
        ):
            if candidate in detail:
                return candidate

    if "斗柜" not in normalized_category:
        return ""
    if re.search(r"(?:八|8)\s*个?\s*抽屉", detail):
        return "经典八斗柜"
    if re.search(r"(?:六|6)\s*个?\s*抽屉", detail):
        return "经典六斗柜"
    if re.search(r"(?:五|5)\s*个?\s*抽屉", detail):
        return "经典五斗柜"
    return ""


def _is_more_specific_category(current_value: str, product_name: str) -> bool:
    if current_value == product_name:
        return False
    if current_value.startswith(product_name) and len(current_value) > len(product_name):
        return True
    if product_name in current_value and len(current_value) > len(product_name):
        return True
    return False


def _is_generic_category(value: str) -> bool:
    normalized = str(value or "").strip()
    return normalized in GENERIC_CATEGORY_TERMS


def _derive_split_status(*, pricing_compare_status: str, pricing_bridge_status: str, formal_quote_status: str) -> str:
    if pricing_compare_status.startswith(("exact_match", "close_match", "approximate_match", "mismatch")):
        return "compared"
    if formal_quote_status == "failed":
        return "formal_quote_failed"
    if pricing_bridge_status == "ready_for_formal_quote":
        return "quote_ready"
    if pricing_bridge_status == "needs_input":
        return "needs_input"
    return "manual_confirmation_required"


def _scale_quote_payload_for_quantity(
    quote_payload: dict[str, Any],
    *,
    quantity: str,
) -> dict[str, Any]:
    qty_text = str(quantity or "").strip()
    if not qty_text.isdigit():
        return quote_payload
    qty = int(qty_text)
    if qty <= 1:
        return quote_payload
    if str(quote_payload.get("status") or "").strip() != "completed":
        return quote_payload

    total_value = pricing_compare.parse_amount(quote_payload.get("pricing_total"))
    if total_value is None:
        return quote_payload

    scaled_payload = dict(quote_payload)
    scaled_total = total_value * qty
    scaled_payload["pricing_total"] = pricing_compare.format_amount(scaled_total)
    scaled_payload["pricing_total_value"] = float(scaled_total)
    scaled_payload["quantity_multiplier"] = qty

    prepared_payload = dict((quote_payload.get("prepared_payload") or {}))
    prepared_payload["total"] = scaled_payload["pricing_total"]
    prepared_payload["quantity_multiplier"] = qty
    items = []
    for item in prepared_payload.get("items") or []:
        cloned = dict(item)
        subtotal_value = pricing_compare.parse_amount(cloned.get("subtotal"))
        if subtotal_value is not None:
            cloned["subtotal"] = pricing_compare.format_amount(subtotal_value * qty)
        calculation_steps = list(cloned.get("calculation_steps") or [])
        calculation_steps.append(f"数量：{qty}")
        cloned["calculation_steps"] = calculation_steps
        items.append(cloned)
    if items:
        prepared_payload["items"] = items
    scaled_payload["prepared_payload"] = prepared_payload
    return scaled_payload


def _retry_with_nearest_catalog_variant(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    line_total: str,
    job_id: str,
    runtime_root: Path,
) -> dict[str, Any] | None:
    if formal_quote_payload.get("status") != "failed":
        return None
    error_text = str(formal_quote_payload.get("error") or "")
    if "未命中唯一目录记录" not in error_text:
        return None

    precheck_result = pricing_bridge_payload.get("precheck_result") or {}
    pricing_route = str(precheck_result.get("pricing_route") or "")
    if pricing_route not in {"table", "catalog_unit_price"}:
        return None

    refined = _build_nearest_catalog_variant_precheck_args(
        pricing_bridge_payload.get("precheck_args") or {},
        line_total=line_total,
    )
    if refined is None:
        return None

    retry_payload = pricing_compare.execute_formal_quote(
        refined["precheck_args"],
        job_id=f"{job_id}-nearest-catalog-variant",
        runtime_root=runtime_root / "nearest-catalog-variant",
    )
    if retry_payload.get("status") != "completed":
        return None

    retry_payload["fallback_strategy"] = "nearest_catalog_variant"
    retry_payload["fallback_detail"] = refined["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_nearest_catalog_variant"
    return retry_payload


def _retry_generic_bed_with_standard_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
    job_id: str,
    runtime_root: Path,
) -> dict[str, Any] | None:
    if pricing_bridge_payload.get("status") != "needs_input":
        return None

    precheck_result = pricing_bridge_payload.get("precheck_result") or {}
    if str(precheck_result.get("next_required_field") or "").strip() != "quote_kind":
        return None
    if str(precheck_result.get("normalized_category_type") or "").strip() != "bed":
        return None

    inferred = _build_generic_bed_candidate_precheck_args(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    retry_payload = pricing_compare.execute_formal_quote(
        inferred["precheck_args"],
        job_id=f"{job_id}-generic-bed-candidate",
        runtime_root=runtime_root / "generic-bed-candidate",
    )
    if retry_payload.get("status") != "completed":
        return None

    retry_payload["fallback_strategy"] = "generic_bed_standard_candidate"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_generic_bed_standard_candidate"
    return retry_payload


def _retry_standard_bed_with_mattress_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    inferred = _build_standard_bed_mattress_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    current_total = pricing_compare.parse_amount(formal_quote_payload.get("pricing_total"))
    contract_total = pricing_compare.parse_amount(line_total)
    inferred_total = pricing_compare.parse_amount((inferred.get("quote_payload") or {}).get("pricing_total"))
    if contract_total is None or inferred_total is None:
        return None

    inferred_diff = abs(inferred_total - contract_total)
    if current_total is not None:
        current_diff = abs(current_total - contract_total)
        if inferred_diff >= current_diff:
            return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "standard_bed_mattress_candidate"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_standard_bed_mattress_candidate"
    return retry_payload


def _retry_with_explicit_catalog_code(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    inferred = _build_explicit_catalog_code_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    inferred_total = pricing_compare.parse_amount((inferred.get("quote_payload") or {}).get("pricing_total"))
    contract_total = pricing_compare.parse_amount(line_total)
    if inferred_total is None or contract_total is None:
        return None

    current_total = pricing_compare.parse_amount(formal_quote_payload.get("pricing_total"))
    inferred_diff = abs(inferred_total - contract_total)
    if current_total is not None:
        current_diff = abs(current_total - contract_total)
        if inferred_diff >= current_diff:
            return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "explicit_catalog_code"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_explicit_catalog_code"
    return retry_payload


def _build_explicit_catalog_code_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    explicit_codes = _extract_explicit_catalog_codes(detail_snippet)
    if not explicit_codes:
        return None

    material = str(precheck_args.get("material") or "").strip()
    category = str(precheck_args.get("category") or "").strip()
    if not material:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    expected_length = _decimal_from_mm_text(precheck_args.get("length"))
    expected_width = _decimal_from_mm_text(precheck_args.get("width"))

    best: tuple[tuple[float, int, float, int, str], dict[str, Any], dict[str, Any]] | None = None
    for record in _precheck_quote_module().load_queryable_price_records():
        product_code = str(record.get("product_code") or "").strip().upper()
        if product_code not in explicit_codes:
            continue
        if str(record.get("pricing_mode") or "").strip() not in _precheck_quote_module().STANDARD_PRICING_MODES:
            continue

        material_price = (record.get("materials") or {}).get(internal_material)
        if material_price in {None, "", "/"}:
            continue

        base_price = Decimal(str(material_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        price_diff = float(abs(base_price - contract_total)) if contract_total is not None else 0.0
        dimensions = record.get("dimensions") or {}
        record_length = _decimal_from_dimension(dimensions.get("length"))
        record_width = _decimal_from_dimension(dimensions.get("width"))
        compared_dimensions = 0
        dimension_gap = Decimal("0.00")
        if expected_length is not None and record_length is not None:
            compared_dimensions += 1
            dimension_gap += abs(expected_length - record_length)
        if expected_width is not None and record_width is not None:
            compared_dimensions += 1
            dimension_gap += abs(expected_width - record_width)

        code_rank = explicit_codes.index(product_code)
        sort_key = (
            price_diff,
            code_rank,
            float(dimension_gap),
            -compared_dimensions,
            str(record.get("product_code") or "").strip(),
        )
        detail = {
            "candidate_category": category,
            "matched_name": str(record.get("name") or "").strip(),
            "matched_product_code": str(record.get("product_code") or "").strip(),
            "source_row": record.get("source_row"),
            "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            "candidate_quote_total": pricing_compare.format_amount(base_price),
            "candidate_quote_diff": pricing_compare.format_amount(abs(base_price - contract_total)) if contract_total is not None else "",
            "candidate_quote_diff_value": price_diff,
            "base_price": float(base_price),
            "explicit_codes": explicit_codes,
            "record_length": f"{_format_decimal(record_length)}m" if record_length is not None else "",
            "record_width": f"{_format_decimal(record_width)}m" if record_width is not None else "",
            "dimension_gap_m": float(dimension_gap),
            "compared_dimensions": compared_dimensions,
        }
        quote_payload = {
            "status": "completed",
            "handled_by": "contract_review_explicit_catalog_code",
            "pricing_route": "explicit_catalog_code_fallback",
            "pricing_total": pricing_compare.format_amount(base_price),
            "pricing_total_value": float(base_price),
            "reply_text": "",
            "prepared_payload": {
                "items": [
                    {
                        "product": f"{material}{str(record.get('name') or '').strip()}",
                        "confirmed": f"{material}，按合同明确产品编号 {product_code}",
                        "pricing_method": "合同明确目录编号回放",
                        "calculation_steps": [
                            f"合同备注命中目录编号：{product_code}",
                            f"目录基础价：{_format_decimal(base_price)} 元",
                        ],
                        "subtotal": pricing_compare.format_amount(base_price),
                    }
                ],
                "total": pricing_compare.format_amount(base_price),
                "pricing_route": "explicit_catalog_code_fallback",
            },
            "raw_result": {
                "source": "contract_review_explicit_catalog_code",
                "product_code": product_code,
                "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            },
        }
        if best is None or sort_key < best[0]:
            best = (sort_key, detail, quote_payload)

    if best is None:
        return None

    return {
        "detail": best[1],
        "quote_payload": best[2],
    }


def _build_standard_bed_mattress_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    material = str(precheck_args.get("material") or "").strip()
    if not category or not material:
        return None

    mattress_dims = _extract_mattress_dimensions(detail_snippet)
    if mattress_dims is None:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    mattress_length = _decimal_from_mm_text(mattress_dims["length"])
    mattress_width = _decimal_from_mm_text(mattress_dims["width"])
    if mattress_length is None or mattress_width is None:
        return None

    best: tuple[tuple[float, float, int, str], dict[str, Any], dict[str, Any]] | None = None
    for record in _precheck_quote_module().load_queryable_price_records():
        if str(record.get("name") or "").strip() != category:
            continue
        if str(record.get("pricing_mode") or "").strip() not in _precheck_quote_module().STANDARD_PRICING_MODES:
            continue

        dimensions = record.get("dimensions") or {}
        record_length = _decimal_from_dimension(dimensions.get("length"))
        record_width = _decimal_from_dimension(dimensions.get("width"))
        if record_length is None or record_width is None or record_length == 0 or record_width == 0:
            continue

        material_price = (record.get("materials") or {}).get(internal_material)
        if material_price in {None, "", "/"}:
            continue

        base_price = Decimal(str(material_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        scale_ratio = ((mattress_length * mattress_width) / (record_length * record_width)).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        total_value = (base_price * scale_ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        price_diff = float(abs(total_value - contract_total)) if contract_total is not None else 0.0
        dimension_gap = float(abs(record_width - mattress_width) + abs(record_length - mattress_length))
        sort_key = (price_diff, dimension_gap, int(record.get("source_row") or 0), str(record.get("product_code") or "").strip())
        detail = {
            "candidate_category": category,
            "matched_product_code": str(record.get("product_code") or "").strip(),
            "source_row": record.get("source_row"),
            "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            "candidate_quote_total": pricing_compare.format_amount(total_value),
            "candidate_quote_diff": pricing_compare.format_amount(abs(total_value - contract_total)) if contract_total is not None else "",
            "candidate_quote_diff_value": price_diff,
            "base_price": float(base_price),
            "scale_ratio": float(scale_ratio),
            "mattress_length": mattress_dims["length"],
            "mattress_width": mattress_dims["width"],
            "record_length": f"{_format_decimal(record_length)}m",
            "record_width": f"{_format_decimal(record_width)}m",
        }
        quote_payload = {
            "status": "completed",
            "handled_by": "contract_review_mattress_fallback",
            "pricing_route": "bed_mattress_area_fallback",
            "pricing_total": pricing_compare.format_amount(total_value),
            "pricing_total_value": float(total_value),
            "reply_text": "",
            "prepared_payload": {
                "items": [
                    {
                        "product": f"{material}{category}",
                        "confirmed": f"{material}，床垫尺寸{mattress_dims['width']} × {mattress_dims['length']}",
                        "pricing_method": "标准床型按床垫尺寸比例估算",
                        "calculation_steps": [
                            f"目录基础价：{_format_decimal(base_price)} 元",
                            f"参考目录尺寸：{_format_decimal(record_width)}m × {_format_decimal(record_length)}m",
                            f"床垫尺寸：{mattress_dims['width']} × {mattress_dims['length']}",
                            f"面积比例：{_format_decimal(scale_ratio)}",
                            f"基础价格：{_format_decimal(base_price)} × {_format_decimal(scale_ratio)} = {_format_decimal(total_value)} 元",
                        ],
                        "subtotal": pricing_compare.format_amount(total_value),
                    }
                ],
                "total": pricing_compare.format_amount(total_value),
                "pricing_route": "bed_mattress_area_fallback",
            },
            "raw_result": {
                "source": "contract_review_mattress_fallback",
                "product_code": str(record.get("product_code") or "").strip(),
                "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            },
        }
        if best is None or sort_key < best[0]:
            best = (sort_key, detail, quote_payload)

    if best is None:
        return None

    return {
        "detail": best[1],
        "quote_payload": best[2],
    }


def _extract_explicit_catalog_codes(detail_snippet: str) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for match in EXPLICIT_STANDARD_CODE_PATTERN.finditer(str(detail_snippet or "")):
        code = str(match.group(1) or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _retry_generic_stool_with_catalog_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    if formal_quote_payload.get("status") != "failed":
        return None
    if str(formal_quote_payload.get("reason") or "").strip() != "formal_quote_total_missing":
        return None
    if str(formal_quote_payload.get("pricing_route") or "").strip() != "generic":
        return None

    inferred = _build_generic_stool_candidate_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "generic_stool_standard_candidate"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_generic_stool_standard_candidate"
    return retry_payload


def _retry_generic_cabinet_with_projection_fallback(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    route = str(formal_quote_payload.get("pricing_route") or "").strip()
    status = str(formal_quote_payload.get("status") or "").strip()
    if status not in {"failed", "completed"}:
        return None
    if status == "failed" and str(formal_quote_payload.get("reason") or "").strip() != "formal_quote_total_missing":
        return None
    if route not in {"generic", "cabinet", "cabinet_projection_area"}:
        return None

    inferred = _build_generic_cabinet_projection_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    if status == "completed":
        current_total = pricing_compare.parse_amount(formal_quote_payload.get("pricing_total"))
        fallback_total = pricing_compare.parse_amount((inferred.get("quote_payload") or {}).get("pricing_total"))
        contract_total = pricing_compare.parse_amount(line_total)
        if current_total is not None and fallback_total is not None and contract_total is not None:
            current_diff = abs(current_total - contract_total)
            fallback_diff = abs(fallback_total - contract_total)
            if fallback_diff >= current_diff:
                return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "generic_cabinet_projection_profile"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_generic_cabinet_projection_profile"
    return retry_payload


def _retry_generic_cabinet_with_unit_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    route = str(formal_quote_payload.get("pricing_route") or "").strip()
    status = str(formal_quote_payload.get("status") or "").strip()
    if status not in {"failed", "completed"}:
        return None
    if status == "failed" and str(formal_quote_payload.get("reason") or "").strip() != "formal_quote_total_missing":
        return None
    if route and route not in {"generic", "cabinet", "cabinet_projection_area", "cabinet_projection_area_fallback"}:
        return None

    inferred = _build_generic_cabinet_unit_candidate_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    current_total = pricing_compare.parse_amount(formal_quote_payload.get("pricing_total"))
    candidate_total = pricing_compare.parse_amount((inferred.get("quote_payload") or {}).get("pricing_total"))
    contract_total = pricing_compare.parse_amount(line_total)
    if candidate_total is None or contract_total is None:
        return None
    if current_total is not None:
        current_diff = abs(current_total - contract_total)
        candidate_diff = abs(candidate_total - contract_total)
        if candidate_diff >= current_diff:
            return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "generic_cabinet_unit_candidate"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_generic_cabinet_unit_candidate"
    return retry_payload


def _canonicalize_generic_cabinet_category(value: str) -> str:
    category = str(value or "").strip()
    if not category.startswith("其他"):
        return category

    for keyword in ("玄关柜", "书柜", "餐边柜", "衣柜", "电视柜", "酒柜", "组合柜"):
        if keyword in category:
            return keyword
    return category


def _retry_generic_desk_with_catalog_candidate(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    if formal_quote_payload.get("status") != "failed":
        return None
    if str(formal_quote_payload.get("reason") or "").strip() != "formal_quote_total_missing":
        return None
    if str(formal_quote_payload.get("pricing_route") or "").strip() != "generic":
        return None

    inferred = _build_generic_desk_candidate_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "generic_desk_catalog_candidate"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_generic_desk_catalog_candidate"
    return retry_payload


def _retry_dining_cabinet_combo_with_unit_candidates(
    *,
    pricing_bridge_payload: dict[str, Any],
    formal_quote_payload: dict[str, Any],
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    route = str(formal_quote_payload.get("pricing_route") or "").strip()
    status = str(formal_quote_payload.get("status") or "").strip()
    if status not in {"completed", "failed"}:
        return None
    if status == "failed" and str(formal_quote_payload.get("reason") or "").strip() != "formal_quote_total_missing":
        return None
    if route and route not in {"generic", "cabinet", "cabinet_projection_area", "cabinet_projection_area_fallback"}:
        return None

    inferred = _build_dining_cabinet_combo_quote_payload(
        pricing_bridge_payload.get("precheck_args") or {},
        detail_snippet=detail_snippet,
        line_total=line_total,
    )
    if inferred is None:
        return None

    current_total = pricing_compare.parse_amount(formal_quote_payload.get("pricing_total"))
    combo_total = pricing_compare.parse_amount((inferred.get("quote_payload") or {}).get("pricing_total"))
    contract_total = pricing_compare.parse_amount(line_total)
    if combo_total is None or contract_total is None:
        return None
    if current_total is not None:
        current_diff = abs(current_total - contract_total)
        combo_diff = abs(combo_total - contract_total)
        if combo_diff >= current_diff:
            return None

    retry_payload = inferred["quote_payload"]
    retry_payload["fallback_strategy"] = "dining_cabinet_unit_price_combo"
    retry_payload["fallback_detail"] = inferred["detail"]
    retry_payload["reason"] = "formal_quote_completed_via_dining_cabinet_unit_price_combo"
    return retry_payload


def _build_nearest_catalog_variant_precheck_args(
    precheck_args: dict[str, Any],
    *,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    if not category:
        return None

    handle_quote_message = _handle_quote_message_module()
    precheck_quote = _precheck_quote_module()
    material_names = _material_names_module()

    normalized = dict(handle_quote_message.PRECHECK_DEFAULTS)
    normalized.update(precheck_args)
    args = argparse.Namespace(**normalized)
    matched_product = precheck_quote.infer_explicit_product_match(args)
    if not matched_product:
        return None

    internal_material = material_names.normalize_material_for_query(str(precheck_args.get("material") or ""))
    contract_line_total = pricing_compare.parse_amount(line_total)
    candidates: list[tuple[tuple[float, float, int, int], dict[str, Any], dict[str, Any]]] = []

    for record in precheck_quote.load_queryable_price_records():
        if record.get("sheet") != matched_product.get("sheet"):
            continue
        if record.get("product_code") != matched_product.get("product_code"):
            continue
        if record.get("name") != matched_product.get("name"):
            continue
        if str(record.get("pricing_mode") or "").strip() not in precheck_quote.STANDARD_PRICING_MODES:
            continue

        score_detail = _score_catalog_variant_candidate(
            args=args,
            record=record,
            internal_material=internal_material,
            contract_line_total=contract_line_total,
            precheck_quote=precheck_quote,
        )
        if score_detail is None:
            continue
        sort_key = (
            score_detail["dimension_distance_m"],
            score_detail["price_diff"],
            -score_detail["compared_dimensions"],
            int(record.get("source_row") or 0),
        )
        candidates.append((sort_key, record, score_detail))

    if not candidates:
        return None

    _, record, score_detail = min(candidates, key=lambda item: item[0])
    if score_detail["dimension_distance_m"] > 0.2:
        return None

    refined_args = dict(precheck_args)
    for field_name in ("length", "depth", "height", "width"):
        record_value = (record.get("dimensions") or {}).get(field_name)
        if record_value is None:
            refined_args.pop(field_name, None)
            continue
        refined_args[field_name] = _format_catalog_dimension_mm(record_value)

    return {
        "precheck_args": refined_args,
        "detail": {
            "matched_name": str(record.get("name") or "").strip(),
            "matched_product_code": str(record.get("product_code") or "").strip(),
            "source_row": record.get("source_row"),
            "matched_dimensions": {
                field_name: refined_args[field_name]
                for field_name in ("length", "depth", "height", "width")
                if field_name in refined_args
            },
            "dimension_distance_m": score_detail["dimension_distance_m"],
            "compared_dimensions": score_detail["compared_dimensions"],
            "price_diff": score_detail["price_diff"],
            "material_price": score_detail["material_price"],
        },
    }


def _build_generic_bed_candidate_precheck_args(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    if category not in {"床", "其他床", "经典床"}:
        return None

    material = str(precheck_args.get("material") or "").strip()
    if not material:
        return None

    mattress_dims = _extract_mattress_dimensions(detail_snippet)
    if mattress_dims is None:
        return None

    candidates = _candidate_bed_categories_for_generic_bed(detail_snippet)
    if not candidates:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    best: tuple[tuple[float, float, str], dict[str, Any], dict[str, Any], dict[str, Any]] | None = None

    for candidate in candidates:
        candidate_args = {
            "category": candidate,
            "material": material,
            "length": mattress_dims["length"],
            "width": mattress_dims["width"],
            "quote_kind": "standard",
        }
        quote_payload = pricing_compare.execute_formal_quote(
            candidate_args,
            job_id=f"probe-{candidate}",
            runtime_root=Path("/tmp") / "contract-review-bed-candidates" / _slugify(candidate),
        )
        if quote_payload.get("status") != "completed":
            continue

        pricing_total = pricing_compare.parse_amount(quote_payload.get("pricing_total"))
        if pricing_total is None or contract_total is None:
            continue

        price_diff = float(abs(pricing_total - contract_total))
        heuristic_penalty = float(_bed_candidate_penalty(candidate, detail_snippet))
        sort_key = (price_diff, heuristic_penalty, candidate)
        detail = {
            "mattress_length": mattress_dims["length"],
            "mattress_width": mattress_dims["width"],
            "candidate_category": candidate,
            "candidate_quote_total": quote_payload.get("pricing_total"),
            "candidate_quote_diff": pricing_compare.format_amount(abs(pricing_total - contract_total)),
            "candidate_quote_diff_value": price_diff,
            "heuristic_penalty": heuristic_penalty,
        }
        if best is None or sort_key < best[0]:
            best = (sort_key, candidate_args, detail, quote_payload)

    if best is None:
        return None

    best_price_diff = best[0][0]
    if best_price_diff > 1000:
        return None

    return {
        "precheck_args": best[1],
        "detail": best[2],
    }


def _build_generic_stool_candidate_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    if "凳" not in category:
        return None

    material = str(precheck_args.get("material") or "").strip()
    if not material:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    if contract_total is None:
        return None

    best: tuple[tuple[float, int, str, int], dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    for record in _precheck_quote_module().load_queryable_price_records():
        if str(record.get("sheet") or "").strip() != "凳":
            continue

        estimate = _estimate_stool_candidate_quote(
            record=record,
            internal_material=internal_material,
        )
        if estimate is None:
            continue
        estimate = _select_best_stool_estimate_for_contract(
            record=record,
            estimate=estimate,
            source_category=category,
            contract_total=contract_total,
        )

        price_diff = abs(float(estimate["pricing_total_value"]) - float(contract_total))
        heuristic_penalty = _stool_candidate_penalty(
            candidate_name=str(record.get("name") or "").strip(),
            source_category=category,
            detail_snippet=detail_snippet,
        )
        sort_key = (
            price_diff,
            heuristic_penalty,
            str(record.get("name") or "").strip(),
            int(record.get("source_row") or 0),
        )
        detail = {
            "candidate_category": str(record.get("name") or "").strip(),
            "matched_product_code": str(record.get("product_code") or "").strip(),
            "source_row": record.get("source_row"),
            "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            "candidate_quote_total": estimate["pricing_total"],
            "candidate_quote_diff": pricing_compare.format_amount(Decimal(str(price_diff)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "candidate_quote_diff_value": round(price_diff, 2),
            "unit_price": estimate["unit_price"],
            "dimensions": estimate["dimensions"],
            "projection_area": estimate.get("projection_area"),
            "heuristic_penalty": heuristic_penalty,
        }
        if best is None or sort_key < best[0]:
            best = (sort_key, record, detail, estimate["quote_payload"])

    if best is None:
        return None

    best_price_diff = best[0][0]
    if best_price_diff > 1000:
        return None

    return {
        "quote_payload": best[3],
        "detail": best[2],
    }


def _build_generic_cabinet_projection_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    profile_key = _generic_cabinet_profile_key(category)
    if not profile_key:
        return None

    material = str(precheck_args.get("material") or "").strip()
    if not material:
        return None

    length = _decimal_from_mm_text(precheck_args.get("length"))
    height = _decimal_from_mm_text(precheck_args.get("height"))
    if length is None or height is None:
        return None

    precheck_quote = _precheck_quote_module()
    profile = dict(precheck_quote.DEFAULT_CABINET_PROFILES.get(profile_key) or {})
    if not profile:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    detail_text = str(detail_snippet or "")
    area = (length * height).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    preferred_sheet = str(profile.get("sheet") or "").strip()
    require_door_glass_signal = any(token in detail_text for token in ("门", "玻璃"))
    matched_record = None
    unit_price = None

    if require_door_glass_signal:
        candidates: list[tuple[tuple[float, int, str], dict[str, Any], Decimal]] = []
        for record in precheck_quote.load_queryable_price_records():
            if str(record.get("sheet") or "").strip() != preferred_sheet:
                continue
            if str(record.get("pricing_mode") or "").strip() != "projection_area":
                continue
            material_price = (record.get("materials") or {}).get(internal_material)
            if material_price in {None, "", "/"}:
                continue
            name = str(record.get("name") or "").strip()
            if not any(token in name for token in ("门", "玻璃")):
                continue
            candidate_unit_price = Decimal(str(material_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_value = (area * candidate_unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            price_diff = float(abs(total_value - contract_total)) if contract_total is not None else 0.0
            semantic_penalty = _cabinet_projection_candidate_penalty(
                candidate_name=name,
                detail_snippet=detail_text,
            )
            candidates.append(((price_diff, semantic_penalty, name), record, candidate_unit_price))

        if candidates:
            _, matched_record, unit_price = min(candidates, key=lambda item: item[0])

    if matched_record is None:
        for record in precheck_quote.load_queryable_price_records():
            if str(record.get("sheet") or "").strip() != str(profile.get("sheet") or "").strip():
                continue
            if str(record.get("product_code") or "").strip() != str(profile.get("product_code") or "").strip():
                continue
            if str(record.get("name") or "").strip() != str(profile.get("name") or "").strip():
                continue
            if str(record.get("pricing_mode") or "").strip() != "projection_area":
                continue
            material_price = (record.get("materials") or {}).get(internal_material)
            if material_price in {None, "", "/"}:
                return None
            matched_record = record
            unit_price = Decimal(str(material_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            break

    if matched_record is None or unit_price is None:
        return None
    subtotal = (area * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_value = subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    pricing_total = pricing_compare.format_amount(total_value)
    diff_value = abs(float(total_value) - float(contract_total)) if contract_total is not None else None
    assumed_depth = profile.get("assumed_depth")
    contract_depth = _decimal_from_mm_text(precheck_args.get("depth") or precheck_args.get("width"))
    note_parts = []
    if "门" in str(detail_snippet or ""):
        note_parts.append("detail_mentions_doors")
    if "玻璃" in str(detail_snippet or ""):
        note_parts.append("detail_mentions_glass")
    if "抽屉" in str(detail_snippet or ""):
        note_parts.append("detail_mentions_drawers")

    quote_payload = {
        "status": "completed",
        "handled_by": "contract_review_projection_fallback",
        "pricing_route": "cabinet_projection_area_fallback",
        "pricing_total": pricing_total,
        "pricing_total_value": float(total_value),
        "reply_text": "",
        "prepared_payload": {
            "items": [
                {
                    "product": str(matched_record.get("name") or profile.get("display_name") or profile.get("name") or profile_key).strip(),
                    "confirmed": str(matched_record.get("product_code") or profile.get("product_code") or "").strip(),
                    "pricing_method": "默认柜体投影面积估算",
                    "calculation_steps": [
                        f"投影面积：{_format_decimal(length)} × {_format_decimal(height)} = {_format_decimal(area)}㎡",
                        f"目录单价：{_format_decimal(unit_price)} 元/㎡",
                        f"基础价格：{_format_decimal(area)} × {_format_decimal(unit_price)} = {_format_decimal(subtotal)} 元",
                    ],
                    "subtotal": pricing_total,
                }
            ],
            "total": pricing_total,
            "pricing_route": "cabinet_projection_area_fallback",
        },
        "raw_result": {
            "source": "contract_review_projection_fallback",
            "profile_key": profile_key,
            "product_code": str(matched_record.get("product_code") or profile.get("product_code") or "").strip(),
            "pricing_mode": "projection_area",
        },
    }
    return {
        "quote_payload": quote_payload,
        "detail": {
            "profile_key": profile_key,
            "candidate_category": str(matched_record.get("name") or profile.get("display_name") or profile.get("name") or profile_key).strip(),
            "matched_product_code": str(matched_record.get("product_code") or profile.get("product_code") or "").strip(),
            "sheet": str(matched_record.get("sheet") or profile.get("sheet") or "").strip(),
            "candidate_quote_total": pricing_total,
            "candidate_quote_diff": pricing_compare.format_amount(Decimal(str(diff_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if diff_value is not None else "",
            "candidate_quote_diff_value": round(diff_value, 2) if diff_value is not None else None,
            "unit_price": float(unit_price),
            "projection_area": f"{_format_decimal(area)}㎡",
            "dimensions": {
                "length": f"{int((length * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))}mm",
                "height": f"{int((height * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))}mm",
            },
            "assumed_depth": _format_catalog_dimension_mm(assumed_depth) if assumed_depth is not None else "",
            "contract_depth": f"{int((contract_depth * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))}mm" if contract_depth is not None else "",
            "detail_signals": note_parts,
        },
    }


def _build_generic_cabinet_unit_candidate_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    profile_key = _generic_cabinet_profile_key(category)
    if profile_key != "电视柜":
        return None

    material = str(precheck_args.get("material") or "").strip()
    if not material:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    if contract_total is None:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    compare_length = _decimal_from_mm_text(precheck_args.get("length"))
    compare_depth = _decimal_from_mm_text(precheck_args.get("depth") or precheck_args.get("width"))
    compare_height = _decimal_from_mm_text(precheck_args.get("height"))

    best: tuple[tuple[float, float, int, int, str], dict[str, Any], dict[str, Any]] | None = None
    for record in _precheck_quote_module().load_queryable_price_records():
        if str(record.get("sheet") or "").strip() != profile_key:
            continue
        if str(record.get("pricing_mode") or "").strip() != "unit_price":
            continue

        material_price = (record.get("materials") or {}).get(internal_material)
        if material_price in {None, "", "/"}:
            continue

        dimensions = record.get("dimensions") or {}
        record_length = _decimal_from_dimension(dimensions.get("length"))
        record_depth = _decimal_from_dimension(dimensions.get("depth") or dimensions.get("width"))
        record_height = _decimal_from_dimension(dimensions.get("height"))

        compared_dimensions = 0
        dimension_gap = Decimal("0")
        for expected, actual in (
            (compare_length, record_length),
            (compare_depth, record_depth),
            (compare_height, record_height),
        ):
            if expected is None or actual is None:
                continue
            compared_dimensions += 1
            dimension_gap += abs(expected - actual)

        if compared_dimensions == 0:
            continue
        if compare_length is not None and record_length is not None and abs(compare_length - record_length) > Decimal("1.00"):
            continue

        total_value = Decimal(str(material_price)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        price_diff = abs(float(total_value) - float(contract_total))
        weighted_score = price_diff + float(dimension_gap) * 1000
        pricing_total = pricing_compare.format_amount(total_value)
        detail = {
            "profile_key": profile_key,
            "candidate_category": str(record.get("name") or "").strip(),
            "matched_product_code": str(record.get("product_code") or "").strip(),
            "sheet": str(record.get("sheet") or "").strip(),
            "source_row": record.get("source_row"),
            "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            "candidate_quote_total": pricing_total,
            "candidate_quote_diff": pricing_compare.format_amount(abs(total_value - contract_total)),
            "candidate_quote_diff_value": price_diff,
            "unit_price": float(total_value),
            "dimensions": {
                key: value
                for key, value in {
                    "length": _format_catalog_dimension_mm(record_length) if record_length is not None else "",
                    "depth": _format_catalog_dimension_mm(record_depth) if record_depth is not None else "",
                    "height": _format_catalog_dimension_mm(record_height) if record_height is not None else "",
                }.items()
                if value
            },
            "dimension_gap_m": float(dimension_gap),
            "compared_dimensions": compared_dimensions,
            "detail_signals": [
                signal
                for signal in (
                    "detail_mentions_drawers" if "抽屉" in str(detail_snippet or "") else "",
                    "detail_mentions_floating_base" if "悬浮" in str(detail_snippet or "") else "",
                )
                if signal
            ],
        }
        quote_payload = {
            "status": "completed",
            "handled_by": "contract_review_catalog_fallback",
            "pricing_route": "catalog_cabinet_unit_candidate",
            "pricing_total": pricing_total,
            "pricing_total_value": float(total_value),
            "reply_text": "",
            "prepared_payload": {
                "items": [
                    {
                        "product": str(record.get("name") or "").strip(),
                        "confirmed": str(record.get("product_code") or "").strip(),
                        "pricing_method": "目录柜类候选估算",
                        "calculation_steps": [
                            f"目录标准价：{pricing_total}",
                            f"目录尺寸：{', '.join(f'{key}={value}' for key, value in detail['dimensions'].items())}",
                        ],
                        "subtotal": pricing_total,
                    }
                ],
                "total": pricing_total,
                "pricing_route": "catalog_cabinet_unit_candidate",
            },
            "raw_result": {
                "source": "contract_review_catalog_fallback",
                "sheet": profile_key,
                "product_code": str(record.get("product_code") or "").strip(),
                "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            },
        }
        sort_key = (
            weighted_score,
            price_diff,
            -compared_dimensions,
            int(record.get("source_row") or 0),
            str(record.get("product_code") or "").strip(),
        )
        if best is None or sort_key < best[0]:
            best = (sort_key, detail, quote_payload)

    if best is None:
        return None
    if best[1]["candidate_quote_diff_value"] > 3000:
        return None

    return {
        "quote_payload": best[2],
        "detail": best[1],
    }


def _cabinet_projection_candidate_penalty(*, candidate_name: str, detail_snippet: str) -> int:
    candidate = str(candidate_name or "").strip()
    detail = str(detail_snippet or "")
    penalty = 0

    if "玻璃" in detail:
        penalty -= 10 if "玻璃" in candidate else 8
    if "门" in detail:
        penalty -= 6 if "门" in candidate else 6
    if "开放" in candidate and any(token in detail for token in ("门", "玻璃")):
        penalty += 12
    for token in ("卡座", "书梯", "转角", "像素", "糖果", "Light"):
        if token in candidate and token not in detail:
            penalty += 10
    return penalty


def _build_generic_desk_candidate_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    if "书桌" not in category and "桌" not in category:
        return None

    material = str(precheck_args.get("material") or "").strip()
    if not material:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    if contract_total is None:
        return None

    compare_length = _decimal_from_mm_text(precheck_args.get("length"))
    compare_depth = _decimal_from_mm_text(precheck_args.get("depth") or precheck_args.get("width"))
    compare_height = _decimal_from_mm_text(precheck_args.get("height"))
    composite_layout = _looks_like_composite_desk_layout(detail_snippet)

    best: tuple[tuple[float, float, float, str], dict[str, Any], dict[str, Any]] | None = None
    for record in _precheck_quote_module().load_queryable_price_records():
        if str(record.get("sheet") or "").strip() != "书桌":
            continue
        if str(record.get("pricing_mode") or "").strip() not in {"unit_price", "per_item", "mixed"}:
            continue
        if _is_partial_desk_combo_component(record):
            continue

        material_price = (record.get("materials") or {}).get(internal_material)
        if material_price in {None, "", "/"}:
            continue

        total_value = Decimal(str(material_price)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        price_diff = abs(float(total_value) - float(contract_total))
        semantic_penalty = float(
            _desk_candidate_penalty(
                candidate_name=str(record.get("name") or "").strip(),
                remark=str(record.get("remark") or "").strip(),
                detail_snippet=detail_snippet,
            )
        )
        dimension_penalty = float(
            _desk_candidate_dimension_penalty(
                record=record,
                compare_length=compare_length,
                compare_depth=compare_depth,
                compare_height=compare_height,
                composite_layout=composite_layout,
            )
        )
        weighted_score = price_diff + semantic_penalty * 100 + dimension_penalty * 1000
        sort_key = (
            weighted_score,
            price_diff,
            semantic_penalty,
            str(record.get("name") or "").strip(),
        )
        pricing_total = pricing_compare.format_amount(total_value)
        detail = {
            "candidate_category": str(record.get("name") or "").strip(),
            "matched_product_code": str(record.get("product_code") or "").strip(),
            "source_row": record.get("source_row"),
            "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            "candidate_quote_total": pricing_total,
            "candidate_quote_diff": pricing_compare.format_amount(abs(total_value - contract_total)),
            "candidate_quote_diff_value": price_diff,
            "unit_price": float(total_value),
            "dimensions": {
                key: value
                for key, value in {
                    "length": _format_catalog_dimension_mm((record.get("dimensions") or {}).get("length")) if (record.get("dimensions") or {}).get("length") is not None else "",
                    "depth": _format_catalog_dimension_mm((record.get("dimensions") or {}).get("depth")) if (record.get("dimensions") or {}).get("depth") is not None else "",
                    "height": _format_catalog_dimension_mm((record.get("dimensions") or {}).get("height")) if (record.get("dimensions") or {}).get("height") is not None and isinstance((record.get("dimensions") or {}).get("height"), (int, float)) else "",
                }.items()
                if value
            },
            "remark": str(record.get("remark") or "").strip(),
            "semantic_penalty": semantic_penalty,
            "dimension_penalty": dimension_penalty,
            "composite_layout_detected": composite_layout,
        }
        quote_payload = {
            "status": "completed",
            "handled_by": "contract_review_catalog_fallback",
            "pricing_route": "catalog_desk_candidate",
            "pricing_total": pricing_total,
            "pricing_total_value": float(total_value),
            "reply_text": "",
            "prepared_payload": {
                "items": [
                    {
                        "product": str(record.get("name") or "").strip(),
                        "confirmed": str(record.get("product_code") or "").strip(),
                        "pricing_method": "目录书桌候选估算",
                        "calculation_steps": [f"目录标准价：{pricing_total}"],
                        "subtotal": pricing_total,
                    }
                ],
                "total": pricing_total,
                "pricing_route": "catalog_desk_candidate",
            },
            "raw_result": {
                "source": "contract_review_catalog_fallback",
                "sheet": "书桌",
                "product_code": str(record.get("product_code") or "").strip(),
                "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            },
        }
        if best is None or sort_key < best[0]:
            best = (sort_key, detail, quote_payload)

    if best is None:
        return None

    if best[1]["candidate_quote_diff_value"] > 5000:
        return None

    return {
        "quote_payload": best[2],
        "detail": best[1],
    }


def _build_dining_cabinet_combo_quote_payload(
    precheck_args: dict[str, Any],
    *,
    detail_snippet: str,
    line_total: str,
) -> dict[str, Any] | None:
    category = str(precheck_args.get("category") or "").strip()
    if "餐边柜" not in category:
        return None

    quote_kind = str(precheck_args.get("quote_kind") or "").strip()
    if quote_kind not in {"custom", "standard"}:
        return None

    material = str(precheck_args.get("material") or "").strip()
    if not material:
        return None

    target_length = _decimal_from_mm_text(precheck_args.get("length"))
    if target_length is None or target_length < Decimal("3.0"):
        return None

    contract_total = pricing_compare.parse_amount(line_total)
    if contract_total is None:
        return None

    material_names = _material_names_module()
    internal_material = material_names.normalize_material_for_query(material)
    if not internal_material:
        return None

    max_length_gap = Decimal("1.2") if "组合" in category or any(token in detail_snippet for token in ("高柜", "矮柜", "储物柜")) else Decimal("0.8")
    candidate_records: list[dict[str, Any]] = []
    for record in _precheck_quote_module().load_queryable_price_records():
        if str(record.get("sheet") or "").strip() != "餐边柜":
            continue
        if str(record.get("pricing_mode") or "").strip() != "unit_price":
            continue
        name = str(record.get("name") or "").strip()
        if "岛台" in name:
            continue
        material_price = (record.get("materials") or {}).get(internal_material)
        if material_price in {None, "", "/"}:
            continue
        record_length = _decimal_from_dimension((record.get("dimensions") or {}).get("length"))
        if record_length is None or record_length <= 0:
            continue
        candidate_records.append(
            {
                "record": record,
                "name": name,
                "product_code": str(record.get("product_code") or "").strip(),
                "length": record_length,
                "price": Decimal(str(material_price)).quantize(Decimal("1"), rounding=ROUND_HALF_UP),
            }
        )

    if not candidate_records:
        return None

    best: tuple[tuple[float, float, int, str], list[dict[str, Any]], Decimal, Decimal] | None = None
    for size in range(2, 6):
        for combo in itertools.combinations_with_replacement(candidate_records, size):
            combo_length = sum((item["length"] for item in combo), Decimal("0"))
            length_gap = abs(combo_length - target_length)
            if length_gap > max_length_gap:
                continue

            combo_total = sum((item["price"] for item in combo), Decimal("0"))
            price_diff = abs(combo_total - contract_total)
            combo_penalty = _dining_cabinet_combo_penalty(combo=combo, source_category=category, detail_snippet=detail_snippet)
            sort_key = (
                float(price_diff),
                float(length_gap),
                combo_penalty,
                "|".join(item["product_code"] for item in combo),
            )
            if best is None or sort_key < best[0]:
                best = (sort_key, list(combo), combo_total, combo_length)

    if best is None:
        return None

    _, combo, combo_total, combo_length = best
    pricing_total = pricing_compare.format_amount(combo_total)
    items = []
    combo_codes = []
    combo_names = []
    for item in combo:
        combo_codes.append(item["product_code"])
        combo_names.append(item["name"])
        items.append(
            {
                "product": item["name"],
                "confirmed": item["product_code"],
                "pricing_method": "目录餐边柜组合估算",
                "calculation_steps": [
                    f"目录长度：{_format_decimal(item['length'])}m",
                    f"目录单价：{_format_decimal(item['price'])} 元",
                ],
                "subtotal": pricing_compare.format_amount(item["price"]),
            }
        )

    quote_payload = {
        "status": "completed",
        "handled_by": "contract_review_catalog_fallback",
        "pricing_route": "dining_cabinet_unit_price_combo",
        "pricing_total": pricing_total,
        "pricing_total_value": float(combo_total),
        "reply_text": "",
        "prepared_payload": {
            "items": items,
            "total": pricing_total,
            "pricing_route": "dining_cabinet_unit_price_combo",
        },
        "raw_result": {
            "source": "contract_review_catalog_fallback",
            "sheet": "餐边柜",
            "product_codes": combo_codes,
            "pricing_mode": "unit_price_combo",
        },
    }
    return {
        "quote_payload": quote_payload,
        "detail": {
            "candidate_category": " + ".join(combo_names),
            "matched_product_code": " + ".join(combo_codes),
            "combo_records": [
                {
                    "product_code": item["product_code"],
                    "name": item["name"],
                    "length": _format_catalog_dimension_mm(item["length"]),
                    "unit_price": float(item["price"]),
                }
                for item in combo
            ],
            "candidate_quote_total": pricing_total,
            "candidate_quote_diff": pricing_compare.format_amount(abs(combo_total - contract_total)),
            "candidate_quote_diff_value": float(abs(combo_total - contract_total)),
            "combo_total_length": _format_catalog_dimension_mm(combo_length),
            "target_length": _format_catalog_dimension_mm(target_length),
            "length_gap": _format_catalog_dimension_mm(abs(combo_length - target_length)),
            "combo_count": len(combo),
        },
    }


def _dining_cabinet_combo_penalty(
    *,
    combo: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    source_category: str,
    detail_snippet: str,
) -> int:
    detail = str(detail_snippet or "")
    category = str(source_category or "")
    penalty = 0
    combo_names = [str(item.get("name") or "").strip() for item in combo]

    if "组合" in category:
        penalty -= sum(6 for name in combo_names if "组合餐边柜" in name)
    if any(token in detail for token in ("高柜", "矮柜", "储物柜")):
        penalty -= sum(2 for name in combo_names if "组合餐边柜" in name)
    for name in combo_names:
        if "藤编" in name and "藤编" not in detail:
            penalty += 8
        if "五斗" in name and "五斗" not in detail:
            penalty += 6
        if "新现代" in name and "现代" not in detail:
            penalty += 4
    return penalty


def _score_catalog_variant_candidate(
    *,
    args: argparse.Namespace,
    record: dict[str, Any],
    internal_material: str | None,
    contract_line_total: Any,
    precheck_quote: Any,
) -> dict[str, Any] | None:
    compared_dimensions = 0
    dimension_distance_m = 0.0
    for field_name in ("length", "depth", "height", "width"):
        input_value = precheck_quote.parse_dimension_to_meters(getattr(args, field_name, None))
        record_value = precheck_quote.parse_dimension_to_meters((record.get("dimensions") or {}).get(field_name))
        if input_value is None or record_value is None:
            continue
        compared_dimensions += 1
        dimension_distance_m += abs(record_value - input_value)

    if compared_dimensions == 0:
        return None

    material_price = None
    if internal_material:
        material_price = (record.get("materials") or {}).get(internal_material)
    if contract_line_total is not None and material_price is not None:
        price_diff = float(abs(pricing_compare.parse_amount(f"{material_price}元") - contract_line_total))
    else:
        price_diff = float("inf")

    return {
        "dimension_distance_m": round(dimension_distance_m, 6),
        "compared_dimensions": compared_dimensions,
        "price_diff": price_diff,
        "material_price": material_price,
    }


def _extract_mattress_dimensions(detail_snippet: str) -> dict[str, str] | None:
    detail = str(detail_snippet or "")
    match = re.search(r"(?:床垫尺寸|适配床垫)(?:为|:|：)?\s*(\d{3,4})\s*[*xX×]\s*(\d{3,4})", detail)
    if match:
        first = int(match.group(1))
        second = int(match.group(2))
    else:
        meter_match = re.search(
            r"(?:床垫尺寸|适配床垫)(?:为|:|：)?\s*(\d(?:\.\d)?)\s*(?:米|m)?\s*[*xX×]\s*(\d(?:\.\d)?)\s*(?:米|m)?",
            detail,
        )
        if not meter_match:
            return None
        first = int((Decimal(meter_match.group(1)) * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        second = int((Decimal(meter_match.group(2)) * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    length_mm = max(first, second)
    width_mm = min(first, second)
    return {
        "length": f"{length_mm}mm",
        "width": f"{width_mm}mm",
    }


def _estimate_stool_candidate_quote(
    *,
    record: dict[str, Any],
    internal_material: str,
) -> dict[str, Any] | None:
    pricing_mode = str(record.get("pricing_mode") or "").strip()
    material_price = (record.get("materials") or {}).get(internal_material)
    if material_price in {None, "", "/"}:
        return None

    unit_price = Decimal(str(material_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    dimensions = record.get("dimensions") or {}
    projection_area_text = ""
    if pricing_mode == "projection_area":
        length = _decimal_from_dimension(dimensions.get("length"))
        depth = _decimal_from_dimension(dimensions.get("depth") or dimensions.get("width"))
        if length is None or depth is None:
            return None
        projection_area = (length * depth).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal = (projection_area * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_value = subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        projection_area_text = f"{projection_area.normalize():f}㎡"
        calculation_steps = [
            f"凳面投影面积：{_format_decimal(length)} × {_format_decimal(depth)} = {projection_area.normalize():f}㎡",
            f"目录单价：{_format_decimal(unit_price)} 元/㎡",
            f"基础价格：{projection_area.normalize():f} × {_format_decimal(unit_price)} = {_format_decimal(subtotal)} 元",
        ]
        pricing_method = "目录凳面投影面积估算"
    else:
        total_value = unit_price.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        calculation_steps = [f"目录单价：{_format_decimal(unit_price)} 元"]
        pricing_method = "目录单价估算"

    pricing_total = pricing_compare.format_amount(total_value)
    payload = {
        "status": "completed",
        "handled_by": "contract_review_catalog_fallback",
        "pricing_route": "catalog_stool_candidate",
        "pricing_total": pricing_total,
        "pricing_total_value": float(total_value),
        "reply_text": "",
        "prepared_payload": {
            "items": [
                {
                    "product": str(record.get("name") or "").strip(),
                    "confirmed": str(record.get("product_code") or "").strip(),
                    "pricing_method": pricing_method,
                    "calculation_steps": calculation_steps,
                    "subtotal": pricing_total,
                }
            ],
            "total": pricing_total,
            "pricing_route": "catalog_stool_candidate",
        },
        "raw_result": {
            "source": "contract_review_catalog_fallback",
            "sheet": str(record.get("sheet") or "").strip(),
            "product_code": str(record.get("product_code") or "").strip(),
            "pricing_mode": pricing_mode,
        },
    }
    return {
        "quote_payload": payload,
        "pricing_total": pricing_total,
        "pricing_total_value": total_value,
        "unit_price": float(unit_price),
        "dimensions": {
            key: value
            for key, value in {
                "length": _format_catalog_dimension_mm(dimensions.get("length")) if dimensions.get("length") is not None else "",
                "depth": _format_catalog_dimension_mm(dimensions.get("depth")) if dimensions.get("depth") is not None else "",
                "height": _format_catalog_dimension_mm(dimensions.get("height")) if dimensions.get("height") is not None else "",
                "width": _format_catalog_dimension_mm(dimensions.get("width")) if dimensions.get("width") is not None else "",
            }.items()
            if value
        },
        "projection_area": projection_area_text,
    }


def _select_best_stool_estimate_for_contract(
    *,
    record: dict[str, Any],
    estimate: dict[str, Any],
    source_category: str,
    contract_total: Decimal,
) -> dict[str, Any]:
    candidate_name = str(record.get("name") or "").strip()
    if candidate_name != str(source_category or "").strip():
        return estimate
    if str(record.get("pricing_mode") or "").strip() != "projection_area":
        return estimate

    current_total = Decimal(str(estimate["pricing_total_value"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    unit_price_total = Decimal(str(estimate["unit_price"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if abs(unit_price_total - contract_total) >= abs(current_total - contract_total):
        return estimate

    unit_price_total_text = pricing_compare.format_amount(unit_price_total)
    quote_payload = dict(estimate["quote_payload"])
    quote_payload["pricing_total"] = unit_price_total_text
    quote_payload["pricing_total_value"] = float(unit_price_total)
    prepared_payload = dict((quote_payload.get("prepared_payload") or {}))
    items = []
    for item in prepared_payload.get("items") or []:
        cloned = dict(item)
        calculation_steps = list(cloned.get("calculation_steps") or [])
        calculation_steps.append("同名凳类候选按目录单价直取")
        cloned["calculation_steps"] = calculation_steps
        cloned["subtotal"] = unit_price_total_text
        items.append(cloned)
    if items:
        prepared_payload["items"] = items
    prepared_payload["total"] = unit_price_total_text
    quote_payload["prepared_payload"] = prepared_payload

    refined = dict(estimate)
    refined["quote_payload"] = quote_payload
    refined["pricing_total"] = unit_price_total_text
    refined["pricing_total_value"] = unit_price_total
    refined["projection_area"] = ""
    refined["estimate_mode"] = "exact_name_unit_price"
    return refined


def _decimal_from_dimension(value: Any) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _decimal_from_mm_text(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return None
    lowered = text.lower()
    try:
        if lowered.endswith("mm"):
            return (Decimal(lowered[:-2]) / Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if lowered.endswith("cm"):
            return (Decimal(lowered[:-2]) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if lowered.endswith("m"):
            return Decimal(lowered[:-1]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Decimal(lowered).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _format_decimal(value: Decimal) -> str:
    return f"{value.normalize():f}".rstrip("0").rstrip(".") if value != value.to_integral() else str(int(value))


def _generic_cabinet_profile_key(category: str) -> str:
    normalized = str(category or "").strip()
    if "玄关柜" in normalized:
        return "玄关柜"
    if "书柜" in normalized:
        return "书柜"
    if "餐边柜" in normalized:
        return "餐边柜"
    if "电视柜" in normalized:
        return "电视柜"
    if "衣柜" in normalized:
        return "衣柜"
    return ""


def _looks_like_composite_desk_layout(detail_snippet: str) -> bool:
    detail = str(detail_snippet or "")
    return any(token in detail for token in ("独立部件", "矮柜", "转角高桌", "书桌柜", "转角"))


def _is_partial_desk_combo_component(record: dict[str, Any]) -> bool:
    remark = str(record.get("remark") or "").strip()
    return remark in {"书桌价格", "吊柜开放单价", "吊柜带门单价"}


def _desk_candidate_penalty(*, candidate_name: str, remark: str, detail_snippet: str) -> int:
    candidate = str(candidate_name or "").strip()
    detail = str(detail_snippet or "")
    penalty = 0

    composite_layout = _looks_like_composite_desk_layout(detail_snippet)
    if composite_layout:
        if "书桌柜" in candidate:
            penalty += 0
        elif "书桌与吊柜" in candidate:
            penalty += 2
    elif any(token in detail for token in ("转角", "矮柜", "独立部件", "柜")):
        if "书桌柜" in candidate:
            penalty -= 8
        elif "书桌与吊柜" in candidate:
            penalty -= 2
        else:
            penalty += 18
    if "转角" in detail and "转角" in candidate:
        penalty -= 4
    if "抽屉" in detail or "薄抽屉" in detail:
        if "屉" in candidate or "抽" in remark:
            penalty -= 2
    if "儿童房" in detail and "儿童" in candidate:
        penalty -= 1
    if "升降" in candidate and "升降" not in detail:
        penalty += 8
    if "挂墙" in candidate and "挂墙" not in detail:
        penalty += 8

    return penalty


def _desk_candidate_dimension_penalty(
    *,
    record: dict[str, Any],
    compare_length: Decimal | None,
    compare_depth: Decimal | None,
    compare_height: Decimal | None,
    composite_layout: bool,
) -> float:
    if composite_layout:
        return 0.0

    dimensions = record.get("dimensions") or {}
    total = Decimal("0")
    compared = 0
    for expected, key in (
        (compare_length, "length"),
        (compare_depth, "depth"),
        (compare_height, "height"),
    ):
        if expected is None:
            continue
        actual = _decimal_from_dimension(dimensions.get(key))
        if actual is None:
            continue
        total += abs(actual - expected)
        compared += 1
    if compared == 0:
        return 0.0
    return float(total)


def _candidate_bed_categories_for_generic_bed(detail_snippet: str) -> list[str]:
    detail = str(detail_snippet or "")
    load_records = _precheck_quote_module().load_queryable_price_records()
    names: list[str] = []
    seen: set[str] = set()
    for record in load_records:
        if str(record.get("sheet") or "").strip() != "床榻":
            continue
        if str(record.get("pricing_mode") or "").strip() not in _precheck_quote_module().STANDARD_PRICING_MODES:
            continue
        name = str(record.get("name") or "").strip()
        if not name or name in seen:
            continue
        if not _is_generic_bed_candidate_name(name, detail):
            continue
        seen.add(name)
        names.append(name)

    scored = sorted(names, key=lambda name: (_bed_candidate_penalty(name, detail), name))
    return scored[:8]


def _bed_candidate_penalty(candidate: str, detail_snippet: str) -> int:
    candidate_name = str(candidate or "").strip()
    detail = str(detail_snippet or "")
    penalty = 0

    if "排骨架" in detail or "内嵌" in detail:
        if "箱体床" in candidate_name:
            penalty -= 20
        elif "架式床" in candidate_name:
            penalty += 20

    if any(token in detail for token in ("软包", "华夫格")):
        if "软包" in candidate_name or "华夫格" in candidate_name:
            penalty -= 12
    else:
        if "软包" in candidate_name or "华夫格" in candidate_name:
            penalty += 8

    if "悬浮" in candidate_name and "悬浮" not in detail:
        penalty += 8
    if "支腿" in candidate_name and "支腿" not in detail:
        penalty += 8
    if candidate_name.startswith("经典"):
        penalty -= 2

    return penalty


def _stool_candidate_penalty(*, candidate_name: str, source_category: str, detail_snippet: str) -> int:
    candidate = str(candidate_name or "").strip()
    source = str(source_category or "").strip()
    detail = str(detail_snippet or "")
    text = f"{source} {detail}"
    penalty = 0

    if candidate == source:
        penalty -= 40
    elif source and source in candidate:
        penalty -= 20

    if "条凳" in candidate and "条凳" not in text:
        penalty += 25
    if "条凳" not in candidate and "条凳" in text:
        penalty += 12
    if "圆" in candidate and "圆" not in text:
        penalty += 10
    if "方" in candidate and "方" not in text:
        penalty += 4
    if "美人" in candidate and "美人" not in text:
        penalty += 6
    if "小板凳" in text and candidate == "方凳":
        penalty -= 8
    if "小板凳" in text and candidate == "圆凳凳":
        penalty -= 4

    return penalty


def _is_generic_bed_candidate_name(name: str, detail_snippet: str) -> bool:
    candidate_name = str(name or "").strip()
    detail = str(detail_snippet or "")
    if not candidate_name:
        return False

    if any(token in candidate_name for token in ("美式床", "藤编床", "欧包", "抛物线")):
        return False

    if any(token in candidate_name for token in ("箱体床", "架式床")):
        return True

    if any(token in detail for token in ("软包", "华夫格")) and ("软包" in candidate_name or "华夫格" in candidate_name):
        return True

    return False


def _format_catalog_dimension_mm(value: Any) -> str:
    numeric = float(value)
    millimeters = int(round(numeric * 1000))
    return f"{millimeters}mm"


def _slugify(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5]+", "-", str(value or "").strip()).strip("-") or "candidate"


def _pricing_scripts_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "skill" / "liangqin-pricing" / "scripts"


def _precheck_quote_module():
    scripts_dir = _pricing_scripts_dir()
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("precheck_quote")


def _handle_quote_message_module():
    scripts_dir = _pricing_scripts_dir()
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("handle_quote_message")


def _material_names_module():
    scripts_dir = _pricing_scripts_dir()
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("material_names")
