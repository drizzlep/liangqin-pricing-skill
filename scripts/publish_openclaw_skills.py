#!/usr/bin/env python3
"""Publish Liangqin OpenClaw skills into active and workspace stores."""

from __future__ import annotations

import argparse
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "skill"
DEFAULT_SKILLS_ROOT = Path.home() / ".openclaw" / "skills"
DEFAULT_WORKSPACE_ROOT = Path.home() / ".openclaw" / "workspace" / "skills"
DEFAULT_CONTRACT_REVIEW_APP_ROOT = REPO_ROOT / "apps" / "contract-review"
DEFAULT_SKILLS = ("liangqin-pricing", "liangqin-contract-review")
IGNORE_NAMES = {"__pycache__", ".DS_Store", "tests"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish Liangqin OpenClaw skills into local skill stores.")
    parser.add_argument(
        "--skill",
        action="append",
        choices=sorted(DEFAULT_SKILLS),
        help="Skill name to publish. Repeat to publish multiple skills. Defaults to all supported skills.",
    )
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Directory that contains all shared skill folders.",
    )
    parser.add_argument(
        "--skills-root",
        default=str(DEFAULT_SKILLS_ROOT),
        help="OpenClaw active skills root.",
    )
    parser.add_argument(
        "--workspace-root",
        default=str(DEFAULT_WORKSPACE_ROOT),
        help="OpenClaw workspace skills root.",
    )
    parser.add_argument(
        "--publish-engine",
        help="Optional explicit path to publish_skill.py. Defaults to liangqin-pricing/scripts/publish_skill.py under source-root.",
    )
    parser.add_argument(
        "--contract-review-app-root",
        default=str(DEFAULT_CONTRACT_REVIEW_APP_ROOT),
        help="App runtime directory bundled into liangqin-contract-review during publish.",
    )
    return parser.parse_args(argv)


def resolve_skills(selected: list[str] | None) -> list[str]:
    raw_skills = selected or list(DEFAULT_SKILLS)
    resolved: list[str] = []
    for skill_name in raw_skills:
        if skill_name not in resolved:
            resolved.append(skill_name)
    return resolved


def resolve_publish_engine(source_root: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    return (source_root / "liangqin-pricing" / "scripts" / "publish_skill.py").resolve()


def build_publish_command(
    *,
    publish_engine: Path,
    source_root: Path,
    skills_root: Path,
    workspace_root: Path,
    skill_name: str,
) -> list[str]:
    source_dir = source_root / skill_name
    dest_dir = skills_root / skill_name
    workspace_dir = workspace_root / skill_name
    return [
        sys.executable,
        str(publish_engine),
        "--source",
        str(source_dir),
        "--dest",
        str(dest_dir),
        "--workspace-dest",
        str(workspace_dir),
    ]


def run_step(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=True)


def ignore_filter(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES}


def build_publish_source_dir(
    *,
    skill_name: str,
    source_root: Path,
    skills_root: Path,
    contract_review_app_root: Path,
    staging_root: Path,
) -> Path:
    source_dir = source_root / skill_name
    active_dest_dir = skills_root / skill_name

    def _stage_copy(source_path: Path) -> Path:
        staged_skill_dir = staging_root / skill_name
        if staged_skill_dir.exists():
            shutil.rmtree(staged_skill_dir)
        shutil.copytree(source_path, staged_skill_dir, ignore=ignore_filter)
        return staged_skill_dir

    if skill_name != "liangqin-contract-review":
        if source_dir == active_dest_dir:
            return _stage_copy(source_dir)
        return source_dir

    bundled_app_dir = source_dir / "apps" / "contract-review"
    if bundled_app_dir.exists():
        if source_dir == active_dest_dir:
            return _stage_copy(source_dir)
        return source_dir

    if not contract_review_app_root.exists():
        raise SystemExit(f"未找到合同审核 app 目录：{contract_review_app_root}")

    staged_skill_dir = _stage_copy(source_dir)
    bundled_app_dir = staged_skill_dir / "apps" / "contract-review"
    bundled_app_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(contract_review_app_root, bundled_app_dir, ignore=ignore_filter)
    return staged_skill_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_root = Path(args.source_root).expanduser().resolve()
    skills_root = Path(args.skills_root).expanduser().resolve()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    publish_engine = resolve_publish_engine(source_root, args.publish_engine)
    contract_review_app_root = Path(args.contract_review_app_root).expanduser().resolve()
    selected_skills = resolve_skills(args.skill)

    if not source_root.exists():
        raise SystemExit(f"未找到 skill 根目录：{source_root}")
    if not publish_engine.exists():
        raise SystemExit(f"未找到发布脚本：{publish_engine}")

    with tempfile.TemporaryDirectory() as tmpdir:
        staging_root = Path(tmpdir)
        for skill_name in selected_skills:
            source_dir = source_root / skill_name
            if not source_dir.exists():
                raise SystemExit(f"未找到 skill 目录：{source_dir}")

            publish_source_dir = build_publish_source_dir(
                skill_name=skill_name,
                source_root=source_root,
                skills_root=skills_root,
                contract_review_app_root=contract_review_app_root,
                staging_root=staging_root,
            )
            command = build_publish_command(
                publish_engine=publish_engine,
                source_root=publish_source_dir.parent,
                skills_root=skills_root,
                workspace_root=workspace_root,
                skill_name=skill_name,
            )
            result = run_step(command)
            if result.stdout:
                print(result.stdout.rstrip())
            if result.stderr:
                print(result.stderr.rstrip(), file=sys.stderr)
            if result.returncode != 0:
                return result.returncode

    print(
        "已发布 skill："
        + ", ".join(selected_skills)
        + f"\nactive root: {skills_root}"
        + f"\nworkspace root: {workspace_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
