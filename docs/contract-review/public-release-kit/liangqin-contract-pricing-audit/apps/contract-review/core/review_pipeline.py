from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from attachment_section import extract_attachment_pricing_section
from batch_runtime import write_json, write_markdown
from contract_audit import build_contract_audit_report
from extraction_router import ExtractionConfig, extract_asset
from field_normalizer import normalize_job_fields
from job_models import ReviewJob
from product_code_utils import extract_unique_product_codes
from product_splitter import (
    build_multi_product_split_review,
    extract_product_line_items,
    _scale_quote_payload_for_quantity,
    _retry_generic_cabinet_with_projection_fallback,
    _retry_standard_bed_with_mattress_candidate,
    _retry_with_explicit_catalog_code,
)
import pricing_compare
from pricing_bridge import bridge_contract_to_pricing_precheck


def _build_finding(*, code: str, severity: str, summary: str, detail: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "summary": summary,
        "detail": detail,
    }


def _count_unique_product_codes(job: ReviewJob) -> int:
    codes: set[str] = set()
    for asset in job.primary_contract_assets():
        pricing_text = extract_attachment_pricing_section(str(asset.text_preview or ""))
        codes.update(extract_unique_product_codes(pricing_text))
    return len(codes)


def _extract_single_product_line_item(job: ReviewJob) -> dict[str, Any] | None:
    items = extract_product_line_items(_collect_primary_contract_text(job))
    if len(items) != 1:
        return None
    return items[0]


def _best_match_diff_value(
    *,
    contract_audit_payload: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
    quote_payload: dict[str, Any],
) -> float:
    compare_payload = pricing_compare.build_pricing_comparison(
        contract_audit_payload=contract_audit_payload,
        pricing_bridge_payload=pricing_bridge_payload,
        quote_payload=quote_payload,
    )
    value = compare_payload.get("best_match_diff_value")
    if value in {None, ""}:
        return float("inf")
    return float(value)


def _select_better_single_contract_quote_payload(
    *,
    contract_audit_payload: dict[str, Any],
    pricing_bridge_payload: dict[str, Any],
    current_quote_payload: dict[str, Any],
    candidate_quote_payloads: list[dict[str, Any] | None],
) -> dict[str, Any]:
    best_payload = current_quote_payload
    best_diff = _best_match_diff_value(
        contract_audit_payload=contract_audit_payload,
        pricing_bridge_payload=pricing_bridge_payload,
        quote_payload=current_quote_payload,
    )
    for candidate in candidate_quote_payloads:
        if candidate is None:
            continue
        candidate_diff = _best_match_diff_value(
            contract_audit_payload=contract_audit_payload,
            pricing_bridge_payload=pricing_bridge_payload,
            quote_payload=candidate,
        )
        if candidate_diff < best_diff:
            best_payload = candidate
            best_diff = candidate_diff
    return best_payload


def _derive_review_priority(contract_audit_payload: dict[str, Any]) -> dict[str, Any]:
    priority_scores = {"p0": 0, "p1": 1, "p2": 2}
    suggestions = contract_audit_payload.get("conflict_resolution_suggestions") or []
    for item in suggestions:
        priority = str(item.get("priority") or "").strip()
        if priority not in priority_scores:
            continue
        field_name = str(item.get("field_name") or "").strip()
        action = str(item.get("recommended_action") or "").strip()
        reason = f"{field_name}:{action}" if field_name and action else field_name or action
        return {
            "review_priority": priority,
            "review_priority_score": priority_scores[priority],
            "review_priority_reason": reason,
        }

    return {
        "review_priority": "normal",
        "review_priority_score": 3,
        "review_priority_reason": "",
    }


