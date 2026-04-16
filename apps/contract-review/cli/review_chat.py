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
from manual_batch import build_review_jobs  # noqa: E402
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
    parser.add_argument("--ocr-backend", choices=["disabled", "paddleocr"], default="paddleocr")
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


def _label_verdict(verdict: str) -> str:
    mapping = {
        "recommended_release": "建议放行",
        "pass_with_watch": "可放行但建议留意",
        "manual_review_required": "建议人工核对",
    }
    return mapping.get(verdict, verdict or "待判断")


def _render_review_reply(review_payload: dict[str, Any]) -> tuple[str, str]:
    review_card = review_payload.get("review_card") or {}
    issues = list(review_payload.get("issues") or [])
    contract_total = str(review_card.get("contract_total") or "").strip() or "未识别"
    pricing_total = str(review_card.get("pricing_total") or "").strip() or "未回放"
    delta = ""
    if issues:
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
    if cause_lines:
        lines.append("怀疑原因：")
        for index, cause in enumerate(cause_lines[:3], start=1):
            lines.append(f"{index}. {cause}")
    if next_actions:
        lines.append("请人工核对：")
        for index, action in enumerate(next_actions[:3], start=1):
            lines.append(f"{index}. {action}")
    if next_question and next_question not in next_actions:
        lines.append(next_question)
    return "\n".join(lines).strip(), next_question


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

    command = str(args.text or "").strip()
    if args.batch_dir:
        summary = _run_batch_review(
            batch_dir=Path(args.batch_dir).expanduser().resolve(),
            runtime_root=runtime_root,
            extraction_config=ExtractionConfig(
                ocr_backend=args.ocr_backend,
                paddleocr_lang=args.paddleocr_lang,
                paddleocr_device=args.paddleocr_device,
                force_ocr_for_documents=args.force_ocr_for_documents,
            ),
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
        payload = _handle_show_next(runtime_root=runtime_root, state_root=state_root, state=state)

    _emit(payload, output_mode=args.output_mode)
    return payload


def main(argv: list[str] | None = None) -> int:
    run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
