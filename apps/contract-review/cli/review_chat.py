#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
ADAPTERS_ROOT = APP_ROOT / "adapters"
for root in (CORE_ROOT, ADAPTERS_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from batch_runtime import (  # noqa: E402
    DEFAULT_RUNTIME_ROOT,
    job_output_dir,
    materialize_job,
    read_json,
    write_batch_summary,
    write_json,
)
from extraction_router import ExtractionConfig  # noqa: E402
from job_models import BatchPlan, ReviewJob, SourceAsset  # noqa: E402
from manual_batch import build_review_jobs  # noqa: E402
import pricing_compare  # noqa: E402
from reviewer_card import render_reviewer_card_markdown  # noqa: E402
from review_pipeline import run_review_job  # noqa: E402
from template_learning import apply_review_feedback  # noqa: E402


HANDLED_BY = "contract_review_chat"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chat shell for contract review.")
    parser.add_argument("--text", required=True, help="User message or command.")
    parser.add_argument("--batch-dir", help="Optional batch directory to review.")
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT), help="Runtime root for review outputs.")
    parser.add_argument("--state-root", help="Directory used to persist chat session state.")
    parser.add_argument("--output-mode", choices=["text", "json"], default="text")
    parser.add_argument("--ocr-backend", choices=["disabled", "paddleocr", "mineru"], default="paddleocr")
    parser.add_argument("--paddleocr-lang", default="ch")
    parser.add_argument("--paddleocr-device", default="cpu")
    parser.add_argument("--force-ocr-for-documents", action="store_true")
    return parser.parse_args(argv)


def _state_path(state_root: Path) -> Path:
    return state_root / "contract-review-chat-state.json"


def _load_state(state_root: Path) -> dict[str, Any]:
    path = _state_path(state_root)
    if not path.exists():
        return {"queue_job_ids": [], "cursor": -1, "last_job_id": "", "last_batch_id": ""}
    return read_json(path)


def _save_state(state_root: Path, payload: dict[str, Any]) -> None:
    write_json(_state_path(state_root), payload)


def _run_batch_review(
    *,
    batch_dir: Path,
    runtime_root: Path,
    extraction_config: ExtractionConfig,
) -> dict[str, Any]:
    batch_plan = build_review_jobs(batch_dir)
    batch_results = []
    for job in batch_plan.jobs:
        job_dir = materialize_job(job, runtime_root=runtime_root)
        batch_results.append(run_review_job(job, job_dir=job_dir, extraction_config=extraction_config))
    return write_batch_summary(batch_plan, batch_results=batch_results, runtime_root=runtime_root)


def _load_review(runtime_root: Path, job_id: str) -> dict[str, Any]:
    return read_json(job_output_dir(job_id, runtime_root=runtime_root) / "output" / "review.json")


def _load_batch_dashboard(runtime_root: Path, batch_id: str) -> dict[str, Any]:
    if not batch_id:
        return {}
    return read_json(runtime_root / "batches" / batch_id / "batch-dashboard.json")


def _load_batch_summary(runtime_root: Path, batch_id: str) -> dict[str, Any]:
    if not batch_id:
        return {}
    return read_json(runtime_root / "batches" / batch_id / "batch-summary.json")


