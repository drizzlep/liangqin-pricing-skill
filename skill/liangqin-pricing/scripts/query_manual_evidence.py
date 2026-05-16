#!/usr/bin/env python3
"""Query manual visual evidence for an Agent-facing answer with image assets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


TOPIC_ALIASES = {
    "安全规范": ["安全规范", "安全技术规范", "婴幼儿及儿童家具安全技术规范", "家具结构安全技术规范", "GB 28007", "GB 28008"],
    "儿童床": ["儿童床", "儿童家具", "婴幼儿", "GB 28007", "GB 28008"],
}
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query visual evidence assets for a designer-manual question.")
    parser.add_argument("--text", required=True, help="Natural-language question.")
    parser.add_argument("--candidate-layer", required=True, help="Candidate layer id or directory name.")
    parser.add_argument("--topic", default="岩板", help="Visual evidence topic. First version is scoped to 岩板.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format.")
    return parser.parse_args(argv)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else dict(fallback or {})


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", normalize_inline(text))
    tokens: list[str] = []
    for token in raw_tokens:
        if token not in tokens:
            tokens.append(token)
    return tokens


def topic_terms(topic: str) -> list[str]:
    terms = [topic, *TOPIC_ALIASES.get(topic, [])]
    normalized: list[str] = []
    for term in terms:
        text = normalize_inline(term)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def resolve_manifest(skill_dir: Path, layer: str) -> dict[str, Any]:
    compare_module = load_module("compare_addendum_layers_for_manual_evidence", skill_dir / "scripts" / "compare_addendum_layers.py")
    return compare_module.resolve_manifest(skill_dir / "references" / "addenda", layer)


def resolve_artifact_path(manifest: dict[str, Any], artifact_name: str) -> Path:
    artifacts = manifest.get("artifacts", {})
    raw_path = artifacts.get(artifact_name) if isinstance(artifacts, dict) else ""
    if not raw_path:
        raise SystemExit(f"Missing artifact in manifest: {artifact_name}")
    path = Path(str(raw_path))
    return path if path.is_absolute() else (Path(str(manifest["_manifest_dir"])) / path).resolve()


def asset_path_for(skill_dir: Path, candidate_layer: str, topic: str) -> Path:
    manifest = resolve_manifest(skill_dir, candidate_layer)
    report_dir = resolve_artifact_path(manifest, "rules_candidate_file").parent
    return report_dir / "visual-evidence" / topic / "visual-assets.json"


def ensure_assets(skill_dir: Path, candidate_layer: str, topic: str, asset_path: Path) -> None:
    if asset_path.exists():
        return
    script = skill_dir / "scripts" / "build_visual_evidence_layer.py"
    subprocess.run(
        [sys.executable, str(script), "--candidate-layer", candidate_layer, "--topic", topic, "--skill-dir", str(skill_dir)],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def entry_haystack(entry: dict[str, Any]) -> str:
    fields = [
        entry.get("topic"),
        entry.get("source_title"),
        entry.get("source_path"),
        entry.get("ocr_summary"),
        " ".join(str(value) for value in entry.get("keywords", [])),
    ]
    return normalize_inline(" ".join(str(field or "") for field in fields))


def score_entry(entry: dict[str, Any], text: str) -> float:
    haystack = entry_haystack(entry)
    tokens = tokenize(text)
    score = 0.0
    topic = str(entry.get("topic") or "")
    for keyword in entry.get("keywords", []):
        keyword_text = normalize_inline(keyword)
        if len(keyword_text) >= 2 and keyword_text in text:
            score += 3.0
    for term in topic_terms(topic):
        if term and term in text:
            score += 1.0
        if term and term in haystack:
            score += 0.5
    for token in tokens:
        if token in haystack:
            score += 2.0 if token in str(entry.get("source_title") or "") else 1.0
    if topic in text:
        score += 1.0
    if entry.get("page_image"):
        score += 0.25
    if entry.get("crop_images"):
        score += 0.25
    score += float(entry.get("confidence") or 0) * 0.5
    return score


def choose_matches(entries: list[dict[str, Any]], text: str, limit: int = 3) -> list[dict[str, Any]]:
    ranked = sorted(
        ((score_entry(entry, text), entry) for entry in entries),
        key=lambda item: item[0],
        reverse=True,
    )
    matches = [dict(entry, _score=round(score, 4)) for score, entry in ranked if score > 0]
    return matches[:limit]


def build_answer(text: str, matches: list[dict[str, Any]], topic: str) -> tuple[str, bool, str]:
    if not matches:
        return (
            f"当前{topic}图文证据层没有检索到对应资料，不能编造图片或用通用行业常识补充。",
            True,
            "no_match",
        )
    missing_image = any(not match.get("page_image") for match in matches)
    blank_image = any(match.get("page_image_looks_blank") for match in matches)
    first = matches[0]
    summary = first.get("ocr_summary") or "当前页 OCR 未读到稳定文字，需要回看原图。"
    source = f"{first.get('source_title')} 第 {first.get('source_page')} 页"
    if missing_image:
        return (
            f"检索到{topic}相关资料：{summary} 来源：{source}。但当前资料缺少可展示图片证据，需要人工复核后再给企业 Agent 使用。",
            True,
            "missing_visual_asset",
        )
    if blank_image:
        return (
            f"检索到{topic}相关资料来源：{source}。但对应整页图接近空白，OCR 也没有读出可用内容；当前不能据此给出具体建议，需要重新导出来源页或人工补证据。",
            True,
            "blank_visual_asset",
        )
    return (
        f"检索到{topic}相关资料：{summary} 来源：{source}。已附对应整页图，避免自动裁剪图误导判断。",
        False,
        "",
    )


def build_response(*, text: str, candidate_layer: str, topic: str, skill_dir: Path) -> dict[str, Any]:
    asset_path = asset_path_for(skill_dir, candidate_layer, topic)
    ensure_assets(skill_dir, candidate_layer, topic, asset_path)
    assets = load_json(asset_path, {"entries": []})
    entries = [entry for entry in assets.get("entries", []) if isinstance(entry, dict)]
    matches = choose_matches(entries, text)
    answer, answer_needs_review, answer_review_reason = build_answer(text, matches, topic)
    page_images = [str(match.get("page_image")) for match in matches if match.get("page_image")]
    debug_crop_images: list[str] = []
    for match in matches:
        debug_crop_images.extend(str(path) for path in match.get("debug_crop_images") or match.get("crop_images", []) if path)
    source_refs = [
        {
            "source_title": match.get("source_title", ""),
            "source_page": match.get("source_page", 0),
            "source_path": match.get("source_path", ""),
        }
        for match in matches
    ]
    confidence = max([float(match.get("confidence") or 0) for match in matches], default=0.0)
    evidence_statuses = [str(match.get("evidence_status") or "") for match in matches]
    needs_human_review = answer_needs_review or any(status == "needs_human_review" for status in evidence_statuses)
    agent_visual_review = bool(matches) and not needs_human_review and any(
        status == "agent_visual_review" for status in evidence_statuses
    )
    review_reasons = [str(match.get("review_reason")) for match in matches if match.get("review_reason")]
    unique_review_reasons = list(dict.fromkeys(review_reasons))
    review_reason = answer_review_reason or "; ".join(unique_review_reasons)
    agent_guidance = ""
    if agent_visual_review:
        agent_guidance = "当前匹配有整页图但 OCR 文字偏弱，Agent 应直接阅读整页图，不要求人工先介入。"
    return {
        "answer": answer,
        "matches": matches,
        "page_images": page_images,
        "crop_images": [],
        "debug_crop_images": debug_crop_images,
        "source_refs": source_refs,
        "confidence": confidence,
        "evidence_status": "needs_human_review" if needs_human_review else ("agent_visual_review" if agent_visual_review else "agent_ready"),
        "agent_guidance": agent_guidance,
        "needs_human_review": needs_human_review,
        "review_reason": review_reason,
    }


def render_text(response: dict[str, Any]) -> str:
    lines = [str(response.get("answer") or "")]
    if response.get("page_images"):
        lines.append("整页图：")
        lines.extend(f"- {path}" for path in response["page_images"])
    if response.get("debug_crop_images"):
        lines.append("调试裁剪图：")
        lines.extend(f"- {path}" for path in response["debug_crop_images"][:6])
    if response.get("agent_guidance"):
        lines.append(f"Agent 处理建议：{response.get('agent_guidance')}")
    if response.get("needs_human_review"):
        lines.append(f"需人工复核：{response.get('review_reason') or '证据不足'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    response = build_response(text=args.text, candidate_layer=args.candidate_layer, topic=args.topic, skill_dir=skill_dir)
    if args.output == "json":
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(render_text(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