def _render_review_markdown(review_payload: dict[str, Any], replay_payload: dict[str, Any]) -> str:
    lines = [
        f"# 合同审阅骨架：{review_payload['job_id']}",
        "",
        f"- batch_id: `{review_payload['batch_id']}`",
        f"- group_key: `{review_payload['group_key']}`",
        f"- source_channel: `{review_payload['source_channel']}`",
        f"- status: `{review_payload['status']}`",
        f"- review_priority: `{review_payload['review_priority']}`",
        f"- requested_actions: `{', '.join(review_payload['requested_actions'])}`",
    ]
    if review_payload.get("review_priority_reason"):
        lines.append(f"- review_priority_reason: `{review_payload['review_priority_reason']}`")
    lines.extend(["", "## 资产清单", ""])

    for asset in review_payload["assets"]:
        asset_metadata = asset.get("metadata") or {}
        ocr_status = asset_metadata.get("ocr_status", "")
        lines.append(
            f"- `{asset['file_name']}` / `{asset['media_kind']}` / `{asset['role_hint']}` / "
            f"text_preview={'yes' if asset['text_preview'] else 'no'}"
            + (f" / ocr_status={ocr_status}" if ocr_status else "")
        )
        if asset["text_preview"]:
            lines.append(f"  预览：{asset['text_preview']}")

    lines.extend(["", "## 审阅发现", ""])
    if review_payload["findings"]:
        for finding in review_payload["findings"]:
            lines.append(
                f"- `{finding['severity']}` `{finding['code']}`: {finding['summary']}。{finding['detail']}"
            )
    else:
        lines.append("- 当前未发现 ingest 级阻断项。")

    lines.extend(
        [
            "",
            "## 报价桥接",
            "",
            f"- pricing_bridge_status: `{review_payload['pricing_bridge']['status']}`",
            f"- pricing_bridge_reason: {review_payload['pricing_bridge']['reason']}",
        ]
    )
    if review_payload["pricing_bridge"].get("next_required_field"):
        lines.append(f"- next_required_field: `{review_payload['pricing_bridge']['next_required_field']}`")

    contract_audit = review_payload.get("contract_audit") or {}
    financials = contract_audit.get("financials") or {}
    pricing_alignment = contract_audit.get("pricing_alignment") or {}
    special_notes = contract_audit.get("special_notes") or []
    pricing_compare_payload = review_payload.get("pricing_compare") or {}

    lines.extend(["", "## 合同审核摘要", ""])
    contract_total = financials.get("contract_total")
    if contract_total:
        source_kind = str(contract_total.get("source_kind") or "").strip()
        source_suffix = f" / source={source_kind}" if source_kind else ""
        evidence_count = len(contract_total.get("evidence_refs") or [])
        evidence_suffix = f" / evidence_refs={evidence_count}" if evidence_count else ""
        lines.append(f"- contract_total: `{contract_total['value']}`{source_suffix}{evidence_suffix}")
    list_price_total = financials.get("list_price_total")
    if list_price_total:
        lines.append(f"- list_price_total: `{list_price_total['value']}`")
    discount_rate = financials.get("discount_rate")
    if discount_rate:
        lines.append(f"- discount_rate: `{discount_rate['value']}`")
    discounted_total = financials.get("discounted_total")
    if discounted_total:
        lines.append(f"- discounted_total: `{discounted_total['value']}`")
    add_on_items = financials.get("add_on_items") or []
    if add_on_items:
        for item in add_on_items:
            source_kind = str(item.get("source_kind") or "").strip()
            source_suffix = f" / source={source_kind}" if source_kind else ""
            evidence_count = len(item.get("evidence_refs") or [])
            evidence_suffix = f" / evidence_refs={evidence_count}" if evidence_count else ""
            lines.append(
                f"- add_on: {item['description'] or '未命名增项'} / `{item['amount']}`{source_suffix}{evidence_suffix}"
            )
    if special_notes:
        for item in special_notes:
            source_kind = str(item.get("source_kind") or "").strip()
            source_suffix = f" / source={source_kind}" if source_kind else ""
            evidence_count = len(item.get("evidence_refs") or [])
            evidence_suffix = f" / evidence_refs={evidence_count}" if evidence_count else ""
            lines.append(f"- note: {item['text']}{source_suffix}{evidence_suffix}")
    if pricing_alignment.get("missing_for_pricing"):
        lines.append(
            f"- missing_for_pricing: `{', '.join(pricing_alignment['missing_for_pricing'])}`"
        )
    if pricing_alignment.get("unmapped_high_confidence_fields"):
        lines.append(
            f"- unmapped_high_confidence_fields: `{', '.join(pricing_alignment['unmapped_high_confidence_fields'])}`"
        )
    field_conflicts = contract_audit.get("field_conflicts") or []
    if field_conflicts:
        for item in field_conflicts:
            lines.append(
                f"- field_conflicts: `{item['field_name']}` -> `{', '.join(item['detected_values'])}` / severity={item.get('severity', '')}"
            )
    conflict_resolution_suggestions = contract_audit.get("conflict_resolution_suggestions") or []
    if conflict_resolution_suggestions:
        for item in conflict_resolution_suggestions:
            preferred = str(item.get("preferred_source_kind") or "").strip()
            preferred_suffix = f" / preferred={preferred}" if preferred else ""
            lines.append(
                f"- conflict_resolution: `{item['field_name']}` -> `{item.get('recommended_action', '')}` / priority={item.get('priority', '')}{preferred_suffix}"
            )
    if not any(
        [
            contract_total,
            list_price_total,
            discount_rate,
            discounted_total,
            add_on_items,
            special_notes,
            pricing_alignment.get("missing_for_pricing"),
            pricing_alignment.get("unmapped_high_confidence_fields"),
            field_conflicts,
            conflict_resolution_suggestions,
        ]
    ):
        lines.append("- 当前未抽到额外合同审核摘要。")

    if pricing_compare_payload:
        lines.extend(["", "## 金额对比", ""])
        lines.append(f"- compare_status: `{pricing_compare_payload.get('status', '')}`")
        if pricing_compare_payload.get("pricing_total"):
            lines.append(f"- pricing_total: `{pricing_compare_payload['pricing_total']}`")
        if pricing_compare_payload.get("aggregation_scope"):
            lines.append(f"- aggregation_scope: `{pricing_compare_payload['aggregation_scope']}`")
        if pricing_compare_payload.get("compared_item_count") is not None:
            lines.append(
                f"- compared_item_count: `{pricing_compare_payload.get('compared_item_count', 0)}` / "
                f"excluded_item_count: `{pricing_compare_payload.get('excluded_item_count', 0)}`"
            )
        if pricing_compare_payload.get("best_match_target"):
            lines.append(
                f"- best_match: `{pricing_compare_payload['best_match_target']}` / diff=`{pricing_compare_payload.get('best_match_diff', '')}`"
            )

    product_split_payload = review_payload.get("product_split") or {}
    if product_split_payload.get("item_count"):
        lines.extend(["", "## 多产品拆单", ""])
        lines.append(f"- item_count: `{product_split_payload.get('item_count', 0)}`")
        status_breakdown = product_split_payload.get("status_breakdown") or {}
        if status_breakdown:
            lines.append(f"- status_breakdown: `{status_breakdown}`")
        for item in product_split_payload.get("items") or []:
            lines.append(
                f"- `{item.get('product_name', '')}` / code=`{item.get('product_code', '')}` / "
                f"line_total=`{item.get('line_total', '')}` / split_status=`{item.get('split_status', '')}`"
            )
            detail_resolution = item.get("detail_resolution") or {}
            detail_status = str(detail_resolution.get("status") or "").strip()
            if detail_status:
                lines.append(
                    f"  detail_resolution: {detail_status} / reason={detail_resolution.get('reason', '')} / occurrences={detail_resolution.get('product_code_occurrence_count', '')}"
                )
            compare_payload = item.get("pricing_compare") or {}
            if compare_payload.get("pricing_total"):
                lines.append(f"  pricing_total: {compare_payload['pricing_total']}")
            if compare_payload.get("best_match_target"):
                lines.append(
                    f"  best_match: {compare_payload.get('best_match_target', '')} / diff={compare_payload.get('best_match_diff', '')}"
                )

    lines.extend(
        [
            "",
            "## 回放状态",
            "",
            f"- replay_status: `{replay_payload['status']}`",
            f"- reason: {replay_payload['reason']}",
        ]
    )
    if replay_payload.get("next_steps"):
        lines.append("")
        lines.append("## 下一步")
        lines.append("")
        for item in replay_payload["next_steps"]:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def _apply_extraction_record_to_asset(asset: Any, record: dict[str, Any]) -> None:
    asset.metadata["ocr_status"] = record.get("status", "")
    asset.metadata["ocr_backend"] = record.get("backend", "")
    asset.metadata["ocr_reason"] = record.get("reason", "")
    if record.get("output_dir"):
        asset.metadata["ocr_output_dir"] = record["output_dir"]
    if record.get("markdown_path"):
        asset.metadata["ocr_markdown_path"] = record["markdown_path"]
    if record.get("json_path"):
        asset.metadata["ocr_json_path"] = record["json_path"]
    if record.get("page_count") is not None:
        asset.metadata["ocr_page_count"] = record["page_count"]
    if record.get("ocr_scope"):
        asset.metadata["ocr_scope"] = record["ocr_scope"]
    if record.get("ocr_start_page") is not None:
        asset.metadata["ocr_start_page"] = record["ocr_start_page"]
    if record.get("ocr_source_path"):
        asset.metadata["ocr_source_path"] = record["ocr_source_path"]
    if record.get("install_hint"):
        asset.metadata["ocr_install_hint"] = record["install_hint"]
    if record.get("error"):
        asset.metadata["ocr_error"] = record["error"]

    if record.get("status") == "succeeded" and (record.get("full_text") or record.get("text_preview")):
        extracted_text = str(record.get("full_text") or record.get("text_preview") or "")
        native_text = str(asset.text_preview or "").strip()
        if asset.media_kind == "document" and native_text and extracted_text:
            asset.metadata["native_text_preview"] = native_text
            asset.metadata["native_text_extract_method"] = asset.text_extract_method
            asset.text_preview = _merge_native_and_ocr_text(native_text, extracted_text)
            asset.text_extract_method = "native_plus_ocr"
        else:
            asset.text_preview = extracted_text
            asset.text_extract_method = record.get("text_extract_method", asset.text_extract_method)
        asset.metadata["preview_available"] = True


