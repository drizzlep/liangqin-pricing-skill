#!/usr/bin/env python3
"""Apply independent addendum layers onto a base quote payload."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any


DOMAIN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cabinet", ("柜", "衣柜", "书柜", "玄关柜", "电视柜", "餐边柜", "流云", "飞瀑", "抽屉", "抽面")),
    ("bed", ("床", "箱体床", "架式床", "榻榻米")),
    ("table", ("桌", "书桌", "餐桌", "边几", "岛台")),
    ("accessory", ("拉手", "灯带", "开关", "插座", "脚轮")),
    (
        "door_panel",
        (
            "门板",
            "拼框门",
            "平板门",
            "玻璃门",
            "格栅门",
            "铝框门",
            "针式铰链铝框门",
            "铝框岩板门",
            "藤编门",
            "拱形藤编门",
            "美式木门",
            "美式玻璃门",
            "拱形玻璃门",
            "胶囊玻璃门",
            "超高拼框木门",
            "超高拼框玻璃门",
        ),
    ),
]

DOMAIN_COMPATIBILITY_KEYWORDS: dict[tuple[str, str], tuple[str, ...]] = {
    ("cabinet", "door_panel"): ("门", "门板", "流云", "飞瀑", "平板门", "拼框门", "玻璃门", "格栅门", "铝框"),
    ("door_panel", "cabinet"): ("柜", "柜体", "衣柜", "书柜", "餐边柜", "玄关柜", "电视柜"),
}

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
    "平板门",
    "拼框门",
    "玻璃门",
    "格栅门",
    "铝框门",
    "针式铰链铝框门",
    "铝框岩板门",
    "藤编门",
    "拱形藤编门",
    "美式木门",
    "美式玻璃门",
    "拱形玻璃门",
    "胶囊玻璃门",
    "超高拼框木门",
    "超高拼框玻璃门",
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
    "遇见书柜",
]

UNKNOWN_MARKERS = ("未知", "未提供", "待确认", "待补充", "未确认", "不详", "先不说", "未备注", "没说")
LOW_SIGNAL_TERMS = {
    "门型",
    "材质",
    "长度",
    "高度",
    "宽度",
    "进深",
    "投影面积",
    "抽屉",
    "抽面",
    "层板",
    "背板",
    "门板",
    "柜门",
    "柜体",
}

FIELD_VALUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "岩板长度": (
        r"(?:岩板长度|台面长度|门板长度|长度|长)[^0-9]{0,6}\d+(?:\.\d+)?(?:m|米|cm|厘米|mm|毫米)",
    ),
    "空区高度": (
        r"(?:空区高度|空区高|高度|高)[^0-9]{0,6}\d+(?:\.\d+)?(?:m|米|cm|厘米|mm|毫米)",
    ),
    "超出侧板面积": (
        r"(?:超出侧板面积|侧板面积|面积)[^0-9]{0,6}\d+(?:\.\d+)?(?:㎡|m²|m2|平方米|平米|平方)",
    ),
}

FIELD_VALUE_EXTRACT_PATTERNS: dict[str, tuple[str, ...]] = {
    "空区高度": (
        r"(?:空区高度|空区高|高度|高)[^0-9]{0,6}(\d+(?:\.\d+)?)(mm|毫米|cm|厘米|m|米)",
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply active addendum layers to a quote payload.")
    parser.add_argument("--input-json", help="Quote payload JSON. If omitted, read from stdin.")
    parser.add_argument(
        "--addenda-root",
        default=str(Path(__file__).resolve().parent.parent / "references" / "addenda"),
        help="Directory containing addendum layer manifests.",
    )
    return parser.parse_args(argv)


def load_payload(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SystemExit("Quote payload must be a JSON object")
    if not isinstance(payload.get("items"), list):
        raise SystemExit("Quote payload must include items")
    return payload


def normalize_text(text: str) -> str:
    return "".join(str(text).split()).lower()


def build_item_source_text(item: dict[str, Any]) -> str:
    return " ".join(
        [
            str(item.get("product", "")),
            str(item.get("confirmed", "")),
            str(item.get("pricing_method", "")),
            " ".join(str(step) for step in item.get("calculation_steps", []) or []),
        ]
    )


def extract_signals(text: str, tags: list[str]) -> set[str]:
    combined = " ".join([text, *tags])
    signals = {term for term in SIGNAL_TERMS if term in combined}
    for tag in tags:
        normalized_tag = str(tag).strip()
        if normalized_tag and normalized_tag not in GENERIC_TERMS and len(normalized_tag) >= 2:
            signals.add(normalized_tag)
    return signals


def infer_item_domain(item: dict[str, Any]) -> str:
    text = build_item_source_text(item)
    for domain, keywords in DOMAIN_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return domain
    return "general"


def load_active_layer_manifests(addenda_root: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    if not addenda_root.exists():
        return manifests
    for manifest_path in sorted(addenda_root.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "ACTIVE":
            manifest["_manifest_dir"] = str(manifest_path.parent)
            manifests.append(manifest)
    return manifests


def resolve_manifest_artifact_path(manifest: dict[str, Any], raw_path: object) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    manifest_dir = Path(str(manifest.get("_manifest_dir", "")))
    return (manifest_dir / path).resolve()


def load_active_layer_sources(addenda_root: Path) -> list[dict[str, Any]]:
    layer_sources: list[dict[str, Any]] = []
    for manifest in load_active_layer_manifests(addenda_root):
        artifacts = manifest.get("artifacts", {})
        runtime_rules_file = artifacts.get("runtime_rules_file")
        if runtime_rules_file:
            runtime_rules_path = resolve_manifest_artifact_path(manifest, runtime_rules_file)
            if runtime_rules_path.exists():
                runtime_payload = json.loads(runtime_rules_path.read_text(encoding="utf-8"))
                layer_sources.append(
                    {
                        "manifest": manifest,
                        "match_mode": "runtime",
                        "rules": runtime_payload.get("rules", []),
                    }
                )
                continue
        rules_index_file = artifacts.get("rules_index_file")
        if not rules_index_file:
            continue
        index_path = resolve_manifest_artifact_path(manifest, rules_index_file)
        if not index_path.exists():
            continue
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        layer_sources.append(
            {
                "manifest": manifest,
                "match_mode": "index",
                "rules": index_payload.get("entries", []),
            }
        )
    return layer_sources


def domains_match(item_domain: str, rule_domain: str, item_source_text: str) -> bool:
    if rule_domain in {item_domain, "general"}:
        return True
    compatibility_keywords = DOMAIN_COMPATIBILITY_KEYWORDS.get((item_domain, rule_domain))
    if not compatibility_keywords:
        return False
    return any(keyword in item_source_text for keyword in compatibility_keywords)


def choose_matches(item: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domain = infer_item_domain(item)
    item_source_text = build_item_source_text(item)
    item_text = normalize_text(item_source_text)
    item_signals = extract_signals(item_source_text, [])

    matched: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.get("pricing_relevant"):
            continue
        if not domains_match(domain, str(entry.get("domain", "general")), item_source_text):
            continue
        entry_signals = extract_signals(
            " ".join([str(entry.get("clean_title", "")), str(entry.get("excerpt", ""))]),
            [str(tag) for tag in entry.get("tags", [])],
        )
        if item_signals and entry_signals and not (item_signals & entry_signals):
            continue
        tokens = [normalize_text(str(entry.get("clean_title", ""))), normalize_text(str(entry.get("excerpt", "")))]
        tags = [normalize_text(str(tag)) for tag in entry.get("tags", [])]
        specific_tags = [tag for tag in tags if tag not in {normalize_text(term) for term in GENERIC_TERMS}]
        if any(token and token[:8] in item_text for token in tokens if len(token) >= 6) or any(tag and tag in item_text for tag in specific_tags):
            matched.append(entry)

    matched.sort(key=lambda entry: (-int(entry.get("relevance_score", 0)), str(entry.get("clean_title", ""))))
    return matched[:2]


def choose_runtime_matches(item: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domain = infer_item_domain(item)
    item_source_text = build_item_source_text(item)
    item_text = normalize_text(item_source_text)
    item_signals = extract_signals(item_source_text, [])

    matched: list[tuple[int, dict[str, Any]]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if not domains_match(domain, str(rule.get("domain", "general")), item_source_text):
            continue

        title = str(rule.get("title", ""))
        detail = str(rule.get("detail", ""))
        trigger_terms = [str(term) for term in rule.get("trigger_terms", [])]
        required_fields = [str(field) for field in rule.get("required_fields", [])]
        tags = [str(tag) for tag in rule.get("tags", [])]

        rule_signals = extract_signals(" ".join([title, detail, *required_fields]), [*trigger_terms, *tags])
        if item_signals and rule_signals and not (item_signals & rule_signals):
            continue

        tokens = [normalize_text(title), normalize_text(detail)]
        normalized_terms = [normalize_text(term) for term in [*trigger_terms, *required_fields] if normalize_text(term)]
        significant_terms = [term for term in normalized_terms if term not in {normalize_text(value) for value in LOW_SIGNAL_TERMS}]
        if significant_terms:
            has_term_match = any(term in item_text for term in significant_terms)
            has_token_match = any(token and len(token) >= 6 and token[:8] in item_text for token in tokens if token)
            if not has_term_match and not has_token_match:
                continue
        elif normalized_terms:
            has_term_match = any(term in item_text for term in normalized_terms)
            has_token_match = any(token and len(token) >= 6 and token[:8] in item_text for token in tokens if token)
            if not has_term_match and not has_token_match:
                continue
        elif not any(token and len(token) >= 6 and token[:8] in item_text for token in tokens if token):
            continue

        score = int(rule.get("relevance_score", 0)) * 10
        score += sum(3 for term in trigger_terms if term and term in item_source_text)
        score += sum(2 for term in tags if term and term not in GENERIC_TERMS and term in item_source_text)
        if title and title in item_source_text:
            score += 6
        if any(keyword in item_source_text and keyword in title for keyword in ("餐桌", "书桌", "衣柜", "书柜", "床", "岩板")):
            score += 4
        if title not in {"可选色样", "常规色"}:
            score += 1

        matched.append((score, rule))

    matched.sort(key=lambda item: (-item[0], -int(item[1].get("relevance_score", 0)), int(item[1].get("page", 0)), str(item[1].get("title", ""))))
    selected = [rule for _, rule in matched[:2]]
    if selected and str(selected[0].get("action_type", "")) == "catalog_option":
        top_title = str(selected[0].get("title", "")).strip()
        if top_title not in {"可选色样", "常规色"}:
            return [selected[0]]
    return selected


def classify_match(match: dict[str, Any]) -> str:
    title = str(match.get("clean_title", ""))
    excerpt = str(match.get("excerpt", ""))
    text = f"{title} {excerpt}"
    if any(keyword in text for keyword in ("可选色样", "常规色", "颜色可选")):
        return "catalog_option"
    if any(keyword in text for keyword in ("需先确认", "先确认", "应先追问", "还需要确认", "请先确认", "未知")):
        return "follow_up"
    if any(keyword in text for keyword in ("应≤", "应≥", "不可", "不能", "限制", "上限", "下限", "默认使用", "需改用")):
        return "constraint"
    return "adjustment"


def field_value_present(field: str, item_source_text: str) -> bool:
    patterns = FIELD_VALUE_PATTERNS.get(field, ())
    if not patterns:
        return False
    return any(re.search(pattern, item_source_text, flags=re.IGNORECASE) for pattern in patterns)


def parse_metric_value(value: str, unit: str) -> float:
    number = float(value)
    normalized_unit = unit.lower()
    if normalized_unit in {"mm", "毫米"}:
        return number / 1000
    if normalized_unit in {"cm", "厘米"}:
        return number / 100
    return number


def extract_metric_field_value(field: str, item_source_text: str) -> float | None:
    patterns = FIELD_VALUE_EXTRACT_PATTERNS.get(field, ())
    for pattern in patterns:
        match = re.search(pattern, item_source_text, flags=re.IGNORECASE)
        if match:
            return parse_metric_value(match.group(1), match.group(2))
    return None


def infer_conditional_required_fields(item_source_text: str, match: dict[str, Any]) -> list[str]:
    title = str(match.get("title", "") or match.get("clean_title", ""))
    detail = str(match.get("detail", "") or match.get("excerpt", ""))
    text = f"{title} {detail}"

    if "岩板背板" not in text:
        return []

    opening_height = extract_metric_field_value("空区高度", item_source_text)
    if opening_height is None or opening_height < 0.55:
        return []
    if field_value_present("超出侧板面积", item_source_text):
        return []
    return ["超出侧板面积"]


def infer_missing_required_fields(item: dict[str, Any], match: dict[str, Any]) -> list[str]:
    required_fields = [str(field).strip() for field in match.get("required_fields", []) if str(field).strip()]
    if not required_fields:
        return []

    item_source_text = build_item_source_text(item)
    has_unknown_marker = any(marker in item_source_text for marker in UNKNOWN_MARKERS)

    missing_fields: list[str] = []
    for field in required_fields:
        if field_value_present(field, item_source_text):
            continue
        if has_unknown_marker and field in item_source_text:
            missing_fields.append(field)
            continue
        if field in FIELD_VALUE_PATTERNS:
            missing_fields.append(field)

    if not missing_fields and len(required_fields) == 1:
        if has_unknown_marker:
            missing_fields.append(required_fields[0])
    conditional_missing = infer_conditional_required_fields(item_source_text, match)
    for field in conditional_missing:
        if field not in missing_fields:
            missing_fields.append(field)
    return missing_fields


def build_decision(
    layer_name: str,
    match: dict[str, Any],
    kind: str,
    *,
    required_fields: list[str] | None = None,
) -> dict[str, str]:
    detail = str(match.get("detail", "") or match.get("excerpt", "")).strip()
    title = str(match.get("title", "") or match.get("clean_title", "")).strip() or "追加规则"
    decision = {
        "layer_name": layer_name,
        "title": title,
        "detail": detail,
    }
    if kind == "follow_up":
        if required_fields:
            decision["question"] = f"请确认{'、'.join(required_fields)}"
        else:
            decision["question"] = detail or title
    return decision


def deduplicate_decisions(entries: list[dict[str, str]], *, key_fields: tuple[str, ...]) -> list[dict[str, str]]:
    deduplicated: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for entry in entries:
        key = tuple(str(entry.get(field, "")).strip() for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(entry)
    return deduplicated


def apply_addendum_layers(payload: dict[str, Any], addenda_root: Path) -> dict[str, Any]:
    merged = copy.deepcopy(payload)
    layer_sources = load_active_layer_sources(addenda_root)
    addendum_notes: list[str] = []

    for item in merged.get("items", []):
        if not isinstance(item, dict):
            continue
        item_adjustments: list[str] = []
        decisions = {
            "adjustments": [],
            "constraints": [],
            "follow_up_questions": [],
        }
        for layer_source in layer_sources:
            manifest = layer_source["manifest"]
            rules = layer_source["rules"]
            if layer_source["match_mode"] == "runtime":
                matches = choose_runtime_matches(item, rules)
            else:
                matches = choose_matches(item, rules)
            if not matches:
                continue
            for match in matches:
                kind = str(match.get("action_type", "")) or classify_match(match)
                missing_fields = infer_missing_required_fields(item, match)
                if missing_fields:
                    decision = build_decision(
                        str(manifest["layer_name"]),
                        match,
                        "follow_up",
                        required_fields=missing_fields,
                    )
                    decisions["follow_up_questions"].append(decision)
                    continue

                decision = build_decision(str(manifest["layer_name"]), match, kind)
                if kind == "adjustment":
                    decisions["adjustments"].append(decision)
                    item_adjustments.append(f"{decision['layer_name']}：{decision['title']}。{decision['detail']}".strip())
                elif kind in {"constraint", "catalog_option"}:
                    decisions["constraints"].append(decision)
                else:
                    decisions["follow_up_questions"].append(decision)
            addendum_notes.append(f"已套用设计师追加规则：{manifest['layer_name']}")

        decisions["adjustments"] = deduplicate_decisions(decisions["adjustments"], key_fields=("title", "detail"))
        decisions["constraints"] = deduplicate_decisions(decisions["constraints"], key_fields=("title", "detail"))
        decisions["follow_up_questions"] = deduplicate_decisions(
            decisions["follow_up_questions"],
            key_fields=("question",),
        )

        if item_adjustments:
            item["addendum_adjustments"] = item_adjustments
        if any(decisions.values()):
            item["addendum_decisions"] = decisions

    if addendum_notes:
        merged["addendum_notes"] = list(dict.fromkeys(addendum_notes))
    return merged


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw = args.input_json if args.input_json is not None else sys.stdin.read()
    if not raw.strip():
        raise SystemExit("Quote payload is required")
    payload = load_payload(raw)
    merged = apply_addendum_layers(payload, Path(args.addenda_root).expanduser().resolve())
    json.dump(merged, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
