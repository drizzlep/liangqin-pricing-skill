from __future__ import annotations

import csv
from pathlib import Path
import re
from typing import Any

from batch_runtime import DEFAULT_RUNTIME_ROOT, batch_output_dir, read_json, write_json, write_markdown


CASE_STATUS_ORDER = {
    "reviewed": 0,
    "missing_runtime_case": 1,
    "unexpected_runtime_case": 2,
}
EMPTY_PRIMARY_CHECK_VALUES = {"", "-", "n/a", "na", "none", "无"}
QUOTE_CONFLICT_CODES = {
    "quote_conflict",
    "discount_mismatch",
    "quantity_mismatch",
    "add_on_mismatch",
}


def default_ground_truth_path(batch_dir: Path) -> Path:
    return batch_dir.parent / "acceptance-ground-truth.csv"


def build_acceptance_report(
    *,
    batch_dir: Path,
    runtime_root: Path = DEFAULT_RUNTIME_ROOT,
    ground_truth_path: Path | None = None,
) -> dict[str, Any]:
    resolved_batch_dir = batch_dir.expanduser().resolve()
    resolved_runtime_root = runtime_root.expanduser().resolve()
    resolved_ground_truth_path = (
        ground_truth_path.expanduser().resolve()
        if ground_truth_path is not None
        else default_ground_truth_path(resolved_batch_dir)
    )
    if not resolved_ground_truth_path.exists():
        raise FileNotFoundError(f"未找到验收标注文件：{resolved_ground_truth_path}")

    expected_cases = _load_ground_truth_rows(resolved_ground_truth_path)
    runtime_cases = _load_runtime_cases(batch_id=resolved_batch_dir.name, runtime_root=resolved_runtime_root)

    items: list[dict[str, Any]] = []
    verdict_match_count = 0
    issue_match_count = 0
    primary_check_count = 0
    primary_check_hit_count = 0
    false_negative_count = 0
    false_positive_count = 0
    missing_case_count = 0

    for expected_case in expected_cases:
        case_key = expected_case["case_key"]
        runtime_case = runtime_cases.pop(case_key, None)
        item = _evaluate_expected_case(expected_case=expected_case, runtime_case=runtime_case)
        items.append(item)

        if item["case_status"] == "missing_runtime_case":
            missing_case_count += 1
        if item["verdict_match"]:
            verdict_match_count += 1
        if item["issue_match"]:
            issue_match_count += 1
        if item["primary_check_required"]:
            primary_check_count += 1
            if item["primary_check_match"]:
                primary_check_hit_count += 1
        if item["false_negative"]:
            false_negative_count += 1
        if item["false_positive"]:
            false_positive_count += 1

    unexpected_items = [
        _build_unexpected_runtime_case(case_key=case_key, runtime_case=runtime_case)
        for case_key, runtime_case in runtime_cases.items()
    ]
    items.extend(sorted(unexpected_items, key=lambda item: item["case_key"]))
    unexpected_case_count = len(unexpected_items)

    summary = {
        "total_case_count": len(expected_cases),
        "reviewed_case_count": len([item for item in items if item["case_status"] == "reviewed"]),
        "missing_case_count": missing_case_count,
        "unexpected_case_count": unexpected_case_count,
        "verdict_match_count": verdict_match_count,
        "verdict_match_rate": _safe_rate(verdict_match_count, len(expected_cases)),
        "issue_match_count": issue_match_count,
        "issue_match_rate": _safe_rate(issue_match_count, len(expected_cases)),
        "primary_check_count": primary_check_count,
        "primary_check_hit_count": primary_check_hit_count,
        "primary_check_hit_rate": _safe_rate(primary_check_hit_count, primary_check_count),
        "false_negative_count": false_negative_count,
        "false_positive_count": false_positive_count,
        "ready_to_release": missing_case_count == 0 and false_negative_count == 0,
        "blocking_case_keys": [
            item["case_key"]
            for item in items
            if item["case_status"] == "missing_runtime_case" or item["false_negative"]
        ],
    }

    payload = {
        "batch_id": resolved_batch_dir.name,
        "batch_dir": str(resolved_batch_dir),
        "runtime_root": str(resolved_runtime_root),
        "ground_truth_path": str(resolved_ground_truth_path),
        "summary": summary,
        "items": sorted(
            items,
            key=lambda item: (CASE_STATUS_ORDER.get(str(item.get("case_status") or ""), 9), str(item.get("case_key") or "")),
        ),
    }

    report_dir = batch_output_dir(resolved_batch_dir.name, runtime_root=resolved_runtime_root)
    write_json(report_dir / "acceptance-report.json", payload)
    write_markdown(report_dir / "acceptance-report.md", _render_acceptance_markdown(payload))
    payload["report_json_path"] = str(report_dir / "acceptance-report.json")
    payload["report_markdown_path"] = str(report_dir / "acceptance-report.md")
    return payload


