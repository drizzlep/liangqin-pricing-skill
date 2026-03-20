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
    parser = argparse.ArgumentParser(description="Update the Liangqin skill from one xlsx and one docx.")
    parser.add_argument("--price-book", help="Path to the source product catalog xlsx. Defaults to latest .xlsx in sources/inbox.")
    parser.add_argument("--rules-docx", help="Path to the source pricing-rules docx. Defaults to latest .docx in sources/inbox.")
    parser.add_argument("--version", help="Version label. Defaults to today's date in YYYY-MM-DD.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--activate", action=argparse.BooleanOptionalAction, default=True, help="Activate the built version into data/current.")
    parser.add_argument("--publish", action=argparse.BooleanOptionalAction, default=True, help="Publish the shared skill into the OpenClaw workspace.")
    return parser.parse_args()


def pick_latest(directory: Path, suffix: str) -> Path:
    candidates = sorted(directory.glob(f"*{suffix}"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"未找到 {suffix} 文件：{directory}")
    return candidates[0]


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
    rules_docx = Path(args.rules_docx).expanduser().resolve() if args.rules_docx else pick_latest(inbox_dir, ".docx")

    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = archived_root / version
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_price_book = archive_dir / price_book.name
    archived_rules_docx = archive_dir / rules_docx.name
    shutil.copy2(price_book, archived_price_book)
    shutil.copy2(rules_docx, archived_rules_docx)

    price_index_output = reports_dir / f"price-index-{version}.json"
    rules_candidate_output = reports_dir / f"rules-candidate-{version}.json"
    version_dir = skill_dir / "data" / "versions" / version

    print(f"[1/6] 使用价格目录：{price_book.name}")
    print(f"[2/6] 使用规则文档：{rules_docx.name}")

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
            str(rules_docx),
            "--output",
            str(rules_candidate_output),
        ]
    )
    print(f"[4/6] 已提取规则候选：{rules_candidate_output.name}")

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

    run_step(
        [
            sys.executable,
            str(scripts_dir / "validate_release.py"),
            "--version-dir",
            str(version_dir),
        ]
    )
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
