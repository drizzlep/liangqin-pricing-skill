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


def run_case(case: dict[str, Any], *, thinking: str, timeout: int, max_retries: int) -> dict[str, Any]:
    case_id = str(case.get("id", "case"))
    message = str(case.get("message", ""))
    expected_keywords = [str(entry) for entry in case.get("expected_keywords", [])]
    forbidden_keywords = [str(entry) for entry in case.get("forbidden_keywords", [])]
    expected_any_keywords = [
        [str(keyword) for keyword in group if str(keyword)]
        for group in case.get("expected_any_keywords", [])
        if isinstance(group, list)
    ]

    attempts: list[dict[str, Any]] = []
    attempt_count = max(1, int(max_retries) + 1)
    for attempt_index in range(attempt_count):
        session_id = f"suite-{case_id}-{datetime.now().strftime('%H%M%S')}-{attempt_index + 1}"
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

    latest = attempts[-1]
    return {
        "id": case_id,
        "category": str(case.get("category", "")),
        "message": message,
        "session_id": latest["session_id"],
        "returncode": latest["returncode"],
        "stderr": latest["stderr"],
        "final_text": latest["final_text"],
        "evaluation": latest["evaluation"],
        "attempt_count": len(attempts),
        "attempts": attempts,
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

    results = [run_case(case, thinking=args.thinking, timeout=args.timeout, max_retries=args.max_retries) for case in cases]
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
        "results": results,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
