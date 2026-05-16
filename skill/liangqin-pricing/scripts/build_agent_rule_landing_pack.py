#!/usr/bin/env python3
"""Build an AI Agent landing pack for pricing-rule implementation."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATE_LAYER = "designer-manual-online-2026-05-13"

QUOTE_CALC_RULE = "报价计算硬规则"
QUOTE_PRECHECK_RULE = "报价前追问/拦截规则"
LANDING_LAYERS = {QUOTE_CALC_RULE, QUOTE_PRECHECK_RULE}

ACTION_QUOTE_CALC = "接入报价计算"
ACTION_PRECHECK = "接入报价前追问/拦截"

SENSITIVE_PATTERNS = ("Signature=", "X-Amz-", "token=", "access_token=", "secret", "Bearer")
BLOCKED_TERMS = ("PREVIOUS_ACTIVE", "runtime_hard_rule", "Signature=", "X-Amz-", "access_token", "Bearer")

CONCRETE_MONEY_TERMS = ("加价", "补差", "折减", "单价", "价格", "收费", "差价", "报价原则", "价格计算", "计算方法")
LIMIT_TERMS = ("尺寸限制", "限制", "≤", "≥", "不得", "不可", "不能", "必须", "禁止", "上限", "下限")
SAFETY_TERMS = ("安全", "GB 28007", "GB28007", "承重墙", "固定上墙", "电源", "电线")
NOTE_TERMS = ("备注", "合同", "截图", "告知", "确认", "询问")
LOW_CONFIDENCE_TERMS = ("售后", "问题总结", "更新日志", "问题：")

CSV_COLUMNS = [
    "landing_id",
    "source_data_point_id",
    "first_batch_recommended",
    "priority_score",
    "risk_level",
    "landing_action",
    "suggested_module",
    "domain_label",
    "topic",
    "source_title",
    "source_page",
    "required_fields",
    "trigger_conditions",
    "expected_behavior",
    "test_suggestion",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AI Agent landing pack for pricing rules.")
    parser.add_argument("--candidate-layer", default=DEFAULT_CANDIDATE_LAYER, help="Active designer-manual layer id.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--input-json", default="", help="Override full-document-data-certification.json path.")
    parser.add_argument("--output-dir", default="", help="Override output directory.")
    parser.add_argument("--first-batch-size", type=int, default=20, help="Number of rules recommended for first landing.")
    return parser.parse_args(argv)


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else dict(fallback or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def normalize_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def excerpt(value: Any, limit: int = 280) -> str:
    text = normalize_inline(value)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def is_sensitive(value: Any) -> bool:
    text = str(value or "")
    return any(pattern.lower() in text.lower() for pattern in SENSITIVE_PATTERNS)


def contains_blocked_term(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return any(term.lower() in text.lower() for term in BLOCKED_TERMS)


def resolve_candidate_report_dir(skill_dir: Path, candidate_layer: str) -> Path:
    manifest_path = skill_dir / "references" / "addenda" / candidate_layer / "manifest.json"
    manifest = load_json(manifest_path, {})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rules_candidate_file = artifacts.get("rules_candidate_file")
    if not rules_candidate_file:
        return skill_dir / "reports" / "addenda" / candidate_layer
    raw_path = Path(str(rules_candidate_file))
    resolved = raw_path if raw_path.is_absolute() else (manifest_path.parent / raw_path).resolve()
    return resolved.parent


def certification_json_path(skill_dir: Path, candidate_layer: str, input_json: str = "") -> Path:
    if input_json:
        return Path(input_json).expanduser().resolve()
    return resolve_candidate_report_dir(skill_dir, candidate_layer) / "full-document-data-certification.json"


def source_ref(point: dict[str, Any]) -> dict[str, Any]:
    source = point.get("source") if isinstance(point.get("source"), dict) else {}
    source_path = normalize_inline(source.get("path"))
    return {
        "title": normalize_inline(source.get("title")),
        "page": source.get("page") or "",
        "path": "" if is_sensitive(source_path) else source_path,
        "node_id": normalize_inline(source.get("node_id")),
    }


def required_fields_for(point: dict[str, Any]) -> list[str]:
    text = normalize_inline(" ".join([point.get("topic", ""), point.get("extracted_data", ""), point.get("answer_outline", "")]))
    fields = ["product_or_category"]
    checks = [
        ("height", ("高度", "高", "H=", "H≤", "H≥")),
        ("width", ("宽度", "宽", "W=", "W≤", "W≥", "门宽")),
        ("depth", ("深度", "进深", "D=", "D≤", "D≥")),
        ("length", ("长度", "长", "L=", "L≤", "L≥")),
        ("material", ("材质", "岩板", "木材", "真皮", "颜色", "珐琅")),
        ("door_type", ("门型", "门板", "推拉门", "平开门", "上下翻", "开启方式", "开启方向")),
        ("quote_note", ("备注", "合同", "截图", "告知")),
        ("wall_or_install_condition", ("承重墙", "固定上墙", "安装", "预留", "电源", "电线")),
        ("safety_standard", ("安全", "GB 28007", "GB28007", "婴幼儿", "儿童家具")),
    ]
    for field, terms in checks:
        if any(term in text for term in terms) and field not in fields:
            fields.append(field)
    return fields


def suggested_module_for(point: dict[str, Any]) -> str:
    layer = str(point.get("pricing_system_layer") or "")
    domain = str(point.get("domain") or "")
    text = normalize_inline(" ".join([point.get("topic", ""), point.get("extracted_data", ""), point.get("answer_outline", "")]))
    if has_any(text, SAFETY_TERMS) and not has_any(text, CONCRETE_MONEY_TERMS):
        return "precheck_quote:safety_or_install_gate"
    if layer == QUOTE_PRECHECK_RULE:
        if has_any(text, SAFETY_TERMS):
            return "precheck_quote:safety_or_install_gate"
        if has_any(text, NOTE_TERMS):
            return "precheck_quote:required_note_or_confirmation_gate"
        if has_any(text, LIMIT_TERMS):
            return "precheck_quote:dimension_or_limit_gate"
        return "precheck_quote:rule_gate"
    if domain == "door_panel":
        return "pricing_calculation:door_panel_adjustment"
    if domain == "bed":
        return "pricing_calculation:bed_or_soft_package_adjustment"
    if domain == "cabinet":
        return "pricing_calculation:cabinet_structure_adjustment"
    if domain == "accessory":
        return "pricing_calculation:accessory_adjustment"
    if domain == "material" or "岩板" in text:
        return "pricing_calculation:material_or_rock_slab_adjustment"
    return "pricing_calculation:general_adjustment"


def risk_for(point: dict[str, Any]) -> tuple[str, str]:
    layer = str(point.get("pricing_system_layer") or "")
    text = normalize_inline(" ".join([point.get("topic", ""), point.get("extracted_data", ""), point.get("answer_outline", "")]))
    if has_any(text, SAFETY_TERMS):
        return "P0-影响安全/安装", "涉及安全、承重、用电或儿童家具标准，不能在缺条件时继续报价。"
    if layer == QUOTE_CALC_RULE and has_any(text, CONCRETE_MONEY_TERMS):
        return "P0-影响金额", "会影响收费、补差、折减或报价公式，优先防止少收/错收。"
    if has_any(text, LIMIT_TERMS):
        return "P1-影响能否下单", "涉及尺寸限制、禁止条件或必须确认项，适合进入报价前拦截。"
    if has_any(text, NOTE_TERMS):
        return "P1-影响合同备注", "涉及备注、截图、告知或确认，适合进入报价前追问。"
    if layer == QUOTE_CALC_RULE:
        return "P1-影响金额候选", "被认证包归为报价计算候选，但还要在接入前确认字段和公式。"
    return "P2-影响说明完整性", "适合先作为追问/提示规则，不直接改金额。"


def priority_score(point: dict[str, Any]) -> int:
    layer = str(point.get("pricing_system_layer") or "")
    risk, _reason = risk_for(point)
    text = normalize_inline(" ".join([point.get("topic", ""), point.get("extracted_data", ""), point.get("answer_outline", "")]))
    score = 0
    if layer == QUOTE_CALC_RULE:
        score += 50
    elif layer == QUOTE_PRECHECK_RULE:
        score += 35
    if risk.startswith("P0"):
        score += 40
    elif risk.startswith("P1"):
        score += 25
    else:
        score += 10
    score += sum(4 for term in CONCRETE_MONEY_TERMS if term in text)
    score += sum(3 for term in LIMIT_TERMS if term in text)
    score += sum(5 for term in SAFETY_TERMS if term in text)
    if point.get("domain") in {"door_panel", "cabinet", "bed", "accessory", "material"}:
        score += 6
    score -= 35 * len(quality_flags_for(point))
    return score


def landing_action_for(point: dict[str, Any]) -> str:
    text = normalize_inline(" ".join([point.get("topic", ""), point.get("extracted_data", ""), point.get("answer_outline", "")]))
    if has_any(text, SAFETY_TERMS) and not has_any(text, CONCRETE_MONEY_TERMS):
        return ACTION_PRECHECK
    return ACTION_QUOTE_CALC if point.get("pricing_system_layer") == QUOTE_CALC_RULE else ACTION_PRECHECK


def quality_flags_for(point: dict[str, Any]) -> list[str]:
    source = source_ref(point)
    text = normalize_inline(" ".join([point.get("topic", ""), point.get("extracted_data", ""), point.get("answer_outline", ""), source.get("title", ""), source.get("path", "")]))
    flags: list[str] = []
    if has_any(text, LOW_CONFIDENCE_TERMS):
        flags.append("source_context_not_pricing_standard")
    topic = normalize_inline(point.get("topic"))
    if len(topic) < 10 or re.fullmatch(r"[a-zA-Z0-9）).、；;，,：:\s]+", topic or ""):
        flags.append("fragmented_topic")
    if topic.startswith(("•", "a)", "b)", "c)", "1.", "2.", "3.")) and len(topic) < 36:
        flags.append("fragmented_excerpt")
    return flags


def landing_confidence_for(point: dict[str, Any]) -> str:
    flags = quality_flags_for(point)
    if "source_context_not_pricing_standard" in flags:
        return "low"
    if flags:
        return "medium"
    return "high"


def trigger_conditions_for(point: dict[str, Any]) -> list[str]:
    source = source_ref(point)
    topic = normalize_inline(point.get("topic"))
    title = normalize_inline(source.get("title"))
    triggers = [question for question in point.get("trigger_questions", []) if normalize_inline(question)]
    if topic:
        triggers.append(f"用户问题或报价参数命中主题：{excerpt(topic, 48)}")
    if title and title != topic:
        triggers.append(f"用户问题或报价参数命中来源标题：{excerpt(title, 48)}")
    deduped: list[str] = []
    for trigger in triggers:
        normalized = normalize_inline(trigger)
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:5]


def expected_behavior_for(point: dict[str, Any]) -> str:
    layer = str(point.get("pricing_system_layer") or "")
    topic = normalize_inline(point.get("topic")) or normalize_inline(source_ref(point).get("title")) or "该规则"
    if layer == QUOTE_CALC_RULE:
        return f"当报价请求命中“{excerpt(topic, 42)}”且所需字段齐全时，报价明细应体现对应加价/补差/折减/公式；字段不足时必须先转 precheck。"
    return f"当报价请求命中“{excerpt(topic, 42)}”且缺少必要条件、备注或尺寸边界时，先追问/拦截，不进入正式报价金额计算。"


def test_suggestion_for(point: dict[str, Any]) -> str:
    action = landing_action_for(point)
    topic = normalize_inline(point.get("topic")) or normalize_inline(source_ref(point).get("title")) or "该规则"
    if action == ACTION_QUOTE_CALC:
        return f"新增报价回归：输入包含“{excerpt(topic, 32)}”和完整字段，断言报价明细包含该规则；再测缺字段时不直接出正式报价。"
    return f"新增 precheck 回归：输入包含“{excerpt(topic, 32)}”但缺关键字段或越界，断言返回追问/拦截原因且不生成正式报价。"


def build_landing_rule(point: dict[str, Any], index: int) -> dict[str, Any] | None:
    if point.get("pricing_system_layer") not in LANDING_LAYERS:
        return None
    risk_level, risk_reason = risk_for(point)
    source = source_ref(point)
    return {
        "landing_id": f"landing-rule-{index:04d}",
        "source_data_point_id": point.get("id"),
        "implementation_status": "proposed",
        "first_batch_recommended": False,
        "priority_score": priority_score(point),
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "landing_confidence": landing_confidence_for(point),
        "quality_flags": quality_flags_for(point),
        "pricing_system_layer": point.get("pricing_system_layer"),
        "landing_action": landing_action_for(point),
        "suggested_module": suggested_module_for(point),
        "required_fields": required_fields_for(point),
        "trigger_conditions": trigger_conditions_for(point),
        "expected_behavior": expected_behavior_for(point),
        "test_suggestion": test_suggestion_for(point),
        "domain": point.get("domain"),
        "domain_label": point.get("domain_label"),
        "topic": normalize_inline(point.get("topic")),
        "rule_excerpt": excerpt(point.get("answer_outline") or point.get("extracted_data"), 360),
        "source": source,
        "trace": {
            "source_certification_id": point.get("id"),
            "source_certification_layer": point.get("pricing_system_layer"),
        },
    }


def sort_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risk_order = {"P0": 0, "P1": 1, "P2": 2}
    layer_order = {QUOTE_CALC_RULE: 0, QUOTE_PRECHECK_RULE: 1}
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        rules,
        key=lambda rule: (
            confidence_order.get(str(rule.get("landing_confidence") or ""), 9),
            risk_order.get(str(rule["risk_level"]).split("-", 1)[0], 9),
            layer_order.get(str(rule["pricing_system_layer"]), 9),
            -int(rule["priority_score"]),
            str(rule.get("domain_label") or ""),
            str(rule.get("landing_id") or ""),
        ),
    )


def build_pack_model(*, certification_path: Path, candidate_layer: str, first_batch_size: int = 20) -> dict[str, Any]:
    certification = load_json(certification_path, {})
    data_points = [point for point in certification.get("data_points", []) if isinstance(point, dict)]
    rules = [rule for index, point in enumerate(data_points, start=1) if (rule := build_landing_rule(point, index))]
    rules = sort_rules(rules)
    first_batch_limit = max(0, int(first_batch_size))
    for rule in rules[:first_batch_limit]:
        rule["first_batch_recommended"] = True
    layer_counts = Counter(rule["pricing_system_layer"] for rule in rules)
    action_counts = Counter(rule["landing_action"] for rule in rules)
    risk_counts = Counter(rule["risk_level"] for rule in rules)
    domain_counts = Counter(rule.get("domain_label") or "未分类" for rule in rules)
    first_batch = [rule for rule in rules if rule["first_batch_recommended"]]
    return {
        "title": "新版设计师手册报价规则 AI Agent 落地包一期",
        "candidate_layer": candidate_layer,
        "source_certification": str(certification_path),
        "total_input_data_points": len(data_points),
        "landing_rule_count": len(rules),
        "first_batch_count": len(first_batch),
        "first_batch_size_limit": first_batch_limit,
        "pricing_system_layer_counts": dict(layer_counts),
        "landing_action_counts": dict(action_counts),
        "risk_counts": dict(risk_counts),
        "domain_counts": dict(domain_counts),
        "agent_guardrails": [
            "只使用当前新版设计师手册来源页，不使用旧版归档层兜底。",
            "先写测试再接入规则；没有测试的规则不得修改正式报价链路。",
            "报价计算规则必须同时验证金额明细和缺字段 precheck 分支。",
            "追问/拦截规则不得被自然语言路由绕过。",
            "本包不是人工逐条看板，人只确认方向，Agent 按来源页和测试合同落地。",
        ],
        "recommended_next_action": "先由 AI Agent 接入 first_batch 中的规则；每条规则必须保留来源页、触发条件、字段和测试证据。",
        "first_batch": first_batch,
        "rules": rules,
    }


def csv_row(rule: dict[str, Any]) -> dict[str, str]:
    source = rule.get("source") if isinstance(rule.get("source"), dict) else {}
    return {
        "landing_id": str(rule.get("landing_id") or ""),
        "source_data_point_id": str(rule.get("source_data_point_id") or ""),
        "first_batch_recommended": "yes" if rule.get("first_batch_recommended") else "no",
        "priority_score": str(rule.get("priority_score") or ""),
        "risk_level": str(rule.get("risk_level") or ""),
        "landing_action": str(rule.get("landing_action") or ""),
        "suggested_module": str(rule.get("suggested_module") or ""),
        "domain_label": str(rule.get("domain_label") or ""),
        "topic": str(rule.get("topic") or ""),
        "source_title": str(source.get("title") or ""),
        "source_page": str(source.get("page") or ""),
        "required_fields": " | ".join(rule.get("required_fields") or []),
        "trigger_conditions": " | ".join(rule.get("trigger_conditions") or []),
        "expected_behavior": str(rule.get("expected_behavior") or ""),
        "test_suggestion": str(rule.get("test_suggestion") or ""),
    }


def write_csv(path: Path, rules: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for rule in rules:
            writer.writerow(csv_row(rule))
    os.replace(temp_path, path)


def render_rule_table(rules: list[dict[str, Any]], limit: int = 20) -> str:
    lines = [
        "| ID | 风险 | 动作 | 模块 | 主题 | 来源 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for rule in rules[:limit]:
        source = rule.get("source") if isinstance(rule.get("source"), dict) else {}
        lines.append(
            "| {id} | {risk} | {action} | {module} | {topic} | {source} 第 {page} 页 |".format(
                id=rule.get("landing_id"),
                risk=rule.get("risk_level"),
                action=rule.get("landing_action"),
                module=rule.get("suggested_module"),
                topic=excerpt(rule.get("topic") or rule.get("rule_excerpt"), 42).replace("|", "/"),
                source=excerpt(source.get("title"), 32).replace("|", "/"),
                page=source.get("page") or "",
            )
        )
    return "\n".join(lines)


def render_protocol_markdown(model: dict[str, Any]) -> str:
    return f"""# 新版设计师手册报价规则 AI Agent 落地协议