def _load_review_job(runtime_root: Path, job_id: str) -> ReviewJob:
    payload = read_json(job_output_dir(job_id, runtime_root=runtime_root) / "job.json")
    assets = [
        SourceAsset(
            asset_id=str(item.get("asset_id") or "").strip(),
            source_path=str(item.get("source_path") or "").strip(),
            relative_path=str(item.get("relative_path") or "").strip(),
            file_name=str(item.get("file_name") or "").strip(),
            extension=str(item.get("extension") or "").strip(),
            media_kind=str(item.get("media_kind") or "").strip(),
            role_hint=str(item.get("role_hint") or "").strip(),
            text_preview=str(item.get("text_preview") or ""),
            text_extract_method=str(item.get("text_extract_method") or "").strip(),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in list(payload.get("assets") or [])
        if isinstance(item, dict)
    ]
    return ReviewJob(
        job_id=str(payload.get("job_id") or job_id).strip(),
        batch_id=str(payload.get("batch_id") or "").strip(),
        group_key=str(payload.get("group_key") or "").strip(),
        source_type=str(payload.get("source_type") or "").strip(),
        source_channel=str(payload.get("source_channel") or "").strip(),
        requested_actions=[str(item).strip() for item in list(payload.get("requested_actions") or []) if str(item).strip()],
        assets=assets,
        metadata=dict(payload.get("metadata") or {}),
        created_at=str(payload.get("created_at") or "").strip(),
    )


def _label_verdict(verdict: str) -> str:
    mapping = {
        "recommended_release": "建议放行",
        "pass_with_watch": "可放行但建议留意",
        "manual_review_required": "建议人工核对",
    }
    return mapping.get(verdict, verdict or "待判断")


def _format_product_display(item: dict[str, Any]) -> str:
    product_name = str(item.get("product_name") or "未命名品项").strip() or "未命名品项"
    product_code = str(item.get("product_code") or "").strip()
    return f"{product_name}（{product_code}）" if product_code else product_name


def _describe_pricing_route(item: dict[str, Any]) -> str:
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()
    fallback_detail = item.get("fallback_detail") or {}
    profile_key = str(fallback_detail.get("profile_key") or "").strip()
    if fallback_strategy == "generic_cabinet_projection_profile":
        profile_label = profile_key or "柜体"
        return f"通用{profile_label}投影面积估算"
    if fallback_strategy == "generic_cabinet_unit_candidate":
        return "目录柜类候选估算"
    if fallback_strategy == "dining_cabinet_unit_price_combo":
        return "餐边柜组合估算"
    if fallback_strategy == "generic_tatami_projection_profile":
        return "榻榻米投影面积估算"
    if fallback_strategy == "modular_child_bed_dimension_probe":
        return "儿童床轻量试算"
    if fallback_strategy == "explicit_catalog_code":
        return "目录编码回放"
    if fallback_strategy == "standard_bed_mattress_candidate":
        return "床垫尺寸回放"

    pricing_route = str(item.get("pricing_route") or "").strip()
    route_labels = {
        "bed_standard": "标准报价",
        "cabinet_projection_area_fallback": "柜体投影面积估算",
        "catalog_cabinet_unit_candidate": "目录柜类候选估算",
        "multi_product_aggregate": "多产品汇总",
        "tatami_projection_area_fallback": "榻榻米投影面积估算",
    }
    return route_labels.get(pricing_route, pricing_route)


def _describe_line_risk(item: dict[str, Any]) -> str:
    fallback_strategy = str(item.get("fallback_strategy") or "").strip()
    fallback_detail = item.get("fallback_detail") or {}
    if fallback_strategy == "generic_cabinet_projection_profile":
        diff_text = str(fallback_detail.get("candidate_quote_diff") or "").strip()
        if diff_text:
            return f"当前是粗估结果，自动候选仍差 {diff_text}"
        return "当前是粗估结果，建议人工确认柜型"
    return ""


def _build_multi_product_sections(pricing_compare_payload: dict[str, Any]) -> list[str]:
    if str(pricing_compare_payload.get("aggregation_scope") or "").strip() != "multi_product_split_sum":
        return []

    lines: list[str] = []
    included_items = [item for item in list(pricing_compare_payload.get("included_items") or []) if isinstance(item, dict)]
    if included_items:
        lines.append("单项对比：")
        for index, item in enumerate(included_items, start=1):
            line_total = str(item.get("line_total") or "").strip() or "未识别"
            pricing_total = str(item.get("pricing_total") or "").strip() or "未回放"
            line_total_value = pricing_compare.parse_amount(line_total)
            pricing_total_value = pricing_compare.parse_amount(pricing_total)
            diff_text = ""
            if line_total_value is not None and pricing_total_value is not None:
                diff_text = pricing_compare.format_amount(abs(pricing_total_value - line_total_value))

            summary = f"{index}. {_format_product_display(item)}：合同 {line_total}"
            if str(item.get("pricing_total") or "").strip():
                summary += f" -> 报价 {pricing_total}"
                if diff_text:
                    summary += f"，差额 {diff_text}"
            else:
                summary += "，当前未形成报价金额"
            lines.append(summary)

            route_label = _describe_pricing_route(item)
            if route_label:
                lines.append(f"   路线：{route_label}")
            risk_label = _describe_line_risk(item)
            if risk_label:
                lines.append(f"   风险：{risk_label}")

    excluded_items = [item for item in list(pricing_compare_payload.get("excluded_items") or []) if isinstance(item, dict)]
    if excluded_items:
        lines.append("待确认品项：")
        for index, item in enumerate(excluded_items, start=1):
            line_total = str(item.get("line_total") or "").strip() or "未识别"
            lines.append(f"{index}. {_format_product_display(item)}：合同 {line_total}，当前未形成报价金额")
            follow_up_question = str(item.get("follow_up_question") or "").strip()
            if follow_up_question:
                lines.append(f"   待确认：{follow_up_question}")

    return lines


def _render_review_reply(review_payload: dict[str, Any]) -> tuple[str, str]:
    reviewer_card = review_payload.get("reviewer_card") or {}
    if reviewer_card:
        next_question = str(((review_payload.get("review_analysis") or {}).get("next_question")) or "").strip()
        return render_reviewer_card_markdown(reviewer_card).strip(), next_question

    review_card = review_payload.get("review_card") or {}
    pricing_compare = review_payload.get("pricing_compare") or {}
    issues = list(review_payload.get("issues") or [])
    contract_total = str(review_card.get("contract_total") or "").strip() or "未识别"
    pricing_total = str(review_card.get("pricing_total") or "").strip() or "未回放"
    delta = str(pricing_compare.get("best_match_diff") or "").strip()
    if not delta and issues:
        delta = str(issues[0].get("delta_value") or "").strip()
    cause_lines = []
    for issue in issues[:3]:
        for cause in list(issue.get("suspected_causes") or []):
            if cause and cause not in cause_lines:
                cause_lines.append(cause)
    next_actions = list(review_card.get("next_actions") or [])
    next_question = str(((review_payload.get("review_analysis") or {}).get("next_question")) or "").strip()

    lines = [
        f"是否建议放行：{_label_verdict(str(review_card.get('verdict') or ''))}",
        f"优先级：{review_card.get('priority') or 'normal'}",
        f"合同金额：{contract_total}",
        f"报价金额：{pricing_total}",
    ]
    if delta:
        lines.append(f"差额：{delta}")
    if review_card.get("best_match_target"):
        lines.append(f"最佳匹配目标：{review_card['best_match_target']}")
    multi_product_sections = _build_multi_product_sections(pricing_compare)
    if multi_product_sections:
        lines.extend(multi_product_sections)
    if cause_lines:
        lines.append("怀疑原因：")
        for index, cause in enumerate(cause_lines[:3], start=1):
            lines.append(f"{index}. {cause}")
    if next_actions:
        action_heading = (
            "复核提示："
            if not issues and str(review_card.get("verdict") or "").strip() in {"recommended_release", "pass_with_watch"}
            else "请人工核对："
        )
        lines.append(action_heading)
        for index, action in enumerate(next_actions[:3], start=1):
            lines.append(f"{index}. {action}")
    if next_question and next_question not in next_actions:
        lines.append(next_question)
    return "\n".join(lines).strip(), next_question


def _find_matching_product_code(command: str, product_codes: list[str]) -> str:
    digits = re.findall(r"\d{4,20}", str(command or ""))
    normalized_codes = [str(item or "").strip() for item in product_codes if str(item or "").strip()]
    for digit in digits:
        for product_code in normalized_codes:
            if product_code == digit or product_code.endswith(digit) or digit.endswith(product_code):
                return product_code
    return ""


def _find_child_bed_confirmation_candidate(review_payload: dict[str, Any], command: str) -> dict[str, Any]:
    product_split_items = [item for item in list((review_payload.get("product_split") or {}).get("items") or []) if isinstance(item, dict)]
    excluded_items = [item for item in list((review_payload.get("pricing_compare") or {}).get("excluded_items") or []) if isinstance(item, dict)]
    split_items_by_code = {
        str(item.get("product_code") or "").strip(): item
        for item in product_split_items
        if str(item.get("product_code") or "").strip()
    }
    candidates: list[dict[str, Any]] = []
    for item in excluded_items:
        follow_up_question = str(item.get("follow_up_question") or "").strip()
        product_code = str(item.get("product_code") or "").strip()
        matched_split_item = split_items_by_code.get(product_code)
        if matched_split_item is None and product_code:
            matched_split_item = next(
                (
                    split_item
                    for split_code, split_item in split_items_by_code.items()
                    if split_code.endswith(product_code) or product_code.endswith(split_code)
                ),
                None,
            )
        if not _looks_like_child_bed_confirmation_target(
            excluded_item=item,
            split_item=matched_split_item or {},
            follow_up_question=follow_up_question,
        ):
            continue
        candidates.append(
            {
                "product_code": product_code or str((matched_split_item or {}).get("product_code") or "").strip(),
                "product_name": str(item.get("product_name") or "").strip(),
                "follow_up_question": follow_up_question,
                "split_item": matched_split_item or {},
            }
        )

    if not candidates:
        return {}

    matched_code = _find_matching_product_code(command, [item["product_code"] for item in candidates])
    if matched_code:
        for item in candidates:
            product_code = str(item.get("product_code") or "").strip()
            if product_code == matched_code or product_code.endswith(matched_code) or matched_code.endswith(product_code):
                return item
    if len(candidates) == 1:
        return candidates[0]
    return {}


def _looks_like_child_bed_confirmation_target(
    *,
    excluded_item: dict[str, Any],
    split_item: dict[str, Any],
    follow_up_question: str,
) -> bool:
    product_name = str(excluded_item.get("product_name") or split_item.get("product_name") or "").strip()
    if "儿童床" in product_name:
        return True

    if any(token in str(follow_up_question or "") for token in ("儿童床", "围栏", "梯柜", "上下床")):
        normalized_fields = split_item.get("normalized_fields") or {}
        child_bed_analysis = (
            normalized_fields.get("child_bed_analysis")
            or (split_item.get("pricing_precheck") or {}).get("child_bed_analysis")
            or {}
        )
        if child_bed_analysis.get("is_child_bed"):
            return True
        route_evidence = (
            normalized_fields.get("route_evidence")
            or (split_item.get("pricing_precheck") or {}).get("route_evidence")
            or {}
        )
        if str(route_evidence.get("recommended_route") or "").strip() == "modular_child_bed":
            return True
    return False


def _parse_child_bed_confirmation_fields(
    command: str,
    *,
    default_bed_form: str = "",
    prompt_question: str = "",
) -> dict[str, str]:
    text = str(command or "").strip()
    if not text:
        return {}

    fields: dict[str, str] = {}
    if any(token in text for token in ("梯柜上下床", "梯柜上下铺")):
        fields["access_style"] = "梯柜"
        fields["bed_form"] = "上下床"
    if any(token in text for token in ("直梯上下床", "直梯上下铺")):
        fields["access_style"] = "直梯"
        fields["bed_form"] = "上下床"
    if any(token in text for token in ("斜梯上下床", "斜梯上下铺")):
        fields["access_style"] = "斜梯"
        fields["bed_form"] = "上下床"
    if "梯柜" in text and "access_style" not in fields:
        fields["access_style"] = "梯柜"
    if "直梯" in text and "access_style" not in fields:
        fields["access_style"] = "直梯"
    if "斜梯" in text and "access_style" not in fields:
        fields["access_style"] = "斜梯"
    if any(token in text for token in ("上下床", "上下铺", "上床下床", "上铺下铺")):
        fields["bed_form"] = "上下床"
    if "箱体床" in text:
        fields["lower_bed_type"] = "箱体床"
    elif "架式床" in text:
        fields["lower_bed_type"] = "架式床"
    for candidate in ("篱笆围栏", "胶囊围栏", "城堡围栏"):
        if candidate in text:
            fields["guardrail_style"] = candidate
            break
    guardrail_length = _extract_confirmed_dimension(
        text,
        explicit_keywords=("围栏", "总长", "长度"),
        prompt_question=prompt_question,
        prompt_keywords=("总长", "长度"),
    )
    if guardrail_length:
        fields["guardrail_length"] = guardrail_length
    guardrail_height = _extract_confirmed_dimension(
        text,
        explicit_keywords=("围栏", "高度", "高"),
        prompt_question=prompt_question,
        prompt_keywords=("高度",),
    )
    if guardrail_height:
        fields["guardrail_height"] = guardrail_height
    access_height = _extract_confirmed_dimension(
        text,
        explicit_keywords=("梯子", "垂直高度", "上下床间距", "高度", "高"),
        prompt_question=prompt_question,
        prompt_keywords=("垂直高度", "上下床间距", "梯子高度"),
    )
    if access_height:
        fields["access_height"] = access_height
    stair_width = _extract_confirmed_stair_width(text, prompt_question=prompt_question)
    if stair_width:
        fields["stair_width"] = stair_width
    stair_depth = _extract_confirmed_dimension(
        text,
        explicit_keywords=("梯柜", "进深", "深度", "深"),
        prompt_question=prompt_question,
        prompt_keywords=("进深", "深度"),
    )
    if stair_depth:
        fields["stair_depth"] = stair_depth

    if "bed_form" not in fields and fields and default_bed_form:
        fields["bed_form"] = default_bed_form
    return fields


def _extract_confirmed_stair_width(text: str, *, prompt_question: str) -> str:
    content = str(text or "").strip()
    if not content:
        return ""

    if _looks_like_stair_width_context(content=content, prompt_question=prompt_question):
        band_value = _extract_stair_width_band_value(content)
        if band_value:
            return band_value

    return _extract_confirmed_dimension(
        content,
        explicit_keywords=("梯柜", "踏步宽度", "梯柜宽度", "踏步宽", "宽度", "宽"),
        prompt_question=prompt_question,
        prompt_keywords=("踏步宽度", "梯柜宽度", "宽度"),
    )


def _looks_like_stair_width_context(*, content: str, prompt_question: str) -> bool:
    return _contains_any(prompt_question, ("踏步宽度", "梯柜宽度", "踏步宽", "宽度")) or (
        _contains_any(content, ("梯柜", "踏步")) and _contains_any(content, ("宽度", "宽"))
    )


def _extract_stair_width_band_value(text: str) -> str:
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    if not normalized:
        return ""
    if re.search(r"450(?:mm|毫米)?(?:-|~|—|－|–|至|到)500(?:mm|毫米)?", normalized):
        return "500mm"
    if re.search(r"500(?:mm|毫米)?(?:-|~|—|－|–|至|到)600(?:mm|毫米)?", normalized):
        return "520mm"
    if any(token in normalized for token in ("第一档", "前一档", "前档")):
        return "500mm"
    if any(token in normalized for token in ("第二档", "后一档", "后档")):
        return "520mm"
    return ""


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    content = str(text or "")
    return any(keyword in content for keyword in keywords)


def _extract_confirmed_dimension(
    text: str,
    *,
    explicit_keywords: tuple[str, ...],
    prompt_question: str,
    prompt_keywords: tuple[str, ...],
) -> str:
    content = str(text or "").strip()
    if not content:
        return ""
    allow_numeric_only = bool(prompt_question) and any(keyword in str(prompt_question) for keyword in prompt_keywords)
    if not allow_numeric_only:
        primary_keyword = explicit_keywords[0] if explicit_keywords else ""
        secondary_keywords = explicit_keywords[1:] if len(explicit_keywords) > 1 else ()
        has_primary_keyword = not primary_keyword or primary_keyword in content
        has_secondary_keyword = True if not secondary_keywords else any(keyword in content for keyword in secondary_keywords)
        if not (has_primary_keyword and has_secondary_keyword):
            return ""

    match = re.search(r"(\d+(?:\.\d+)?)\s*(mm|毫米|cm|厘米|m|米)?", content, flags=re.IGNORECASE)
    if not match:
        return ""
    raw_value = str(match.group(1) or "").strip()
    raw_unit = str(match.group(2) or "").strip().lower()
    if not raw_value:
        return ""

    value = float(raw_value)
    if raw_unit in {"m", "米"}:
        millimeters = int(round(value * 1000))
    elif raw_unit in {"cm", "厘米"}:
        millimeters = int(round(value * 10))
    else:
        millimeters = int(round(value))
    return f"{millimeters}mm" if millimeters > 0 else ""


def _collect_existing_split_dimensions(split_item: dict[str, Any]) -> dict[str, str]:
    fields = ((split_item.get("normalized_fields") or {}).get("fields") or {})
    collected: dict[str, str] = {}
    for field_name in ("length", "width", "height"):
        value = str(((fields.get(field_name) or {}).get("value") or "")).strip()
        if value:
            collected[field_name] = value
    return collected


def _refresh_batch_summary_for_job(
    *,
    runtime_root: Path,
    batch_id: str,
    updated_job_result: dict[str, Any],
) -> None:
    summary_payload = _load_batch_summary(runtime_root, batch_id)
    if not summary_payload:
        return

    batch_results = [
        dict(item)
        for item in list(summary_payload.get("jobs") or [])
        if str((item or {}).get("job_id") or "").strip() != str(updated_job_result.get("job_id") or "").strip()
    ]
    batch_results.append(dict(updated_job_result))
    batch_plan = BatchPlan(
        batch_id=str(summary_payload.get("batch_id") or batch_id).strip(),
        batch_dir=runtime_root / "batches" / batch_id,
        source_type=str(summary_payload.get("source_type") or "").strip(),
        source_channel=str(summary_payload.get("source_channel") or "").strip(),
        requested_actions=[
            str(item).strip()
            for item in list(summary_payload.get("requested_actions") or [])
            if str(item).strip()
        ],
        jobs=[],
        manifest=dict(summary_payload.get("manifest") or {}),
        warnings=[str(item).strip() for item in list(summary_payload.get("warnings") or []) if str(item).strip()],
        created_at=str(summary_payload.get("created_at") or "").strip(),
    )
    write_batch_summary(batch_plan, batch_results=batch_results, runtime_root=runtime_root)


def _render_human_confirmation_reply(
    *,
    product_code: str,
    confirmed_fields: dict[str, str],
    review_payload: dict[str, Any],
) -> str:
    summary = "，".join(f"{field_name}={value}" for field_name, value in confirmed_fields.items())
    review_reply, _ = _render_review_reply(review_payload)
    return (
        f"已按人工确认回填并重算：{product_code or '当前品项'}"
        + (f"（{summary}）。" if summary else "。")
        + "\n"
        + review_reply
    ).strip()


def _handle_apply_human_confirmation(
    *,
    command: str,
    runtime_root: Path,
    state_root: Path,
    state: dict[str, Any],
    extraction_config: ExtractionConfig,
) -> dict[str, Any] | None:
    job_id = str(state.get("last_job_id") or "").strip()
    if not job_id:
        return None

    review_payload = _load_review(runtime_root, job_id)
    candidate = _find_child_bed_confirmation_candidate(review_payload, command)
    if not candidate:
        return None

    default_bed_form = "上下床" if "上下床" in str(candidate.get("follow_up_question") or "") else ""
    prompt_question = str(
        candidate.get("follow_up_question")
        or ((review_payload.get("review_analysis") or {}).get("next_question"))
        or ""
    ).strip()
    parsed_fields = _parse_child_bed_confirmation_fields(
        command,
        default_bed_form=default_bed_form,
        prompt_question=prompt_question,
    )
    if not parsed_fields:
        return None

    confirmed_fields = _collect_existing_split_dimensions(candidate.get("split_item") or {})
    confirmed_fields.update(parsed_fields)
    product_code = str(candidate.get("product_code") or "").strip()

    job = _load_review_job(runtime_root, job_id)
    manual_split_field_overrides = dict(job.metadata.get("manual_split_field_overrides") or {})
    override_payload = dict(manual_split_field_overrides.get(product_code) or {})
    existing_field_values = {
        str(field_name).strip(): str(raw_value).strip()
        for field_name, raw_value in dict(override_payload.get("field_values") or {}).items()
        if str(field_name).strip() and str(raw_value).strip()
    }
    existing_field_values.update(confirmed_fields)
    override_payload.update(
        {
            "confirmed": True,
            "confirmed_route": "modular_child_bed",
            "field_values": existing_field_values,
            "evidence_text": str(candidate.get("follow_up_question") or "").strip(),
        }
    )
    manual_split_field_overrides[product_code] = override_payload
    job.metadata["manual_split_field_overrides"] = manual_split_field_overrides

    job_dir = materialize_job(job, runtime_root=runtime_root)
    updated_job_result = run_review_job(
        job,
        job_dir=job_dir,
        extraction_config=extraction_config,
    )
    if job.batch_id:
        _refresh_batch_summary_for_job(
            runtime_root=runtime_root,
            batch_id=job.batch_id,
            updated_job_result=updated_job_result,
        )

    updated_review_payload = _load_review(runtime_root, job_id)
    _save_state(state_root, state)
    reply_text = _render_human_confirmation_reply(
        product_code=product_code,
        confirmed_fields=existing_field_values,
        review_payload=updated_review_payload,
    )
    return {
        "handled_by": HANDLED_BY,
        "action": "applied_human_confirmation",
        "job_id": job_id,
        "target_product_code": product_code,
        "confirmed_fields": existing_field_values,
        "review_card": updated_review_payload.get("review_card") or {},
        "next_question": str(((updated_review_payload.get("review_analysis") or {}).get("next_question")) or "").strip(),
        "reply_text": reply_text,
    }


def _next_job_from_state(state: dict[str, Any]) -> str:
    queue_job_ids = list(state.get("queue_job_ids") or [])
    if not queue_job_ids:
        return ""
    cursor = int(state.get("cursor") or -1) + 1
    if cursor >= len(queue_job_ids):
        cursor = 0
    state["cursor"] = cursor
    state["last_job_id"] = queue_job_ids[cursor]
    return queue_job_ids[cursor]


def _extract_command_options(command: str, *, prefix: str) -> dict[str, str]:
    if prefix not in command:
        return {}
    suffix = str(command.split(prefix, 1)[1] or "").strip()
    if not suffix:
        return {}
    pattern = re.compile(r"([A-Za-z_\u4e00-\u9fff]+)\s*=\s*(.+?)(?=\s+[A-Za-z_\u4e00-\u9fff]+\s*=|$)")
    return {
        str(match.group(1) or "").strip(): str(match.group(2) or "").strip().strip("，,；; ")
        for match in pattern.finditer(suffix)
        if str(match.group(1) or "").strip()
    }


def _parse_corrected_fields(raw_value: str) -> dict[str, str]:
    corrected_fields: dict[str, str] = {}
    for chunk in re.split(r"[，,；;]\s*", str(raw_value or "").strip()):
        item = str(chunk or "").strip()
        if not item:
            continue
        if "：" in item:
            field_name, value = item.split("：", 1)
        elif ":" in item:
            field_name, value = item.split(":", 1)
        else:
            continue
        field_name = str(field_name or "").strip()
        value = str(value or "").strip()
        if field_name and value:
            corrected_fields[field_name] = value
    return corrected_fields


def _normalize_human_decision(raw_value: str, *, has_structured_feedback: bool) -> str:
    value = str(raw_value or "").strip().lower()
    decision_map = {
        "reviewed": "reviewed",
        "已核对": "reviewed",
        "通过": "reviewed",
        "confirmed": "confirmed",
        "确认": "confirmed",
        "确认问题": "confirmed",
        "误报": "false_positive",
        "驳回": "false_positive",
        "false_positive": "false_positive",
    }
    if value in decision_map:
        return decision_map[value]
    return "confirmed" if has_structured_feedback else "reviewed"


def _build_feedback_payload(
    *,
    command: str,
    job_id: str,
    template_id: str,
    issue_code: str,
) -> dict[str, Any]:
    options = _extract_command_options(command, prefix="标记已核对")
    corrected_fields = _parse_corrected_fields(options.get("字段") or options.get("修正字段") or "")
    confirmed_root_cause = str(
        options.get("原因")
        or options.get("根因")
        or options.get("问题")
        or options.get("root_cause")
        or ""
    ).strip()
    human_decision = _normalize_human_decision(
        options.get("结论") or options.get("判定") or options.get("decision") or "",
        has_structured_feedback=bool(corrected_fields or confirmed_root_cause),
    )
    return {
        "job_id": job_id,
        "template_id": template_id,
        "issue_code": issue_code,
        "human_decision": human_decision,
        "corrected_fields": corrected_fields,
        "confirmed_root_cause": confirmed_root_cause,
    }


def _build_template_profile_update_summary(
    template_profile: dict[str, Any],
    *,
    feedback_payload: dict[str, Any],
) -> dict[str, Any]:
    corrected_fields = feedback_payload.get("corrected_fields") or {}
    confirmed_root_cause = str(feedback_payload.get("confirmed_root_cause") or "").strip()
    summary = {
        "template_id": str(template_profile.get("template_id") or "").strip(),
        "trust_score": template_profile.get("trust_score"),
        "feedback_count": int(template_profile.get("feedback_count") or 0),
        "human_decision": str(feedback_payload.get("human_decision") or "").strip(),
        "learned_field_names": sorted(corrected_fields.keys()),
        "confirmed_root_cause": confirmed_root_cause,
    }
    human_decision_breakdown = template_profile.get("human_decision_breakdown") or {}
    if human_decision_breakdown:
        summary["human_decision_breakdown"] = human_decision_breakdown
    return summary


def _render_mark_reviewed_reply(*, job_id: str, feedback_payload: dict[str, Any]) -> str:
    lines = [f"已把 `{job_id}` 标记为已核对。"]
    if feedback_payload.get("confirmed_root_cause"):
        lines.append(f"已记录根因：{feedback_payload['confirmed_root_cause']}")
    corrected_fields = feedback_payload.get("corrected_fields") or {}
    if corrected_fields:
        lines.append(f"已学习字段：{', '.join(sorted(corrected_fields.keys()))}")
    template_profile_update = feedback_payload.get("template_profile_update") or {}
    if template_profile_update.get("template_id"):
        lines.append(f"模板已更新：{template_profile_update['template_id']}")
    return "\n".join(lines)


def _handle_mark_reviewed(
    *,
    command: str,
    runtime_root: Path,
    state_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    job_id = str(state.get("last_job_id") or "").strip()
    if not job_id:
        return {
            "handled_by": HANDLED_BY,
            "action": "missing_last_job",
            "reply_text": "当前还没有可标记的合同，请先审一份合同。",
        }

    review_payload = _load_review(runtime_root, job_id)
    template_profile = review_payload.get("template_profile") or {}
    issue_codes = list((review_payload.get("review_analysis") or {}).get("issue_codes") or [])
    feedback_payload = _build_feedback_payload(
        command=command,
        job_id=job_id,
        template_id=str(template_profile.get("template_id") or "").strip(),
        issue_code=issue_codes[0] if issue_codes else "",
    )
    feedback_path = job_output_dir(job_id, runtime_root=runtime_root) / "output" / "review-feedback.json"
    if feedback_payload["template_id"]:
        updated_template_profile = apply_review_feedback(feedback_payload, runtime_root=runtime_root)
        feedback_payload["template_profile_update"] = _build_template_profile_update_summary(
            updated_template_profile,
            feedback_payload=feedback_payload,
        )
    write_json(feedback_path, feedback_payload)
    _save_state(state_root, state)
    return {
        "handled_by": HANDLED_BY,
        "action": "marked_reviewed",
        "feedback_payload": feedback_payload,
        "reply_text": _render_mark_reviewed_reply(job_id=job_id, feedback_payload=feedback_payload),
    }


def _handle_filter_amount_conflicts(*, runtime_root: Path, state_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    queue_job_ids = list(state.get("queue_job_ids") or [])
    matched: list[str] = []
    for job_id in queue_job_ids:
        review_payload = _load_review(runtime_root, job_id)
        issue_codes = set((review_payload.get("review_analysis") or {}).get("issue_codes") or [])
        if issue_codes & {"quote_conflict", "discount_mismatch", "quantity_mismatch", "add_on_mismatch"}:
            matched.append(job_id)
    reply = "金额冲突队列为空。" if not matched else "金额冲突合同：\n" + "\n".join(f"- {job_id}" for job_id in matched)
    _save_state(state_root, state)
    return {
        "handled_by": HANDLED_BY,
        "action": "filtered_amount_conflicts",
        "matched_job_ids": matched,
        "reply_text": reply,
    }


def _handle_expand_evidence(*, runtime_root: Path, state_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    job_id = str(state.get("last_job_id") or "").strip()
    if not job_id:
        return {
            "handled_by": HANDLED_BY,
            "action": "missing_last_job",
            "reply_text": "当前还没有可展开证据的合同，请先审一份合同。",
        }
    review_payload = _load_review(runtime_root, job_id)
    issues = list(review_payload.get("issues") or [])
    evidence_refs = list((issues[0].get("evidence_refs") if issues else []) or [])
    if not evidence_refs:
        reply_text = "当前没有可展开的证据片段。"
    else:
        lines = ["证据片段："]
        for ref in evidence_refs[:3]:
            lines.append(f"- {str(ref.get('snippet') or '').strip() or '无片段'}")
        reply_text = "\n".join(lines)
    _save_state(state_root, state)
    return {
        "handled_by": HANDLED_BY,
        "action": "expanded_evidence",
        "reply_text": reply_text,
    }


def _handle_show_next(*, runtime_root: Path, state_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    job_id = _next_job_from_state(state)
    if not job_id:
        return {
            "handled_by": HANDLED_BY,
            "action": "empty_queue",
            "reply_text": "当前没有待处理合同，请先导入一个批次。",
        }
    review_payload = _load_review(runtime_root, job_id)
    reply_text, next_question = _render_review_reply(review_payload)
    _save_state(state_root, state)
    return {
        "handled_by": HANDLED_BY,
        "action": "show_next_job",
        "job_id": job_id,
        "review_card": review_payload.get("review_card") or {},
        "next_question": next_question,
        "reply_text": reply_text,
    }


def _find_quick_action(dashboard_payload: dict[str, Any], action_id: str) -> dict[str, Any] | None:
    for item in dashboard_payload.get("template_learning_top_templates") or []:
        for action in item.get("quick_actions") or []:
            if str(action.get("action_id") or "").strip() == action_id:
                return action
    return None


def _find_job_id_for_template(summary_payload: dict[str, Any], template_id: str) -> str:
    for item in summary_payload.get("jobs") or []:
        if str(item.get("template_id") or "").strip() == template_id:
            return str(item.get("job_id") or "").strip()
    return ""


def _extract_action_id(command: str) -> str:
    match = re.search(r"执行模板快捷动作\s+([A-Za-z0-9._:-]+)", command)
    return str(match.group(1) or "").strip() if match else ""


def _handle_execute_template_quick_action(
    *,
    command: str,
    runtime_root: Path,
    state_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    batch_id = str(state.get("last_batch_id") or "").strip()
    if not batch_id:
        return {
            "handled_by": HANDLED_BY,
            "action": "missing_last_batch",
            "reply_text": "当前还没有可执行快捷动作的批次，请先审一份合同。",
        }

    action_id = _extract_action_id(command)
    if not action_id:
        return {
            "handled_by": HANDLED_BY,
            "action": "missing_action_id",
            "reply_text": "请补上要执行的模板快捷动作 ID，例如：`执行模板快捷动作 tpl-001:feedback`。",
        }

    dashboard_payload = _load_batch_dashboard(runtime_root, batch_id)
    summary_payload = _load_batch_summary(runtime_root, batch_id)
    action = _find_quick_action(dashboard_payload, action_id)
    if not action:
        return {
            "handled_by": HANDLED_BY,
            "action": "quick_action_not_found",
            "reply_text": f"当前批次里没有找到快捷动作 `{action_id}`。",
        }

    action_type = str(action.get("action_type") or "").strip()
    template_id = str(action.get("template_id") or "").strip()
    resolved_job_id = _find_job_id_for_template(summary_payload, template_id)
    if resolved_job_id:
        state["last_job_id"] = resolved_job_id

    if action_type == "copy_command":
        payload = _handle_mark_reviewed(
            command=str(action.get("command") or "").strip(),
            runtime_root=runtime_root,
            state_root=state_root,
            state=state,
        )
        payload["action"] = "executed_template_quick_action"
        payload["quick_action"] = action
        payload["reply_text"] = (
            f"已执行模板快捷动作：{action_id}\n"
            + str(payload.get("reply_text") or "").strip()
        ).strip()
        return payload

    if action_type == "filter_issue":
        issue_code = str(action.get("issue_code") or "").strip()
        matched: list[str] = []
        for item in summary_payload.get("jobs") or []:
            if str(item.get("template_id") or "").strip() != template_id:
                continue
            issue_codes = set(item.get("issue_codes") or [])
            if issue_code in issue_codes:
                matched.append(str(item.get("job_id") or "").strip())
        _save_state(state_root, state)
        reply = (
            f"已执行模板快捷动作：{action_id}\n"
            + (
                "当前模板下没有命中该问题的合同。"
                if not matched
                else "命中的合同：\n" + "\n".join(f"- {job_id}" for job_id in matched)
            )
        )
        return {
            "handled_by": HANDLED_BY,
            "action": "executed_template_quick_action",
            "quick_action": action,
            "matched_job_ids": matched,
            "reply_text": reply,
        }

    return {
        "handled_by": HANDLED_BY,
        "action": "unsupported_quick_action",
        "quick_action": action,
        "reply_text": f"当前还不支持执行快捷动作类型 `{action_type}`。",
    }


def _emit(payload: dict[str, Any], *, output_mode: str) -> None:
    if output_mode == "json":
        json.dump(payload, fp=sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    sys.stdout.write(str(payload.get("reply_text") or "").strip() + "\n")


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    state_root = Path(args.state_root).expanduser().resolve() if args.state_root else runtime_root / "state"
    state = _load_state(state_root)
    extraction_config = ExtractionConfig(
        ocr_backend=args.ocr_backend,
        paddleocr_lang=args.paddleocr_lang,
        paddleocr_device=args.paddleocr_device,
        force_ocr_for_documents=args.force_ocr_for_documents,
    )

    command = str(args.text or "").strip()
    if args.batch_dir:
        summary = _run_batch_review(
            batch_dir=Path(args.batch_dir).expanduser().resolve(),
            runtime_root=runtime_root,
            extraction_config=extraction_config,
        )
        queue_job_ids = [str(item.get("job_id") or "").strip() for item in summary.get("jobs") or [] if str(item.get("job_id") or "").strip()]
        state.update(
            {
                "queue_job_ids": queue_job_ids,
                "cursor": 0 if queue_job_ids else -1,
                "last_job_id": queue_job_ids[0] if queue_job_ids else "",
                "last_batch_id": str(summary.get("batch_id") or "").strip(),
            }
        )
        _save_state(state_root, state)
        if queue_job_ids:
            review_payload = _load_review(runtime_root, queue_job_ids[0])
            reply_text, next_question = _render_review_reply(review_payload)
            payload = {
                "handled_by": HANDLED_BY,
                "action": "review_batch",
                "batch_id": summary.get("batch_id"),
                "job_id": queue_job_ids[0],
                "review_card": review_payload.get("review_card") or {},
                "next_question": next_question,
                "reply_text": reply_text,
            }
            _emit(payload, output_mode=args.output_mode)
            return payload

    if "执行模板快捷动作" in command:
        payload = _handle_execute_template_quick_action(
            command=command,
            runtime_root=runtime_root,
            state_root=state_root,
            state=state,
        )
    elif "标记已核对" in command:
        payload = _handle_mark_reviewed(command=command, runtime_root=runtime_root, state_root=state_root, state=state)
    elif "展开证据" in command:
        payload = _handle_expand_evidence(runtime_root=runtime_root, state_root=state_root, state=state)
    elif "只看金额冲突" in command:
        payload = _handle_filter_amount_conflicts(runtime_root=runtime_root, state_root=state_root, state=state)
    elif "看下一份高风险合同" in command:
        payload = _handle_show_next(runtime_root=runtime_root, state_root=state_root, state=state)
    else:
        payload = _handle_apply_human_confirmation(
            command=command,
            runtime_root=runtime_root,
            state_root=state_root,
            state=state,
            extraction_config=extraction_config,
        )
        if payload is None:
            payload = _handle_show_next(runtime_root=runtime_root, state_root=state_root, state=state)

    _emit(payload, output_mode=args.output_mode)
    return payload


def main(argv: list[str] | None = None) -> int:
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