def _load_ground_truth_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw_row in reader:
            case_key = str(raw_row.get("case_key") or "").strip()
            if not case_key:
                continue
            rows.append(
                {
                    "case_key": case_key,
                    "expected_bucket": str(raw_row.get("expected_bucket") or "").strip(),
                    "expected_verdict": str(raw_row.get("expected_verdict") or "").strip(),
                    "expected_issue_codes": _normalize_issue_codes(raw_row.get("expected_issue_codes") or ""),
                    "expected_primary_check": _normalize_primary_check(raw_row.get("expected_primary_check") or ""),
                    "notes": str(raw_row.get("notes") or "").strip(),
                }
            )
    return rows


def _load_runtime_cases(*, batch_id: str, runtime_root: Path) -> dict[str, dict[str, Any]]:
    summary_path = batch_output_dir(batch_id, runtime_root=runtime_root) / "batch-summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"未找到批次输出：{summary_path}")

    summary_payload = read_json(summary_path)
    runtime_cases: dict[str, dict[str, Any]] = {}
    for row in summary_payload.get("jobs") or []:
        case_key = str(row.get("group_key") or "").strip()
        if not case_key:
            continue
        review_payload = _load_review_payload(row)
        actual_issue_codes = _normalize_issue_codes((review_payload.get("review_analysis") or {}).get("issue_codes") or [])
        actual_primary_checks = _collect_primary_checks(review_payload)
        review_card = review_payload.get("review_card") or {}
        runtime_cases[case_key] = {
            "job_id": str(row.get("job_id") or "").strip(),
            "case_key": case_key,
            "review_path": str(row.get("review_path") or "").strip(),
            "actual_verdict": str(review_card.get("verdict") or "").strip(),
            "actual_issue_codes": actual_issue_codes,
            "actual_primary_checks": actual_primary_checks,
            "actual_bucket": _derive_bucket(
                verdict=str(review_card.get("verdict") or "").strip(),
                issue_codes=actual_issue_codes,
            ),
        }
    return runtime_cases


def _load_review_payload(row: dict[str, Any]) -> dict[str, Any]:
    job_dir = Path(str(row.get("job_dir") or "")).expanduser()
    candidates = []
    if job_dir:
        candidates.append(job_dir / "output" / "review.json")
    review_path = str(row.get("review_path") or "").strip()
    if review_path:
        candidates.append(Path(review_path).with_suffix(".json"))

    for candidate in candidates:
        if candidate.exists():
            return read_json(candidate)
    return {}