## 目标
把新版设计师手册中已经被认证为 `{QUOTE_CALC_RULE}` 和 `{QUOTE_PRECHECK_RULE}` 的规则，分批接入良禽佳木报价系统。当前阶段不做人类逐条审核看板，不直接要求不懂规则的人确认每一条规则。

## 输入
- 规则包：`agent-rule-landing-pack.json`
- 规则表：`agent-rule-landing-pack.csv`
- 来源认证：`{model.get('source_certification')}`

## 执行顺序
1. 只从 `first_batch` 开始，不要一次接入全部 `{model.get('landing_rule_count')}` 条。
2. 每条规则先读 `source.title`、`source.page`、`rule_excerpt` 和 `expected_behavior`。
3. 先写或更新测试，再改 `suggested_module` 指向的代码。
4. 报价计算规则必须覆盖完整字段出价和缺字段 precheck 两条路径。
5. 追问/拦截规则必须证明不会被 `handle_quote_message` 路由绕过。

## 硬性边界
- 不使用旧版归档手册兜底。
- 不凭行业常识补规则。
- 不把 `人工复核`、`设计师咨询知识`、`不开放` 数据点混入第一批落地。
- 不在输出中暴露签名 URL、token、内部状态或旧版运行状态。

## 第一批推荐
{render_rule_table(model.get('first_batch', []), limit=20)}
"""


def render_summary_markdown(model: dict[str, Any]) -> str:
    return f"""# 新版设计师手册报价规则落地摘要

