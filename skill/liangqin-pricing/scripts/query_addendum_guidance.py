#!/usr/bin/env python3
"""Query active addendum runtime rules for a natural-language message."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from apply_addendum_layers import (
    apply_addendum_layers,
    build_decision,
    choose_matches,
    choose_runtime_matches,
    classify_match,
    infer_missing_required_fields,
    load_active_layer_sources,
)

FOCUS_TERMS = (
    "床垫重量",
    "举升器",
    "限位器",
    "开启方式",
    "开启方向",
    "无把手",
    "无抠手",
    "单色温灯带",
    "无线单面板动能开关",
    "纹理连续",
    "连纹",
    "补差",
    "岩板长度",
    "空区高度",
    "超出侧板面积",
    "柜侧前开口",
    "柜侧前缺口",
    "柜侧闭合缺口",
    "遇见书柜",
    "分段缝",
    "开放格",
    "常规拆装柜体",
    "牙称",
    "牙称高度",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query active addendum guidance for a natural-language message.")
    parser.add_argument("--text", required=True, help="User message to evaluate against active addendum rules.")
    parser.add_argument(
        "--addenda-root",
        default=str(Path(__file__).resolve().parent.parent / "references" / "addenda"),
        help="Directory containing active addendum layer manifests.",
    )
    return parser.parse_args(argv)


def build_probe_payload(text: str) -> dict[str, Any]:
    return {
        "items": [
            {
                "product": text,
                "confirmed": text,
                "pricing_method": "规则咨询",
                "calculation_steps": [],
                "subtotal": "待确认",
            }
        ],
        "total": "待确认",
    }


def extract_focus_terms(text: str) -> list[str]:
    focus_terms = [term for term in FOCUS_TERMS if term in text]
    if "榻榻米" in text and "托称" in text:
        focus_terms.append("榻榻米组合柜空区加托称时需固定上墙")
    if "柜侧前开口" in text:
        focus_terms.append("柜侧前开口尺寸限制")
    if "柜侧前缺口" in text:
        focus_terms.append("柜侧前缺口尺寸限制")
    if "柜侧闭合缺口" in text:
        focus_terms.append("柜侧闭合缺口尺寸限制")
    if "遇见书柜" in text:
        focus_terms.append("遇见书柜下柜高度超过1700mm时不建议做侧包顶底")
    if "开放格" in text and "分段缝" in text:
        focus_terms.append("超高带门柜体开放格分段缝优先对齐层板上方")
    if "常规拆装柜体" in text and ("顶盖侧" in text or "侧盖顶" in text or "1700" in text):
        focus_terms.append("常规拆装柜体高度≤1700mm默认顶盖侧，＞1700mm默认侧盖顶")
    if "牙称" in text:
        focus_terms.append("常规拆装柜体牙称常用50/80mm，允许范围50-250mm")
    if "岩板" in text and "台面" in text:
        focus_terms.append("岩板台面")
    if "岩板" in text and "背板" in text:
        focus_terms.append("岩板背板")
    if "铝框" in text and "岩板" in text and ("门" in text or "门板" in text):
        focus_terms.extend(["铝框岩板门板", "铝框岩板门"])
    return list(dict.fromkeys(focus_terms))


def should_use_strict_focus(focus_terms: list[str]) -> bool:
    return any(
        term in {
            "岩板台面",
            "岩板背板",
            "铝框岩板门板",
            "铝框岩板门",
            "岩板长度",
            "空区高度",
            "超出侧板面积",
            "榻榻米组合柜空区加托称时需固定上墙",
            "柜侧前开口尺寸限制",
            "柜侧前缺口尺寸限制",
            "柜侧闭合缺口尺寸限制",
            "遇见书柜下柜高度超过1700mm时不建议做侧包顶底",
            "超高带门柜体开放格分段缝优先对齐层板上方",
            "常规拆装柜体高度≤1700mm默认顶盖侧，＞1700mm默认侧盖顶",
            "常规拆装柜体牙称常用50/80mm，允许范围50-250mm",
        }
        for term in focus_terms
    )


def filter_by_focus(entries: list[dict[str, Any]], focus_terms: list[str], *, fallback_to_original: bool = True) -> list[dict[str, Any]]:
    if not focus_terms:
        return entries
    focused = [
        entry
        for entry in entries
        if any(term in f"{entry.get('title', '')} {entry.get('detail', '')}" for term in focus_terms)
    ]
    if focused:
        return focused
    if fallback_to_original:
        return entries
    return []


def query_guidance(text: str, addenda_root: Path) -> dict[str, Any]:
    probe_payload = build_probe_payload(text)
    probe_item = probe_payload["items"][0]
    merged = apply_addendum_layers(probe_payload, addenda_root)
    item = (merged.get("items") or [{}])[0]
    decisions = item.get("addendum_decisions") or {}
    follow_ups = list(decisions.get("follow_up_questions") or [])
    constraints = list(decisions.get("constraints") or [])
    adjustments = list(decisions.get("adjustments") or [])

    for layer_source in load_active_layer_sources(addenda_root):
        manifest = layer_source["manifest"]
        rules = layer_source["rules"]
        if layer_source["match_mode"] == "runtime":
            matches = choose_runtime_matches(probe_item, rules)
        else:
            matches = choose_matches(probe_item, rules)
        for match in matches:
            kind = str(match.get("action_type", "")) or classify_match(match)
            missing_fields = infer_missing_required_fields(probe_item, match)
            decision = build_decision(str(manifest["layer_name"]), match, kind)
            if kind == "constraint" and all(
                existing.get("title") != decision["title"] or existing.get("detail") != decision["detail"]
                for existing in constraints
            ):
                constraints.append(decision)
            if kind == "adjustment" and all(
                existing.get("title") != decision["title"] or existing.get("detail") != decision["detail"]
                for existing in adjustments
            ):
                adjustments.append(decision)
            if missing_fields:
                follow_up = build_decision(
                    str(manifest["layer_name"]),
                    match,
                    "follow_up",
                    required_fields=missing_fields,
                )
                if all(existing.get("question") != follow_up["question"] for existing in follow_ups):
                    follow_ups.append(follow_up)

    focus_terms = extract_focus_terms(text)
    strict_focus = should_use_strict_focus(focus_terms)
    follow_ups = filter_by_focus(follow_ups, focus_terms)
    constraints = filter_by_focus(constraints, focus_terms, fallback_to_original=not strict_focus)
    adjustments = filter_by_focus(adjustments, focus_terms, fallback_to_original=not strict_focus)

    if follow_ups:
        reply_mode = "follow_up"
    elif constraints or adjustments:
        reply_mode = "rule_explanation"
    else:
        reply_mode = "none"

    suggested_parts: list[str] = []
    if reply_mode == "follow_up" and follow_ups:
        suggested_parts.append(follow_ups[0]["question"])
        supporting_entries = [*constraints, *adjustments]
        if supporting_entries:
            supporting_text = "；".join(
                f"{entry.get('title', '').strip()}；{entry.get('detail', '').strip()}".strip("；")
                for entry in supporting_entries[:2]
                if entry.get("title") or entry.get("detail")
            )
            if supporting_text:
                suggested_parts.append(f"当前追加规则：{supporting_text}")
    elif reply_mode == "rule_explanation":
        explanation_text = "；".join(
            f"{entry.get('title', '').strip()}；{entry.get('detail', '').strip()}".strip("；")
            for entry in [*constraints, *adjustments][:3]
            if entry.get("title") or entry.get("detail")
        )
        if explanation_text:
            suggested_parts.append(explanation_text)

    return {
        "matched": bool(follow_ups or constraints or adjustments),
        "recommended_reply_mode": reply_mode,
        "follow_up_questions": follow_ups,
        "constraints": constraints,
        "adjustments": adjustments,
        "addendum_notes": merged.get("addendum_notes", []),
        "suggested_reply": "\n".join(suggested_parts).strip(),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = query_guidance(args.text, Path(args.addenda_root).expanduser().resolve())
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
