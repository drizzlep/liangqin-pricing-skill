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
    load_active_layer_manifests,
    resolve_manifest_artifact_path,
)

FOCUS_TERMS = (
    "床垫重量",
    "举升器",
    "限位器",
    "床垫限位器",
    "尾翻箱体床",
    "侧翻箱体床",
    "床头方向",
    "锁扣相反方向",
    "开启方式",
    "开启方向",
    "奇数柜门",
    "单数柜门",
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
    "凹槽内退尺寸",
    "节点尺寸",
    "直角圆边",
    "窄边高柜",
    "顶挡条",
    "有线开关",
    "走线位置",
    "开关名称",
    "备注安装位置",
    "现场确定开关位置",
    "分区控制",
    "多个开关",
    "额外收费",
    "外露式",
    "安装位置及使用方式",
    "底装",
    "侧装",
    "手扫开启",
    "触摸开关",
    "集控感应开关",
    "人体红外感应开关",
    "手扫感应开关",
    "触模感应开关",
    "内空高度",
    "内空长度",
    "床屉板",
    "小蜻蜓举升器",
    "默认挡位",
    "排骨架",
    "排骨条",
    "排骨条宽",
    "单块排骨架",
    "双块排骨架",
    "抽面",
    "全盖层板",
    "内嵌抽屉",
    "四边内嵌",
    "推拉门",
    "单小块门板",
    "内缩",
    "22厚门板",
    "26厚门板",
    "带抽屉桌",
    "抽屉内部空间",
    "抽屉净空",
    "并立书桌",
    "拆装结构",
    "搬运",
    "入户门",
    "进户",
    "升降桌",
    "带屉升降桌",
    "预留插座",
    "插线板",
    "现场接线",
    "剪插头",
    "改线",
    "弹簧电源线",
    "罗胖带屉餐桌",
    "罗胖书桌",
    "屉柜总长",
    "屉柜宽度",
    "屉柜深度",
    "屉柜高度",
    "标准屉柜高度",
    "经典圆餐桌",
    "桌面直径",
    "简美大桌",
    "订制上限",
    "无屉定制款",
    "横称高度",
    "定制无腿书桌",
    "无腿书桌",
    "承重墙",
    "左右与柜子固定",
    "高度≤150",
    "儿童家具",
    "儿童拉手",
    "优先使用扣手",
    "藤编",
    "网布",
    "翻门",
    "翻板",
    "玻璃部件",
    "儿童高架床",
    "上层床",
    "进出通道",
    "挂梯",
    "踏步",
    "儿童木质拉手",
    "甜甜圈",
    "云朵",
    "小熊",
    "小鱼",
    "兔子",
    "四叶草",
    "托称",
    "空区托称",
    "前托称",
    "后托称",
    "60*26",
    "70*26",
    "80*26",
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
    if "手扫雷达开关" in text and ("安装" in text or "怎么装" in text or "底装" in text or "侧装" in text):
        focus_terms.extend(["安装位置及使用方式", "底装", "侧装", "触摸开关"])
    if "集控" in text and ("感应开关" in text or "人体红外" in text or "手扫" in text or "触摸" in text):
        focus_terms.extend(["集控感应开关", "人体红外感应开关", "手扫感应开关", "触模感应开关"])
    if ("举升器" in text or "小蜻蜓" in text) and ("内空" in text or "床屉板" in text):
        focus_terms.extend(["内空高度", "内空长度", "床屉板", "小蜻蜓举升器"])
    if ("床垫限位器" in text or "限位器" in text) and ("尾翻" in text or "侧翻" in text or "床头" in text or "锁扣" in text or "几个" in text or "规格" in text):
        focus_terms.extend(["床垫限位器", "尾翻箱体床", "侧翻箱体床", "床头方向", "锁扣相反方向", "50*80*260", "1500mm"])
    if "排骨架" in text and ("双块" in text or "单块" in text or "排骨条" in text or "1450" in text or "80" in text):
        focus_terms.extend(["单块排骨架", "双块排骨架", "排骨条宽", "排骨条"])
    if ("抽面" in text or "抽屉" in text) and ("内嵌" in text or "全盖层板" in text or "26厚" in text or "22mm" in text):
        focus_terms.extend(["抽面", "全盖层板", "内嵌抽屉", "四边内嵌", "22厚门板", "26厚门板"])
    if "推拉门" in text and ("内缩" in text or "单小块门板" in text or "22厚" in text or "60mm" in text or "65mm" in text):
        focus_terms.extend(["推拉门", "单小块门板", "内缩", "22厚门板"])
    if ("书桌" in text or "桌" in text) and ("抽屉内部空间" in text or "抽屉净空" in text or "钢管" in text or "1400" in text):
        focus_terms.extend(["带抽屉桌", "抽屉内部空间", "抽屉净空", "钢管"])
    if ("并立书桌" in text or "书桌" in text) and ("分段" in text or "拆装" in text or "搬运" in text or "入户" in text or "进户" in text):
        focus_terms.extend(["并立书桌", "拆装结构", "搬运", "入户门", "进户"])
    if "升降桌" in text and ("电源" in text or "插座" in text or "插线板" in text or "接线" in text or "插头" in text):
        focus_terms.extend(["升降桌", "预留插座", "插线板", "现场接线", "剪插头", "改线", "弹簧电源线"])
    if "罗胖" in text and ("屉柜" in text or "双面抽屉" in text or "单面抽屉" in text or "L-160" in text or "L-180" in text or "L-220" in text):
        focus_terms.extend(["罗胖带屉餐桌", "罗胖书桌", "屉柜总长", "屉柜宽度", "屉柜深度", "屉柜高度", "标准屉柜高度"])
    if "罗胖" in text and ("订制" in text or "上限" in text or "长度" in text or "宽度" in text):
        focus_terms.extend(["罗胖桌系列", "订制上限", "长度不超过2000mm", "宽度不超过900mm"])
    if ("经典圆餐桌" in text or "简美大桌" in text) and ("订制" in text or "尺寸上限" in text or "直径" in text or "长度" in text or "宽度" in text):
        focus_terms.extend(["经典圆餐桌", "桌面直径", "简美大桌", "订制上限"])
    if ("并立书桌" in text or "定制并立书桌" in text) and ("无屉" in text or "横称" in text or "2200" in text or "屉柜移至一侧" in text):
        focus_terms.extend(["无屉款", "无屉定制款", "横称高度", "2200mm", "屉柜可移至一侧"])
    if "无腿书桌" in text and ("固定" in text or "承重墙" in text or "抽屉" in text or "进深" in text or "高度" in text):
        focus_terms.extend(["定制无腿书桌", "无腿书桌", "承重墙", "左右与柜子固定", "高度≤150", "带屉定制款", "无屉定制款"])
    if ("奇数柜门" in text or "单数柜门" in text or "柜门数量" in text) and ("开启方向" in text or "图纸" in text or "附图" in text):
        focus_terms.extend(["奇数柜门", "单数柜门", "开启方向", "附图说明开启方向"])
    if "儿童家具" in text and ("拉手" in text or "翻门" in text or "翻板" in text or "玻璃" in text or "藤编" in text or "网布" in text):
        focus_terms.extend(["儿童家具", "儿童拉手", "优先使用扣手", "藤编", "网布", "翻门", "翻板", "玻璃部件"])
    if ("儿童床" in text or "高架床" in text or "上层床" in text) and ("进出通道" in text or "挂梯" in text or "梯子" in text or "踏步" in text or "围栏" in text):
        focus_terms.extend(["儿童高架床", "上层床", "进出通道", "挂梯", "踏步", "500mm", "400mm", "小于7mm", "60-75mm"])
    if ("儿童拉手" in text or "儿童房家具" in text) and ("甜甜圈" in text or "云朵" in text or "小熊" in text or "小鱼" in text or "兔子" in text or "四叶草" in text):
        focus_terms.extend(["儿童木质拉手", "甜甜圈", "云朵", "小熊", "小鱼", "兔子", "四叶草"])
    if "托称" in text and ("空区" in text or "前托称" in text or "后托称" in text or "60*26" in text or "70*26" in text or "80*26" in text):
        focus_terms.extend(["托称", "空区托称", "前托称", "后托称", "60*26", "70*26", "80*26"])
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
            "凹槽内退尺寸",
            "节点尺寸",
            "直角圆边",
            "窄边高柜",
            "顶挡条",
            "有线开关",
            "走线位置",
            "开关名称",
            "备注安装位置",
            "现场确定开关位置",
            "分区控制",
            "多个开关",
            "额外收费",
            "外露式",
            "安装位置及使用方式",
            "底装",
            "侧装",
            "手扫开启",
            "触摸开关",
            "集控感应开关",
            "人体红外感应开关",
            "手扫感应开关",
            "触模感应开关",
            "内空高度",
            "内空长度",
            "床屉板",
            "小蜻蜓举升器",
            "默认挡位",
            "床垫限位器",
            "尾翻箱体床",
            "侧翻箱体床",
            "床头方向",
            "锁扣相反方向",
            "排骨架",
            "排骨条",
            "排骨条宽",
            "单块排骨架",
            "双块排骨架",
            "抽面",
            "全盖层板",
            "内嵌抽屉",
            "四边内嵌",
            "推拉门",
            "单小块门板",
            "内缩",
            "22厚门板",
            "26厚门板",
            "带抽屉桌",
            "抽屉内部空间",
            "抽屉净空",
            "并立书桌",
            "拆装结构",
            "搬运",
            "入户门",
            "进户",
            "升降桌",
            "带屉升降桌",
            "预留插座",
            "插线板",
            "现场接线",
            "剪插头",
            "改线",
            "弹簧电源线",
            "罗胖带屉餐桌",
            "罗胖书桌",
            "屉柜总长",
            "屉柜宽度",
            "屉柜深度",
            "屉柜高度",
            "标准屉柜高度",
            "经典圆餐桌",
            "桌面直径",
            "简美大桌",
            "订制上限",
            "无屉定制款",
            "横称高度",
            "定制无腿书桌",
            "无腿书桌",
            "承重墙",
            "左右与柜子固定",
            "高度≤150",
            "奇数柜门",
            "单数柜门",
            "儿童家具",
            "儿童拉手",
            "优先使用扣手",
            "藤编",
            "网布",
            "翻门",
            "翻板",
            "玻璃部件",
            "儿童高架床",
            "上层床",
            "进出通道",
            "挂梯",
            "踏步",
            "儿童木质拉手",
            "甜甜圈",
            "云朵",
            "小熊",
            "小鱼",
            "兔子",
            "四叶草",
            "托称",
            "空区托称",
            "前托称",
            "后托称",
            "60*26",
            "70*26",
            "80*26",
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


def normalize_lookup_text(text: str) -> str:
    return "".join(str(text).split()).lower()


def load_active_knowledge_sources(addenda_root: Path) -> list[dict[str, Any]]:
    knowledge_sources: list[dict[str, Any]] = []
    for manifest in load_active_layer_manifests(addenda_root):
        artifacts = manifest.get("artifacts", {})
        knowledge_layer_file = artifacts.get("knowledge_layer_file")
        if not knowledge_layer_file:
            continue
        knowledge_path = resolve_manifest_artifact_path(manifest, knowledge_layer_file)
        if not knowledge_path.exists():
            continue
        payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
        knowledge_sources.append(
            {
                "manifest": manifest,
                "entries": payload.get("entries", []),
            }
        )
    return knowledge_sources


def choose_knowledge_match(text: str, knowledge_sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw_text = str(text)
    normalized_text = normalize_lookup_text(raw_text)
    best_match: dict[str, Any] | None = None
    best_score = 0

    for source in knowledge_sources:
        manifest = source["manifest"]
        for entry in source["entries"]:
            if not isinstance(entry, dict):
                continue
            trigger_terms = [str(term).strip() for term in entry.get("trigger_terms", []) if str(term).strip()]
            topic = str(entry.get("topic", "")).strip()
            matched_terms = [
                term
                for term in trigger_terms
                if term in raw_text or normalize_lookup_text(term) in normalized_text
            ]
            topic_match = topic and (topic in raw_text or normalize_lookup_text(topic) in normalized_text)
            if not matched_terms and not topic_match:
                continue

            score = sum(max(len(term), 2) for term in matched_terms)
            if topic_match:
                score += max(min(len(topic), 12), 4)
            score += len(matched_terms) * 3
            if entry.get("evidence_level") == "hard_rule":
                score += 2

            if score > best_score:
                best_score = score
                best_match = {
                    "layer_name": str(manifest.get("layer_name", "")),
                    "entry": entry,
                    "score": score,
                }

    return best_match


def score_runtime_focus(entries: list[dict[str, Any]], focus_terms: list[str], text: str) -> int:
    if not entries:
        return 0
    raw_text = str(text)
    normalized_text = normalize_lookup_text(raw_text)
    best_score = 0
    for entry in entries:
        haystack = f"{entry.get('title', '')} {entry.get('detail', '')}"
        normalized_haystack = normalize_lookup_text(haystack)
        matched_terms = [
            term
            for term in focus_terms
            if term in haystack or normalize_lookup_text(term) in normalized_haystack
        ]
        score = sum(max(len(term), 2) for term in matched_terms)
        if matched_terms:
            score += len(matched_terms) * 2
        if haystack and any(chunk in haystack for chunk in [raw_text.strip(), normalized_text]):
            score += 1
        best_score = max(best_score, score)
    return best_score


def naturalize_runtime_detail(detail: str) -> str:
    text = str(detail).strip()
    replacements = (
        ("柜体中，", "柜体里，"),
        ("最少需要留出", "至少预留"),
        ("需明确备注", "要明确备注"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def build_natural_runtime_answer(
    *,
    reply_mode: str,
    follow_ups: list[dict[str, Any]],
    constraints: list[dict[str, Any]],
    adjustments: list[dict[str, Any]],
) -> tuple[str, str, str]:
    if reply_mode == "follow_up" and follow_ups:
        question = str(follow_ups[0].get("question", "")).strip()
        supporting_entries = [*constraints, *adjustments]
        if supporting_entries:
            support_title = str(supporting_entries[0].get("title", "")).strip()
            support_detail = naturalize_runtime_detail(str(supporting_entries[0].get("detail", "")).strip())
            confidence_note = "；".join(part for part in [support_title, support_detail] if part)
        else:
            confidence_note = ""
        return question, "needs_confirmation", confidence_note
    if constraints:
        title = str(constraints[0].get("title", "")).strip()
        detail = naturalize_runtime_detail(str(constraints[0].get("detail", "")).strip())
        if title and title not in detail:
            summary = f"这个场景有明确要求。{title}。{detail}".strip()
        else:
            summary = f"这个场景有明确要求。{detail}".strip()
        return summary, "hard_rule", ""
    if adjustments:
        title = str(adjustments[0].get("title", "")).strip()
        detail = naturalize_runtime_detail(str(adjustments[0].get("detail", "")).strip())
        if title and title not in detail:
            summary = f"这块有明确的补充规则。{title}，{detail}".strip()
        else:
            summary = f"这块有明确的补充规则。{detail}".strip()
        return summary, "hard_rule", ""
    return "", "needs_confirmation", ""


def build_natural_knowledge_answer(match: dict[str, Any]) -> tuple[str, str, str]:
    entry = match["entry"]
    evidence_level = str(entry.get("evidence_level", "high_confidence_review")).strip() or "high_confidence_review"
    base_summary = str(entry.get("answerable_summary", "")).strip()
    answer_lead = str(entry.get("answer_lead", "")).strip()
    if evidence_level == "hard_rule":
        prefix = answer_lead or "这个场景有明确要求。"
        summary = f"{prefix}{base_summary}".strip()
    elif evidence_level == "high_confidence_review":
        prefix = answer_lead or "这块目前有比较明确的结构口径，但还没到完全可程序化的程度。"
        summary = f"{prefix}{base_summary}".strip()
    else:
        prefix = answer_lead or "这块目前能确认到一部分信息。"
        summary = f"{prefix}{base_summary}".strip()
    raw_note = str(entry.get("do_not_overclaim", "")).strip()
    if evidence_level == "high_confidence_review":
        prefix = "这块目前还是高置信复盘口径，术语口径还没完全锁定。"
        confidence_note = f"{prefix}{raw_note}".strip()
    else:
        confidence_note = raw_note
    return summary, evidence_level, confidence_note


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
            if kind in {"constraint", "catalog_option"} and all(
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

    knowledge_match = None
    if not follow_ups:
        knowledge_match = choose_knowledge_match(text, load_active_knowledge_sources(addenda_root))
        if knowledge_match and (not constraints and not adjustments):
            constraints = []
            adjustments = []
            follow_ups = []
        elif knowledge_match and strict_focus:
            runtime_focus_score = score_runtime_focus([*constraints, *adjustments], focus_terms, text)
            if int(knowledge_match.get("score", 0)) > runtime_focus_score:
                constraints = []
                adjustments = []
                follow_ups = []

    if follow_ups:
        reply_mode = "follow_up"
    elif constraints or adjustments or knowledge_match:
        reply_mode = "rule_explanation"
    else:
        reply_mode = "none"

    answer_style = "none"
    answer_summary = ""
    evidence_level = "needs_confirmation"
    confidence_note = ""
    if knowledge_match:
        answer_style = "natural_rule_explanation"
        answer_summary, evidence_level, confidence_note = build_natural_knowledge_answer(knowledge_match)
    elif reply_mode in {"follow_up", "rule_explanation"}:
        answer_style = "natural_rule_explanation"
        answer_summary, evidence_level, confidence_note = build_natural_runtime_answer(
            reply_mode=reply_mode,
            follow_ups=follow_ups,
            constraints=constraints,
            adjustments=adjustments,
        )

    suggested_parts: list[str] = []
    if answer_summary:
        suggested_parts.append(answer_summary)
    if confidence_note:
        suggested_parts.append(confidence_note)

    return {
        "matched": bool(follow_ups or constraints or adjustments or knowledge_match),
        "recommended_reply_mode": reply_mode,
        "follow_up_questions": follow_ups,
        "constraints": constraints,
        "adjustments": adjustments,
        "addendum_notes": merged.get("addendum_notes", []),
        "answer_style": answer_style,
        "answer_summary": answer_summary,
        "evidence_level": evidence_level,
        "confidence_note": confidence_note,
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