本阶段已经生成给 AI Agent 使用的落地合同包，不做人类逐条规则看板。人只需要确认方向：先接入第一批高价值规则，优先防止少收/错收钱，以及缺关键条件还继续报价。

## 数量
- 可落地规则：{model.get('landing_rule_count')}
- 第一批推荐：{model.get('first_batch_count')}
- 报价计算：{model.get('pricing_system_layer_counts', {}).get(QUOTE_CALC_RULE, 0)}
- 追问/拦截：{model.get('pricing_system_layer_counts', {}).get(QUOTE_PRECHECK_RULE, 0)}

## 风险分布
{chr(10).join(f'- {key}：{value}' for key, value in model.get('risk_counts', {}).items())}

## 下一步
由后续 AI Agent 按 `agent-landing-protocol.md` 执行第一批规则。每条规则必须带测试、来源页和字段条件；未完成测试前不能进入正式报价链路。
"""


def validate_public_outputs(payloads: list[Any]) -> None:
    for payload in payloads:
        if contains_blocked_term(payload):
            raise RuntimeError("Generated landing pack contains blocked internal or sensitive terms.")


def build_and_write_pack(*, skill_dir: Path, candidate_layer: str, input_json: str, output_dir: Path, first_batch_size: int) -> dict[str, Any]:
    cert_path = certification_json_path(skill_dir, candidate_layer, input_json)
    model = build_pack_model(certification_path=cert_path, candidate_layer=candidate_layer, first_batch_size=first_batch_size)
    output_json = output_dir / "agent-rule-landing-pack.json"
    output_csv = output_dir / "agent-rule-landing-pack.csv"
    output_protocol = output_dir / "agent-landing-protocol.md"
    output_summary = output_dir / "agent-landing-summary.md"
    model["outputs"] = {
        "json": str(output_json),
        "csv": str(output_csv),
        "protocol": str(output_protocol),
        "summary": str(output_summary),
    }
    protocol = render_protocol_markdown(model)
    summary = render_summary_markdown(model)
    validate_public_outputs([model, protocol, summary])
    write_json(output_json, model)
    write_csv(output_csv, model["rules"])
    output_protocol.write_text(protocol, encoding="utf-8")
    output_summary.write_text(summary, encoding="utf-8")
    return model


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else resolve_candidate_report_dir(skill_dir, args.candidate_layer)
    model = build_and_write_pack(
        skill_dir=skill_dir,
        candidate_layer=args.candidate_layer,
        input_json=args.input_json,
        output_dir=output_dir,
        first_batch_size=args.first_batch_size,
    )
    print(
        json.dumps(
            {
                "json": model["outputs"]["json"],
                "csv": model["outputs"]["csv"],
                "protocol": model["outputs"]["protocol"],
                "summary": model["outputs"]["summary"],
                "landing_rule_count": model["landing_rule_count"],
                "first_batch_count": model["first_batch_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
