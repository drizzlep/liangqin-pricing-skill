#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI_ROOT = PROJECT_ROOT / "apps" / "contract-review" / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

import review_chat  # noqa: E402


DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "apps" / "contract-review" / "runtime"
SUPPORTED_CONTRACT_SUFFIXES = {
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw entrypoint for Liangqin contract review.")
    parser.add_argument("--text", required=True, help="User message or command.")
    parser.add_argument("--batch-dir", help="Existing batch directory. If provided, takes precedence over --input-path.")
    parser.add_argument(
        "--input-path",
        action="append",
        help="Single contract file or a directory that contains contract files. Can be provided multiple times.",
    )
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT), help="Runtime root for review outputs.")
    parser.add_argument("--state-root", help="Optional explicit state root.")
    parser.add_argument("--context-json", help="Optional OpenClaw conversation context JSON.")
    parser.add_argument("--channel", help="Optional OpenClaw channel id, such as dingtalk-connector.")
    parser.add_argument("--output-mode", choices=["text", "json"], default="text")
    parser.add_argument("--ocr-backend", choices=["disabled", "paddleocr"], default="paddleocr")
    parser.add_argument("--paddleocr-lang", default="ch")
    parser.add_argument("--paddleocr-device", default="cpu")
    parser.add_argument("--force-ocr-for-documents", action="store_true")
    return parser.parse_args(argv)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "item"


def _parse_context_json(context_json: str | None) -> dict[str, Any]:
    if not context_json:
        return {}
    payload = json.loads(context_json)
    if not isinstance(payload, dict):
        raise ValueError("context-json must be a JSON object")
    return payload


def _resolve_conversation_slug(*, context_json: str | None, channel: str | None) -> str:
    if not context_json or not channel:
        return ""
    payload = _parse_context_json(context_json)
    sender_id = str(payload.get("sender_id") or "").strip()
    if not sender_id:
        return ""
    group_channel = str(payload.get("group_channel") or "").strip()
    is_group_chat = bool(payload.get("is_group_chat")) or bool(group_channel)
    if group_channel:
        return _slugify(group_channel)
    if is_group_chat:
        group_seed = (
            str(payload.get("conversation_label") or "").strip()
            or str(payload.get("group_subject") or "").strip()
            or sender_id
        )
        return _slugify(f"agent-main-{channel}-group-{group_seed}")
    return _slugify(f"agent-main-{channel}-direct-{sender_id}")


def _resolve_state_root(*, runtime_root: Path, state_root: str | None, context_json: str | None, channel: str | None) -> Path:
    if state_root:
        return Path(state_root).expanduser().resolve()
    conversation_slug = _resolve_conversation_slug(context_json=context_json, channel=channel)
    if conversation_slug:
        return runtime_root / "chat-state" / conversation_slug
    return runtime_root / "state"


def _is_supported_contract_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_CONTRACT_SUFFIXES


def _collect_input_files(input_paths: list[str]) -> list[Path]:
    collected: list[Path] = []
    for raw_path in input_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"输入路径不存在：{path}")
        if path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if _is_supported_contract_file(candidate):
                    collected.append(candidate)
            continue
        if _is_supported_contract_file(path):
            collected.append(path)
            continue
        raise ValueError(f"当前入口暂不支持该文件类型：{path.name}")
    if not collected:
        raise FileNotFoundError("当前输入里没有可审核的 pdf/docx/图片 文件。")
    return collected


def _stage_input_file(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() or target_path.is_symlink():
        target_path.unlink()
    try:
        target_path.symlink_to(source_path)
    except OSError:
        shutil.copy2(source_path, target_path)


def _build_batch_id(*, context_json: str | None, channel: str | None) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = _parse_context_json(context_json)
    message_id = str(payload.get("message_id") or "").strip() if payload else ""
    if channel and message_id:
        return _slugify(f"{channel}-{message_id}-{timestamp}")
    return _slugify(f"openclaw-import-{timestamp}")


def prepare_input_batch(
    *,
    input_paths: list[str],
    runtime_root: Path,
    context_json: str | None,
    channel: str | None,
) -> Path:
    source_files = _collect_input_files(input_paths)
    batch_id = _build_batch_id(context_json=context_json, channel=channel)
    batch_dir = runtime_root / "imported-batches" / batch_id
    raw_dir = batch_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[dict[str, Any]] = []
    for index, source_path in enumerate(source_files, start=1):
        case_dir = raw_dir / f"case-{index:03d}-{_slugify(source_path.stem)}"
        staged_path = case_dir / source_path.name
        _stage_input_file(source_path, staged_path)
        jobs.append(
            {
                "job_key": source_path.stem,
                "paths": [str(staged_path.relative_to(batch_dir))],
                "input_mode": "openclaw_attachment",
                "source_file_name": source_path.name,
            }
        )

    manifest = {
        "source_type": "openclaw_attachment_batch",
        "source_channel": str(channel or "openclaw").strip() or "openclaw",
        "source_batch_id": batch_id,
        "requested_actions": ["audit", "replay"],
        "operator": "",
        "received_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "notes": "Auto-imported from OpenClaw file inputs.",
        "jobs": jobs,
    }
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return batch_dir


def _forward_review_chat_args(
    *,
    args: argparse.Namespace,
    batch_dir: Path | None,
    resolved_state_root: Path,
) -> list[str]:
    forwarded = [
        "--text",
        args.text,
        "--runtime-root",
        str(Path(args.runtime_root).expanduser().resolve()),
        "--state-root",
        str(resolved_state_root),
        "--output-mode",
        args.output_mode,
        "--ocr-backend",
        args.ocr_backend,
        "--paddleocr-lang",
        args.paddleocr_lang,
        "--paddleocr-device",
        args.paddleocr_device,
    ]
    if batch_dir is not None:
        forwarded.extend(["--batch-dir", str(batch_dir)])
    if args.force_ocr_for_documents:
        forwarded.append("--force-ocr-for-documents")
    return forwarded


def _emit_precheck_status(*, args: argparse.Namespace, batch_dir: Path | None) -> None:
    if args.output_mode != "text":
        return
    if batch_dir is None:
        return

    manifest_path = batch_dir / "manifest.json"
    job_count = 0
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            job_count = len(list(manifest.get("jobs") or []))
        except (OSError, ValueError, TypeError):
            job_count = 0

    batch_label = "这份合同" if job_count <= 1 else f"这批合同（{job_count} 份）"
    sys.stdout.write(
        f"已收到{batch_label}，正在预检中：先抽取关键信息，再和报价系统做金额与字段对账，请稍等。\n"
    )
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    resolved_state_root = _resolve_state_root(
        runtime_root=runtime_root,
        state_root=args.state_root,
        context_json=args.context_json,
        channel=args.channel,
    )
    batch_dir: Path | None = None
    if args.batch_dir:
        batch_dir = Path(args.batch_dir).expanduser().resolve()
    elif args.input_path:
        batch_dir = prepare_input_batch(
            input_paths=list(args.input_path),
            runtime_root=runtime_root,
            context_json=args.context_json,
            channel=args.channel,
        )

    forwarded_argv = _forward_review_chat_args(
        args=args,
        batch_dir=batch_dir,
        resolved_state_root=resolved_state_root,
    )
    _emit_precheck_status(args=args, batch_dir=batch_dir)
    return review_chat.main(forwarded_argv)


if __name__ == "__main__":
    raise SystemExit(main())
