from __future__ import annotations

import csv
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from job_models import BatchPlan, ReviewJob


DEFAULT_RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"
PRIORITY_ORDER = {"p0": 0, "p1": 1, "p2": 2, "normal": 3}


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
            str(row.get("job_id") or ""),
        ),
    )


def _build_manual_review_queue_payload(batch_plan: BatchPlan, sorted_results: list[dict[str, Any]]) -> dict[str, Any]:
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
            "risk_flags": list(row.get("risk_flags") or []),
            "review_path": row["review_path"],
            "job_dir": row["job_dir"],
        }
        for row in sorted_results
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
    ocr_blocked_count = 0

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

    return {
        "batch_id": batch_plan.batch_id,
        "source_type": batch_plan.source_type,
        "source_channel": batch_plan.source_channel,
        "job_count": len(sorted_results),
        "warning_count": len(batch_plan.warnings),
        "manual_queue_count": queue_payload["queue_count"],
        "ocr_blocked_count": ocr_blocked_count,
        "review_priority_breakdown": review_priority_breakdown,
        "automation_state_breakdown": automation_state_breakdown,
        "pricing_compare_breakdown": pricing_compare_breakdown,
        "top_priority_job_ids": [item["job_id"] for item in queue_payload["items"][:10]],
        "top_priority_groups": [item["group_key"] for item in queue_payload["items"][:10]],
    }


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

    write_json(output_dir / "batch-summary.json", summary_payload)
    queue_payload = _build_manual_review_queue_payload(batch_plan, sorted_results)
    write_json(output_dir / "manual-review-queue.json", queue_payload)
    dashboard_payload = _build_batch_dashboard_payload(batch_plan, sorted_results, queue_payload)
    write_json(output_dir / "batch-dashboard.json", dashboard_payload)
    pricing_compare_payload = _build_pricing_compare_payload(batch_plan, sorted_results)
    write_json(output_dir / "pricing-compare.json", pricing_compare_payload)
    pricing_diagnosis_payload = _build_pricing_diagnosis_payload(batch_plan, sorted_results)
    write_json(output_dir / "pricing-compare-diagnosis.json", pricing_diagnosis_payload)

    csv_rows = [
        {
            "job_id": row["job_id"],
            "group_key": row["group_key"],
            "status": row["status"],
            "review_priority": row.get("review_priority", "normal"),
            "review_priority_score": row.get("review_priority_score", PRIORITY_ORDER["normal"]),
            "review_priority_reason": row.get("review_priority_reason", ""),
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
            f"status={item['status']} / conflicts={item['conflict_count']}"
        )
        if item["review_priority_reason"]:
            queue_lines.append(f"  review_priority_reason: {item['review_priority_reason']}")
        if item["manual_review_reasons"]:
            queue_lines.append(f"  manual_review_reasons: {', '.join(item['manual_review_reasons'])}")
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
    dashboard_lines.extend(["", "## 自动化状态分布", ""])
    for state, count in dashboard_payload["automation_state_breakdown"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    dashboard_lines.extend(["", "## 报价对比分布", ""])
    for state, count in dashboard_payload["pricing_compare_breakdown"].items():
        dashboard_lines.append(f"- {state}: `{count}`")
    write_markdown(output_dir / "batch-dashboard.md", "\n".join(dashboard_lines).strip() + "\n")
    return summary_payload
