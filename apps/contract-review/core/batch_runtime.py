from __future__ import annotations

import csv
import html
import json
import os
import re
import shutil
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from job_models import BatchPlan, ReviewJob


DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"
PRIORITY_ORDER = {"p0": 0, "p1": 1, "p2": 2, "normal": 3}
ACTIONABLE_PRIORITY_ORDER = {
    "ready_now": 0,
    "need_user_input": 1,
    "monitor": 2,
    "blocked_by_ocr": 3,
    "auto_pass_candidate": 4,
}
TEMPLATE_FEEDBACK_FIELD_PRIORITY = {
    "missing_required_field": ["width", "length", "depth", "height", "product_category", "wood_material", "quote_kind"],
    "quote_conflict": ["product_category", "width", "length", "depth", "height", "wood_material"],
    "discount_mismatch": ["discount_rate", "product_category", "width", "length", "wood_material"],
    "quantity_mismatch": ["product_category", "width", "length", "depth"],
    "add_on_mismatch": ["product_category", "wood_material", "width", "length"],
}
TEMPLATE_FEEDBACK_ROOT_CAUSE = {
    "missing_required_field": "template_alias_missing",
    "quote_conflict": "pricing_scope_mismatch",
    "discount_mismatch": "discount_scope_mismatch",
    "quantity_mismatch": "quantity_mapping_error",
    "add_on_mismatch": "add_on_omission",
    "field_conflict": "template_field_conflict",
}
REVIEWER_DECISION_LABELS = {
    "auto_pass": "可自动通过",
    "review_recommended": "建议人工复核",
    "manual_required": "必须人工确认",
}
REVIEWER_DECISION_ORDER = ("manual_required", "review_recommended", "auto_pass")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "item"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    ensure_dir(path.parent)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)