def _evaluate_expected_case(
    *,
    expected_case: dict[str, Any],
    runtime_case: dict[str, Any] | None,
) -> dict[str, Any]:
    expected_issue_codes = list(expected_case["expected_issue_codes"])
    expected_primary_check = str(expected_case["expected_primary_check"] or "").strip()

    if runtime_case is None:
        return {
            "case_key": expected_case["case_key"],
            "case_status": "missing_runtime_case",
            "expected_bucket": expected_case["expected_bucket"],
            "actual_bucket": "",
            "expected_verdict": expected_case["expected_verdict"],
            "actual_verdict": "",
            "verdict_match": False,
            "expected_issue_codes": expected_issue_codes,
            "actual_issue_codes": [],
            "missing_issue_codes": expected_issue_codes,
            "unexpected_issue_codes": [],
            "issue_match": False,
            "expected_primary_check": expected_primary_check,
            "actual_primary_checks": [],
            "primary_check_required": bool(expected_primary_check),
            "primary_check_match": False if expected_primary_check else None,
            "false_negative": expected_case["expected_verdict"] == "manual_review_required",
            "false_positive": False,
            "job_id": "",
            "review_path": "",
            "notes": expected_case["notes"],
        }

    actual_issue_codes = list(runtime_case["actual_issue_codes"])
    missing_issue_codes = [code for code in expected_issue_codes if code not in actual_issue_codes]
    unexpected_issue_codes = [code for code in actual_issue_codes if code not in expected_issue_codes]
    issue_match = not missing_issue_codes and (
        bool(expected_issue_codes) or not actual_issue_codes
    )
    verdict_match = runtime_case["actual_verdict"] == expected_case["expected_verdict"]
    primary_check_required = bool(expected_primary_check)
    primary_check_match = (
        _primary_check_matches(expected_primary_check, runtime_case["actual_primary_checks"])
        if primary_check_required
        else None
    )
    false_negative = expected_case["expected_verdict"] == "manual_review_required" and (
        not verdict_match or not issue_match
    )
    false_positive = expected_case["expected_verdict"] == "recommended_release" and (
        runtime_case["actual_verdict"] != "recommended_release" or bool(actual_issue_codes)
    )
    return {
        "case_key": expected_case["case_key"],
        "case_status": "reviewed",
        "expected_bucket": expected_case["expected_bucket"],
        "actual_bucket": runtime_case["actual_bucket"],
        "expected_verdict": expected_case["expected_verdict"],
        "actual_verdict": runtime_case["actual_verdict"],
        "verdict_match": verdict_match,
        "expected_issue_codes": expected_issue_codes,
        "actual_issue_codes": actual_issue_codes,
        "missing_issue_codes": missing_issue_codes,
        "unexpected_issue_codes": unexpected_issue_codes,
        "issue_match": issue_match,
        "expected_primary_check": expected_primary_check,
        "actual_primary_checks": list(runtime_case["actual_primary_checks"]),
        "primary_check_required": primary_check_required,
        "primary_check_match": primary_check_match,
        "false_negative": false_negative,
        "false_positive": false_positive,
        "job_id": runtime_case["job_id"],
        "review_path": runtime_case["review_path"],
        "notes": expected_case["notes"],
    }


def _build_unexpected_runtime_case(*, case_key: str, runtime_case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_key": case_key,
        "case_status": "unexpected_runtime_case",
        "expected_bucket": "",
        "actual_bucket": runtime_case["actual_bucket"],
        "expected_verdict": "",
        "actual_verdict": runtime_case["actual_verdict"],
        "verdict_match": False,
        "expected_issue_codes": [],
        "actual_issue_codes": list(runtime_case["actual_issue_codes"]),
        "missing_issue_codes": [],
        "unexpected_issue_codes": list(runtime_case["actual_issue_codes"]),
        "issue_match": False,
        "expected_primary_check": "",
        "actual_primary_checks": list(runtime_case["actual_primary_checks"]),
        "primary_check_required": False,
        "primary_check_match": None,
        "false_negative": False,
        "false_positive": False,
        "job_id": runtime_case["job_id"],
        "review_path": runtime_case["review_path"],
        "notes": "运行结果存在，但 ground truth 未标注。",
    }


