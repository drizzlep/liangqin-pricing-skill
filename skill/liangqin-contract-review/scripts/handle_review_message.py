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


def _resolve_app_root(script_path: Path | None = None) -> Path:
    anchor = (script_path or Path(__file__)).resolve()
    candidates = [
        anchor.parents[1] / "apps" / "contract-review",
        anchor.parents[3] / "apps" / "contract-review",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"未找到合同审核 app 目录，已检查：{', '.join(str(path) for path in candidates)}")


APP_ROOT = _resolve_app_root()
CLI_ROOT = APP_ROOT / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

import review_chat  # noqa: E402


DEFAULT_RUNTIME_ROOT = APP_ROOT / "runtime"
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

FRESH_REVIEW_HINT_KEYWORDS = (
    "审这份合同",
    "审核这份合同",
    "审核这个合同",
    "请审核这份合同",
    "请审核这个合同",
    "开始审核",
    "开始审单",
    "合同审核",
)
OPENCLAW_FALLBACK_CHANNEL = "openclaw"


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
    parser.add_argument("--ocr-backend", choices=["disabled", "paddleocr", "mineru"], default="paddleocr")
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


def _extract_labeled_json_block(text: str, *, label_pattern: str) -> dict[str, Any]:
    content = str(text or "")
    if not content:
        return {}
    match = re.search(
        rf"{label_pattern}\s*```json\s*(\{{.*?\}})\s*```",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_inline_openclaw_context(text: str | None) -> dict[str, Any]:
    content = str(text or "")
    if not content:
        return {}

    conversation = _extract_labeled_json_block(
        content,
        label_pattern=r"Conversation info(?: \(untrusted metadata\))?:",
    )
    sender = _extract_labeled_json_block(
        content,
        label_pattern=r"Sender(?: \(untrusted metadata\))?:",
    )
    if not conversation and not sender:
        return {}

    payload: dict[str, Any] = {}
    message_id = str(conversation.get("message_id") or conversation.get("msg_id") or "").strip()
    sender_id = str(conversation.get("sender_id") or sender.get("id") or "").strip()
    sender_name = str(conversation.get("sender") or sender.get("name") or "").strip()
    chat_id = str(
        conversation.get("group_channel")
        or conversation.get("chat_id")
        or conversation.get("conversation_id")
        or conversation.get("conversationId")
        or ""
    ).strip()
    if message_id:
        payload["message_id"] = message_id
    if sender_id:
        payload["sender_id"] = sender_id
    if sender_name:
        payload["sender"] = sender_name
    if chat_id:
        payload["chat_id"] = chat_id
        payload["group_channel"] = chat_id
    sender_label = str(sender.get("label") or "").strip()
    if sender_label:
        payload["conversation_label"] = sender_label
    return payload


def _strip_inline_openclaw_metadata(text: str | None) -> str:
    content = str(text or "")
    if not content:
        return ""
    normalized = re.sub(
        r"Conversation info(?: \(untrusted metadata\))?:\s*```json\s*\{.*?\}\s*```\s*",
        "",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    normalized = re.sub(
        r"Sender(?: \(untrusted metadata\))?:\s*```json\s*\{.*?\}\s*```\s*",
        "",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return normalized.strip()


def _resolve_effective_channel(
    *,
    channel: str | None,
    context_payload: dict[str, Any],
    context_source: str,
) -> tuple[str, str]:
    normalized_channel = str(channel or "").strip()
    if normalized_channel:
        return normalized_channel, "cli_arg"

    for key in ("channel", "source_channel", "connector", "channel_id", "channelId"):
        candidate = str(context_payload.get(key) or "").strip()
        if candidate:
            return candidate, "context_payload"

    if context_payload:
        if context_source == "inline_text_metadata":
            return OPENCLAW_FALLBACK_CHANNEL, "inline_text_fallback"
        return OPENCLAW_FALLBACK_CHANNEL, "context_fallback"

    return "", "missing"


def _resolve_conversation_slug_from_payload(*, payload: dict[str, Any], channel: str | None) -> str:
    if not payload:
        return ""
    sender_id = str(payload.get("sender_id") or "").strip()
    if not sender_id:
        return ""
    group_channel = str(
        payload.get("group_channel")
        or payload.get("chat_id")
        or payload.get("conversation_id")
        or payload.get("conversationId")
        or ""
    ).strip()
    if group_channel:
        return _slugify(group_channel)
    resolved_channel = str(channel or "").strip() or OPENCLAW_FALLBACK_CHANNEL
    is_group_chat = bool(payload.get("is_group_chat")) or bool(group_channel)
    if is_group_chat:
        group_seed = (
            str(payload.get("conversation_label") or "").strip()
            or str(payload.get("group_subject") or "").strip()
            or sender_id
        )
        return _slugify(f"agent-main-{resolved_channel}-group-{group_seed}")
    return _slugify(f"agent-main-{resolved_channel}-direct-{sender_id}")


def _resolve_conversation_slug(*, context_json: str | None, channel: str | None) -> str:
    if not context_json:
        return ""
    payload = _parse_context_json(context_json)
    resolved_channel, _ = _resolve_effective_channel(
        channel=channel,
        context_payload=payload,
        context_source="cli_arg" if context_json else "none",
    )
    return _resolve_conversation_slug_from_payload(payload=payload, channel=resolved_channel)


def _normalize_openclaw_request(
    *,
    text: str,
    context_json: str | None,
    channel: str | None,
) -> dict[str, Any]:
    context_payload = _parse_context_json(context_json) if context_json else {}
    context_source = "cli_arg" if context_payload else "none"
    normalized_text = str(text or "").strip()
    if not context_payload:
        context_payload = _extract_inline_openclaw_context(normalized_text)
        if context_payload:
            context_source = "inline_text_metadata"
            stripped_text = _strip_inline_openclaw_metadata(normalized_text)
            if stripped_text:
                normalized_text = stripped_text

    resolved_channel, channel_source = _resolve_effective_channel(
        channel=channel,
        context_payload=context_payload,
        context_source=context_source,
    )
    effective_context_json = json.dumps(context_payload, ensure_ascii=False) if context_payload else None
    conversation_slug = _resolve_conversation_slug_from_payload(payload=context_payload, channel=resolved_channel)
    return {
        "text": normalized_text,
        "context_json": effective_context_json,
        "channel": resolved_channel,
        "context_payload": context_payload,
        "context_source": context_source,
        "channel_source": channel_source,
        "conversation_slug": conversation_slug,
    }


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
    openclaw_context: dict[str, Any] | None = None,
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
    if openclaw_context:
        manifest["openclaw_context"] = dict(openclaw_context)
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return batch_dir


def _forward_review_chat_args(
    *,
    args: argparse.Namespace,
    forwarded_text: str,
    batch_dir: Path | None,
    resolved_state_root: Path,
) -> list[str]:
    forwarded = [
        "--text",
        forwarded_text,
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


def _looks_like_fresh_review_request(text: str) -> bool:
    command = str(text or "").strip()
    if not command:
        return False
    if any(keyword in command for keyword in FRESH_REVIEW_HINT_KEYWORDS):
        return True
    return command.startswith("审") and "合同" in command


def _emit_missing_input_warning(*, args: argparse.Namespace) -> int:
    reply_text = (
        "这次没有收到新的合同附件，所以我先不复用上一份合同的审核结果。"
        "请重新上传合同，或确保渠道把附件路径透传到 `--input-path` / `--batch-dir` 后再试。"
    )
    if args.output_mode == "json":
        sys.stdout.write(
            json.dumps(
                {
                    "handled_by": "contract_review_chat",
                    "action": "missing_contract_input",
                    "reply_text": reply_text,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    else:
        sys.stdout.write(reply_text + "\n")
    sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    request_context = _normalize_openclaw_request(
        text=args.text,
        context_json=args.context_json,
        channel=args.channel,
    )
    resolved_state_root = _resolve_state_root(
        runtime_root=runtime_root,
        state_root=args.state_root,
        context_json=request_context["context_json"],
        channel=request_context["channel"],
    )
    batch_dir: Path | None = None
    if args.batch_dir:
        batch_dir = Path(args.batch_dir).expanduser().resolve()
    elif args.input_path:
        batch_dir = prepare_input_batch(
            input_paths=list(args.input_path),
            runtime_root=runtime_root,
            context_json=request_context["context_json"],
            channel=request_context["channel"],
            openclaw_context={
                "context_source": request_context["context_source"],
                "channel_source": request_context["channel_source"],
                "conversation_slug": request_context["conversation_slug"],
            },
        )
    elif _looks_like_fresh_review_request(request_context["text"]):
        return _emit_missing_input_warning(args=args)

    forwarded_argv = _forward_review_chat_args(
        args=args,
        forwarded_text=str(request_context["text"]),
        batch_dir=batch_dir,
        resolved_state_root=resolved_state_root,
    )
    _emit_precheck_status(args=args, batch_dir=batch_dir)
    return review_chat.main(forwarded_argv)


if __name__ == "__main__":
    raise SystemExit(main())