def write_markdown(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


def write_csv(path: Path, rows: list[dict[str, Any]], *, fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def batch_output_dir(batch_id: str, *, runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> Path:
    return runtime_root / "batches" / slugify(batch_id)


def job_output_dir(job_id: str, *, runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> Path:
    return runtime_root / "jobs" / slugify(job_id)


def sort_batch_results(batch_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        batch_results,
        key=lambda row: (
            PRIORITY_ORDER.get(str(row.get("review_priority") or "normal"), 9),
            ACTIONABLE_PRIORITY_ORDER.get(str(row.get("actionable_priority") or "monitor"), 9),
            str(row.get("job_id") or ""),
        ),
    )


def _build_manual_review_queue_payload(
    batch_plan: BatchPlan,
    sorted_results: list[dict[str, Any]],
    reviewer_card_summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reviewer_decisions = {
        str(item.get("job_id") or "").strip(): str(item.get("decision") or "").strip()
        for item in list((reviewer_card_summary_payload or {}).get("items") or [])
        if str(item.get("job_id") or "").strip()
    }
    items = [
        {
            "job_id": row["job_id"],
            "group_key": row["group_key"],
            "status": row["status"],
            "review_priority": row.get("review_priority", "normal"),
            "review_priority_score": row.get("review_priority_score", PRIORITY_ORDER["normal"]),
            "review_priority_reason": row.get("review_priority_reason", ""),
            "finding_count": row["finding_count"],
            "blocking_finding_count": row["blocking_finding_count"],
            "automation_state": row.get("automation_state", ""),
            "conflict_count": row.get("conflict_count", 0),
            "conflict_fields": list(row.get("conflict_fields") or []),
            "manual_review_reasons": list(row.get("manual_review_reasons") or []),
            "issue_codes": list(row.get("issue_codes") or []),
            "risk_flags": list(row.get("risk_flags") or []),
            "actionable_priority": row.get("actionable_priority", "monitor"),
            "actionable_priority_score": row.get("actionable_priority_score", ACTIONABLE_PRIORITY_ORDER["monitor"]),
            "review_path": row["review_path"],
            "job_dir": row["job_dir"],
        }
        for row in sorted_results
        if reviewer_decisions.get(str(row.get("job_id") or "").strip(), "manual_required") != "auto_pass"
    ]
    return {
        "batch_id": batch_plan.batch_id,
        "queue_count": len(items),
        "items": items,
    }


def _build_batch_dashboard_payload(
    batch_plan: BatchPlan,
    sorted_results: list[dict[str, Any]],
    queue_payload: dict[str, Any],
) -> dict[str, Any]:
    review_priority_breakdown = {key: 0 for key in PRIORITY_ORDER}
    automation_state_breakdown: dict[str, int] = {}
    pricing_compare_breakdown: dict[str, int] = {}
    actionable_priority_breakdown = {key: 0 for key in ACTIONABLE_PRIORITY_ORDER}
    root_cause_breakdown: dict[str, int] = {}
    template_breakdown: dict[str, int] = {}
    ocr_blocked_count = 0
    template_profiles: dict[str, dict[str, Any]] = {}

    for row in sorted_results:
        priority = str(row.get("review_priority") or "normal")
        if priority not in review_priority_breakdown:
            review_priority_breakdown[priority] = 0
        review_priority_breakdown[priority] += 1

        automation_state = str(row.get("automation_state") or "unknown")
        automation_state_breakdown[automation_state] = automation_state_breakdown.get(automation_state, 0) + 1
        if automation_state == "ocr_or_vision_required":
            ocr_blocked_count += 1

        compare_status = str(row.get("pricing_compare_status") or "not_compared")
        pricing_compare_breakdown[compare_status] = pricing_compare_breakdown.get(compare_status, 0) + 1

        actionable_priority = str(row.get("actionable_priority") or "monitor")
        if actionable_priority not in actionable_priority_breakdown:
            actionable_priority_breakdown[actionable_priority] = 0
        actionable_priority_breakdown[actionable_priority] += 1

        template_id = str(row.get("template_id") or "").strip()
        if template_id:
            template_breakdown[template_id] = template_breakdown.get(template_id, 0) + 1
            if template_id not in template_profiles:
                template_profile = _load_job_output_payload(Path(str(row.get("job_dir") or "")), "template-profile.json")
                if template_profile:
                    template_profiles[template_id] = template_profile

        for issue_code in list(row.get("issue_codes") or []):
            code = str(issue_code or "").strip()
            if not code:
                continue
            root_cause_breakdown[code] = root_cause_breakdown.get(code, 0) + 1

    template_learning_payload = _build_template_learning_payload(template_profiles)

    return {
        "batch_id": batch_plan.batch_id,
        "source_type": batch_plan.source_type,
        "source_channel": batch_plan.source_channel,
        "job_count": len(sorted_results),
        "warning_count": len(batch_plan.warnings),
        "manual_queue_count": queue_payload["queue_count"],
        "ocr_blocked_count": ocr_blocked_count,
        "review_priority_breakdown": review_priority_breakdown,
        "actionable_priority_breakdown": actionable_priority_breakdown,
        "automation_state_breakdown": automation_state_breakdown,
        "pricing_compare_breakdown": pricing_compare_breakdown,
        "root_cause_breakdown": root_cause_breakdown,
        "template_breakdown": template_breakdown,
        "template_learning_overview": template_learning_payload["overview"],
        "template_learning_false_positive_breakdown": template_learning_payload["false_positive_breakdown"],
        "template_learning_top_templates": template_learning_payload["top_templates"],
        "top_priority_job_ids": [item["job_id"] for item in queue_payload["items"][:10]],
        "top_priority_groups": [item["group_key"] for item in queue_payload["items"][:10]],
    }


def _build_template_learning_payload(template_profiles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    overview = {
        "template_count": 0,
        "templates_with_feedback": 0,
        "templates_with_confirmed_feedback": 0,
        "templates_with_false_positive_feedback": 0,
        "templates_with_learned_fields": 0,
    }
    false_positive_breakdown: dict[str, int] = {}
    top_templates: list[dict[str, Any]] = []

    for template_id, profile in template_profiles.items():
        decision_breakdown = profile.get("human_decision_breakdown") or {}
        observed_issue_breakdown = profile.get("observed_issue_breakdown") or {}
        feedback_issue_breakdown = profile.get("feedback_issue_breakdown") or {}
        field_aliases = profile.get("field_aliases") or {}
        learned_field_count = sum(
            1
            for entry in field_aliases.values()
            if list(entry.get("confirmed_values") or [])
        )
        feedback_count = int(profile.get("feedback_count") or 0)
        confirmed_feedback_count = int(decision_breakdown.get("confirmed") or 0)
        false_positive_feedback_count = int(decision_breakdown.get("false_positive") or 0)
        reviewed_feedback_count = int(decision_breakdown.get("reviewed") or 0)
        dominant_issue_code = ""
        dominant_issue_count = 0
        for issue_code, count in observed_issue_breakdown.items():
            issue_count = int(count or 0)
            if issue_count > dominant_issue_count:
                dominant_issue_code = str(issue_code)
                dominant_issue_count = issue_count
        for issue_code, issue_payload in feedback_issue_breakdown.items():
            false_positive_count = int((issue_payload or {}).get("false_positive_count") or 0)
            if false_positive_count:
                false_positive_breakdown[str(issue_code)] = (
                    false_positive_breakdown.get(str(issue_code), 0) + false_positive_count
                )

        overview["template_count"] += 1
        overview["templates_with_feedback"] += 1 if feedback_count else 0
        overview["templates_with_confirmed_feedback"] += 1 if confirmed_feedback_count else 0
        overview["templates_with_false_positive_feedback"] += 1 if false_positive_feedback_count else 0
        overview["templates_with_learned_fields"] += 1 if learned_field_count else 0
        item = {
            "template_id": template_id,
            "trust_score": profile.get("trust_score"),
            "observed_job_count": int(profile.get("observed_job_count") or 0),
            "feedback_count": feedback_count,
            "confirmed_feedback_count": confirmed_feedback_count,
            "reviewed_feedback_count": reviewed_feedback_count,
            "false_positive_feedback_count": false_positive_feedback_count,
            "learned_field_count": learned_field_count,
            "dominant_issue_code": dominant_issue_code,
            "dominant_issue_count": dominant_issue_count,
            "missing_required_field_observed_count": int(observed_issue_breakdown.get("missing_required_field") or 0),
            "quote_conflict_observed_count": int(observed_issue_breakdown.get("quote_conflict") or 0),
            "missing_required_field_false_positive_count": int(
                ((feedback_issue_breakdown.get("missing_required_field") or {}).get("false_positive_count") or 0)
            ),
            "quote_conflict_false_positive_count": int(
                ((feedback_issue_breakdown.get("quote_conflict") or {}).get("false_positive_count") or 0)
            ),
        }
        action, reason = _recommend_template_next_action(item)
        item["recommended_action"] = action
        item["recommended_reason"] = reason
        item["suggested_feedback_command"] = _build_template_feedback_command(profile=profile, item=item)
        item["quick_actions"] = _build_template_quick_actions(item=item)
        top_templates.append(item)

    top_templates.sort(
        key=lambda item: (
            -int(item.get("feedback_count") or 0),
            -int(item.get("false_positive_feedback_count") or 0),
            -int(item.get("observed_job_count") or 0),
            str(item.get("template_id") or ""),
        )
    )
    return {
        "overview": overview,
        "false_positive_breakdown": false_positive_breakdown,
        "top_templates": top_templates[:10],
    }


def _recommend_template_next_action(item: dict[str, Any]) -> tuple[str, str]:
    missing_required_field_false_positive_count = int(item.get("missing_required_field_false_positive_count") or 0)
    quote_conflict_false_positive_count = int(item.get("quote_conflict_false_positive_count") or 0)
    missing_required_field_observed_count = int(item.get("missing_required_field_observed_count") or 0)
    learned_field_count = int(item.get("learned_field_count") or 0)
    false_positive_feedback_count = int(item.get("false_positive_feedback_count") or 0)
    dominant_issue_code = str(item.get("dominant_issue_code") or "").strip()

    if missing_required_field_false_positive_count > 0:
        return (
            "优先补字段锚点",
            "这个模板已经出现“缺字段误报”，建议先补宽度/材质/类目等固定标签锚点。",
        )
    if quote_conflict_false_positive_count > 0:
        return (
            "优先校准金额口径",
            "这个模板出现过金额冲突误报，建议先核对折前价、折扣和增项的默认落点。",
        )
    if missing_required_field_observed_count >= 2 and learned_field_count == 0:
        return (
            "优先沉淀已确认字段",
            "这个模板经常缺字段，但还没有稳定记忆，建议先把人工确认过的字段写回模板。",
        )
    if false_positive_feedback_count > 0:
        return (
            "优先清理误报规则",
            "这个模板已有误报反馈，建议先减少重复误报，再继续扩大自动化通过范围。",
        )
    if dominant_issue_code:
        return (
            f"继续观察 {dominant_issue_code}",
            "当前主要价值是继续积累样本，确认这个模板的高频问题是否稳定复现。",
        )
    return ("继续积累样本", "当前模板样本还不够，先继续跑单并沉淀人工反馈。")


def _build_template_feedback_command(*, profile: dict[str, Any], item: dict[str, Any]) -> str:
    target_issue_code, decision = _select_feedback_issue_and_decision(item)
    root_cause = _pick_feedback_root_cause(profile=profile, issue_code=target_issue_code)
    fields = _pick_template_feedback_fields(profile=profile, issue_code=target_issue_code)
    command_parts = ["标记已核对", f"结论={decision}"]
    if root_cause:
        command_parts.append(f"原因={root_cause}")
    if fields:
        command_parts.append("字段=" + ",".join(f"{field_name}:{value}" for field_name, value in fields))
    return " ".join(command_parts)


def _build_template_quick_actions(*, item: dict[str, Any]) -> list[dict[str, str]]:
    template_id = str(item.get("template_id") or "").strip()
    command = str(item.get("suggested_feedback_command") or "").strip()
    dominant_issue_code = str(item.get("dominant_issue_code") or "").strip()
    actions: list[dict[str, str]] = []
    if command:
        actions.append(
            {
                "action_id": f"{template_id}:feedback",
                "label": "复制反馈命令",
                "action_type": "copy_command",
                "template_id": template_id,
                "issue_code": dominant_issue_code,
                "command": command,
            }
        )
    if dominant_issue_code:
        actions.append(
            {
                "action_id": f"{template_id}:focus:{dominant_issue_code}",
                "label": "聚焦高频问题",
                "action_type": "filter_issue",
                "template_id": template_id,
                "issue_code": dominant_issue_code,
                "command": f"只看 {dominant_issue_code}",
            }
        )
    return actions


def _select_feedback_issue_and_decision(item: dict[str, Any]) -> tuple[str, str]:
    if int(item.get("missing_required_field_false_positive_count") or 0) > 0:
        return "missing_required_field", "误报"
    if int(item.get("quote_conflict_false_positive_count") or 0) > 0:
        return "quote_conflict", "误报"
    dominant_issue_code = str(item.get("dominant_issue_code") or "").strip()
    if dominant_issue_code:
        return dominant_issue_code, "确认问题"
    return "", "已核对"


def _pick_feedback_root_cause(*, profile: dict[str, Any], issue_code: str) -> str:
    rules = list(profile.get("common_conflict_rules") or [])
    for item in rules:
        if str(item.get("issue_code") or "").strip() == issue_code and str(item.get("root_cause") or "").strip():
            return str(item.get("root_cause") or "").strip()
    return TEMPLATE_FEEDBACK_ROOT_CAUSE.get(issue_code, "template_alias_missing" if issue_code else "")


def _pick_template_feedback_fields(*, profile: dict[str, Any], issue_code: str) -> list[tuple[str, str]]:
    field_aliases = profile.get("field_aliases") or {}
    learned_fields = {
        str(field_name): str((list((entry or {}).get("confirmed_values") or [""])[:1] or [""])[0]).strip()
        for field_name, entry in field_aliases.items()
        if str(field_name).strip() and str((list((entry or {}).get("confirmed_values") or [""])[:1] or [""])[0]).strip()
    }
    if not learned_fields:
        return []

    priority = list(TEMPLATE_FEEDBACK_FIELD_PRIORITY.get(issue_code, []))
    ordered_names: list[str] = []
    for field_name in priority:
        if field_name in learned_fields and field_name not in ordered_names:
            ordered_names.append(field_name)
    for field_name in sorted(learned_fields.keys()):
        if field_name not in ordered_names:
            ordered_names.append(field_name)
    return [(field_name, learned_fields[field_name]) for field_name in ordered_names[:3]]


def _build_pricing_compare_payload(batch_plan: BatchPlan, sorted_results: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "job_id": row["job_id"],
            "group_key": row["group_key"],
            "pricing_compare_status": str(row.get("pricing_compare_status") or "").strip(),
            "pricing_compare_match_band": str(row.get("pricing_compare_match_band") or "").strip(),
            "pricing_compare_best_match_target": str(row.get("pricing_compare_best_match_target") or "").strip(),
            "pricing_compare_best_match_diff": str(row.get("pricing_compare_best_match_diff") or "").strip(),
            "contract_total": str(row.get("contract_total") or "").strip(),
            "list_price_total": str(row.get("list_price_total") or "").strip(),
            "discount_rate": str(row.get("discount_rate") or "").strip(),
            "discounted_total": str(row.get("discounted_total") or "").strip(),
            "pricing_total": str(row.get("pricing_total") or "").strip(),
            "pricing_route": str(row.get("pricing_route") or "").strip(),
            "review_path": row["review_path"],
        }
        for row in sorted_results
    ]
    return {
        "batch_id": batch_plan.batch_id,
        "item_count": len(items),
        "items": items,
    }


def _load_job_output_payload(job_dir: Path, file_name: str) -> dict[str, Any]:
    path = job_dir / "output" / file_name
    if not path.exists():
        return {}
    return read_json(path)


def _derive_pricing_diagnosis(item: dict[str, Any]) -> tuple[str, str, list[str]]:
    compare_status = str(item.get("pricing_compare_status") or "").strip()
    precheck_status = str(item.get("precheck_status") or "").strip()
    formal_quote_status = str(item.get("formal_quote_status") or "").strip()
    formal_quote_reason = str(item.get("formal_quote_reason") or "").strip()
    replay_status = str(item.get("replay_status") or "").strip()
    replay_reason = str(item.get("replay_reason") or "").strip()

    if compare_status.startswith(("exact_match", "close_match", "approximate_match", "mismatch")):
        if compare_status.startswith("exact_match"):
            return "compared_effective", "已完成金额对比，结果为精确匹配。", ["优先复核是否存在备注或增项未入参。"]
        if compare_status.startswith("close_match"):
            return "compared_effective", "已完成金额对比，结果接近匹配。", ["优先看合同折前价与报价系统总价是否更接近。"]
        if compare_status.startswith("approximate_match"):
            return "compared_effective", "已完成金额对比，结果为近似匹配。", ["优先人工复核默认条件、折扣和附加项差异。"]
        return "compared_effective", "已完成金额对比，但当前差异较大。", [
            "回看类目映射、默认尺寸/深度、折扣和备注是否遗漏。"
        ]

    if "多个产品编码" in replay_reason or formal_quote_reason == "multi_product_contract":
        return "multi_product_contract", "合同包含多个产品，当前整单不适合直接拿单个产品报价对比。", [
            "先按产品行拆单，再分别映射到报价系统。",
            "若后续要做整单核价，需要补多产品汇总报价回放层。",
        ]

    if formal_quote_status == "failed":
        return "formal_quote_failed", "预检已通过，但正式报价执行失败。", [
            "检查 formal-quote.json 里的错误信息。",
            "确认当前类目路径是否支持自动正式报价。",
        ]

    if precheck_status == "manual_confirmation_required":
        return "manual_confirmation_required", "当前字段还不足以可信进入报价系统，需要人工确认关键类目或字段。", [
            "优先人工确认类目、关键尺寸和材质。"
        ]

    if precheck_status == "needs_input":
        return "needs_more_input", "已进入报价预检，但还缺正式报价必需字段。", [
            "根据 pricing-precheck.json 补齐 next_required_field 后再重跑。"
        ]

    if replay_status == "blocked":
        return "replay_blocked", replay_reason or "当前回放被阻塞。", [
            "优先查看 replay.json 的 reason 和 next_steps。"
        ]

    return "not_compared", "当前尚未形成有效金额对比。", ["优先查看 pricing-precheck.json 与 replay.json。"]


def _build_pricing_diagnosis_payload(batch_plan: BatchPlan, sorted_results: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    breakdown: dict[str, int] = {}
    for row in sorted_results:
        job_dir = Path(str(row.get("job_dir") or ""))
        pricing_precheck = _load_job_output_payload(job_dir, "pricing-precheck.json")
        formal_quote = _load_job_output_payload(job_dir, "formal-quote.json")
        replay = _load_job_output_payload(job_dir, "replay.json")
        diagnosis_code, diagnosis_summary, next_actions = _derive_pricing_diagnosis(
            {
                "pricing_compare_status": row.get("pricing_compare_status"),
                "precheck_status": pricing_precheck.get("status"),
                "formal_quote_status": formal_quote.get("status"),
                "formal_quote_reason": formal_quote.get("reason"),
                "replay_status": replay.get("status"),
                "replay_reason": replay.get("reason"),
            }
        )
        breakdown[diagnosis_code] = breakdown.get(diagnosis_code, 0) + 1
        items.append(
            {
                "job_id": row["job_id"],
                "group_key": row["group_key"],
                "template_id": str(row.get("template_id") or "").strip(),
                "template_fingerprint": str(row.get("template_fingerprint") or "").strip(),
                "issue_codes": list(row.get("issue_codes") or []),
                "diagnosis_code": diagnosis_code,
                "diagnosis_summary": diagnosis_summary,
                "pricing_compare_status": str(row.get("pricing_compare_status") or "").strip(),
                "precheck_status": str(pricing_precheck.get("status") or "").strip(),
                "formal_quote_status": str(formal_quote.get("status") or "").strip(),
                "formal_quote_reason": str(formal_quote.get("reason") or "").strip(),
                "replay_status": str(replay.get("status") or "").strip(),
                "replay_reason": str(replay.get("reason") or "").strip(),
                "contract_total": str(row.get("contract_total") or "").strip(),
                "list_price_total": str(row.get("list_price_total") or "").strip(),
                "discounted_total": str(row.get("discounted_total") or "").strip(),
                "pricing_total": str(row.get("pricing_total") or "").strip(),
                "pricing_route": str(row.get("pricing_route") or "").strip(),
                "best_match_target": str(row.get("pricing_compare_best_match_target") or "").strip(),
                "best_match_diff": str(row.get("pricing_compare_best_match_diff") or "").strip(),
                "recommended_next_actions": next_actions,
                "review_path": row["review_path"],
            }
        )
    return {
        "batch_id": batch_plan.batch_id,
        "item_count": len(items),
        "diagnosis_breakdown": breakdown,
        "items": items,
    }


def _parse_amount(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = (
        text.replace(",", "")
        .replace("，", "")
        .replace("人民币", "")
        .replace("元", "")
        .strip()
    )
    if not normalized:
        return None
    try:
        return Decimal(normalized).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _format_amount(value: Decimal | None) -> str:
    if value is None:
        return ""
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized == quantized.to_integral():
        return f"{int(quantized)}元"
    return f"{format(quantized.normalize(), 'f')}元"


def _derive_fallback_item_ledger(row: dict[str, Any], pricing_compare_payload: dict[str, Any]) -> list[dict[str, Any]]:
    contract_amount = (
        str(row.get("contract_total") or "").strip()
        or str(row.get("discounted_total") or "").strip()
        or str(row.get("list_price_total") or "").strip()
    )
    pricing_amount = str(row.get("pricing_total") or "").strip()
    compare_status = str(row.get("pricing_compare_status") or "").strip()
    ledger_status = "compared" if pricing_amount else "pending"
    difference = ""
    difference_value: float | None = None
    contract_decimal = _parse_amount(contract_amount)
    pricing_decimal = _parse_amount(pricing_amount)
    if contract_decimal is not None and pricing_decimal is not None:
        difference_decimal = abs(pricing_decimal - contract_decimal)
        difference = _format_amount(difference_decimal)
        difference_value = float(difference_decimal)

    reason = str(pricing_compare_payload.get("reason") or "").strip()
    if not reason:
        reason = compare_status or ("pricing_total_compared" if pricing_amount else "formal_quote_not_available")

    entry = {
        "product_name": "整单",
        "product_code": "",
        "ledger_status": ledger_status,
        "contract_amount": contract_amount,
        "pricing_amount": pricing_amount,
        "difference": difference,
        "difference_value": difference_value,
        "pricing_route": str(row.get("pricing_route") or "").strip(),
        "reason": reason,
    }
    best_match_target = str(pricing_compare_payload.get("best_match_target") or "").strip()
    if best_match_target:
        entry["best_match_target"] = best_match_target
    best_match_diff = str(pricing_compare_payload.get("best_match_diff") or "").strip()
    if best_match_diff:
        entry["best_match_diff"] = best_match_diff
    return [entry]


def _build_pricing_replay_baseline_payload(batch_plan: BatchPlan, sorted_results: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in sorted_results:
        job_dir = Path(str(row.get("job_dir") or ""))
        review_payload = _load_job_output_payload(job_dir, "review.json")
        pricing_compare_payload = (review_payload.get("pricing_compare") or {})
        if not pricing_compare_payload:
            pricing_compare_payload = _load_job_output_payload(job_dir, "pricing-compare.json")

        item_ledger = [
            dict(item)
            for item in list(pricing_compare_payload.get("item_ledger") or [])
            if isinstance(item, dict)
        ]
        if not item_ledger:
            item_ledger = _derive_fallback_item_ledger(row, pricing_compare_payload)

        items.append(
            {
                "job_id": row["job_id"],
                "group_key": row["group_key"],
                "pricing_compare_status": str(row.get("pricing_compare_status") or "").strip(),
                "pricing_route": str(row.get("pricing_route") or "").strip(),
                "contract_total": str(row.get("contract_total") or "").strip(),
                "pricing_total": str(row.get("pricing_total") or "").strip(),
                "review_path": row["review_path"],
                "item_ledger": item_ledger,
            }
        )
    return {
        "batch_id": batch_plan.batch_id,
        "job_count": len(items),
        "items": items,
    }


def _build_reviewer_card_summary_payload(batch_plan: BatchPlan, sorted_results: list[dict[str, Any]]) -> dict[str, Any]:
    decision_breakdown = {key: 0 for key in REVIEWER_DECISION_LABELS}
    items: list[dict[str, Any]] = []
    for row in sorted_results:
        job_dir = Path(str(row.get("job_dir") or ""))
        reviewer_card = _load_job_output_payload(job_dir, "reviewer-card.json")
        decision = str(reviewer_card.get("decision") or "").strip()
        if decision not in REVIEWER_DECISION_LABELS:
            decision = "manual_required"

        decision_breakdown[decision] += 1
        amounts = reviewer_card.get("amounts") or {}
        line_items = [
            dict(item)
            for item in list(reviewer_card.get("line_items") or [])
            if isinstance(item, dict)
        ]
        manual_required_items = [
            item
            for item in line_items
            if str(item.get("review_status") or "").strip() == "manual_required"
        ]
        review_recommended_items = [
            item
            for item in line_items
            if str(item.get("review_status") or "").strip() == "review_recommended"
        ]
        compared_items = [
            item
            for item in line_items
            if str(item.get("review_status") or "").strip() == "compared"
        ]
        next_actions = [
            str(action).strip()
            for action in list(reviewer_card.get("next_actions") or [])
            if str(action).strip()
        ]
        primary_reason = str(reviewer_card.get("primary_reason") or "").strip()
        if not primary_reason:
            primary_reason = "未生成审核员决策卡，请人工确认该单是否已形成系统报价。"
        if not next_actions and decision == "manual_required":
            next_actions = ["优先确认该单是否存在未入账品项或无法形成报价的品项。"]

        items.append(
            {
                "job_id": row["job_id"],
                "group_key": row["group_key"],
                "decision": decision,
                "decision_label": str(reviewer_card.get("decision_label") or REVIEWER_DECISION_LABELS[decision]).strip(),
                "primary_reason": primary_reason,
                "contract_amount": str(amounts.get("contract_amount") or row.get("contract_total") or "").strip(),
                "pricing_amount": str(amounts.get("pricing_amount") or row.get("pricing_total") or "").strip(),
                "difference": str(amounts.get("difference") or row.get("pricing_compare_best_match_diff") or "").strip(),
                "comparison_basis_label": str(amounts.get("comparison_basis_label") or "").strip(),
                "manual_required_item_count": len(manual_required_items),
                "review_recommended_item_count": len(review_recommended_items),
                "compared_item_count": len(compared_items),
                "pending_item_names": [
                    str(item.get("product_name") or "未命名品项").strip() or "未命名品项"
                    for item in manual_required_items
                ],
                "next_actions": next_actions[:3],
                "review_path": row["review_path"],
                "reviewer_card_path": str(job_dir / "output" / "reviewer-card.md") if job_dir else "",
            }
        )

    return {
        "batch_id": batch_plan.batch_id,
        "job_count": len(items),
        "decision_breakdown": decision_breakdown,
        "items": items,
    }


def _render_reviewer_card_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 审核员批量决策汇总：{payload['batch_id']}",
        "",
        f"- 单据数：`{payload['job_count']}`",
    ]
    breakdown = payload.get("decision_breakdown") or {}
    for decision in REVIEWER_DECISION_ORDER:
        lines.append(f"- {REVIEWER_DECISION_LABELS[decision]}：`{breakdown.get(decision, 0)}`")

    lines.extend(["", "## 逐单结论", ""])
    for item in list(payload.get("items") or []):
        lines.append(
            f"- `{item['job_id']}` / `{item['group_key']}` / {item['decision_label']} / "
            f"合同={item.get('contract_amount') or '未识别'} / "
            f"报价={item.get('pricing_amount') or '未形成报价'} / "
            f"差额={item.get('difference') or '无法对比'}"
        )
        if item.get("primary_reason"):
            lines.append(f"  原因：{item['primary_reason']}")
        if item.get("pending_item_names"):
            lines.append(f"  未入账品项：{'、'.join(item['pending_item_names'])}")
        if item.get("next_actions"):
            lines.append(f"  建议动作：{'；'.join(item['next_actions'])}")
    return "\n".join(lines).strip() + "\n"


def materialize_job(job: ReviewJob, *, runtime_root: Path = DEFAULT_RUNTIME_ROOT) -> Path:
    job_dir = job_output_dir(job.job_id, runtime_root=runtime_root)
    input_dir = ensure_dir(job_dir / "input")
    ensure_dir(job_dir / "normalized")
    ensure_dir(job_dir / "output")

    for asset in job.assets:
        source_path = Path(asset.source_path)
        staged_name = slugify(source_path.stem) + source_path.suffix.lower()
        staged_path = input_dir / staged_name
        shutil.copy2(source_path, staged_path)
        asset.metadata["staged_input_path"] = str(staged_path)

    serialized_job = job.to_dict()
    write_json(job_dir / "job.json", serialized_job)
    return job_dir


def write_batch_summary(
    batch_plan: BatchPlan,
    *,
    batch_results: list[dict[str, Any]],
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
) -> dict[str, Any]:
    output_dir = batch_output_dir(batch_plan.batch_id, runtime_root=runtime_root)
    ensure_dir(output_dir)
    sorted_results = sort_batch_results(batch_results)

    summary_payload = {
        "batch_id": batch_plan.batch_id,
        "source_type": batch_plan.source_type,
        "source_channel": batch_plan.source_channel,
        "requested_actions": list(batch_plan.requested_actions),
        "job_count": len(sorted_results),
        "warnings": list(batch_plan.warnings),
        "jobs": sorted_results,
        "manifest": batch_plan.manifest,
        "created_at": batch_plan.created_at,
    }

    reviewer_card_summary_payload = _build_reviewer_card_summary_payload(batch_plan, sorted_results)
    queue_payload = _build_manual_review_queue_payload(batch_plan, sorted_results, reviewer_card_summary_payload)
    write_json(output_dir / "manual-review-queue.json", queue_payload)
    dashboard_payload = _build_batch_dashboard_payload(batch_plan, sorted_results, queue_payload)
    write_json(output_dir / "batch-dashboard.json", dashboard_payload)
    pricing_compare_payload = _build_pricing_compare_payload(batch_plan, sorted_results)
    write_json(output_dir / "pricing-compare.json", pricing_compare_payload)
    pricing_diagnosis_payload = _build_pricing_diagnosis_payload(batch_plan, sorted_results)
    write_json(output_dir / "pricing-compare-diagnosis.json", pricing_diagnosis_payload)
    pricing_replay_baseline_payload = _build_pricing_replay_baseline_payload(batch_plan, sorted_results)
    write_json(output_dir / "pricing-replay-baseline.json", pricing_replay_baseline_payload)
    write_json(output_dir / "reviewer-card-summary.json", reviewer_card_summary_payload)
    summary_payload["reviewer_card_summary"] = {
        "decision_breakdown": reviewer_card_summary_payload["decision_breakdown"],
        "job_count": reviewer_card_summary_payload["job_count"],
    }
    write_json(output_dir / "batch-summary.json", summary_payload)

    csv_rows = [
        {
            "job_id": row["job_id"],
            "group_key": row["group_key"],
            "status": row["status"],
            "review_priority": row.get("review_priority", "normal"),
            "review_priority_score": row.get("review_priority_score", PRIORITY_ORDER["normal"]),
            "review_priority_reason": row.get("review_priority_reason", ""),
            "actionable_priority": row.get("actionable_priority", "monitor"),
            "finding_count": row["finding_count"],
            "blocking_finding_count": row["blocking_finding_count"],
            "primary_contract_count": row["primary_contract_count"],
            "review_path": row["review_path"],
        }
        for row in sorted_results
    ]
    write_csv(
        output_dir / "batch-summary.csv",
        csv_rows,
        fieldnames=[
            "job_id",
            "group_key",
            "status",
            "review_priority",
            "review_priority_score",
            "review_priority_reason",
            "actionable_priority",
            "finding_count",
            "blocking_finding_count",
            "primary_contract_count",
            "review_path",
        ],
    )
    write_csv(
        output_dir / "pricing-compare.csv",
        list(pricing_compare_payload["items"]),
        fieldnames=[
            "job_id",
            "group_key",
            "pricing_compare_status",
            "pricing_compare_match_band",
            "pricing_compare_best_match_target",
            "pricing_compare_best_match_diff",
            "contract_total",
            "list_price_total",
            "discount_rate",
            "discounted_total",
            "pricing_total",
            "pricing_route",
            "review_path",
        ],
    )

    lines = [
        f"# 批次审阅汇总：{batch_plan.batch_id}",
        "",
        f"- source_type: `{batch_plan.source_type}`",
        f"- source_channel: `{batch_plan.source_channel}`",
        f"- requested_actions: `{', '.join(batch_plan.requested_actions)}`",
        f"- job_count: `{len(sorted_results)}`",
    ]
    if batch_plan.warnings:
        lines.append(f"- warnings: `{len(batch_plan.warnings)}`")
        lines.append("")
        lines.append("## 批次提醒")
        lines.append("")
        for warning in batch_plan.warnings:
            lines.append(f"- {warning}")
    lines.append("")
    lines.append("## 单据结果")
    lines.append("")
    for row in sorted_results:
        priority_reason = str(row.get("review_priority_reason") or "").strip()
        reason_suffix = f" / reason={priority_reason}" if priority_reason else ""
        lines.append(
            f"- `{row['job_id']}` / `{row['group_key']}` / `{row['status']}` / findings={row['finding_count']} / "
            f"blockers={row['blocking_finding_count']} / priority={row.get('review_priority', 'normal')}{reason_suffix}"
        )
    write_markdown(output_dir / "batch-summary.md", "\n".join(lines).strip() + "\n")

    queue_lines = [
        f"# 人工复核队列：{batch_plan.batch_id}",
        "",
        f"- queue_count: `{queue_payload['queue_count']}`",
        "",
        "## 待处理任务",
        "",
    ]
    for item in queue_payload["items"]:
        queue_lines.append(
            f"- `{item['job_id']}` / `{item['group_key']}` / priority={item['review_priority']} / "
            f"actionable={item['actionable_priority']} / status={item['status']} / conflicts={item['conflict_count']}"
        )
        if item["review_priority_reason"]:
            queue_lines.append(f"  review_priority_reason: {item['review_priority_reason']}")
        if item["manual_review_reasons"]:
            queue_lines.append(f"  manual_review_reasons: {', '.join(item['manual_review_reasons'])}")
        if item["issue_codes"]:
            queue_lines.append(f"  issue_codes: {', '.join(item['issue_codes'])}")
        if item["conflict_fields"]:
            queue_lines.append(f"  conflict_fields: {', '.join(item['conflict_fields'])}")
    write_markdown(output_dir / "manual-review-queue.md", "\n".join(queue_lines).strip() + "\n")

    pricing_compare_lines = [
        f"# 报价对比：{batch_plan.batch_id}",
        "",
        f"- item_count: `{pricing_compare_payload['item_count']}`",
        "",
        "## 对比明细",
        "",
    ]
    for item in pricing_compare_payload["items"]:
        pricing_compare_lines.append(
            f"- `{item['job_id']}` / `{item['group_key']}` / compare={item['pricing_compare_status'] or 'n/a'} / "
            f"contract_total={item['contract_total'] or 'n/a'} / pricing_total={item['pricing_total'] or 'n/a'}"
        )
        if item["list_price_total"]:
            pricing_compare_lines.append(f"  list_price_total: {item['list_price_total']}")
        if item["discount_rate"]:
            pricing_compare_lines.append(f"  discount_rate: {item['discount_rate']}")
        if item["discounted_total"]:
            pricing_compare_lines.append(f"  discounted_total: {item['discounted_total']}")
        if item["pricing_compare_best_match_target"]:
            pricing_compare_lines.append(
                f"  best_match: {item['pricing_compare_best_match_target']} / diff={item['pricing_compare_best_match_diff'] or 'n/a'}"
            )
    write_markdown(output_dir / "pricing-compare.md", "\n".join(pricing_compare_lines).strip() + "\n")

    diagnosis_lines = [
        f"# 报价诊断：{batch_plan.batch_id}",
        "",
        f"- item_count: `{pricing_diagnosis_payload['item_count']}`",
        "",
        "## 诊断分布",
        "",
    ]
    for diagnosis_code, count in pricing_diagnosis_payload["diagnosis_breakdown"].items():
        diagnosis_lines.append(f"- {diagnosis_code}: `{count}`")
    diagnosis_lines.extend(["", "## 逐单诊断", ""])
    for item in pricing_diagnosis_payload["items"]:
        diagnosis_lines.append(
            f"- `{item['job_id']}` / `{item['group_key']}` / diagnosis={item['diagnosis_code']} / "
            f"compare={item['pricing_compare_status'] or 'n/a'} / contract_total={item['contract_total'] or 'n/a'} / "
            f"pricing_total={item['pricing_total'] or 'n/a'}"
        )
        if item["template_id"]:
            diagnosis_lines.append(f"  template_id: {item['template_id']}")
        if item["issue_codes"]:
            diagnosis_lines.append(f"  issue_codes: {', '.join(item['issue_codes'])}")
        diagnosis_lines.append(f"  summary: {item['diagnosis_summary']}")
        if item["best_match_target"]:
            diagnosis_lines.append(
                f"  best_match: {item['best_match_target']} / diff={item['best_match_diff'] or 'n/a'}"
            )
        if item["formal_quote_reason"]:
            diagnosis_lines.append(f"  formal_quote_reason: {item['formal_quote_reason']}")
        if item["replay_reason"]:
            diagnosis_lines.append(f"  replay_reason: {item['replay_reason']}")
        if item["recommended_next_actions"]:
            diagnosis_lines.append(f"  next_actions: {'；'.join(item['recommended_next_actions'])}")
    write_markdown(output_dir / "pricing-compare-diagnosis.md", "\n".join(diagnosis_lines).strip() + "\n")

    replay_baseline_lines = [
        f"# 报价回放基准集：{batch_plan.batch_id}",
        "",
        f"- job_count: `{pricing_replay_baseline_payload['job_count']}`",
        "",
        "## 逐单台账",
        "",
    ]
    for item in pricing_replay_baseline_payload["items"]:
        replay_baseline_lines.append(
            f"- `{item['job_id']}` / `{item['group_key']}` / compare={item['pricing_compare_status'] or 'n/a'} / "
            f"pricing_route={item['pricing_route'] or 'n/a'}"
        )
        for ledger in item["item_ledger"]:
            replay_baseline_lines.append(
                f"  - {ledger.get('product_name') or '未命名品项'} / "
                f"合同={ledger.get('contract_amount') or 'n/a'} / "
                f"报价={ledger.get('pricing_amount') or 'n/a'} / "
                f"差额={ledger.get('difference') or 'n/a'} / "
                f"status={ledger.get('ledger_status') or 'n/a'}"
            )
    write_markdown(output_dir / "pricing-replay-baseline.md", "\n".join(replay_baseline_lines).strip() + "\n")
    write_markdown(
        output_dir / "reviewer-card-summary.md",
        _render_reviewer_card_summary_markdown(reviewer_card_summary_payload),
    )

    dashboard_lines = [
        f"# 批次首页：{batch_plan.batch_id}",
        "",
        f"- job_count: `{dashboard_payload['job_count']}`",
        f"- warning_count: `{dashboard_payload['warning_count']}`",
        f"- manual_queue_count: `{dashboard_payload['manual_queue_count']}`",
        f"- ocr_blocked_count: `{dashboard_payload['ocr_blocked_count']}`",
        f"- top_priority_job_ids: `{', '.join(dashboard_payload['top_priority_job_ids'])}`",
        "",
        "## 优先级分布",
        "",
    ]
    for priority, count in dashboard_payload["review_priority_breakdown"].items():
        dashboard_lines.append(f"- {priority}: `{count}`")
    dashboard_lines.extend(["", "## 可行动优先级分布", ""])
    for priority, count in dashboard_payload["actionable_priority_breakdown"].items():
        dashboard_lines.append(f"- {priority}: `{count}`")
    dashboard_lines.extend(["", "## 自动化状态分布", ""])
    for state, count in dashboard_payload["automation_state_breakdown"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    dashboard_lines.extend(["", "## 报价对比分布", ""])
    for state, count in dashboard_payload["pricing_compare_breakdown"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    dashboard_lines.extend(["", "## 根因分布", ""])
    for state, count in dashboard_payload["root_cause_breakdown"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    dashboard_lines.extend(["", "## 模板分布", ""])
    for state, count in dashboard_payload["template_breakdown"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    dashboard_lines.extend(["", "## 模板学习成效", ""])
    for state, count in dashboard_payload["template_learning_overview"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    if dashboard_payload["template_learning_false_positive_breakdown"]:
        dashboard_lines.extend(["", "## 模板误报分布", ""])
        for state, count in dashboard_payload["template_learning_false_positive_breakdown"].items():
            dashboard_lines.append(f"- {state}: `{count}`")
        if dashboard_payload["template_learning_top_templates"]:
            dashboard_lines.extend(["", "## 重点模板", ""])
            for item in dashboard_payload["template_learning_top_templates"]:
                dashboard_lines.append(
                    f"- `{item['template_id']}` / feedback={item['feedback_count']} / confirmed={item['confirmed_feedback_count']} / "
                    f"false_positive={item['false_positive_feedback_count']} / learned_fields={item['learned_field_count']} / "
                    f"dominant_issue={item['dominant_issue_code'] or 'n/a'}"
                )
                if item.get("recommended_action"):
                    dashboard_lines.append(f"  next_action: {item['recommended_action']} / {item.get('recommended_reason') or ''}".rstrip())
                if item.get("suggested_feedback_command"):
                    dashboard_lines.append(f"  suggested_feedback_command: `{item['suggested_feedback_command']}`")
                for action in item.get("quick_actions") or []:
                    dashboard_lines.append(
                        f"  quick_action: {action.get('label') or '未命名动作'} / `{action.get('action_type') or ''}` / `{action.get('command') or ''}`"
                    )
    write_markdown(output_dir / "batch-dashboard.md", "\n".join(dashboard_lines).strip() + "\n")
    write_markdown(output_dir / "workbench.html", _render_batch_workbench_html(
        batch_plan=batch_plan,
        dashboard_payload=dashboard_payload,
        queue_payload=queue_payload,
        pricing_diagnosis_payload=pricing_diagnosis_payload,
    ))
    return summary_payload


def _render_batch_workbench_html(
    *,
    batch_plan: BatchPlan,
    dashboard_payload: dict[str, Any],
    queue_payload: dict[str, Any],
    pricing_diagnosis_payload: dict[str, Any],
    ) -> str:
    def metric_cards(items: dict[str, int]) -> str:
        if not items:
            return "<p class='muted'>暂无数据</p>"
        return "".join(
            f"<div class='metric'><span>{html.escape(str(name))}</span><strong>{count}</strong></div>"
            for name, count in items.items()
        )

    queue_cards = "".join(
        (
            "<article class='card'>"
            f"<h3>{html.escape(str(item['group_key']))}</h3>"
            f"<p><strong>{html.escape(str(item['job_id']))}</strong></p>"
            f"<p>优先级：{html.escape(str(item['review_priority']))} / 可行动：{html.escape(str(item['actionable_priority']))}</p>"
            f"<p>Issue：{html.escape(', '.join(item.get('issue_codes') or [])) or '无'}</p>"
            f"<p>复核原因：{html.escape(', '.join(item.get('manual_review_reasons') or [])) or '无'}</p>"
            "</article>"
        )
        for item in queue_payload.get("items") or []
    )
    diagnosis_cards = "".join(
        (
            "<article class='card'>"
            f"<h3>{html.escape(str(item['group_key']))}</h3>"
            f"<p>诊断：{html.escape(str(item['diagnosis_code']))}</p>"
            f"<p>模板：{html.escape(str(item.get('template_id') or '')) or '无'}</p>"
            f"<p>Issue：{html.escape(', '.join(item.get('issue_codes') or [])) or '无'}</p>"
            f"<p>{html.escape(str(item['diagnosis_summary']))}</p>"
            "</article>"
        )
        for item in pricing_diagnosis_payload.get("items") or []
    )
    template_learning_cards = "".join(
        (
            "<article class='card'>"
            f"<h3>{html.escape(str(item.get('template_id') or ''))}</h3>"
            f"<p>反馈：{html.escape(str(item.get('feedback_count') or 0))} / 确认：{html.escape(str(item.get('confirmed_feedback_count') or 0))} / 误报：{html.escape(str(item.get('false_positive_feedback_count') or 0))}</p>"
            f"<p>已学习字段：{html.escape(str(item.get('learned_field_count') or 0))} / trust_score：{html.escape(str(item.get('trust_score') or ''))}</p>"
            f"<p>高频问题：{html.escape(str(item.get('dominant_issue_code') or '无'))}</p>"
            f"<p><strong>建议动作：</strong>{html.escape(str(item.get('recommended_action') or '继续积累样本'))}</p>"
            f"<p>{html.escape(str(item.get('recommended_reason') or ''))}</p>"
            f"<p><strong>建议反馈命令：</strong></p><p><code>{html.escape(str(item.get('suggested_feedback_command') or ''))}</code></p>"
            f"{_render_quick_actions_html(item.get('quick_actions') or [])}"
            "</article>"
        )
        for item in dashboard_payload.get("template_learning_top_templates") or []
    )
    empty_queue_html = "<p class='muted'>当前没有待处理任务</p>"
    empty_diagnosis_html = "<p class='muted'>当前没有诊断项</p>"
    empty_template_learning_html = "<p class='muted'>当前没有模板学习样本</p>"
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<title>合同审核工作台 - {html.escape(batch_plan.batch_id)}</title>"
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue',sans-serif;"
        "margin:0;background:#f6f2ea;color:#182018;}header{padding:32px 40px;background:#153226;color:#f6f2ea;}"
        "main{padding:24px 40px;display:grid;gap:24px;}section{background:#fff;border-radius:18px;padding:20px 22px;"
        "box-shadow:0 10px 30px rgba(21,50,38,.08);}h1,h2,h3{margin:0 0 12px;}h2{font-size:18px;}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;}"
        ".metric,.card{border:1px solid #e6dccd;border-radius:14px;padding:14px;background:#fffdfa;}"
        ".metric span,.muted{color:#6a706a;font-size:13px;display:block;margin-bottom:6px;}"
        ".metric strong{font-size:26px;}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;}"
        "p{margin:6px 0 0;line-height:1.5;}</style></head><body>"
        f"<header><h1>合同审核工作台</h1><p>批次：{html.escape(batch_plan.batch_id)} / 渠道：{html.escape(batch_plan.source_channel)}</p></header>"
        "<main>"
        "<section><h2>概览</h2><div class='grid'>"
        f"<div class='metric'><span>合同数</span><strong>{dashboard_payload.get('job_count', 0)}</strong></div>"
        f"<div class='metric'><span>人工队列</span><strong>{dashboard_payload.get('manual_queue_count', 0)}</strong></div>"
        f"<div class='metric'><span>OCR 阻塞</span><strong>{dashboard_payload.get('ocr_blocked_count', 0)}</strong></div>"
        f"<div class='metric'><span>Top Job</span><strong>{html.escape(', '.join(dashboard_payload.get('top_priority_job_ids') or []) or '无')}</strong></div>"
        "</div></section>"
        f"<section><h2>可行动优先级</h2><div class='grid'>{metric_cards(dashboard_payload.get('actionable_priority_breakdown') or {})}</div></section>"
        f"<section><h2>根因分布</h2><div class='grid'>{metric_cards(dashboard_payload.get('root_cause_breakdown') or {})}</div></section>"
        f"<section><h2>模板分布</h2><div class='grid'>{metric_cards(dashboard_payload.get('template_breakdown') or {})}</div></section>"
        f"<section><h2>模板学习成效</h2><div class='grid'>{metric_cards(dashboard_payload.get('template_learning_overview') or {})}</div></section>"
        f"<section><h2>模板误报分布</h2><div class='grid'>{metric_cards(dashboard_payload.get('template_learning_false_positive_breakdown') or {})}</div></section>"
        f"<section><h2>重点模板</h2><div class='cards'>{template_learning_cards or empty_template_learning_html}</div></section>"
        f"<section><h2>人工复核队列</h2><div class='cards'>{queue_cards or empty_queue_html}</div></section>"
        f"<section><h2>报价诊断</h2><div class='cards'>{diagnosis_cards or empty_diagnosis_html}</div></section>"
        "</main></body></html>"
    )


def _render_quick_actions_html(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return ""
    items = "".join(
        (
            "<li>"
            f"<strong>{html.escape(str(action.get('label') or '未命名动作'))}</strong>"
            f" <code>{html.escape(str(action.get('command') or ''))}</code>"
            "</li>"
        )
        for action in actions
    )
    return f"<p><strong>快捷操作：</strong></p><ul>{items}</ul>"
