#!/usr/bin/env python3
"""Run a reusable OpenClaw regression prompt suite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SUITE_PATH = Path(__file__).resolve().parent.parent / "references" / "current" / "openclaw-prompt-suite.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OpenClaw regression prompt suite for liangqin-pricing.")
    parser.add_argument("--suite", default=str(DEFAULT_SUITE_PATH), help="Path to suite JSON.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--thinking", default="minimal", help="OpenClaw thinking level.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-case timeout in seconds.")
    parser.add_argument("--case-id", action="append", default=[], help="Only run selected case id. Can repeat.")
    parser.add_argument("--category", action="append", default=[], help="Only run selected case category. Can repeat.")
    parser.add_argument("--limit", type=int, default=0, help="Only run first N cases after filtering.")
    parser.add_argument("--repeat-each", type=int, default=1, help="Run each selected case this many times unless case.repeat_count overrides it.")
    parser.add_argument("--max-retries", type=int, default=1, help="Retry incomplete case outputs this many additional times.")
    parser.add_argument("--publish-skill", action="store_true", help="Publish skill before running suite.")
    parser.add_argument("--reset-quote-sessions", action="store_true", help="Reset stale quote sessions before running suite.")
    parser.add_argument(
        "--include-feishu",
        action="store_true",
        help="When resetting quote sessions, also reset Feishu quote sessions.",
    )
    parser.add_argument("--output", help="Optional explicit output JSON path.")
    return parser.parse_args(argv)


def load_suite(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise SystemExit("suite JSON must contain cases[]")
    return payload


def filter_cases(cases: list[dict[str, Any]], case_ids: list[str], categories: list[str], limit: int) -> list[dict[str, Any]]:
    case_id_set = set(case_ids)
    category_set = set(categories)
    filtered = [
        case
        for case in cases
        if (not case_id_set or str(case.get("id", "")) in case_id_set)
        and (not category_set or str(case.get("category", "")) in category_set)
    ]
    if limit > 0:
        return filtered[:limit]
    return filtered


def extract_json_payload(raw: str) -> dict[str, Any] | None:
    lines = [line for line in raw.splitlines() if line.strip()]
    for start in range(len(lines)):
        candidate = "\n".join(lines[start:])
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def final_text_from_payload(payload: dict[str, Any] | None, raw_stdout: str) -> str:
    if not isinstance(payload, dict):
        return raw_stdout
    texts = [item.get("text", "") for item in payload.get("result", {}).get("payloads", []) if item.get("text")]
    return texts[-1] if texts else raw_stdout


def is_incomplete_text(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    if normalized == "<end_turn>":
        return True
    if "[TOOL_CALL]" in normalized or "{tool =>" in normalized:
        return True
    if normalized.endswith(("：", ":")):
        return True
    return False


def evaluate_text(
    text: str,
    expected_keywords: list[str],
    forbidden_keywords: list[str],
    expected_any_keywords: list[list[str]] | None = None,
) -> dict[str, Any]:
    missing = [keyword for keyword in expected_keywords if keyword and keyword not in text]
    missing_any_groups = [
        group for group in (expected_any_keywords or []) if group and not any(keyword and keyword in text for keyword in group)
    ]
    forbidden_hits = [keyword for keyword in forbidden_keywords if keyword and keyword in text]
    passed = not missing and not missing_any_groups and not forbidden_hits
    return {
        "passed": passed,
        "missing_expected_keywords": missing,
        "missing_expected_any_groups": missing_any_groups,
        "forbidden_keyword_hits": forbidden_hits,
    }


def validate_output_contract_text(text: str) -> bool:
    normalized = str(text or "")
    if "正式报价：" not in normalized and "参考总价（仅供参考）：" not in normalized:
        return False
    return bool(
        ("产品：" in normalized or "产品1：" in normalized)
        and "已确认：" in normalized
        and "这次按" in normalized
        and "计算过程：" in normalized
        and "小计：" in normalized
    )


def evaluate_validation_assertions(
    *,
    text: str,
    evaluation: dict[str, Any],
    assertion_names: list[str],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name in assertion_names:
        if name == "no_boundary_pollution":
            passed = not evaluation.get("forbidden_keyword_hits")
        elif name == "formula_correct":
            passed = (
                ("正式报价：" in text or "参考总价（仅供参考）：" in text)
                and "计算过程：" in text
                and "小计：" in text
                and any(token in text for token in ("=", "×", "*"))
            )
        elif name == "output_contract_pass":
            passed = validate_output_contract_text(text)
        elif name == "limit_blocked":
            passed = "正式报价：" not in text and any(keyword in text for keyword in ("不能", "超出范围", "只支持"))
        else:
            passed = bool(evaluation.get("passed"))
        results[name] = {"passed": passed}
    return results


def default_output_path(skill_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return skill_dir / "reports" / "validation" / f"openclaw-prompt-suite-{timestamp}.json"


def run_step(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=True)


def build_reset_command(scripts_dir: Path, *, include_feishu: bool) -> list[str]:
    command = [sys.executable, str(scripts_dir / "reset_quote_sessions.py"), "--apply"]
    if include_feishu:
        command.append("--include-feishu")
    return command


def aggregate_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    missing_expected_keywords: list[str] = []
    missing_expected_any_groups: list[list[str]] = []
    forbidden_keyword_hits: list[str] = []
    validation_assertions: dict[str, dict[str, Any]] = {}

    for evaluation in evaluations:
        for keyword in evaluation.get("missing_expected_keywords", []):
            if keyword not in missing_expected_keywords:
                missing_expected_keywords.append(keyword)
        for group in evaluation.get("missing_expected_any_groups", []):
            normalized_group = [str(keyword) for keyword in group]
            if normalized_group not in missing_expected_any_groups:
                missing_expected_any_groups.append(normalized_group)
        for keyword in evaluation.get("forbidden_keyword_hits", []):
            if keyword not in forbidden_keyword_hits:
                forbidden_keyword_hits.append(keyword)
        for assertion_name, assertion_result in (evaluation.get("validation_assertions") or {}).items():
            entry = validation_assertions.setdefault(assertion_name, {"passed": True, "passed_runs": 0, "failed_runs": 0})
            if assertion_result.get("passed"):
                entry["passed_runs"] += 1
            else:
                entry["failed_runs"] += 1
                entry["passed"] = False

    return {
        "passed": all(bool(evaluation.get("passed")) for evaluation in evaluations),
        "missing_expected_keywords": missing_expected_keywords,
        "missing_expected_any_groups": missing_expected_any_groups,
        "forbidden_keyword_hits": forbidden_keyword_hits,
        "validation_assertions": validation_assertions,
    }


def infer_validation_assertion_names(case: dict[str, Any]) -> list[str]:
    names: list[str] = [str(name) for name in case.get("validation_assertions", []) if str(name).strip()]
    expected_keywords = [str(entry) for entry in case.get("expected_keywords", [])]
    if case.get("forbidden_keywords") and "no_boundary_pollution" not in names:
        names.append("no_boundary_pollution")
    if any(keyword in {"正式报价", "参考总价（仅供参考）"} for keyword in expected_keywords):
        if "formula_correct" not in names:
            names.append("formula_correct")
        if "output_contract_pass" not in names:
            names.append("output_contract_pass")
    return names


def summarize_validation_assertions(results: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for result in results:
        for assertion_name, assertion_result in (result.get("evaluation", {}).get("validation_assertions") or {}).items():
            entry = summary.setdefault(assertion_name, {"passed": 0, "failed": 0})
            if assertion_result.get("passed"):
                entry["passed"] += 1
            else:
                entry["failed"] += 1
    return summary


def run_case(case: dict[str, Any], *, thinking: str, timeout: int, max_retries: int, repeat_each: int = 1) -> dict[str, Any]:
    case_id = str(case.get("id", "case"))
    message = str(case.get("message", ""))
    expected_keywords = [str(entry) for entry in case.get("expected_keywords", [])]
    forbidden_keywords = [str(entry) for entry in case.get("forbidden_keywords", [])]
    expected_any_keywords = [
        [str(keyword) for keyword in group if str(keyword)]
        for group in case.get("expected_any_keywords", [])
        if isinstance(group, list)
    ]
    validation_assertion_names = infer_validation_assertion_names(case)
    run_count = max(1, int(case.get("repeat_count", repeat_each) or 1))
    runs: list[dict[str, Any]] = []

    for run_index in range(run_count):
        attempts: list[dict[str, Any]] = []
        attempt_count = max(1, int(max_retries) + 1)
        for attempt_index in range(attempt_count):
            session_id = f"suite-{case_id}-{datetime.now().strftime('%H%M%S')}-r{run_index + 1}-a{attempt_index + 1}"
            command = [
                "openclaw",
                "agent",
                "--session-id",
                session_id,
                "--message",
                message,
                "--json",
                "--thinking",
                thinking,
                "--timeout",
                str(timeout),
            ]
            result = run_step(command)
            parsed = extract_json_payload(result.stdout)
            final_text = final_text_from_payload(parsed, result.stdout)
            evaluation = evaluate_text(
                final_text,
                expected_keywords,
                forbidden_keywords,
                expected_any_keywords,
            )
            evaluation["validation_assertions"] = evaluate_validation_assertions(
                text=final_text,
                evaluation=evaluation,
                assertion_names=validation_assertion_names,
            )
            if evaluation["validation_assertions"]:
                evaluation["passed"] = bool(evaluation.get("passed")) and all(
                    assertion["passed"] for assertion in evaluation["validation_assertions"].values()
                )
            attempts.append(
                {
                    "session_id": session_id,
                    "returncode": result.returncode,
                    "stderr": result.stderr,
                    "final_text": final_text,
                    "evaluation": evaluation,
                }
            )
            if result.returncode == 0 and not is_incomplete_text(final_text):
                break

        latest_attempt = attempts[-1]
        runs.append(
            {
                "run_index": run_index + 1,
                "session_id": latest_attempt["session_id"],
                "returncode": latest_attempt["returncode"],
                "stderr": latest_attempt["stderr"],
                "final_text": latest_attempt["final_text"],
                "evaluation": latest_attempt["evaluation"],
                "attempt_count": len(attempts),
                "attempts": attempts,
            }
        )

    latest = runs[-1]
    aggregate_evaluation = aggregate_evaluations([run["evaluation"] for run in runs])
    aggregate_returncode = 0 if all(run["returncode"] == 0 for run in runs) else next(
        run["returncode"] for run in runs if run["returncode"] != 0
    )
    return {
        "id": case_id,
        "category": str(case.get("category", "")),
        "message": message,
        "session_id": latest["session_id"],
        "returncode": aggregate_returncode,
        "stderr": "\n".join([run["stderr"] for run in runs if run.get("stderr")]).strip(),
        "final_text": latest["final_text"],
        "evaluation": aggregate_evaluation,
        "attempt_count": sum(int(run.get("attempt_count", 0)) for run in runs),
        "attempts": latest["attempts"],
        "run_count": run_count,
        "runs": runs,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    suite_path = Path(args.suite).expanduser().resolve()
    suite = load_suite(suite_path)
    cases = filter_cases(
        [case for case in suite.get("cases", []) if isinstance(case, dict)],
        args.case_id,
        args.category,
        args.limit,
    )
    if not cases:
        raise SystemExit("没有匹配到要运行的 case")

    scripts_dir = skill_dir / "scripts"
    if args.publish_skill:
        publish = run_step([sys.executable, str(scripts_dir / "publish_skill.py"), "--source", str(skill_dir)])
        if publish.returncode != 0:
            if publish.stdout:
                print(publish.stdout)
            if publish.stderr:
                print(publish.stderr, file=sys.stderr)
            return publish.returncode
    if args.reset_quote_sessions:
        reset = run_step(build_reset_command(scripts_dir, include_feishu=args.include_feishu))
        if reset.returncode != 0:
            if reset.stdout:
                print(reset.stdout)
            if reset.stderr:
                print(reset.stderr, file=sys.stderr)
            return reset.returncode

    results = [
        run_case(case, thinking=args.thinking, timeout=args.timeout, max_retries=args.max_retries, repeat_each=args.repeat_each)
        for case in cases
    ]
    passed_count = sum(1 for result in results if result["returncode"] == 0 and result["evaluation"]["passed"])
    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(skill_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "suite_name": suite.get("suite_name"),
        "suite_version": suite.get("version"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "case_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "validation_assertion_summary": summarize_validation_assertions(results),
        "results": results,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
