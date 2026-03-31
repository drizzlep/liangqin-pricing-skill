#!/usr/bin/env python3
"""Create a GitHub Release for the Liangqin pricing skill from the current main HEAD."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path


DEFAULT_VERIFY_COMMAND = "python3 -m unittest discover -s skill/liangqin-pricing/tests"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build release assets and publish a GitHub Release from current main HEAD.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]), help="Repository root directory.")
    parser.add_argument("--repo", default="", help="GitHub repo slug like owner/name. Defaults to origin remote.")
    parser.add_argument("--tag", default="", help="Release tag. Defaults to the next date-based tag.")
    parser.add_argument("--title", default="", help="Release title. Defaults to '<tag> - GitHub release'.")
    parser.add_argument("--notes-file", default="", help="Optional markdown release notes file.")
    parser.add_argument("--dist-dir", default="", help="Optional output directory for generated assets.")
    parser.add_argument("--verify-command", default=DEFAULT_VERIFY_COMMAND, help="Command to verify before publishing.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip verification command.")
    parser.add_argument("--dry-run", action="store_true", help="Build assets and notes, but do not create the GitHub Release.")
    return parser.parse_args(argv)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, check=True, text=True, capture_output=True)


def shell_run(command: str, *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, check=True, text=True, shell=True, capture_output=True)


def git_output(repo_root: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo_root).stdout.strip()


def parse_github_repo(remote_url: str) -> str:
    normalized = remote_url.strip()
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    if normalized.startswith("git@github.com:"):
        return normalized.split("git@github.com:", 1)[1]
    if normalized.startswith("https://github.com/"):
        return normalized.split("https://github.com/", 1)[1]
    raise ValueError(f"Unsupported GitHub remote URL: {remote_url}")


def release_stamp_for_tag(tag: str) -> str:
    normalized = tag.removeprefix("v")
    parts = normalized.split(".")
    if len(parts) < 3:
        raise ValueError(f"Unexpected tag format: {tag}")
    base = "".join(parts[:3])
    if len(parts) > 3:
        return f"{base}-{'-'.join(parts[3:])}"
    return base


def choose_next_tag(existing_tags: list[str], *, today: date) -> str:
    prefix = today.strftime("v%Y.%m.%d")
    matching = [tag for tag in existing_tags if tag == prefix or tag.startswith(f"{prefix}.")]
    if not matching:
        return prefix

    suffixes = [0]
    for tag in matching:
        remainder = tag.removeprefix(prefix)
        if not remainder:
            suffixes.append(0)
            continue
        if remainder.startswith(".") and remainder[1:].isdigit():
            suffixes.append(int(remainder[1:]))
    next_suffix = max(suffixes) + 1
    return f"{prefix}.{next_suffix}"


def build_release_notes(
    *,
    tag: str,
    target_commit: str,
    previous_tag: str | None,
    verify_command: str,
    assets: list[str],
    commit_lines: list[str],
) -> str:
    lines = [
        f"良禽佳木报价 skill 发布 `{tag}`。",
        "",
        f"- 目标提交：`{target_commit}`",
    ]
    if previous_tag:
        lines.append(f"- 对比上一版：`{previous_tag}`")
    lines.extend(
        [
            f"- 验证命令：`{verify_command}`",
            "",
            "本次包含提交：",
        ]
    )
    if commit_lines:
        lines.extend(f"- `{line}`" for line in commit_lines)
    else:
        lines.append("- 无新增提交说明")
    lines.extend(
        [
            "",
            "附件：",
        ]
    )
    lines.extend(f"- `{asset}`" for asset in assets)
    return "\n".join(lines) + "\n"


def ensure_release_base(repo_root: Path) -> tuple[str, str]:
    run(["git", "fetch", "origin"], cwd=repo_root)
    current_branch = git_output(repo_root, "branch", "--show-current")
    if current_branch != "main":
        raise SystemExit(f"发布前请先切到 main，当前分支为：{current_branch}")

    head_sha = git_output(repo_root, "rev-parse", "HEAD")
    origin_main_sha = git_output(repo_root, "rev-parse", "origin/main")
    if head_sha != origin_main_sha:
        raise SystemExit("当前 HEAD 还没有和 origin/main 对齐，请先把 main 推到远端再发布。")
    return current_branch, head_sha


def create_snapshot(repo_root: Path) -> Path:
    snapshot_root = Path(tempfile.mkdtemp(prefix="liangqin-release-snapshot."))
    archive_path = snapshot_root / "repo.tar"
    run(["git", "archive", "--format=tar", f"--output={archive_path}", "HEAD"], cwd=repo_root)
    with tarfile.open(archive_path) as archive:
        archive.extractall(snapshot_root)
    archive_path.unlink()
    return snapshot_root


def build_release_assets(snapshot_root: Path, *, tag: str, previous_tag: str | None, repo_root: Path, dist_dir: Path) -> list[Path]:
    dist_dir.mkdir(parents=True, exist_ok=True)
    run(["bash", str(snapshot_root / "scripts" / "package_openclaw_skill.sh"), str(dist_dir)], cwd=snapshot_root)
    installer_env = dict(os.environ)
    installer_env["DIST_DIR"] = str(dist_dir)
    run(["bash", str(snapshot_root / "scripts" / "build_single_file_installer.sh")], cwd=snapshot_root, env=installer_env)

    stamp = release_stamp_for_tag(tag)
    patch_path = dist_dir / f"liangqin-pricing-github-release-{stamp}.patch"
    if previous_tag:
        shell_run(f"git diff {previous_tag}..HEAD > '{patch_path}'", cwd=repo_root)
    else:
        shell_run(f"git diff HEAD > '{patch_path}'", cwd=repo_root)

    asset_paths = sorted(path for path in dist_dir.iterdir() if path.is_file() and path.suffix in {".zip", ".sh", ".patch"})
    if not asset_paths:
        raise SystemExit("未生成任何 release 附件。")
    return asset_paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    _, target_commit = ensure_release_base(repo_root)

    if not args.skip_verify:
        verification = shell_run(args.verify_command, cwd=repo_root)
        sys.stdout.write(verification.stdout)
        sys.stderr.write(verification.stderr)

    repo_slug = args.repo.strip()
    if not repo_slug:
        repo_slug = parse_github_repo(git_output(repo_root, "remote", "get-url", "origin"))

    existing_tags = [line.strip() for line in git_output(repo_root, "tag", "--sort=-creatordate").splitlines() if line.strip()]
    tag = args.tag.strip() or choose_next_tag(existing_tags, today=date.today())
    title = args.title.strip() or f"{tag} - GitHub release"

    previous_tag = next((existing for existing in existing_tags if existing != tag), None)
    commit_range = [f"{previous_tag}..HEAD"] if previous_tag else ["HEAD"]
    commit_lines = [line for line in git_output(repo_root, "log", "--oneline", *commit_range).splitlines() if line.strip()]

    snapshot_root = create_snapshot(repo_root)
    dist_dir = Path(args.dist_dir).expanduser().resolve() if args.dist_dir else snapshot_root / "dist"
    asset_paths = build_release_assets(snapshot_root, tag=tag, previous_tag=previous_tag, repo_root=repo_root, dist_dir=dist_dir)

    notes_file = Path(args.notes_file).expanduser().resolve() if args.notes_file else dist_dir / f"release-notes-{tag}.md"
    if not args.notes_file:
        notes_file.write_text(
            build_release_notes(
                tag=tag,
                target_commit=target_commit,
                previous_tag=previous_tag,
                verify_command=args.verify_command,
                assets=[path.name for path in asset_paths],
                commit_lines=commit_lines,
            ),
            encoding="utf-8",
        )

    if args.dry_run:
        print(f"Dry run ready: tag={tag}")
        print(f"Repo: {repo_slug}")
        print(f"Notes: {notes_file}")
        for asset_path in asset_paths:
            print(f"Asset: {asset_path}")
        return 0

    command = [
        "gh",
        "release",
        "create",
        tag,
        *[str(path) for path in asset_paths],
        "--repo",
        repo_slug,
        "--target",
        target_commit,
        "--title",
        title,
        "--notes-file",
        str(notes_file),
    ]
    release = run(command, cwd=repo_root)
    sys.stdout.write(release.stdout)
    sys.stderr.write(release.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