def _normalize_issue_codes(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value or "").split("|")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        code = str(item or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def _normalize_primary_check(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized.lower() in EMPTY_PRIMARY_CHECK_VALUES:
        return ""
    return normalized


def _collect_primary_checks(review_payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    review_card = review_payload.get("review_card") or {}
    for raw_value in list(review_card.get("next_actions") or []):
        value = str(raw_value or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    for issue in review_payload.get("issues") or []:
        value = str((issue or {}).get("recommended_check") or "").strip()
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _derive_bucket(*, verdict: str, issue_codes: list[str]) -> str:
    issue_code_set = set(issue_codes)
    if "calculation_error" in issue_code_set:
        return "calc_error"
    if issue_code_set & QUOTE_CONFLICT_CODES:
        return "quote_conflict"
    if verdict == "recommended_release" and not issue_code_set:
        return "normal"
    return "watch"


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _primary_check_matches(expected_value: str, actual_values: list[str]) -> bool:
    normalized_expected = str(expected_value or "").strip()
    if not normalized_expected:
        return False
    for actual_value in actual_values:
        if normalized_expected in str(actual_value or ""):
            return True

    keyword = re.sub(r"[请先优继续再是否人工复核检查对这份合同的\s、，。；:：/]+", "", normalized_expected)
    keyword = keyword.replace("核对", "")
    if not keyword:
        return False
    return any(keyword in str(actual_value or "") for actual_value in actual_values)


def _render_acceptance_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# 发布验收报告：{payload['batch_id']}",
        "",
        f"- ground_truth: `{payload['ground_truth_path']}`",
        f"- total_case_count: `{summary['total_case_count']}`",
        f"- reviewed_case_count: `{summary['reviewed_case_count']}`",
        f"- missing_case_count: `{summary['missing_case_count']}`",
        f"- unexpected_case_count: `{summary['unexpected_case_count']}`",
        f"- verdict_match_count: `{summary['verdict_match_count']}` / rate=`{summary['verdict_match_rate']}`",
        f"- issue_match_count: `{summary['issue_match_count']}` / rate=`{summary['issue_match_rate']}`",
        f"- primary_check_hit_count: `{summary['primary_check_hit_count']}` / `{summary['primary_check_count']}` / rate=`{summary['primary_check_hit_rate']}`",
        f"- false_negative_count: `{summary['false_negative_count']}`",
        f"- false_positive_count: `{summary['false_positive_count']}`",
        f"- ready_to_release: `{summary['ready_to_release']}`",
    ]
    if summary["blocking_case_keys"]:
        lines.extend(["", "## 阻塞样本", ""])
        for case_key in summary["blocking_case_keys"]:
            lines.append(f"- `{case_key}`")

    lines.extend(["", "## 样本明细", ""])
    for item in payload["items"]:
        lines.append(
            f"- `{item['case_key']}` / status={item['case_status']} / verdict={item['actual_verdict'] or 'n/a'} / "
            f"expected={item['expected_verdict'] or 'n/a'} / actual_bucket={item['actual_bucket'] or 'n/a'}"
        )
        if item["expected_issue_codes"]:
            lines.append(f"  expected_issue_codes: {', '.join(item['expected_issue_codes'])}")
        if item["actual_issue_codes"]:
            lines.append(f"  actual_issue_codes: {', '.join(item['actual_issue_codes'])}")
        if item["missing_issue_codes"]:
            lines.append(f"  missing_issue_codes: {', '.join(item['missing_issue_codes'])}")
        if item["unexpected_issue_codes"]:
            lines.append(f"  unexpected_issue_codes: {', '.join(item['unexpected_issue_codes'])}")
        if item["expected_primary_check"]:
            lines.append(f"  expected_primary_check: {item['expected_primary_check']}")
        if item["actual_primary_checks"]:
            lines.append(f"  actual_primary_checks: {'；'.join(item['actual_primary_checks'])}")
        if item["review_path"]:
            lines.append(f"  review_path: {item['review_path']}")
    return "\n".join(lines).strip() + "\n"