def _merge_native_and_ocr_text(native_text: str, ocr_text: str) -> str:
    native = str(native_text or "").strip()
    ocr = str(ocr_text or "").strip()
    if not native:
        return ocr
    if not ocr:
        return native
    if ocr in native:
        return native
    if native in ocr:
        return ocr
    return f"{native}\n\n[OCR补充]\n{ocr}"


def _collect_primary_contract_text(job: ReviewJob) -> str:
    return "\n".join(
        str(asset.text_preview or "").strip()
        for asset in job.primary_contract_assets()
        if str(asset.text_preview or "").strip()
    ).strip()


def run_review_job(
    job: ReviewJob,
    *,
    job_dir: Path,
    extraction_config: ExtractionConfig | None = None,
    ocr_extractor: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    extraction_config = extraction_config or ExtractionConfig()
    extraction_records: list[dict[str, Any]] = []
    for asset in job.assets:
        needs_ocr = bool((asset.metadata or {}).get("needs_ocr"))
        if ocr_extractor is None or not needs_ocr:
            record = extract_asset(asset, job_dir=job_dir, config=extraction_config)
        else:
            source_path = Path(str((asset.metadata or {}).get("staged_input_path") or asset.source_path))
            record = ocr_extractor(asset, source_path=source_path, job_dir=job_dir, config=extraction_config)
        extraction_records.append(record)
        _apply_extraction_record_to_asset(asset, record)

    normalized_fields_payload = normalize_job_fields(job)
    pricing_bridge_payload = bridge_contract_to_pricing_precheck(normalized_fields_payload)
    contract_audit_payload = build_contract_audit_report(
        job=job,
        normalized_fields_payload=normalized_fields_payload,
        pricing_bridge_payload=pricing_bridge_payload,
    )
    unique_product_code_count = _count_unique_product_codes(job)
    single_product_line_item = _extract_single_product_line_item(job) if unique_product_code_count == 1 else None
    quote_runtime_root = job_dir / "output" / "quote-runtime"
    product_split_payload = (
        build_multi_product_split_review(job, runtime_root=quote_runtime_root)
        if "replay" in job.requested_actions and unique_product_code_count > 1
        else {"job_id": job.job_id, "item_count": 0, "status_breakdown": {}, "items": []}
    )
    if "replay" in job.requested_actions and unique_product_code_count > 1:
        formal_quote_payload = {
            "status": "skipped",
            "reason": "multi_product_contract",
            "pricing_route": "",
            "pricing_total": "",
            "pricing_total_value": None,
            "prepared_payload": {},
            "raw_result": None,
        }
    elif "replay" in job.requested_actions and pricing_bridge_payload["status"] == "ready_for_formal_quote":
        primary_contract_text = _collect_primary_contract_text(job)
        formal_quote_payload = pricing_compare.execute_formal_quote(
            pricing_bridge_payload.get("precheck_args") or {},
            job_id=job.job_id,
            runtime_root=quote_runtime_root,
        )
        inferred_named_bed_quote_payload = _retry_standard_bed_with_mattress_candidate(
            pricing_bridge_payload=pricing_bridge_payload,
            formal_quote_payload=formal_quote_payload,
            detail_snippet=primary_contract_text,
            line_total=str(
                ((contract_audit_payload.get("financials") or {}).get("contract_total") or {}).get("value")
                or ""
            ),
        )
        if inferred_named_bed_quote_payload is not None:
            formal_quote_payload = inferred_named_bed_quote_payload
        inferred_explicit_code_quote_payload = _retry_with_explicit_catalog_code(
            pricing_bridge_payload=pricing_bridge_payload,
            formal_quote_payload=formal_quote_payload,
            detail_snippet=primary_contract_text,
            line_total=str(
                ((contract_audit_payload.get("financials") or {}).get("contract_total") or {}).get("value")
                or ""
            ),
        )
        if inferred_explicit_code_quote_payload is not None:
            formal_quote_payload = inferred_explicit_code_quote_payload
        financials = contract_audit_payload.get("financials") or {}
        contract_total_text = str((financials.get("contract_total") or {}).get("value") or "").strip()
        list_price_total_text = str((financials.get("list_price_total") or {}).get("value") or "").strip()
        cabinet_fallback_candidates = [
            _retry_generic_cabinet_with_projection_fallback(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=primary_contract_text,
                line_total=contract_total_text,
            )
            if contract_total_text
            else None,
            _retry_generic_cabinet_with_projection_fallback(
                pricing_bridge_payload=pricing_bridge_payload,
                formal_quote_payload=formal_quote_payload,
                detail_snippet=primary_contract_text,
                line_total=list_price_total_text,
            )
            if list_price_total_text and list_price_total_text != contract_total_text
            else None,
        ]
        formal_quote_payload = _select_better_single_contract_quote_payload(
            contract_audit_payload=contract_audit_payload,
            pricing_bridge_payload=pricing_bridge_payload,
            current_quote_payload=formal_quote_payload,
            candidate_quote_payloads=cabinet_fallback_candidates,
        )
        if single_product_line_item is not None:
            formal_quote_payload = _scale_quote_payload_for_quantity(
                formal_quote_payload,
                quantity=str(single_product_line_item.get("quantity") or "").strip(),
            )
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
    if "replay" in job.requested_actions and unique_product_code_count > 1:
        pricing_compare_payload = pricing_compare.build_multi_product_aggregate_comparison(
            contract_audit_payload=contract_audit_payload,
            product_split_payload=product_split_payload,
        )
    else:
        pricing_compare_payload = pricing_compare.build_pricing_comparison(
            contract_audit_payload=contract_audit_payload,
            pricing_bridge_payload=pricing_bridge_payload,
            quote_payload=formal_quote_payload,
        )
    review_priority_payload = _derive_review_priority(contract_audit_payload)

    primary_contracts = job.primary_contract_assets()
    drawing_assets = [asset for asset in job.assets if asset.role_hint == "drawing_attachment"]
    visual_assets = [asset for asset in job.assets if asset.media_kind == "image"]
    ocr_candidate_assets = [asset for asset in job.assets if bool((asset.metadata or {}).get("needs_ocr"))]
    ocr_completed_assets = [asset for asset in ocr_candidate_assets if (asset.metadata or {}).get("ocr_status") == "succeeded"]
    unresolved_ocr_assets = [asset for asset in ocr_candidate_assets if (asset.metadata or {}).get("ocr_status") != "succeeded"]
    unavailable_ocr_assets = [asset for asset in unresolved_ocr_assets if (asset.metadata or {}).get("ocr_status") == "unavailable"]
    failed_ocr_assets = [asset for asset in unresolved_ocr_assets if (asset.metadata or {}).get("ocr_status") == "failed"]
    findings: list[dict[str, str]] = []
    risk_flags: list[str] = []

    if not primary_contracts:
        findings.append(
            _build_finding(
                code="job.missing_primary_contract",
                severity="blocker",
                summary="当前任务没有识别到主合同文件",
                detail="至少需要一个非图纸类的 `.docx` 或 `.pdf` 作为主合同输入。",
            )
        )

    if len(primary_contracts) > 1:
        findings.append(
            _build_finding(
                code="job.multiple_primary_contracts",
                severity="warning",
                summary="当前任务里存在多个主合同候选",
                detail="V1 只完成批次拆单和 ingest 级检查，后续结构化回放前建议人工确认哪一份是主合同。",
            )
        )

    previewless_primary_assets = [
        asset for asset in primary_contracts if asset.extension in {".docx", ".pdf"} and not asset.text_preview
    ]
    if previewless_primary_assets:
        risk_flags.append("ocr_required_for_primary_contract")
        findings.append(
            _build_finding(
                code="job.primary_contract_preview_empty",
                severity="warning",
                summary="主合同文件暂未抽到稳定文字预览",
                detail="这通常意味着 PDF 为扫描件，或当前文档需要后续 OCR / 视觉分支处理。",
            )
        )

    if visual_assets and unresolved_ocr_assets:
        risk_flags.append("visual_assets_present")
        findings.append(
            _build_finding(
                code="job.visual_assets_need_ocr",
                severity="warning",
                summary="当前任务包含图片类附件",
                detail="这类图片里可能包含尺寸、结构备注和图纸说明；当前 V1 不能把它们视为已读内容，后续必须补 OCR 或文档视觉提取。",
            )
        )

    if drawing_assets and unresolved_ocr_assets:
        risk_flags.append("drawing_attachments_present")
        findings.append(
            _build_finding(
                code="job.drawing_attachment_requires_visual_review",
                severity="warning",
                summary="当前任务包含图纸型附件",
                detail="图纸附件通常承载开启方向、节点、尺寸和备注，后续需要进入视觉提取或人工复核，而不能只靠正文文字判断。",
            )
        )

    if drawing_assets and not primary_contracts:
        findings.append(
            _build_finding(
                code="job.image_only_bundle",
                severity="warning",
                summary="当前任务里有图纸附件，但没有对应主合同",
                detail="建议补一份主合同或报价表，再进入规则审核和报价回放。",
            )
        )

    if unavailable_ocr_assets:
        risk_flags.append("paddleocr_backend_unavailable")
        findings.append(
            _build_finding(
                code="job.paddleocr_backend_unavailable",
                severity="warning",
                summary="当前任务需要 OCR，但本地 PaddleOCR 后端不可用",
                detail='请先安装 PaddlePaddle，再执行 `python -m pip install "paddleocr[doc-parser]"`，然后重跑该批次。',
            )
        )

    if failed_ocr_assets:
        risk_flags.append("paddleocr_execution_failed")
        findings.append(
            _build_finding(
                code="job.paddleocr_execution_failed",
                severity="warning",
                summary="PaddleOCR 已接入，但当前文件提取失败",
                detail="请查看 `normalized/ocr/` 下的输出和错误信息，必要时先人工复核该附件。",
            )
        )

    if pricing_bridge_payload["status"] == "manual_confirmation_required":
        risk_flags.append("pricing_bridge_manual_confirmation_required")
        findings.append(
            _build_finding(
                code="job.pricing_bridge_manual_confirmation_required",
                severity="warning",
                summary="合同字段已部分提取，但关键报价字段置信度不足",
                detail="当前只允许高置信字段进入 liangqin-pricing 预检；低置信字段需要人工确认后再继续。",
            )
        )

    for risk_flag in contract_audit_payload.get("risk_flags") or []:
        if risk_flag not in risk_flags:
            risk_flags.append(risk_flag)

    if "replay" in job.requested_actions and primary_contracts and unresolved_ocr_assets:
        replay_payload = {
            "job_id": job.job_id,
            "status": "blocked",
            "reason": "当前任务存在扫描件、图片或图纸附件，核心尺寸和备注很可能主要在视觉层，必须先补 OCR / 文档视觉提取，再进入可靠的报价回放。",
            "next_steps": [
                "先补 OCR / 文档视觉提取，把图片里的尺寸、结构和备注转成可回链的块级证据。",
                "再生成 Markdown 供模型归纳，但不要把 Markdown 当最终证据层。",
                "最后再把结构化字段映射到现有 liangqin-pricing 的 precheck / quote 路径。",
            ],
        }
    elif "replay" in job.requested_actions and unique_product_code_count > 1:
        if str(pricing_compare_payload.get("best_match_target") or "").strip():
            replay_payload = {
                "job_id": job.job_id,
                "status": "completed",
                "reason": "当前合同已按产品行拆单完成报价，并已汇总各品项报价后与合同金额做整单对比。",
                "next_steps": [
                    "优先查看 `output/pricing-compare.json`，确认更接近合同总价、折前合计还是折后合计。",
                    "若整单差异较大，再回看拆单类目、默认尺寸、折扣和备注是否仍有遗漏。",
                ],
            }
        elif str(pricing_compare_payload.get("pricing_total") or "").strip():
            replay_payload = {
                "job_id": job.job_id,
                "status": "blocked",
                "reason": "当前合同已完成多产品报价汇总，但合同总价/折扣字段还未稳定抽取，暂时只能拿到报价系统汇总总价。",
                "next_steps": [
                    "优先补强合同总价、折前合计、折扣后合计的抽取。",
                    "补齐后重跑该合同，即可得到整单金额对比结果。",
                ],
            }
        else:
            replay_payload = {
                "job_id": job.job_id,
                "status": "skipped",
                "reason": "当前合同包含多个产品编码，但还没有形成可用的多产品报价汇总结果。",
                "next_steps": [
                    "优先检查 `output/product-split.json` 里哪些品项还没进入 `compared`。",
                    "先补齐失败品项，再做整单汇总金额对比。",
                ],
            }
    elif (
        "replay" in job.requested_actions
        and pricing_bridge_payload["status"] == "ready_for_formal_quote"
        and formal_quote_payload.get("status") == "completed"
    ):
        replay_payload = {
            "job_id": job.job_id,
            "status": "completed",
            "reason": "当前任务已通过 liangqin-pricing 预检，并已完成一次正式报价回放与金额对比。",
            "next_steps": [
                "优先查看 `output/pricing-compare.json`，确认是匹配合同总价、接近折前价，还是存在明显差异。",
                "若差异明显，再回看合同备注、折扣、门型和附加项是否未进入当前报价入参。",
            ],
        }
    elif "replay" in job.requested_actions and pricing_bridge_payload["status"] == "ready_for_formal_quote":
        replay_payload = {
            "job_id": job.job_id,
            "status": "blocked",
            "reason": "当前任务的高置信字段已经通过 liangqin-pricing 预检，但正式报价回放未成功完成。",
            "next_steps": [
                "检查 `output/formal-quote.json` 里的执行返回与 `reply_text`。",
                "确认当前类目路径是否支持正式报价，以及入参是否仍缺隐含条件。",
            ],
        }
    elif "replay" in job.requested_actions and pricing_bridge_payload["status"] == "needs_input":
        replay_payload = {
            "job_id": job.job_id,
            "status": "blocked",
            "reason": "合同字段已经进入 liangqin-pricing 预检，但当前仍缺少正式报价必需字段。",
            "next_steps": [
                f"优先补充字段：{pricing_bridge_payload['precheck_result'].get('next_required_field') or 'unknown'}。",
                "补齐后再重新运行合同审核批次。",
            ],
        }
    elif "replay" in job.requested_actions and primary_contracts and ocr_completed_assets:
        replay_payload = {
            "job_id": job.job_id,
            "status": "blocked",
            "reason": "当前任务已完成 OCR（PaddleOCR）提取，图片/扫描件已有可读证据，但 V1 还没有把这些结构化证据正式映射到报价回放流程。",
            "next_steps": [
                "基于 `normalized/ocr/` 下的 JSON / Markdown 输出做字段归一化。",
                "把尺寸、材质、五金、金额等字段映射到现有 liangqin-pricing 的 precheck / quote 路径。",
            ],
        }
    elif "replay" in job.requested_actions and primary_contracts:
        replay_payload = {
            "job_id": job.job_id,
            "status": "blocked",
            "reason": "当前 V1 只完成批次拆单、文件分层和 ingest 级审阅，还未进入结构化字段映射与正式报价回放。",
            "next_steps": [
                "先补合同字段提取器，把产品、尺寸、材质、金额抽成结构化对象。",
                "再把结构化对象映射到现有 liangqin-pricing 的 precheck / quote 路径。",
            ],
        }
    elif "replay" in job.requested_actions:
        replay_payload = {
            "job_id": job.job_id,
            "status": "blocked",
            "reason": "没有主合同文件，无法进入回放。",
            "next_steps": ["补充至少一个主合同文件，再重新运行。"],
        }
    else:
        replay_payload = {
            "job_id": job.job_id,
            "status": "skipped",
            "reason": "当前批次未请求 replay。",
            "next_steps": [],
        }

    blocking_findings_count = len([finding for finding in findings if finding["severity"] == "blocker"])
    status = "failed" if blocking_findings_count else "manual_review_required"
    review_payload = {
        "job_id": job.job_id,
        "batch_id": job.batch_id,
        "group_key": job.group_key,
        "source_channel": job.source_channel,
        "requested_actions": list(job.requested_actions),
        "status": status,
        "review_priority": review_priority_payload["review_priority"],
        "review_priority_score": review_priority_payload["review_priority_score"],
        "review_priority_reason": review_priority_payload["review_priority_reason"],
        "assets": [asset.to_dict() for asset in job.assets],
        "findings": findings,
        "summary": {
            "asset_count": len(job.assets),
            "primary_contract_count": len(primary_contracts),
            "drawing_asset_count": len(drawing_assets),
            "visual_asset_count": len(visual_assets),
            "ocr_candidate_asset_count": len(ocr_candidate_assets),
            "ocr_completed_asset_count": len(ocr_completed_assets),
            "ocr_unresolved_asset_count": len(unresolved_ocr_assets),
            "normalized_field_count": normalized_fields_payload["field_count"],
            "blocking_finding_count": blocking_findings_count,
            "risk_flags": risk_flags,
            "product_split_item_count": product_split_payload.get("item_count", 0),
        },
        "metadata": dict(job.metadata),
        "contract_audit": contract_audit_payload,
        "formal_quote": formal_quote_payload,
        "pricing_compare": pricing_compare_payload,
        "product_split": product_split_payload,
        "pricing_bridge": {
            "status": pricing_bridge_payload["status"],
            "reason": pricing_bridge_payload["reason"],
            "next_required_field": (
                str((pricing_bridge_payload.get("precheck_result") or {}).get("next_required_field") or "").strip()
            ),
        },
        "automation_state": (
            "ocr_or_vision_required"
            if unresolved_ocr_assets or (drawing_assets and not ocr_completed_assets)
            else "ocr_evidence_ready"
            if ocr_completed_assets
            else "ingest_scaffold_ready"
        ),
    }

    normalized_assets_payload = {
        "job_id": job.job_id,
        "group_key": job.group_key,
        "primary_contract_assets": [asset.to_dict() for asset in primary_contracts],
        "all_assets": [asset.to_dict() for asset in job.assets],
    }

    write_json(job_dir / "normalized" / "source-assets.json", normalized_assets_payload)
    write_json(job_dir / "normalized" / "normalized-fields.json", normalized_fields_payload)
    write_json(
        job_dir / "normalized" / "extraction-results.json",
        {
            "job_id": job.job_id,
            "ocr_backend": extraction_config.ocr_backend,
            "assets": extraction_records,
        },
    )
    write_json(job_dir / "output" / "pricing-precheck.json", pricing_bridge_payload)
    write_json(job_dir / "output" / "formal-quote.json", formal_quote_payload)
    write_json(job_dir / "output" / "pricing-compare.json", pricing_compare_payload)
    write_json(job_dir / "output" / "product-split.json", product_split_payload)
    write_json(job_dir / "output" / "review.json", review_payload)
    write_json(job_dir / "output" / "replay.json", replay_payload)
    write_markdown(job_dir / "output" / "review.md", _render_review_markdown(review_payload, replay_payload))
    write_json(
        job_dir / "status.json",
        {
            "job_id": job.job_id,
            "status": status,
            "blocking_finding_count": blocking_findings_count,
            "finding_count": len(findings),
            "review_priority": review_priority_payload["review_priority"],
            "review_priority_score": review_priority_payload["review_priority_score"],
            "replay_status": replay_payload["status"],
            "automation_state": review_payload["automation_state"],
            "product_split_item_count": product_split_payload.get("item_count", 0),
        },
    )

    return {
        "job_id": job.job_id,
        "group_key": job.group_key,
        "status": status,
        "finding_count": len(findings),
        "blocking_finding_count": blocking_findings_count,
        "primary_contract_count": len(primary_contracts),
        "review_priority": review_priority_payload["review_priority"],
        "review_priority_score": review_priority_payload["review_priority_score"],
        "review_priority_reason": review_priority_payload["review_priority_reason"],
        "automation_state": review_payload["automation_state"],
        "risk_flags": list(risk_flags),
        "product_split_item_count": int(product_split_payload.get("item_count", 0) or 0),
        "conflict_count": len(contract_audit_payload.get("field_conflicts") or []),
        "conflict_fields": [
            str(item.get("field_name") or "").strip()
            for item in contract_audit_payload.get("field_conflicts") or []
            if str(item.get("field_name") or "").strip()
        ],
        "manual_review_reasons": [
            f"{str(item.get('field_name') or '').strip()}:{str(item.get('recommended_action') or '').strip()}".strip(":")
            for item in contract_audit_payload.get("conflict_resolution_suggestions") or []
            if str(item.get("field_name") or "").strip() or str(item.get("recommended_action") or "").strip()
        ],
        "contract_total": str(((contract_audit_payload.get("financials") or {}).get("contract_total") or {}).get("value") or "").strip(),
        "list_price_total": str(((contract_audit_payload.get("financials") or {}).get("list_price_total") or {}).get("value") or "").strip(),
        "discounted_total": str(((contract_audit_payload.get("financials") or {}).get("discounted_total") or {}).get("value") or "").strip(),
        "discount_rate": str(((contract_audit_payload.get("financials") or {}).get("discount_rate") or {}).get("value") or "").strip(),
        "pricing_total": str(pricing_compare_payload.get("pricing_total") or "").strip(),
        "pricing_compare_status": str(pricing_compare_payload.get("status") or "").strip(),
        "pricing_compare_match_band": str(pricing_compare_payload.get("match_band") or "").strip(),
        "pricing_compare_best_match_target": str(pricing_compare_payload.get("best_match_target") or "").strip(),
        "pricing_compare_best_match_diff": str(pricing_compare_payload.get("best_match_diff") or "").strip(),
        "pricing_route": str(pricing_compare_payload.get("pricing_route") or formal_quote_payload.get("pricing_route") or "").strip(),
        "review_path": str(job_dir / "output" / "review.md"),
        "job_dir": str(job_dir),
    }
