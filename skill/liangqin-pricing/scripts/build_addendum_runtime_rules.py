#!/usr/bin/env python3
"""Build explicit runtime rules for an independent addendum layer."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


GENERIC_TERMS = {
    "柜体",
    "材质",
    "公式",
    "尺寸阈值",
    "表格",
    "门型",
    "投影面积",
    "计价",
    "规则",
    "说明",
    "默认",
    "产品",
}

SIGNAL_TERMS = [
    "流云",
    "飞瀑",
    "纹理连续",
    "无把手",
    "无抠手",
    "开启方式",
    "平板门",
    "拼框门",
    "玻璃门",
    "格栅门",
    "开放格",
    "圆边",
    "层板",
    "背板",
    "书梯",
    "抽屉",
    "抽面",
    "天地铰链",
    "举升器",
    "床垫",
    "排骨架",
    "榻榻米",
    "拉手",
    "灯带",
    "开关",
    "岩板",
    "洞洞板",
    "轨道插座",
    "儿童房",
    "冰箱柜",
    "钻石柜",
    "操作空区",
]

LOW_SIGNAL_TERMS = {
    "门型",
    "材质",
    "长度",
    "高度",
    "宽度",
    "进深",
    "投影面积",
    "开启方式",
    "拉手",
    "抽屉",
    "抽面",
    "层板",
    "背板",
    "门板",
    "柜门",
    "柜体",
    "灯带",
    "开关",
}

MEDIUM_RISK_DENYLIST: dict[int, tuple[str, ...]] = {
    78: ("DG-02", "圆直腿", "圆斜腿"),
    203: ("快速检索表", "拼框平开门尺寸限制"),
    206: ("快速检索表", "拼框平开门尺寸限制"),
    207: ("快速检索表", "拼框平开门尺寸限制", "门高＞1500"),
    208: ("快速检索表", "拼框平开门", "≤2300"),
}

HIGH_SIGNAL_KEYWORDS = tuple(term for term in SIGNAL_TERMS if term not in LOW_SIGNAL_TERMS) + (
    "连纹",
    "断开连纹",
    "空区高度",
    "超出侧板面积",
    "岩板背板",
    "岩板台面",
    "床垫限位器",
    "顶挡条",
    "牙称",
)

FIELD_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("床垫重量", ("床垫重量", "超重", "举升器")),
    ("开启方式", ("开启方式", "开启方向", "按弹开启", "推弹开启", "抠手开启", "拉手开启", "无把手", "无抠手")),
    ("门型", ("门型", "平板门", "拼框门", "玻璃门", "格栅门")),
    ("进深", ("进深", "深度")),
    ("材质", ("材质", "木种", "黑胡桃", "樱桃木", "白橡木", "白蜡木", "玫瑰木")),
    ("长度", ("长度", "长边", "长向")),
    ("高度", ("高度", "高", "离地")),
    ("宽度", ("宽度", "宽", "宽向")),
    ("投影面积", ("投影面积",)),
]

NOISY_TITLE_PHRASES = (
    "打开米家APP",
    "点击首页",
    "选择添加设备",
    "下一步",
    "界面显示连接中",
    "连接成功",
)

BACKGROUND_KEYWORDS = (
    "前言",
    "设计师标准手册",
    "原木定制三大误区",
    "木材小知识",
    "nhla",
    "拆装注意事项",
)

MATERIAL_KNOWLEDGE_KEYWORDS = (
    "nhla分等规则",
    "了解nhla分等规则",
    "美国硬木",
    "净划面数量",
)

PRICING_SIGNAL_KEYWORDS = (
    "报价",
    "价格",
    "单价",
    "计价",
    "加价",
    "补差",
    "收费",
    "折减",
    "尺寸",
    "限制",
    "默认",
    "备注",
    "开启",
    "门型",
    "材质",
    "适用",
    "应≤",
    "应≥",
    "不可",
    "不能",
    "纹理",
    "连纹",
    "拉手",
    "灯带",
    "举升器",
    "床垫",
    "榻榻米",
    "抽屉",
    "铰链",
    "背板",
    "层板",
    "轨道",
    "开关",
    "玻璃门",
    "平板门",
    "拼框门",
)

PRODUCT_TITLE_PATTERN = re.compile(
    r"([^\s。；•，,:：]{2,40}(?:开关|拉手|铰链|门板|柜门|铝框门|格栅门|拼框门|平板门|门|背板|抽屉|举升器|灯带|榻榻米|床|轨道))"
)
SHORT_PRODUCT_TITLE_PATTERN = re.compile(r"([^\s。；•，,:：]{2,16}(?:开关|拉手|铰链|举升器|灯带|轨道))")
WIRELESS_PRODUCT_TITLE_PATTERN = re.compile(r"(无线[^\s。；•，,:：]{1,20}开关)")
INSTALLATION_TITLE_PATTERN = re.compile(r"([^\s。；•，,:：]{2,30}安装于[^\s。；•，,:：]{2,12})")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build explicit runtime rules from addendum rules-index JSON.")
    parser.add_argument("--input", required=True, help="Path to rules-index JSON.")
    parser.add_argument("--output", required=True, help="Path to write runtime-rules JSON.")
    parser.add_argument("--layer-id", required=True, help="Stable addendum layer id.")
    parser.add_argument("--layer-name", required=True, help="Human readable addendum layer name.")
    return parser.parse_args(argv)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).replace("\r", "\n").replace("\n", " ")).strip()


def strip_leading_marker(text: str) -> str:
    return re.sub(
        r"^(?:(?:[0-9一二三四五六七八九十]+[.\-、]|[（(][0-9一二三四五六七八九十]+[)）])|(?:[0-9]+(?=[\u4e00-\u9fff])))\s*",
        "",
        text,
    ).strip()


def mostly_numeric(text: str) -> bool:
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return True
    numeric_like = [
        char
        for char in visible
        if char.isdigit() or char in {"≤", "≥", "<", ">", "*", "/", ".", "-", "=", "m", "M", "W", "H", "L"}
    ]
    return len(numeric_like) / max(len(visible), 1) > 0.55


def is_noisy_title(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    if any(phrase in normalized for phrase in NOISY_TITLE_PHRASES):
        return True
    if mostly_numeric(normalized):
        return True
    return False


def candidate_title_score(candidate: str, detail: str, tags: list[str]) -> int:
    text = strip_leading_marker(normalize_text(candidate))
    if not text:
        return -100

    score = 0
    if not is_noisy_title(text):
        score += 4
    else:
        score -= 4
    if 6 <= len(text) <= 36:
        score += 2
    elif len(text) <= 60:
        score += 1
    if any(term in text for term in SIGNAL_TERMS):
        score += 3
    if any(tag and tag not in GENERIC_TERMS and tag in text for tag in tags):
        score += 2
    if any(keyword in text for keyword in ("需", "应", "默认", "不可", "不能", "备注", "适用", "加价", "收费")):
        score += 2
    if "安装于" in text:
        score += 3
    if re.fullmatch(r"[^\s。；•，,:：]{2,16}(?:开关|拉手|铰链|举升器|灯带|轨道)", text):
        score += 5
    if re.search(r"(开关|拉手|铰链|门板|柜门|铝框门|格栅门|拼框门|平板门|背板|抽屉|举升器|灯带|榻榻米|轨道)", text):
        score += 3
    if len(text) <= 8 and re.search(r"(床垫限位器床|分别连续)", text):
        score -= 4
    if "适用于所有型号" in text and len(text) > 18:
        score -= 2
    if text in normalize_text(detail):
        score += 1
    return score


def clean_runtime_detail(detail: str, domain: str) -> str:
    normalized_detail = normalize_text(detail)
    if not normalized_detail:
        return normalized_detail

    if domain == "accessory" and any(phrase in normalized_detail for phrase in NOISY_TITLE_PHRASES):
        wireless_match = WIRELESS_PRODUCT_TITLE_PATTERN.search(normalized_detail)
        if wireless_match:
            return normalized_detail[wireless_match.start() :].strip()
        for match in PRODUCT_TITLE_PATTERN.finditer(normalized_detail):
            candidate = match.group(1)
            if candidate.endswith(("开关", "灯带", "拉手", "轨道")):
                return normalized_detail[match.start() :].strip()
    return normalized_detail


def preferred_runtime_title(detail: str, domain: str) -> str:
    if domain == "accessory":
        wireless_match = WIRELESS_PRODUCT_TITLE_PATTERN.search(detail)
        if wireless_match:
            return strip_leading_marker(wireless_match.group(1))
        match = SHORT_PRODUCT_TITLE_PATTERN.search(detail)
        if match:
            return strip_leading_marker(match.group(1))
    return ""


def choose_runtime_title(title: str, detail: str, tags: list[str]) -> str:
    normalized_title = normalize_text(title)
    normalized_detail = normalize_text(detail)
    candidates: list[str] = []

    def add(candidate: str) -> None:
        normalized_candidate = strip_leading_marker(normalize_text(candidate))
        if normalized_candidate and normalized_candidate not in candidates:
            candidates.append(normalized_candidate)

    explicit_rule_keywords = ("需", "应", "默认", "不可", "不能", "备注", "适用", "加价", "收费", "开启方式")
    stripped_title = strip_leading_marker(normalized_title)
    if stripped_title and not is_noisy_title(stripped_title) and any(keyword in stripped_title for keyword in explicit_rule_keywords):
        return stripped_title

    add(normalized_title)
    for chunk in re.split(r"[。；，]", normalized_title):
        add(chunk)
    for chunk in re.split(r"[。；•]", normalized_detail):
        add(chunk)
    for match in SHORT_PRODUCT_TITLE_PATTERN.findall(normalized_detail):
        add(match)
    for match in INSTALLATION_TITLE_PATTERN.findall(normalized_detail):
        add(match)
    for match in PRODUCT_TITLE_PATTERN.findall(normalized_detail):
        add(match)

    if not candidates:
        return "追加规则"

    best = max(candidates, key=lambda candidate: candidate_title_score(candidate, normalized_detail, tags))
    if candidate_title_score(best, normalized_detail, tags) < 0 and normalized_title:
        return strip_leading_marker(normalized_title) or "追加规则"
    return best


def runtime_noise_score(
    *,
    title: str,
    detail: str,
    domain: str,
    relevance_score: int,
) -> int:
    combined = f"{title} {detail}".lower()
    score = 0
    if domain in {"material", "general"}:
        score += 2
    if domain == "material" and any(keyword in combined for keyword in MATERIAL_KNOWLEDGE_KEYWORDS):
        score += 4
    if relevance_score <= 5:
        score += 2
    if domain == "general" and "快速检索表" in combined:
        score += 5
    if any(keyword in combined for keyword in BACKGROUND_KEYWORDS):
        score += 4
    if re.search(r"[A-Za-z]{6,}", title):
        score += 3
    if re.search(r"[—|]{2,}", title):
        score += 3
    if len(re.findall(r"[A-Z]{2,4}-\d{2}", f"{title} {detail}")) >= 3:
        score += 5
    if len([char for char in title if char.isdigit()]) >= 4 and not any(token in title for token in ("mm", "kg", "N")):
        score += 2
    if not any(keyword in combined for keyword in PRICING_SIGNAL_KEYWORDS):
        score += 4
    return score


def should_include_runtime_rule(rule: dict[str, object], *, entry: dict[str, object] | None = None) -> bool:
    title = str(rule.get("title", ""))
    detail = str(rule.get("detail", ""))
    domain = str(rule.get("domain", "general"))
    relevance_score = int(rule.get("relevance_score", 0))
    if not list(rule.get("match_terms_specific", [])):
        return False
    if entry is not None and is_medium_risk_denylisted(entry, title=title, detail=detail):
        return False
    return runtime_noise_score(
        title=title,
        detail=detail,
        domain=domain,
        relevance_score=relevance_score,
    ) < 8


def classify_action_type(text: str, *, response_kind: str = "") -> str:
    if response_kind == "catalog_option" or "可选色样" in text or "常规色" in text:
        return "catalog_option"
    if any(keyword in text for keyword in ("需先确认", "先确认", "应先追问", "还需要确认", "请先确认", "未知")):
        return "follow_up"
    if any(keyword in text for keyword in ("应≤", "应≥", "不可", "不能", "限制", "上限", "下限", "默认使用", "需改用")):
        return "constraint"
    return "adjustment"


def infer_required_fields(text: str) -> list[str]:
    required_fields: list[str] = []
    for field_name, keywords in FIELD_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            required_fields.append(field_name)
    return required_fields


def looks_like_product_signal(term: str) -> bool:
    normalized = normalize_text(term)
    if not normalized:
        return False
    if any(keyword in normalized for keyword in ("不能", "不可", "默认", "需", "应", "备注", "收费", "加价", "使用", "安装")):
        return False
    if any(
        normalized.endswith(suffix) and len(normalized) > len(suffix)
        for suffix in ("柜体", "开口", "缺口", "开放格", "分段缝", "牙称", "顶盖侧", "侧盖顶")
    ):
        return True
    return bool(
        re.fullmatch(
            r"[^\s。；•，,:：]{2,40}(?:开关|拉手|扣手|圆扣手|铰链|门板|柜门|玻璃门|藤编门|铝框门|格栅门|拼框门|平板门|推拉门|上翻门|展板门|木门|背板|抽屉|举升器|灯带|榻榻米|床|轨道)",
            normalized,
        )
    )


def is_specific_phrase(term: str) -> bool:
    normalized = normalize_text(term)
    if not normalized or normalized in GENERIC_TERMS or normalized in LOW_SIGNAL_TERMS:
        return False
    if looks_like_product_signal(normalized):
        return True
    if any(keyword in term for keyword in HIGH_SIGNAL_KEYWORDS):
        return True
    if (
        len(normalized) >= 4
        and not any(marker in term for marker in ("、", "，", "。", "；"))
        and any(base in term for base in LOW_SIGNAL_TERMS)
        and not any(generic in term for generic in ("高度", "宽度", "长度", "材质", "门型", "开启方式"))
    ):
        return True
    return False


def split_match_terms(title: str, detail: str, tags: list[str], required_fields: list[str]) -> tuple[list[str], list[str]]:
    combined = " ".join([title, detail, *tags, *required_fields])
    specific_terms: list[str] = []
    generic_terms: list[str] = []
    seen: set[str] = set()

    def add(term: str, *, specific: bool) -> None:
        normalized = normalize_text(term)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        if specific:
            specific_terms.append(normalized)
        else:
            generic_terms.append(normalized)

    for field_name in required_fields:
        add(field_name, specific=field_name not in LOW_SIGNAL_TERMS)
    for tag in tags:
        normalized_tag = normalize_text(tag)
        if not normalized_tag or len(normalized_tag) < 2:
            continue
        add(normalized_tag, specific=is_specific_phrase(normalized_tag))
    for term in SIGNAL_TERMS:
        if term in combined:
            add(term, specific=is_specific_phrase(term))
    for match in PRODUCT_TITLE_PATTERN.findall(f"{title} {detail}"):
        add(match, specific=is_specific_phrase(match))
    for match in INSTALLATION_TITLE_PATTERN.findall(f"{title} {detail}"):
        add(match, specific=True)
    stripped_title = strip_leading_marker(title)
    if stripped_title:
        add(stripped_title, specific=is_specific_phrase(stripped_title))

    return specific_terms, generic_terms


def extract_trigger_terms(title: str, detail: str, tags: list[str], required_fields: list[str]) -> list[str]:
    specific_terms, generic_terms = split_match_terms(title, detail, tags, required_fields)
    return [*specific_terms, *generic_terms]


def build_user_summary(*, title: str, detail: str, action_type: str) -> str:
    clean_title = strip_leading_marker(normalize_text(title))
    clean_detail = strip_leading_marker(normalize_text(detail))
    if action_type == "catalog_option":
        return clean_detail or clean_title
    if not clean_detail:
        return clean_title
    if clean_title and clean_title in clean_detail:
        return clean_detail
    if clean_title:
        return f"{clean_title}。{clean_detail}".strip()
    return clean_detail


def build_question_template(*, title: str, detail: str, required_fields: list[str], domain: str) -> str:
    if not required_fields:
        return ""
    field_name = required_fields[0]
    combined = f"{title} {detail}"
    if domain == "door_panel" or any(keyword in combined for keyword in ("柜门", "门板", "无把手", "无抠手", "流云门", "飞瀑门")):
        return f"这组柜门还需要确认{field_name}。"
    return f"请确认{field_name}"


def is_medium_risk_denylisted(entry: dict[str, object], *, title: str, detail: str) -> bool:
    page = int(entry.get("page", 0) or 0)
    denylist_fragments = MEDIUM_RISK_DENYLIST.get(page)
    if not denylist_fragments:
        return False
    combined = " ".join(
        [
            str(entry.get("clean_title", "")),
            str(entry.get("heading", "")),
            str(entry.get("excerpt", "")),
            title,
            detail,
        ]
    )
    return any(fragment in combined for fragment in denylist_fragments)


def build_runtime_rule(entry: dict[str, object]) -> dict[str, object]:
    domain = str(entry.get("domain", "general"))
    detail = clean_runtime_detail(str(entry.get("excerpt", "")), domain)
    tags = [normalize_text(str(tag)) for tag in entry.get("tags", []) if normalize_text(str(tag))]
    title = preferred_runtime_title(detail, domain) or choose_runtime_title(str(entry.get("clean_title", "")), detail, tags)
    combined_text = " ".join([title, detail, *tags])
    response_kind = str(entry.get("response_kind", "")).strip()
    action_type = classify_action_type(combined_text, response_kind=response_kind)
    required_fields = infer_required_fields(combined_text)
    match_terms_specific, match_terms_generic = split_match_terms(title, detail, tags, required_fields)
    trigger_terms = extract_trigger_terms(title, detail, tags, required_fields)
    user_summary = build_user_summary(title=title, detail=detail, action_type=action_type)
    question_template = build_question_template(title=title, detail=detail, required_fields=required_fields, domain=domain)

    return {
        "page": int(entry.get("page", 1)),
        "domain": domain,
        "action_type": action_type,
        "title": title,
        "detail": detail,
        "trigger_terms": trigger_terms,
        "match_terms_specific": match_terms_specific,
        "match_terms_generic": match_terms_generic,
        "required_fields": required_fields,
        "tags": tags,
        "confidence": float(entry.get("confidence", 0.0)),
        "relevance_score": int(entry.get("relevance_score", 0)),
        "source_heading": str(entry.get("heading", "")),
        "normalized_rule": str(entry.get("normalized_rule", "")),
        "response_kind": response_kind,
        "user_summary": user_summary,
        "question_template": question_template,
        "evidence_level": "hard_rule",
    }


def build_runtime_rules(index: dict[str, object], *, layer_id: str, layer_name: str) -> dict[str, object]:
    entries = index.get("entries", [])
    rules = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not bool(entry.get("pricing_relevant", False)) and not bool(entry.get("runtime_relevant", False)):
            continue
        rule = build_runtime_rule(entry)
        if should_include_runtime_rule(rule, entry=entry):
            rules.append(rule)
    rules.sort(key=lambda rule: (-int(rule.get("relevance_score", 0)), int(rule.get("page", 0)), str(rule.get("title", ""))))

    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "source_file": index.get("source_file"),
        "page_count": index.get("page_count"),
        "rule_count": len(rules),
        "rules": rules,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    index = json.loads(input_path.read_text(encoding="utf-8"))
    payload = build_runtime_rules(index, layer_id=args.layer_id, layer_name=args.layer_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, output_path)

    print(f"Wrote {payload['rule_count']} runtime rules to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
