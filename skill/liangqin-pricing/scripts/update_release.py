#!/usr/bin/env python3
"""One-command maintenance entrypoint for the Liangqin pricing skill."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update the Liangqin skill from one xlsx and one rule source.")
    parser.add_argument("--price-book", help="Path to the source product catalog xlsx. Defaults to latest .xlsx in sources/inbox.")
    parser.add_argument(
        "--rules-source",
        dest="rules_source",
        help="Path to the source pricing-rules docx/pdf. Defaults to the latest docx, or latest pdf when no docx exists.",
    )
    parser.add_argument(
        "--rules-docx",
        dest="rules_source",
        help="Backward-compatible alias for --rules-source. Can point to a docx or pdf rule file.",
    )
    parser.add_argument("--version", help="Version label. Defaults to today's date in YYYY-MM-DD.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--activate", action=argparse.BooleanOptionalAction, default=True, help="Activate the built version into data/current.")
    parser.add_argument("--publish", action=argparse.BooleanOptionalAction, default=True, help="Publish the shared skill into the OpenClaw workspace.")
    parser.add_argument("--prompt-suite-report", help="Optional prompt suite report JSON used for release gating.")
    parser.add_argument(
        "--required-assertion",
        action="append",
        default=[],
        help="Validation assertion name that must have zero failures in the prompt suite report.",
    )
    parser.add_argument("--runtime-noise-review", help="Optional runtime noise review report (.md/.json) used for release gating.")
    parser.add_argument("--max-suspicious-runtime", type=int, help="Maximum allowed suspicious runtime entries when runtime noise review is provided.")
    return parser.parse_args()


def pick_latest(directory: Path, suffix: str) -> Path:
    candidates = sorted(directory.glob(f"*{suffix}"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"未找到 {suffix} 文件：{directory}")
    return candidates[0]


def pick_latest_rules_source(directory: Path) -> Path:
    docx_candidates = sorted(directory.glob("*.docx"), key=lambda path: path.stat().st_mtime, reverse=True)
    if docx_candidates:
        return docx_candidates[0]

    pdf_candidates = sorted(directory.glob("*.pdf"), key=lambda path: path.stat().st_mtime, reverse=True)
    if pdf_candidates:
        return pdf_candidates[0]

    raise SystemExit(f"未找到规则文件（.docx / .pdf）：{directory}")


def run_step(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    args = parse_args()
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    scripts_dir = skill_dir / "scripts"
    inbox_dir = skill_dir / "sources" / "inbox"
    archived_root = skill_dir / "sources" / "archived"
    reports_dir = skill_dir / "reports" / "validation"

    version = args.version or datetime.now().strftime("%Y-%m-%d")
    price_book = Path(args.price_book).expanduser().resolve() if args.price_book else pick_latest(inbox_dir, ".xlsx")
    rules_source = Path(args.rules_source).expanduser().resolve() if args.rules_source else pick_latest_rules_source(inbox_dir)

    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = archived_root / version
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_price_book = archive_dir / price_book.name
    archived_rules_source = archive_dir / rules_source.name
    shutil.copy2(price_book, archived_price_book)
    shutil.copy2(rules_source, archived_rules_source)

    price_index_output = reports_dir / f"price-index-{version}.json"
    rules_candidate_output = reports_dir / f"rules-candidate-{version}.json"
    rules_markdown_output = reports_dir / f"rules-source-{version}.md"
    rules_index_output = reports_dir / f"rules-index-{version}.json"
    rules_index_markdown_output = reports_dir / f"rules-index-{version}.md"
    rules_drafts_output_dir = reports_dir / f"rules-drafts-{version}"
    version_dir = skill_dir / "data" / "versions" / version

    print(f"[1/6] 使用价格目录：{price_book.name}")
    print(f"[2/6] 使用规则文档：{rules_source.name}")

    run_step(
        [
            sys.executable,
            str(scripts_dir / "extract_price_index.py"),
            "--input",
            str(price_book),
            "--output",
            str(price_index_output),
            "--pretty",
        ]
    )
    print(f"[3/6] 已生成价格索引：{price_index_output.name}")

    run_step(
        [
            sys.executable,
            str(scripts_dir / "extract_rules_candidate.py"),
            "--input",
            str(rules_source),
            "--output",
            str(rules_candidate_output),
            "--markdown-output",
            str(rules_markdown_output),
        ]
    )
    print(f"[4/6] 已提取规则候选：{rules_candidate_output.name}")
    print(f"      已生成审阅稿：{rules_markdown_output.name}")

    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_rules_index.py"),
            "--input",
            str(rules_candidate_output),
            "--output",
            str(rules_index_output),
            "--markdown-output",
            str(rules_index_markdown_output),
        ]
    )
    print(f"      已生成规则索引：{rules_index_output.name}")
    print(f"      已生成索引概览：{rules_index_markdown_output.name}")

    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_rules_drafts.py"),
            "--input",
            str(rules_index_output),
            "--output-dir",
            str(rules_drafts_output_dir),
        ]
    )
    print(f"      已生成分域规则草稿目录：{rules_drafts_output_dir.name}")

    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_release.py"),
            "--version",
            version,
            "--price-index",
            str(price_index_output),
            "--rules-candidate",
            str(rules_candidate_output),
            "--skill-dir",
            str(skill_dir),
        ]
    )

    validate_command = [
        sys.executable,
        str(scripts_dir / "validate_release.py"),
        "--version-dir",
        str(version_dir),
    ]
    if args.prompt_suite_report:
        validate_command.extend(["--prompt-suite-report", str(Path(args.prompt_suite_report).expanduser().resolve())])
    for assertion_name in args.required_assertion:
        validate_command.extend(["--required-assertion", assertion_name])
    if args.runtime_noise_review:
        validate_command.extend(["--runtime-noise-review", str(Path(args.runtime_noise_review).expanduser().resolve())])
    if args.max_suspicious_runtime is not None:
        validate_command.extend(["--max-suspicious-runtime", str(args.max_suspicious_runtime)])

    run_step(validate_command)
    print(f"[5/6] 版本构建并校验通过：{version}")

    if args.activate:
        run_step(
            [
                sys.executable,
                str(scripts_dir / "activate_release.py"),
                "--version-dir",
                str(version_dir),
                "--skill-dir",
                str(skill_dir),
            ]
        )
        print(f"[6/6] 已激活版本：{version}")
    else:
        print(f"[6/6] 已跳过激活：{version}")

    if args.publish:
        run_step([sys.executable, str(scripts_dir / "publish_skill.py"), "--source", str(skill_dir)])
        print("已同步到 OpenClaw workspace")

    print("更新完成。后续日常维护优先使用这一条命令。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
