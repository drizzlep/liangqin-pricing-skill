#!/usr/bin/env python3
"""Snapshot the online DingTalk designer manual into local inbox files."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE = "https://alidocs.dingtalk.com/i/spaces/oqvGpEPrWwAkVzDy/overview"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Snapshot a DingTalk designer-manual workspace.")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE, help="DingTalk workspace id or URL.")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent.parent / "sources" / "inbox" / "designer-manual-online"),
        help="Local directory for the snapshot.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max file-node count for smoke tests.")
    parser.add_argument("--skip-binary", action="store_true", help="Only write metadata and online-doc markdown.")
    return parser.parse_args(argv)


def run_dws(args: list[str]) -> dict[str, Any]:
    command = ["dws", *args, "--format", "json"]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    raw = result.stdout.strip() or result.stderr.strip()
    if result.returncode != 0:
        raise RuntimeError(raw)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected dws response: {raw[:200]}")
    return payload


def list_children(*, workspace: str | None = None, folder: str | None = None) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        args = ["doc", "list", "--page-size", "50"]
        if workspace:
            args.extend(["--workspace", workspace])
        if folder:
            args.extend(["--folder", folder])
        if page_token:
            args.extend(["--page-token", page_token])
        payload = run_dws(args)
        nodes.extend([node for node in payload.get("nodes", []) if isinstance(node, dict)])
        if not payload.get("hasMore"):
            break
        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break
    return nodes


def collect_nodes(workspace: str) -> list[dict[str, Any]]:
    all_nodes: list[dict[str, Any]] = []
    queue: deque[tuple[str | None, str]] = deque([(None, "<root>")])
    seen_folders: set[str] = set()

    while queue:
        folder_id, parent_path = queue.popleft()
        if folder_id is None:
            children = list_children(workspace=workspace)
        else:
            if folder_id in seen_folders:
                continue
            seen_folders.add(folder_id)
            children = list_children(folder=folder_id)
        for node in children:
            node = dict(node)
            node_path = f"{parent_path}/{node.get('name', '')}"
            node["path"] = node_path
            all_nodes.append(node)
            if node.get("nodeType") == "folder" and node.get("nodeId"):
                queue.append((str(node["nodeId"]), node_path))
    return all_nodes


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\t\r\n]+", "_", value).strip(" .")
    return cleaned[:120] or "untitled"


def node_output_stem(node: dict[str, Any], index: int) -> str:
    parts = [safe_name(part) for part in str(node.get("path", "")).split("/") if part and part != "<root>"]
    name = "__".join(parts) or safe_name(str(node.get("name", "")))
    node_id = safe_name(str(node.get("nodeId", "")))[:12]
    return f"{index:04d}__{name}__{node_id}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_online_doc(node_id: str) -> dict[str, Any]:
    return run_dws(["doc", "read", "--node", node_id])


def download_binary_node(node_id: str, output_path: Path) -> dict[str, Any]:
    payload = run_dws(["doc", "download", "--node", node_id])
    url = str(payload.get("resourceUrl") or "")
    if not url:
        raise RuntimeError(f"No resourceUrl returned for node {node_id}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        output_path.write_bytes(response.read())
    return payload


def snapshot_workspace(*, workspace: str, output_dir: Path, limit: int = 0, skip_binary: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = collect_nodes(workspace)
    file_nodes = [node for node in nodes if node.get("nodeType") == "file"]
    if limit > 0:
        file_nodes = file_nodes[:limit]

    markdown_dir = output_dir / "markdown"
    files_dir = output_dir / "files"
    errors: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    for index, node in enumerate(file_nodes, start=1):
        node_id = str(node.get("nodeId", "")).strip()
        if not node_id:
            continue
        stem = node_output_stem(node, index)
        content_type = str(node.get("contentType", "")).strip()
        extension = str(node.get("extension", "") or "").strip().lower()
        try:
            if content_type == "ALIDOC" and extension in {"", "adoc"}:
                payload = read_online_doc(node_id)
                markdown_path = markdown_dir / f"{stem}.md"
                title = str(payload.get("title") or node.get("name") or "").strip()
                markdown = str(payload.get("markdown") or "")
                markdown_path.parent.mkdir(parents=True, exist_ok=True)
                markdown_path.write_text(f"# {title}\n\n{markdown}".strip() + "\n", encoding="utf-8")
                artifacts.append({**node, "snapshot_type": "markdown", "local_path": str(markdown_path)})
            elif not skip_binary:
                suffix = f".{extension}" if extension else ".pdf"
                binary_path = files_dir / f"{stem}{suffix}"
                download_payload = download_binary_node(node_id, binary_path)
                artifacts.append(
                    {
                        **node,
                        "snapshot_type": "binary",
                        "local_path": str(binary_path),
                        "expirationSeconds": download_payload.get("expirationSeconds"),
                    }
                )
            else:
                artifacts.append({**node, "snapshot_type": "skipped_binary"})
        except Exception as exc:  # noqa: BLE001 - keep per-node snapshot moving.
            errors.append({**node, "error": str(exc)})

    manifest = {
        "workspace": workspace,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "node_count": len(nodes),
        "file_count": len([node for node in nodes if node.get("nodeType") == "file"]),
        "folder_count": len([node for node in nodes if node.get("nodeType") == "folder"]),
        "processed_file_count": len(file_nodes),
        "artifact_count": len(artifacts),
        "error_count": len(errors),
        "artifacts": artifacts,
        "errors": errors,
    }
    write_json(output_dir / "nodes.json", nodes)
    write_json(output_dir / "snapshot-manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = snapshot_workspace(
        workspace=args.workspace,
        output_dir=Path(args.output_dir).expanduser().resolve(),
        limit=args.limit,
        skip_binary=args.skip_binary,
    )
    print(json.dumps({k: manifest[k] for k in ("node_count", "processed_file_count", "artifact_count", "error_count")}, ensure_ascii=False, indent=2))
    return 0 if not manifest["error_count"] else 1


if __name__ == "__main__":
    sys.exit(main())
