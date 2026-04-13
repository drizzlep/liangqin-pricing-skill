#!/usr/bin/env python3
import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from apply_addendum_layers import apply_addendum_layers
from material_names import formalize_text
import quote_flow_state
from quote_result_bundle import (
    DEFAULT_BUNDLE_ROOT,
    append_quote_card_prompt,
    build_quote_result_bundle,
    is_bundle_eligible,
    resolve_conversation_context,
    store_latest_quote_result_bundle,
)


INTERNAL_PROCESS_PHRASES = (
    "我先运行预检",
    "我先查价",
    "直接走预检",
    "根据 SKILL.md",
    "让我先看脚本",
    "现在运行玫瑰木折减计算",
    "现在运行门板补差计算",
)
FORMAL_QUOTE_FOLLOW_UP_PHRASES = (
    "还需要确认",
    "请问",
    "先确认",
    "告诉我",
    "能不能补充",
)
CONSULTANT_QUICK_ACTION_GROUP_LABELS = {
    "quote_send": "当前发送",
    "compare_offer": "对比邀约",
    "followthrough": "成交推进",
    "objection_reply": "异议回复",
    "objection_transition": "异议承接",
    "next_touch": "下次跟进",
}
CONSULTANT_QUICK_ACTION_GROUP_ORDER = (
    "quote_send",
    "compare_offer",
    "followthrough",
    "objection_reply",
    "objection_transition",
    "next_touch",
)


def _assertion_result(passed: bool, detail: str) -> dict[str, Any]:
    return {"passed": passed, "detail": detail}


def validate_output_contract(rendered_text: str, *, reference: bool) -> dict[str, Any]:
    text = str(rendered_text or "")
    assertions = {
        "has_product_line": _assertion_result(bool(re.search(r"^产品\d*：", text, re.MULTILINE)), "必须包含产品行"),
        "has_confirmed_line": _assertion_result("已确认：" in text, "必须包含已确认行"),
        "has_pricing_method_line": _assertion_result("这次按" in text, "必须包含计价方式行"),
        "has_calculation_steps": _assertion_result("计算过程：" in text and "\n- " in text, "必须展开计算过程"),
        "has_subtotal_line": _assertion_result("小计：" in text, "必须包含分项小计"),
        "has_total_line": _assertion_result(
            ("参考总价（仅供参考）：" in text) if reference else ("正式报价：" in text),
            "必须包含最终总价",
        ),
        "no_internal_process_leak": _assertion_result(
            not any(phrase in text for phrase in INTERNAL_PROCESS_PHRASES),
            "不能暴露内部执行过程",
        ),
        "no_follow_up_after_quote": _assertion_result(
            reference or not any(phrase in text for phrase in FORMAL_QUOTE_FOLLOW_UP_PHRASES),
            "正式报价后不能继续追问",
        ),
    }
    assertions["output_contract_pass"] = _assertion_result(
        all(result["passed"] for result in assertions.values()),
        "正式报价输出契约通过",
    )
    return {
        "passed": assertions["output_contract_pass"]["passed"],
        "assertions": assertions,
    }


def load_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON payload: {exc}")
    if not isinstance(payload, dict):
        raise SystemExit("Payload must be a JSON object")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise SystemExit("Payload.items must be a non-empty array")
    return payload


def prepare_payload(payload: dict[str, Any], *, addenda_root: Path, disable_addenda: bool) -> dict[str, Any]:
    if disable_addenda:
        return payload
    return apply_addendum_layers(payload, addenda_root)


def _normalize_role(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in {"customer", "designer", "consultant"} else ""


def _resolve_output_profile(audience_role: str | None, output_profile: str | None) -> str:
    normalized_profile = str(output_profile or "").strip()
    if normalized_profile in {"customer_simple", "designer_full", "consultant_dual"}:
        return normalized_profile
    normalized_role = _normalize_role(audience_role)
    if normalized_role == "customer":
        return "customer_simple"
    if normalized_role == "designer":
        return "designer_full"
    if normalized_role == "consultant":
        return "consultant_dual"
    return "legacy"


def _merge_note_entries(payload: dict[str, Any]) -> list[str]:
    note = str(formalize_text(str(payload.get("note", "")).strip()) or "").strip()
    addendum_notes = [
        str(formalize_text(str(note_item).strip()) or "").strip()
        for note_item in (payload.get("addendum_notes") or [])
    ]
    return [entry for entry in [note, *addendum_notes] if entry]


def _customer_safe_notes(payload: dict[str, Any]) -> list[str]:
    return [
        entry
        for entry in _merge_note_entries(payload)
        if entry and not entry.startswith("已套用设计师追加规则") and entry != "按当前规则可正式报价"
    ]


def _combined_quote_text(payload: dict[str, Any]) -> str:
    fragments: list[str] = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        fragments.extend(
            [
                str(item.get("product", "")).strip(),
                str(item.get("confirmed", "")).strip(),
                str(item.get("pricing_method", "")).strip(),
                " ".join(str(step).strip() for step in (item.get("calculation_steps") or []) if str(step).strip()),
            ]
        )
    fragments.extend(_merge_note_entries(payload))
    return formalize_text(" ".join(fragment for fragment in fragments if fragment)) or ""


def _customer_priority(payload: dict[str, Any]) -> str:
    return str(payload.get("customer_priority") or "").strip()


def _consultant_priority_label(priority: str) -> str:
    labels = {
        "budget": "预算控制",
        "aesthetics": "整体效果",
        "storage": "收纳效率",
        "space_efficiency": "空间利用",
        "eco_material": "材质安全与环保感受",
    }
    return labels.get(priority, "")


def _consultant_follow_up_hint(priority: str) -> str:
    hints = {
        "budget": "建议跟进：先围绕预算收口，优先解释哪些配置可以后置、哪些主体结构建议保留。",
        "aesthetics": "建议跟进：先围绕整体效果收口，优先对比门型层次、材质气质和细节做法。",
        "storage": "建议跟进：先围绕收纳效率收口，优先确认高频收纳区和内部结构分配。",
        "space_efficiency": "建议跟进：先围绕空间利用收口，优先确认布局效率、动线和关键尺寸。",
        "eco_material": "建议跟进：先围绕材质边界收口，优先确认材质偏好和环保顾虑。",
    }
    return hints.get(priority, "")


def _consultant_action_hint(priority: str) -> str:
    actions = {
        "budget": "建议动作：先发当前版；如客户继续压预算，再补一版降配对比。",
        "aesthetics": "建议动作：先发当前版；如客户想看效果，再补一版门型/材质升级对比。",
        "storage": "建议动作：先发当前版；如客户继续问收纳，再补一版内部结构优化对比。",
        "space_efficiency": "建议动作：先发当前版；如客户继续问空间利用，再补一版布局优化对比。",
        "eco_material": "建议动作：先发当前版；如客户继续问材质，再补一版材质边界说明或替代材质对比。",
    }
    return actions.get(priority, "")


def _consultant_compare_hint(priority: str) -> str:
    hints = {
        "budget": "对比指令：下一版优先只减附加项或收一档门型，不改主体尺寸和核心结构。",
        "aesthetics": "对比指令：下一版保持结构不变，只替换门型层次或材质表达。",
        "storage": "对比指令：下一版优先只调整内部结构和高频收纳区，不改主体尺寸。",
        "space_efficiency": "对比指令：下一版优先只调整布局和关键尺寸，不先动材质档位。",
        "eco_material": "对比指令：下一版优先只替换材质方案，并保留当前结构与尺寸。",
    }
    return hints.get(priority, "")


def _consultant_action_code(priority: str) -> str:
    codes = {
        "budget": "send_current_then_budget_compare",
        "aesthetics": "send_current_then_finish_upgrade_compare",
        "storage": "send_current_then_storage_compare",
        "space_efficiency": "send_current_then_layout_compare",
        "eco_material": "send_current_then_material_compare",
    }
    return codes.get(priority, "")


def _consultant_compare_code(priority: str) -> str:
    codes = {
        "budget": "reduce_addons_keep_structure",
        "aesthetics": "replace_finish_keep_structure",
        "storage": "tune_internal_layout_keep_outer_size",
        "space_efficiency": "tune_layout_keep_material_grade",
        "eco_material": "replace_material_keep_structure",
    }
    return codes.get(priority, "")


def _consultant_compare_variables(priority: str) -> list[dict[str, str]]:
    variables = {
        "budget": [
            {
                "code": "addons",
                "label": "附加项",
                "instruction": "先只减纹理连续、灯带、抽屉或专项配置，不先动主体结构。",
            },
            {
                "code": "door_style",
                "label": "门型层次",
                "instruction": "如果还要继续压预算，再把门型表达收一档。",
            },
        ],
        "aesthetics": [
            {
                "code": "door_style",
                "label": "门型层次",
                "instruction": "先替换门型层次，看整体气质变化。",
            },
            {
                "code": "material_finish",
                "label": "材质表达",
                "instruction": "再对比材质气质或表面表达，不先改结构。",
            },
        ],
        "storage": [
            {
                "code": "internal_layout",
                "label": "内部结构",
                "instruction": "先调整层板、挂区、抽屉等内部结构分配。",
            },
            {
                "code": "high_frequency_zone",
                "label": "高频收纳区",
                "instruction": "再强化真正高频使用的收纳区，不先改主体尺寸。",
            },
        ],
        "space_efficiency": [
            {
                "code": "layout",
                "label": "布局方式",
                "instruction": "先调整布局关系和开合动线。",
            },
            {
                "code": "key_dimensions",
                "label": "关键尺寸",
                "instruction": "再微调关键尺寸，不先动材质档位。",
            },
        ],
        "eco_material": [
            {
                "code": "material_option",
                "label": "材质方案",
                "instruction": "先替换材质方案，确认环保边界和触感预期。",
            },
            {
                "code": "surface_finish",
                "label": "表面做法",
                "instruction": "再补表面做法差异，结构和尺寸先保持不变。",
            },
        ],
    }
    return variables.get(priority, [])


def _consultant_keep_fixed_fields(priority: str) -> list[str]:
    fields = {
        "budget": ["主体尺寸", "核心结构"],
        "aesthetics": ["主体结构", "主体尺寸"],
        "storage": ["主体尺寸", "外部轮廓"],
        "space_efficiency": ["材质档位", "主体结构"],
        "eco_material": ["当前结构", "当前尺寸"],
    }
    return fields.get(priority, [])


def _consultant_compare_version_title(priority: str) -> str:
    titles = {
        "budget": "预算收一档对比版",
        "aesthetics": "效果升级对比版",
        "storage": "收纳优化对比版",
        "space_efficiency": "布局优化对比版",
        "eco_material": "材质替代对比版",
    }
    return titles.get(priority, "")


def _consultant_compare_variable_summary(priority: str) -> str:
    variables = _consultant_compare_variables(priority)
    fixed_fields = _consultant_keep_fixed_fields(priority)
    variable_labels = [str(entry.get("label", "")).strip() for entry in variables if str(entry.get("label", "")).strip()]
    if not variable_labels:
        return ""
    summary = f"先看{'，再看'.join(variable_labels)}"
    if fixed_fields:
        summary = f"{summary}；{'、'.join(fixed_fields)}保持不变。"
    else:
        summary = f"{summary}。"
    return summary


def _normalize_consultant_compare_variables(raw: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code", "")).strip()
        label = str(entry.get("label", "")).strip()
        instruction = str(entry.get("instruction", "")).strip()
        normalized_entry = {
            "code": code,
            "label": label,
            "instruction": instruction,
        }
        normalized_entry = {key: value for key, value in normalized_entry.items() if value}
        if normalized_entry:
            normalized.append(normalized_entry)
    return normalized


def _normalize_consultant_handoff_plan(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "priority",
        "priority_label",
        "follow_up_hint",
        "action_code",
        "action_hint",
        "compare_code",
        "compare_hint",
        "handoff_focus_note",
        "compare_version_title",
        "compare_variable_summary",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    compare_variables = _normalize_consultant_compare_variables(raw.get("compare_variables"))
    if compare_variables:
        normalized["compare_variables"] = compare_variables
    keep_fixed_fields = [str(entry).strip() for entry in (raw.get("keep_fixed_fields") or []) if str(entry).strip()]
    if keep_fixed_fields:
        normalized["keep_fixed_fields"] = keep_fixed_fields
    return normalized


def _default_compare_variables(payload: dict[str, Any]) -> list[dict[str, str]]:
    combined = _combined_quote_text(payload)
    if any(keyword in combined for keyword in ("衣柜", "书柜", "玄关柜", "餐边柜", "电视柜", "柜体")):
        return [
            {
                "code": "door_style",
                "label": "门型层次",
                "instruction": "先对比门型层次，不先动主体结构。",
            },
            {
                "code": "material_finish",
                "label": "材质层次",
                "instruction": "再对比材质层次或表面表达。",
            },
        ]
    if any(keyword in combined for keyword in ("儿童房", "儿童床", "半高床", "高架床", "错层床", "上下床", "床")):
        return [
            {
                "code": "bed_feature",
                "label": "梯体/围栏做法",
                "instruction": "先对比梯体、围栏或局部功能做法。",
            },
            {
                "code": "material_finish",
                "label": "材质层次",
                "instruction": "再对比材质层次和局部细节表达。",
            },
        ]
    return [
        {
            "code": "configuration",
            "label": "配置项",
            "instruction": "先对比配置项和附加项，不先动主体结构。",
        },
        {
            "code": "material_finish",
            "label": "材质层次",
            "instruction": "再对比材质层次或局部效果。",
        },
    ]


def _default_keep_fixed_fields(payload: dict[str, Any]) -> list[str]:
    combined = _combined_quote_text(payload)
    if "床" in combined:
        return ["当前尺寸", "当前主体结构"]
    return ["当前尺寸", "当前结构"]


def _default_compare_version_title(payload: dict[str, Any]) -> str:
    combined = _combined_quote_text(payload)
    if "床" in combined:
        return "空间方案对比版"
    return "方案对比版"


def _default_compare_variable_summary(payload: dict[str, Any]) -> str:
    variable_labels = [
        str(entry.get("label", "")).strip()
        for entry in _default_compare_variables(payload)
        if str(entry.get("label", "")).strip()
    ]
    fixed_fields = _default_keep_fixed_fields(payload)
    if not variable_labels:
        return ""
    summary = f"先看{'，再看'.join(variable_labels)}"
    if fixed_fields:
        summary = f"{summary}；{'、'.join(fixed_fields)}保持不变。"
    else:
        summary = f"{summary}。"
    return summary


def _compare_customer_explanation(priority: str, version_title: str) -> str:
    explanations = {
        "budget": f"如果你更在意预算，我可以按同样结构再补一版{version_title}，方便你看差价主要落在哪些项上。",
        "aesthetics": f"如果你更在意整体效果，我可以在结构不变的前提下，再补一版{version_title}，让你直接看门型和材质差异。",
        "storage": f"如果你更在意收纳效率，我可以再补一版{version_title}，让你直接看内部结构怎么调更合适。",
        "space_efficiency": f"如果你更在意空间利用，我可以再补一版{version_title}，让你直接看布局和关键尺寸差异。",
        "eco_material": f"如果你更在意材质边界，我可以再补一版{version_title}，让你直接看不同材质方案的区别。",
    }
    return explanations.get(priority, f"如果你愿意，我也可以基于这版再补一版{version_title}，方便你横向比较。")


def _normalize_compare_plan(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, Any] = {}
    for key in ("code", "version_title", "customer_explanation", "consultant_execution_note", "variable_summary"):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    adjustable_variables = _normalize_consultant_compare_variables(raw.get("adjustable_variables"))
    if adjustable_variables:
        normalized["adjustable_variables"] = adjustable_variables
    locked_fields = [str(entry).strip() for entry in (raw.get("locked_fields") or []) if str(entry).strip()]
    if locked_fields:
        normalized["locked_fields"] = locked_fields
    return normalized


def _build_compare_plan(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("reference"):
        return {}
    priority = _customer_priority(payload)
    handoff_plan = _consultant_handoff_plan(payload)
    if handoff_plan:
        return {
            "code": str(handoff_plan.get("compare_code", "")).strip(),
            "version_title": str(handoff_plan.get("compare_version_title", "")).strip(),
            "customer_explanation": _compare_customer_explanation(
                priority,
                str(handoff_plan.get("compare_version_title", "")).strip() or "方案对比版",
            ),
            "consultant_execution_note": str(handoff_plan.get("compare_hint", "")).strip(),
            "variable_summary": str(handoff_plan.get("compare_variable_summary", "")).strip(),
            "adjustable_variables": handoff_plan.get("compare_variables") or [],
            "locked_fields": handoff_plan.get("keep_fixed_fields") or [],
        }
    return {
        "code": "standard_compare",
        "version_title": _default_compare_version_title(payload),
        "customer_explanation": _compare_customer_explanation("", _default_compare_version_title(payload)),
        "consultant_execution_note": f"下一版优先只改{_default_compare_variable_summary(payload)}",
        "variable_summary": _default_compare_variable_summary(payload),
        "adjustable_variables": _default_compare_variables(payload),
        "locked_fields": _default_keep_fixed_fields(payload),
    }


def _compare_plan(payload: dict[str, Any]) -> dict[str, Any]:
    existing = _normalize_compare_plan(payload.get("compare_plan"))
    if existing:
        return existing
    return _build_compare_plan(payload)


def _normalize_follow_up_script_set(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, str] = {}
    for key in (
        "customer_reassurance",
        "customer_compare_offer",
        "consultant_follow_up",
        "next_touch_if_silent",
        "customer_followthrough_offer",
        "consultant_followthrough_prompt",
        "next_touch_followthrough",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _build_follow_up_script_set(payload: dict[str, Any]) -> dict[str, str]:
    next_best_action = payload.get("next_best_action") or {}
    followthrough_code = str(next_best_action.get("followthrough_action_code", "")).strip()
    followthrough_text = str(next_best_action.get("followthrough_text", "")).strip()
    followthrough_map = {
        "lock_formal_quote": {
            "customer": "如果你认可这个方向，下一步就把关键条件补齐，我这边直接帮你锁正式报价。",
            "consultant": "这轮先别停在参考价，重点把关键条件补齐，直接转正式报价并锁正式报价。",
            "next_touch": "如果客户暂时没回，下一次跟进优先把关键条件补齐，直接转正式报价。",
        },
        "schedule_store_visit": {
            "customer": "如果这版区间你能接受，我建议下一步先约到店或约设计沟通，把预算边界和取舍一次收清。",
            "consultant": "这轮重点不是再解释价格，而是把客户往到店/沟通收口，尽快把预算边界定下来。",
            "next_touch": "如果客户暂时没回，下一次跟进优先推进约到店或沟通，把预算边界收清。",
        },
        "request_design_deepening": {
            "customer": "如果你认可这个方向，我建议下一步直接转深化或出图前确认，把效果细节一次锁清。",
            "consultant": "这轮重点不是继续泛讲效果，而是尽快收口到深化/出图前确认，把门型和材质细节定下来。",
            "next_touch": "如果客户暂时没回，下一次跟进优先确认是否继续深化或进入出图前确认。",
        },
        "confirm_layout_deepening": {
            "customer": "如果你认可这个方向，我建议下一步直接转深化确认布局，把尺寸和内部结构一次锁清。",
            "consultant": "这轮重点是把客户往布局深化收口，不要停留在泛泛比较。",
            "next_touch": "如果客户暂时没回，下一次跟进优先确认是否继续做布局深化。",
        },
        "confirm_material_and_deepen": {
            "customer": "如果你认可这个方向，我建议下一步先把材质边界确认下来，再继续深化或出图。",
            "consultant": "这轮重点是先把材质边界定下来，再推进深化，不要停留在材质泛聊。",
            "next_touch": "如果客户暂时没回，下一次跟进优先确认材质边界，再推进深化。",
        },
        "schedule_store_or_design_followup": {
            "customer": "如果你认可这个方向，我建议下一步先约一次沟通，把到店、对比还是转深化一次定下来。",
            "consultant": "这轮重点是把客户往沟通推进收口，尽快判断是到店还是转深化，是否还要继续对比一次定下来。",
            "next_touch": "如果客户暂时没回，下一次跟进优先约一次沟通，把下一步路径定下来。",
        },
    }
    followthrough_copy = followthrough_map.get(followthrough_code, {})

    if payload.get("reference"):
        return {
            "customer_reassurance": "这版我先按你现在给到的条件做参考，等关键条件补齐后我再帮你转正式报价。",
            "customer_compare_offer": "如果你愿意，也可以先告诉我你更在意预算、效果还是收纳，我会按那个方向继续帮你收。",
            "consultant_follow_up": "先别急着做对比版，优先补齐影响价格的关键条件。",
            "next_touch_if_silent": "如果客户暂时没回，下一次跟进优先确认影响价格的关键条件有没有补齐。",
            "customer_followthrough_offer": str(followthrough_copy.get("customer", "")).strip() or followthrough_text,
            "consultant_followthrough_prompt": str(followthrough_copy.get("consultant", "")).strip() or followthrough_text,
            "next_touch_followthrough": str(followthrough_copy.get("next_touch", "")).strip() or followthrough_text,
        }

    compare_plan = _compare_plan(payload)
    customer_offer = str(compare_plan.get("customer_explanation", "")).strip()
    version_title = str(compare_plan.get("version_title", "")).strip() or "方案对比版"
    locked_fields = [str(entry).strip() for entry in (compare_plan.get("locked_fields") or []) if str(entry).strip()]
    locked_fields_text = f"{'、'.join(locked_fields)}先保持不变，" if locked_fields else ""
    return {
        "customer_reassurance": f"这版我先按当前确认条件给你锁住，{locked_fields_text}如果后面你还想比较，我再继续往下细化。",
        "customer_compare_offer": customer_offer or f"如果你愿意，我也可以基于这版再补一版{version_title}。",
        "consultant_follow_up": f"先发当前版，再补一句：{customer_offer or f'如果您愿意，我也可以基于这版再补一版{version_title}。'}",
        "next_touch_if_silent": f"如果客户暂时没回，下一次跟进优先确认是否要看“{version_title}”。",
        "customer_followthrough_offer": str(followthrough_copy.get("customer", "")).strip() or followthrough_text,
        "consultant_followthrough_prompt": str(followthrough_copy.get("consultant", "")).strip() or followthrough_text,
        "next_touch_followthrough": str(followthrough_copy.get("next_touch", "")).strip() or followthrough_text,
    }


def _follow_up_script_set(payload: dict[str, Any]) -> dict[str, str]:
    existing = _normalize_follow_up_script_set(payload.get("follow_up_script_set"))
    if existing:
        return existing
    return _build_follow_up_script_set(payload)


def _normalize_post_quote_stage(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, str] = {}
    for key in ("code", "label"):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _derive_post_quote_stage(payload: dict[str, Any]) -> dict[str, str]:
    if payload.get("reference"):
        return {
            "code": "reference_quote_pending_confirmation",
            "label": "参考报价待确认",
        }

    priority = _customer_priority(payload)
    mapping = {
        "budget": ("formal_quote_waiting_budget_feedback", "正式报价待预算反馈"),
        "aesthetics": ("formal_quote_waiting_finish_feedback", "正式报价待效果反馈"),
        "storage": ("formal_quote_waiting_storage_feedback", "正式报价待收纳反馈"),
        "space_efficiency": ("formal_quote_waiting_layout_feedback", "正式报价待布局反馈"),
        "eco_material": ("formal_quote_waiting_material_feedback", "正式报价待材质反馈"),
    }
    code, label = mapping.get(priority, ("formal_quote_waiting_reply", "正式报价待回复"))
    return {"code": code, "label": label}


def _post_quote_stage(payload: dict[str, Any]) -> dict[str, str]:
    existing = _normalize_post_quote_stage(payload.get("post_quote_stage"))
    if existing:
        return existing
    return _derive_post_quote_stage(payload)


def _version_transition_trigger(priority: str) -> str:
    mapping = {
        "budget": "继续压预算",
        "aesthetics": "想看更高一级效果",
        "storage": "想继续细化收纳",
        "space_efficiency": "想继续优化布局",
        "eco_material": "想继续比较材质边界",
    }
    return mapping.get(priority, "想继续横向比较")


def _normalize_quote_version_summary(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, str] = {}
    for key in (
        "current_version_code",
        "current_version_label",
        "current_version_index",
        "current_version_reason",
        "next_version_code",
        "next_version_label",
        "next_version_index",
        "next_version_reason",
        "version_transition_note",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _build_quote_version_summary(payload: dict[str, Any]) -> dict[str, str]:
    priority = _customer_priority(payload)
    compare_plan = _compare_plan(payload)
    if payload.get("reference"):
        return {
            "current_version_code": "reference_base",
            "current_version_label": "当前参考版",
            "current_version_index": "V1",
            "current_version_reason": "当前仍属于参考阶段，适合作为确认关键条件前的估算基线。",
            "next_version_code": "formal_quote_ready",
            "next_version_label": "正式报价版",
            "next_version_index": "V2",
            "next_version_reason": "关键条件补齐后，下一步应从参考版进入正式报价版。",
            "version_transition_note": "建议先发 V1 当前参考版；等关键条件补齐后，再转到 V2 正式报价版。",
        }

    next_version_label = str(compare_plan.get("version_title", "")).strip() or "方案对比版"
    next_version_code = str(compare_plan.get("code", "")).strip() or "standard_compare"
    variable_summary = str(compare_plan.get("variable_summary", "")).strip()
    trigger_text = _version_transition_trigger(priority)

    current_reason_map = {
        "budget": "当前版按已确认条件锁价，适合作为后续预算收法的基线版。",
        "aesthetics": "当前版按已确认条件锁价，适合作为后续效果升级对比的基线版。",
        "storage": "当前版按已确认条件锁价，适合作为后续收纳优化对比的基线版。",
        "space_efficiency": "当前版按已确认条件锁价，适合作为后续布局优化对比的基线版。",
        "eco_material": "当前版按已确认条件锁价，适合作为后续材质替代对比的基线版。",
    }
    current_reason = current_reason_map.get(priority, "当前版按已确认条件锁价，适合作为后续方案对比的基线版。")

    next_reason = (
        f"如果客户{trigger_text}，下一步建议从当前版衔接到 {next_version_label}。"
        f"{f' 对比重点：{variable_summary}' if variable_summary else ''}"
    ).strip()

    return {
        "current_version_code": "formal_base",
        "current_version_label": "当前正式版",
        "current_version_index": "V1",
        "current_version_reason": current_reason,
        "next_version_code": next_version_code,
        "next_version_label": next_version_label,
        "next_version_index": "V2",
        "next_version_reason": next_reason,
        "version_transition_note": f"建议先发 V1 当前正式版；如客户{trigger_text}，再发 V2 {next_version_label}。",
    }


def _quote_version_summary(payload: dict[str, Any]) -> dict[str, str]:
    existing = _normalize_quote_version_summary(payload.get("quote_version_summary"))
    if existing:
        return existing
    return _build_quote_version_summary(payload)


def _normalize_quote_version_actions(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, str] = {}
    for key in (
        "current_send_action",
        "next_version_offer_action",
        "customer_transition_line",
        "consultant_transition_action",
        "recommended_trigger",
        "copy_ready_offer",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _build_quote_version_actions(payload: dict[str, Any]) -> dict[str, str]:
    version_summary = _quote_version_summary(payload)
    priority = _customer_priority(payload)
    compare_plan = _compare_plan(payload)
    current_label = str(version_summary.get("current_version_label", "")).strip() or "当前正式版"
    current_index = str(version_summary.get("current_version_index", "")).strip() or "V1"
    next_label = str(version_summary.get("next_version_label", "")).strip() or "方案对比版"
    next_index = str(version_summary.get("next_version_index", "")).strip() or "V2"

    if payload.get("reference"):
        customer_transition_line = "这版我先按当前条件给你做参考，等关键条件补齐后，我再转正式报价给你。"
        return {
            "current_send_action": f"先发 {current_index} {current_label}，明确这是基于当前条件的参考估算。",
            "next_version_offer_action": f"关键条件补齐后，再转 {next_index} {next_label}。",
            "customer_transition_line": customer_transition_line,
            "consultant_transition_action": "先发参考版，不急着谈收价；优先补齐关键条件后再转正式报价。",
            "recommended_trigger": "关键条件补齐后",
            "copy_ready_offer": "这版你可以先作为参考看一下；等关键条件补齐后，我再给你转正式报价版。",
        }

    recommended_trigger = _version_transition_trigger(priority)
    locked_fields = [str(entry).strip() for entry in (compare_plan.get("locked_fields") or []) if str(entry).strip()]
    locked_fields_text = "、".join(locked_fields[:2])

    customer_transition_map = {
        "budget": (
            "如果你想把预算再往下收，我可以先让主体结构先不动，"
            f"{f'{locked_fields_text}继续保持稳定，' if locked_fields_text else ''}再补你一版{next_label}。"
        ),
        "aesthetics": f"如果你想看更高一级效果，我可以在结构不变的前提下，再补你一版{next_label}。",
        "storage": f"如果你想继续细化收纳，我可以在主体结构先不动的前提下，再补你一版{next_label}。",
        "space_efficiency": f"如果你想继续优化布局，我可以在材质档位先不动的前提下，再补你一版{next_label}。",
        "eco_material": f"如果你想继续比较材质边界，我可以在当前结构先不动的前提下，再补你一版{next_label}。",
    }
    customer_transition_line = customer_transition_map.get(
        priority,
        f"如果你想继续横向比较，我可以基于这版再补你一版{next_label}。",
    )

    consultant_transition_map = {
        "budget": "先发当前正式版；客户继续压预算时，只减附加项或收一档门型，不改主体尺寸和核心结构。",
        "aesthetics": "先发当前正式版；客户想看更高一级效果时，保持结构不变，优先对比门型层次和材质表达。",
        "storage": "先发当前正式版；客户想继续细化收纳时，优先调整内部结构和高频收纳区。",
        "space_efficiency": "先发当前正式版；客户想继续优化布局时，优先调整布局和关键尺寸。",
        "eco_material": "先发当前正式版；客户想继续比较材质边界时，优先替换材质方案并保留当前结构。",
    }
    consultant_transition_action = consultant_transition_map.get(
        priority,
        f"先发当前正式版；客户如果继续比较，再转 {next_index} {next_label}。",
    )

    return {
        "current_send_action": f"先发 {current_index} {current_label}，先把当前锁价结果发给客户。",
        "next_version_offer_action": f"如果客户{recommended_trigger}，再发 {next_index} {next_label}。",
        "customer_transition_line": customer_transition_line,
        "consultant_transition_action": consultant_transition_action,
        "recommended_trigger": recommended_trigger,
        "copy_ready_offer": f"这版我先发你{current_label}；{customer_transition_line}",
    }


def _quote_version_actions(payload: dict[str, Any]) -> dict[str, str]:
    existing = _normalize_quote_version_actions(payload.get("quote_version_actions"))
    if existing:
        return existing
    return _build_quote_version_actions(payload)


def _normalize_objection_playbook_entry(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, str] = {}
    for key in (
        "label",
        "customer_reply",
        "consultant_tactic",
        "recommended_action",
        "transition_action_code",
        "transition_action_label",
        "transition_line",
        "followthrough_line",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _recommended_first_objection_code(payload: dict[str, Any]) -> str:
    if payload.get("reference"):
        return "why_this_price"
    priority = _customer_priority(payload)
    mapping = {
        "budget": "cheaper_option",
        "aesthetics": "why_this_price",
        "storage": "price_high",
        "space_efficiency": "why_this_price",
        "eco_material": "why_this_price",
    }
    return mapping.get(priority, "price_high")


def _objection_adjustable_labels(compare_plan: dict[str, Any]) -> str:
    labels = [
        str(entry.get("label", "")).strip()
        for entry in (compare_plan.get("adjustable_variables") or [])
        if isinstance(entry, dict) and str(entry.get("label", "")).strip()
    ]
    return "、".join(labels[:3])


def _build_objection_playbook(payload: dict[str, Any]) -> dict[str, Any]:
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    compare_plan = _compare_plan(payload)
    follow_up_script_set = _follow_up_script_set(payload)
    quote_version_actions = _quote_version_actions(payload)
    priority = _customer_priority(payload)
    version_title = str(compare_plan.get("version_title", "")).strip() or "方案对比版"
    variable_summary = str(compare_plan.get("variable_summary", "")).strip()
    adjustable_labels = _objection_adjustable_labels(compare_plan)
    locked_fields = [str(entry).strip() for entry in (compare_plan.get("locked_fields") or []) if str(entry).strip()]
    locked_fields_text = "、".join(locked_fields)
    price_basis_text = "这次主要是按已确认的尺寸、材质、结构和做法计算的。"
    primary_action_code = str(next_best_action.get("primary_action_code", "")).strip() or "confirm_key_fields"
    primary_action_label = str(next_best_action.get("primary_action_label", "")).strip() or "补关键条件"
    secondary_action_code = str(next_best_action.get("secondary_action_code", "")).strip() or "offer_compare_version"
    secondary_action_label = str(next_best_action.get("secondary_action_label", "")).strip() or f"补{version_title}"
    customer_reassurance = str(follow_up_script_set.get("customer_reassurance", "")).strip()
    customer_compare_offer = str(follow_up_script_set.get("customer_compare_offer", "")).strip()
    customer_followthrough_offer = str(follow_up_script_set.get("customer_followthrough_offer", "")).strip()
    version_transition_line = str(quote_version_actions.get("customer_transition_line", "")).strip()
    copy_ready_offer = str(quote_version_actions.get("copy_ready_offer", "")).strip()
    reference_transition_line = (
        version_transition_line
        or "这版我先按当前条件给你做参考，等关键条件补齐后，我再转正式报价给你。"
    )
    formal_compare_transition_line = (
        version_transition_line
        or customer_compare_offer
        or f"如果你愿意，我也可以基于这版再补一版{version_title}。"
    )
    formal_followthrough_line = (
        customer_followthrough_offer
        or str(next_best_action.get("followthrough_text", "")).strip()
    )
    formal_hold_line = customer_reassurance or copy_ready_offer or formal_compare_transition_line

    def with_transition(
        entry: dict[str, str],
        *,
        action_code: str,
        action_label: str,
        transition_line: str,
        followthrough_line: str,
    ) -> dict[str, str]:
        enriched = dict(entry)
        if action_code:
            enriched["transition_action_code"] = action_code
        if action_label:
            enriched["transition_action_label"] = action_label
        if transition_line:
            enriched["transition_line"] = transition_line
        if followthrough_line:
            enriched["followthrough_line"] = followthrough_line
        return enriched

    if payload.get("reference"):
        entries = {
            "price_high": with_transition({
                "label": "客户说价格偏高",
                "customer_reply": "可以理解，这版还是按当前条件先做的参考价，等关键条件补齐后我再帮你收正式报价。",
                "consultant_tactic": "先提醒这是参考阶段，不要急着谈降价，优先补齐影响价格的关键条件。",
                "recommended_action": "先补关键条件，再转正式报价。",
            }, action_code=primary_action_code, action_label=primary_action_label, transition_line=reference_transition_line, followthrough_line=formal_followthrough_line),
            "why_this_price": with_transition({
                "label": "客户追问为什么是这个价",
                "customer_reply": "这次还是参考阶段，我先按你目前确认的条件估出来；等尺寸、材质和结构锁定后，价格会更准。",
                "consultant_tactic": "先解释参考依据，再把客户拉回到关键条件确认上。",
                "recommended_action": "解释参考依据，并继续确认关键条件。",
            }, action_code=primary_action_code, action_label=primary_action_label, transition_line=reference_transition_line, followthrough_line=formal_followthrough_line),
            "cheaper_option": with_transition({
                "label": "客户问能不能便宜点",
                "customer_reply": "可以，但我不建议现在直接往下压，先把关键条件锁清楚会更稳；如果你愿意，也可以先告诉我你更在意预算、效果还是收纳。",
                "consultant_tactic": "不要在参考阶段直接做大幅收价，优先缩小需求范围。",
                "recommended_action": "先确认客户更在意的方向，再继续追问。",
            }, action_code=primary_action_code, action_label=primary_action_label, transition_line=reference_transition_line, followthrough_line=formal_followthrough_line),
            "need_time": with_transition({
                "label": "客户说再考虑下",
                "customer_reply": "没问题，这版你先留着做参考；等你方便时，把关键条件补给我，我再帮你转正式报价。",
                "consultant_tactic": "先结束当前轮，不逼单；下次跟进继续补关键条件。",
                "recommended_action": str(follow_up_script_set.get("next_touch_if_silent", "")).strip(),
            }, action_code=primary_action_code, action_label=primary_action_label, transition_line=reference_transition_line, followthrough_line=formal_followthrough_line),
        }
        return {
            "recommended_first_code": _recommended_first_objection_code(payload),
            **entries,
        }

    if priority == "budget":
        price_high_reply = (
            f"可以理解，当前这版是按已经确认的条件锁出来的。"
            f"我不建议先动{locked_fields_text or '主体结构'}；如果你愿意，我可以按同样结构再补一版{version_title}，"
            "这样你会更直观看到差价主要落在哪些项上。"
        )
    elif priority == "aesthetics":
        price_high_reply = (
            f"可以理解，这版价格主要落在当前结构、门型层次和材质表达上。"
            f"如果你想先把预算收一点，我可以在结构不变的前提下，再补一版{version_title}。"
        )
    else:
        price_high_reply = (
            f"可以理解，这版是按当前确认条件算出来的。"
            f"如果你愿意，我也可以基于这版再补一版{version_title}，让你更直观看到差价主要落在哪些项上。"
        )

    why_this_price_reply = (
        f"{price_basis_text}"
        f"{f' 差异通常集中在{adjustable_labels}这些地方。' if adjustable_labels else ''}"
        f"{f' 如果要做下一版，我会优先按“{variable_summary}”来收。' if variable_summary else ''}"
    ).strip()

    cheaper_option_reply = str(
        compare_plan.get("customer_explanation")
        or f"如果你更想先控预算，我可以基于这版再补一版{version_title}。"
    ).strip()

    need_time_reply = (
        f"没问题，这版你可以先留着内部讨论。"
        f" {str(follow_up_script_set.get('customer_reassurance', '')).strip()}"
        f" {str(follow_up_script_set.get('customer_compare_offer', '')).strip()}"
    ).strip()

    entries = {
        "price_high": with_transition({
            "label": "客户说价格偏高",
            "customer_reply": price_high_reply,
            "consultant_tactic": (
                f"先承认预算压力，再解释价格依据；不要先谈折扣，优先把客户带到{version_title}。"
            ),
            "recommended_action": f"先发当前版，再补发{version_title}邀约。",
        }, action_code=secondary_action_code, action_label=secondary_action_label, transition_line=formal_compare_transition_line, followthrough_line=formal_followthrough_line),
        "why_this_price": with_transition({
            "label": "客户追问为什么是这个价",
            "customer_reply": why_this_price_reply,
            "consultant_tactic": (
                f"优先解释已确认条件和价格组成，避免泛泛谈贵不贵；{f'重点解释{adjustable_labels}。' if adjustable_labels else '重点解释当前做法和材质差异。'}"
            ),
            "recommended_action": "先解释价格依据，再问客户更在意预算、效果还是功能。",
        }, action_code=secondary_action_code, action_label=secondary_action_label, transition_line=formal_compare_transition_line, followthrough_line=formal_followthrough_line),
        "cheaper_option": with_transition({
            "label": "客户问能不能便宜点",
            "customer_reply": cheaper_option_reply,
            "consultant_tactic": (
                f"不要直接打折，优先用{version_title}承接；{f'{locked_fields_text}先别动。' if locked_fields_text else ''}"
            ).strip(),
            "recommended_action": f"生成{version_title}，优先只改{adjustable_labels or '附加项和局部做法'}。",
        }, action_code=secondary_action_code, action_label=secondary_action_label, transition_line=customer_compare_offer or formal_compare_transition_line, followthrough_line=formal_followthrough_line),
        "need_time": with_transition({
            "label": "客户说再考虑下",
            "customer_reply": need_time_reply,
            "consultant_tactic": "先让客户带走当前版，不急着推进成交；下次跟进优先问是否需要看对比版。",
            "recommended_action": str(follow_up_script_set.get("next_touch_if_silent", "")).strip(),
        }, action_code=str(next_best_action.get("primary_action_code", "")).strip() or "send_current_quote", action_label="先留当前版", transition_line=formal_hold_line, followthrough_line=formal_followthrough_line),
    }
    return {
        "recommended_first_code": _recommended_first_objection_code(payload),
        **entries,
    }


def _normalize_objection_playbook(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, Any] = {}
    recommended_first_code = str(raw.get("recommended_first_code", "")).strip()
    if recommended_first_code:
        normalized["recommended_first_code"] = recommended_first_code
    for key in ("price_high", "why_this_price", "cheaper_option", "need_time"):
        entry = _normalize_objection_playbook_entry(raw.get(key))
        if entry:
            normalized[key] = entry
    return normalized


def _objection_playbook(payload: dict[str, Any]) -> dict[str, Any]:
    existing = _normalize_objection_playbook(payload.get("objection_playbook"))
    if existing:
        return existing
    return _build_objection_playbook(payload)


def _normalize_consultant_quick_actions(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        return []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        normalized_entry: dict[str, str] = {}
        for key in ("code", "label", "text", "group", "priority", "source"):
            value = str(entry.get(key, "")).strip()
            if value:
                normalized_entry[key] = value
        label = normalized_entry.get("label", "")
        text = normalized_entry.get("text", "")
        if not label or not text:
            continue
        signature = (normalized_entry.get("code", label), text)
        if signature in seen:
            continue
        seen.add(signature)
        normalized.append(normalized_entry)
    return normalized


def _build_consultant_quick_actions(payload: dict[str, Any]) -> list[dict[str, str]]:
    quote_version_actions = _quote_version_actions(payload)
    follow_up_script_set = _follow_up_script_set(payload)
    objection_playbook = _objection_playbook(payload)
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)

    actions: list[dict[str, str]] = []
    seen_signatures: set[tuple[str, str]] = set()

    def append_action(
        *,
        code: str,
        label: str,
        text: str,
        group: str,
        priority: str,
        source: str,
    ) -> None:
        normalized_text = str(text).strip()
        signature = (group, normalized_text)
        if not label or not normalized_text or signature in seen_signatures:
            return
        seen_signatures.add(signature)
        actions.append(
            {
                "code": code,
                "label": label,
                "text": normalized_text,
                "group": group,
                "priority": priority,
                "source": source,
            }
        )

    append_action(
        code="copy_ready_offer",
        label="当前发送句",
        text=str(quote_version_actions.get("copy_ready_offer", "")).strip() or str(payload.get("customer_forward_text", "")).strip(),
        group="quote_send",
        priority="primary",
        source="quote_version_actions.copy_ready_offer",
    )
    append_action(
        code="copy_compare_offer",
        label="对比邀约句",
        text=str(follow_up_script_set.get("customer_compare_offer", "")).strip()
        or str(quote_version_actions.get("customer_transition_line", "")).strip(),
        group="compare_offer",
        priority="secondary",
        source="follow_up_script_set.customer_compare_offer",
    )
    append_action(
        code="copy_followthrough_offer",
        label="成交推进句",
        text=str(follow_up_script_set.get("customer_followthrough_offer", "")).strip()
        or str(next_best_action.get("followthrough_text", "")).strip(),
        group="followthrough",
        priority="primary",
        source="follow_up_script_set.customer_followthrough_offer",
    )

    recommended_code = str(objection_playbook.get("recommended_first_code", "")).strip()
    recommended_entry = objection_playbook.get(recommended_code) if recommended_code else None
    if isinstance(recommended_entry, dict):
        recommended_label = str(recommended_entry.get("label", "")).strip() or recommended_code
        append_action(
            code="copy_recommended_objection_reply",
            label=f"推荐异议回复 | {recommended_label}",
            text=str(recommended_entry.get("customer_reply", "")).strip(),
            group="objection_reply",
            priority="primary",
            source=f"objection_playbook.{recommended_code}.customer_reply",
        )
        append_action(
            code="copy_recommended_objection_transition",
            label=f"推荐异议承接 | {recommended_label}",
            text=str(recommended_entry.get("transition_line", "")).strip(),
            group="objection_transition",
            priority="primary",
            source=f"objection_playbook.{recommended_code}.transition_line",
        )

    append_action(
        code="copy_next_touch_follow_up",
        label="下次跟进句",
        text=str(follow_up_script_set.get("next_touch_followthrough", "")).strip()
        or str(follow_up_script_set.get("next_touch_if_silent", "")).strip(),
        group="next_touch",
        priority="secondary",
        source="follow_up_script_set.next_touch_followthrough",
    )
    return actions


def _consultant_quick_actions(payload: dict[str, Any]) -> list[dict[str, str]]:
    existing = _normalize_consultant_quick_actions(payload.get("consultant_quick_actions"))
    if existing:
        return existing
    return _build_consultant_quick_actions(payload)


def _normalize_consultant_action_queue(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            continue
        normalized_entry: dict[str, Any] = {}
        for key in ("code", "title", "text", "group", "priority", "source", "stage_code", "trigger_hint"):
            value = str(entry.get(key, "")).strip()
            if value:
                normalized_entry[key] = value
        title = str(normalized_entry.get("title", "")).strip()
        text = str(normalized_entry.get("text", "")).strip()
        if not title or not text:
            continue
        try:
            normalized_entry["rank"] = int(entry.get("rank"))
        except (TypeError, ValueError):
            normalized_entry["rank"] = index
        normalized_entry["recommended"] = bool(entry.get("recommended"))
        signature = (
            str(normalized_entry.get("group", "")).strip(),
            str(normalized_entry.get("code", title)).strip(),
            text,
        )
        if signature in seen:
            continue
        seen.add(signature)
        normalized.append(normalized_entry)
    normalized.sort(key=lambda item: (int(item.get("rank", 9999)), str(item.get("title", "")).strip()))
    if normalized and not any(bool(item.get("recommended")) for item in normalized):
        normalized[0]["recommended"] = True
    return normalized


def _build_consultant_action_queue(payload: dict[str, Any]) -> list[dict[str, Any]]:
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    post_quote_stage = _post_quote_stage(payload)
    quote_version_summary = _quote_version_summary(payload)
    quote_version_actions = _quote_version_actions(payload)
    follow_up_script_set = _follow_up_script_set(payload)
    objection_playbook = _objection_playbook(payload)
    stage_code = str(post_quote_stage.get("code", "")).strip() or str(payload.get("quote_stage", "")).strip()
    next_version_label = str(quote_version_summary.get("next_version_label", "")).strip() or "下一版"
    next_version_index = str(quote_version_summary.get("next_version_index", "")).strip() or "V2"
    recommended_trigger = str(quote_version_actions.get("recommended_trigger", "")).strip() or "继续往下推进"

    actions: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str, str]] = set()

    def _join_unique_texts(*values: Any) -> str:
        parts: list[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if normalized and normalized not in parts:
                parts.append(normalized)
        return " ".join(parts)

    def append_action(
        *,
        code: str,
        title: str,
        text: str,
        group: str,
        priority: str,
        rank: int,
        recommended: bool,
        source: str,
        trigger_hint: str,
    ) -> None:
        normalized_title = str(title).strip()
        normalized_text = str(text).strip()
        normalized_group = str(group).strip()
        normalized_code = str(code).strip() or normalized_group or f"queue_action_{rank}"
        if not normalized_title or not normalized_text:
            return
        signature = (normalized_group, normalized_code, normalized_text)
        if signature in seen_signatures:
            return
        seen_signatures.add(signature)
        actions.append(
            {
                "code": normalized_code,
                "title": normalized_title,
                "text": normalized_text,
                "group": normalized_group,
                "priority": str(priority).strip() or "p2",
                "rank": rank,
                "recommended": recommended,
                "source": str(source).strip(),
                "stage_code": stage_code,
                "trigger_hint": str(trigger_hint).strip(),
            }
        )

    primary_code = str(next_best_action.get("primary_action_code", "")).strip() or (
        "confirm_key_fields" if payload.get("reference") else "send_current_quote"
    )
    primary_title = str(next_best_action.get("primary_action_label", "")).strip() or (
        "补关键条件" if payload.get("reference") else "先发当前版"
    )
    primary_text = (
        str(next_best_action.get("text", "")).strip()
        if payload.get("reference")
        else str(quote_version_actions.get("current_send_action", "")).strip() or str(next_best_action.get("text", "")).strip()
    )
    append_action(
        code=primary_code,
        title=primary_title,
        text=primary_text,
        group="current_main",
        priority="p1",
        rank=1,
        recommended=True,
        source="next_best_action.text" if payload.get("reference") else "quote_version_actions.current_send_action",
        trigger_hint=(
            "适合当前仍在参考阶段，优先把影响价格的关键条件补齐。"
            if payload.get("reference")
            else "适合正式报价刚生成这一轮，先把当前真实报价结果发出去。"
        ),
    )

    append_action(
        code=str(next_best_action.get("secondary_action_code", "")).strip()
        or str(quote_version_summary.get("next_version_code", "")).strip()
        or "offer_next_version",
        title=str(next_best_action.get("secondary_action_label", "")).strip() or f"转{next_version_label}",
        text=str(quote_version_actions.get("next_version_offer_action", "")).strip()
        or str(follow_up_script_set.get("consultant_follow_up", "")).strip(),
        group="compare_next",
        priority="p2",
        rank=2,
        recommended=False,
        source="quote_version_actions.next_version_offer_action",
        trigger_hint=(
            "适合关键条件补齐后，衔接到正式报价版。"
            if payload.get("reference")
            else f"适合客户{recommended_trigger}时，再切到 {next_version_index} {next_version_label}。"
        ),
    )

    append_action(
        code=str(next_best_action.get("followthrough_action_code", "")).strip() or "followthrough_action",
        title=str(next_best_action.get("followthrough_action_label", "")).strip() or "成交推进",
        text=str(follow_up_script_set.get("consultant_followthrough_prompt", "")).strip()
        or str(next_best_action.get("followthrough_text", "")).strip(),
        group="followthrough",
        priority="p2",
        rank=3,
        recommended=False,
        source=(
            "follow_up_script_set.consultant_followthrough_prompt"
            if str(follow_up_script_set.get("consultant_followthrough_prompt", "")).strip()
            else "next_best_action.followthrough_text"
        ),
        trigger_hint="适合客户接受当前方向后，继续把报价往到店、深化或正式确认推进。",
    )

    recommended_code = str(objection_playbook.get("recommended_first_code", "")).strip()
    recommended_entry = objection_playbook.get(recommended_code) if recommended_code else None
    if isinstance(recommended_entry, dict):
        recommended_label = str(recommended_entry.get("label", "")).strip() or "推荐异议"
        append_action(
            code=f"handle_{recommended_code}" if recommended_code else "handle_objection",
            title=f"异议承接 | {recommended_label}",
            text=_join_unique_texts(
                str(recommended_entry.get("consultant_tactic", "")).strip(),
                str(recommended_entry.get("transition_line", "")).strip(),
                str(recommended_entry.get("customer_reply", "")).strip()
                if not str(recommended_entry.get("transition_line", "")).strip()
                else "",
            ),
            group="objection_transition",
            priority="p2",
            rank=4,
            recommended=False,
            source=f"objection_playbook.{recommended_code}",
            trigger_hint=f"适合客户出现“{recommended_label}”这类异议时优先使用。",
        )

    next_touch_text = str(follow_up_script_set.get("next_touch_followthrough", "")).strip() or str(
        follow_up_script_set.get("next_touch_if_silent", "")
    ).strip()
    append_action(
        code="next_touch_follow_up",
        title="下次跟进",
        text=next_touch_text,
        group="next_touch",
        priority="p3",
        rank=5,
        recommended=False,
        source=(
            "follow_up_script_set.next_touch_followthrough"
            if str(follow_up_script_set.get("next_touch_followthrough", "")).strip()
            else "follow_up_script_set.next_touch_if_silent"
        ),
        trigger_hint="适合客户暂时没回时，作为下一次触达的默认动作。",
    )
    return actions


def _consultant_action_queue(payload: dict[str, Any]) -> list[dict[str, Any]]:
    existing = _normalize_consultant_action_queue(payload.get("consultant_action_queue"))
    if existing:
        return existing
    return _build_consultant_action_queue(payload)


def _consultant_workbench_badges(payload: dict[str, Any]) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def append_badge(group: str, code: str, label: str) -> None:
        normalized_group = str(group).strip()
        normalized_code = str(code).strip()
        normalized_label = str(label).strip()
        if not normalized_group or not normalized_code or not normalized_label:
            return
        signature = (normalized_group, normalized_code)
        if signature in seen:
            return
        seen.add(signature)
        badges.append(
            {
                "group": normalized_group,
                "code": normalized_code,
                "label": normalized_label,
            }
        )

    post_quote_stage = _post_quote_stage(payload)
    stage_code = str(post_quote_stage.get("code", "")).strip()
    stage_label = str(post_quote_stage.get("label", "")).strip() or str(payload.get("quote_stage", "")).strip()
    if stage_code or stage_label:
        append_badge("stage", stage_code or stage_label, stage_label or stage_code)

    confidence = str(payload.get("quote_confidence", "")).strip()
    confidence_labels = {
        "high": "高把握度",
        "medium": "中等把握度",
        "low": "低把握度",
    }
    if confidence:
        append_badge("quote_confidence", confidence, confidence_labels.get(confidence, confidence))

    intent = str(payload.get("conversion_intent_level", "")).strip()
    intent_labels = {
        "high": "高转化意向",
        "medium": "中等转化意向",
        "low": "低转化意向",
    }
    if intent:
        append_badge("conversion_intent", intent, intent_labels.get(intent, intent))

    priority_plan = _consultant_handoff_plan(payload)
    priority_code = str(priority_plan.get("priority", "")).strip()
    priority_label = str(priority_plan.get("priority_label", "")).strip()
    if priority_code and priority_label:
        append_badge("customer_priority", priority_code, priority_label)
    return badges


def _consultant_workbench_quick_action_groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for entry in _consultant_quick_actions(payload):
        if not isinstance(entry, dict):
            continue
        group = str(entry.get("group", "")).strip() or "other"
        grouped.setdefault(group, []).append(
            {
                "code": str(entry.get("code", "")).strip(),
                "label": str(entry.get("label", "")).strip(),
                "text": str(entry.get("text", "")).strip(),
                "priority": str(entry.get("priority", "")).strip(),
                "source": str(entry.get("source", "")).strip(),
            }
        )

    groups: list[dict[str, Any]] = []
    ordered_groups = [
        group
        for group in [*CONSULTANT_QUICK_ACTION_GROUP_ORDER, *sorted(grouped.keys())]
        if group in grouped
    ]
    seen_groups: set[str] = set()
    for group in ordered_groups:
        if group in seen_groups:
            continue
        seen_groups.add(group)
        items = [item for item in grouped.get(group, []) if item.get("label") and item.get("text")]
        if not items:
            continue
        groups.append(
            {
                "group": group,
                "label": CONSULTANT_QUICK_ACTION_GROUP_LABELS.get(group, group),
                "count": len(items),
                "items": items,
            }
        )
    return groups


def _build_consultant_workbench_panels(payload: dict[str, Any]) -> list[dict[str, Any]]:
    quote_version_summary = _quote_version_summary(payload)
    quote_version_actions = _quote_version_actions(payload)
    compare_plan = _compare_plan(payload)
    follow_up_script_set = _follow_up_script_set(payload)
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    objection_playbook = _objection_playbook(payload)
    decision_risk_points = [str(point).strip() for point in (payload.get("decision_risk_points") or []) if str(point).strip()]

    panels: list[dict[str, Any]] = []

    def append_panel(
        *,
        code: str,
        title: str,
        lines: list[str],
        action_code: str = "",
        action_label: str = "",
    ) -> None:
        normalized_lines: list[str] = []
        for line in lines:
            normalized = str(line).strip()
            if normalized and normalized not in normalized_lines:
                normalized_lines.append(normalized)
        if not code or not title or not normalized_lines:
            return
        panel: dict[str, Any] = {
            "code": code,
            "title": title,
            "lines": normalized_lines,
        }
        if action_code:
            panel["action_code"] = action_code
        if action_label:
            panel["action_label"] = action_label
        panels.append(panel)

    current_version_index = str(quote_version_summary.get("current_version_index", "")).strip()
    current_version_label = str(quote_version_summary.get("current_version_label", "")).strip()
    next_version_index = str(quote_version_summary.get("next_version_index", "")).strip()
    next_version_label = str(quote_version_summary.get("next_version_label", "")).strip()
    append_panel(
        code="version_focus",
        title="版本推进",
        lines=[
            f"当前版本：{current_version_index} {current_version_label}".strip(),
            f"下一版本：{next_version_index} {next_version_label}".strip(),
            str(quote_version_summary.get("version_transition_note", "")).strip(),
            str(quote_version_actions.get("consultant_transition_action", "")).strip(),
        ],
        action_code=str(next_best_action.get("secondary_action_code", "")).strip(),
        action_label=str(next_best_action.get("secondary_action_label", "")).strip(),
    )

    adjustable_variables = [
        str(variable.get("label", "")).strip()
        for variable in (compare_plan.get("adjustable_variables") or [])
        if isinstance(variable, dict) and str(variable.get("label", "")).strip()
    ]
    locked_fields = [str(field).strip() for field in (compare_plan.get("locked_fields") or []) if str(field).strip()]
    append_panel(
        code="compare_focus",
        title="下一版建议",
        lines=[
            f"建议版本：{str(compare_plan.get('version_title', '')).strip()}",
            f"优先改：{'、'.join(adjustable_variables)}" if adjustable_variables else "",
            f"保持不动：{'、'.join(locked_fields)}" if locked_fields else "",
            str(compare_plan.get("customer_explanation", "")).strip()
            or str(quote_version_actions.get("customer_transition_line", "")).strip(),
        ],
        action_code=str(compare_plan.get("code", "")).strip(),
        action_label=str(compare_plan.get("version_title", "")).strip(),
    )

    append_panel(
        code="followthrough_focus",
        title="成交推进",
        lines=[
            str(follow_up_script_set.get("consultant_followthrough_prompt", "")).strip()
            or str(next_best_action.get("followthrough_text", "")).strip(),
            str(follow_up_script_set.get("customer_followthrough_offer", "")).strip(),
            str(follow_up_script_set.get("next_touch_followthrough", "")).strip()
            or str(follow_up_script_set.get("next_touch_if_silent", "")).strip(),
        ],
        action_code=str(next_best_action.get("followthrough_action_code", "")).strip(),
        action_label=str(next_best_action.get("followthrough_action_label", "")).strip(),
    )

    recommended_code = str(objection_playbook.get("recommended_first_code", "")).strip()
    recommended_entry = objection_playbook.get(recommended_code) if recommended_code else None
    if isinstance(recommended_entry, dict):
        append_panel(
            code="objection_focus",
            title=f"推荐异议承接 | {str(recommended_entry.get('label', '')).strip() or recommended_code}",
            lines=[
                str(recommended_entry.get("consultant_tactic", "")).strip(),
                str(recommended_entry.get("customer_reply", "")).strip(),
                str(recommended_entry.get("transition_line", "")).strip(),
                str(recommended_entry.get("followthrough_line", "")).strip(),
            ],
            action_code=str(recommended_entry.get("transition_action_code", "")).strip(),
            action_label=str(recommended_entry.get("transition_action_label", "")).strip(),
        )

    append_panel(
        code="risk_focus",
        title="价格变动提醒",
        lines=decision_risk_points[:3],
    )
    return panels


def _build_consultant_workbench(payload: dict[str, Any]) -> dict[str, Any]:
    action_queue = _consultant_action_queue(payload)
    quick_action_groups = _consultant_workbench_quick_action_groups(payload)
    info_panels = _build_consultant_workbench_panels(payload)
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    post_quote_stage = _post_quote_stage(payload)
    quote_version_summary = _quote_version_summary(payload)
    handoff_plan = _consultant_handoff_plan(payload)

    primary_action = copy.deepcopy(action_queue[0]) if action_queue else {}
    if not primary_action and isinstance(next_best_action, dict):
        primary_action = {
            "code": str(next_best_action.get("primary_action_code", "")).strip(),
            "title": str(next_best_action.get("primary_action_label", "")).strip() or str(next_best_action.get("title", "")).strip(),
            "text": str(next_best_action.get("text", "")).strip(),
            "recommended": True,
        }

    title = str(post_quote_stage.get("label", "")).strip()
    if not title:
        title = "参考报价推进" if payload.get("reference") else "正式报价推进"

    summary = (
        str(handoff_plan.get("handoff_focus_note", "")).strip()
        or str(quote_version_summary.get("version_transition_note", "")).strip()
        or str(next_best_action.get("text", "")).strip()
    )

    workbench = {
        "header": {
            "title": title,
            "summary": summary,
            "badges": _consultant_workbench_badges(payload),
        },
        "primary_action": primary_action,
        "action_queue": [copy.deepcopy(entry) for entry in action_queue],
        "quick_action_groups": quick_action_groups,
        "info_panels": info_panels,
    }

    if quote_version_summary:
        workbench["version_snapshot"] = {
            "current_version_index": str(quote_version_summary.get("current_version_index", "")).strip(),
            "current_version_label": str(quote_version_summary.get("current_version_label", "")).strip(),
            "next_version_index": str(quote_version_summary.get("next_version_index", "")).strip(),
            "next_version_label": str(quote_version_summary.get("next_version_label", "")).strip(),
        }
    return workbench


def _consultant_workbench(payload: dict[str, Any]) -> dict[str, Any]:
    existing = payload.get("consultant_workbench")
    if isinstance(existing, dict) and existing:
        return existing
    return _build_consultant_workbench(payload)


def _normalize_quote_followup_state(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "code",
        "label",
        "status",
        "current_phase",
        "recommended_track",
        "current_version_status",
        "compare_version_status",
        "followthrough_status",
        "next_action_code",
        "compare_action_code",
        "followthrough_action_code",
        "next_version_label",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    recommended_next_codes = [
        str(entry).strip()
        for entry in (raw.get("recommended_next_codes") or [])
        if str(entry).strip()
    ]
    if recommended_next_codes:
        normalized["recommended_next_codes"] = recommended_next_codes
    return normalized


def _quote_followup_track(payload: dict[str, Any]) -> str:
    if payload.get("reference"):
        return "formal_confirmation"
    priority = _customer_priority(payload)
    mapping = {
        "budget": "budget_compare",
        "aesthetics": "finish_upgrade",
        "storage": "storage_refine",
        "space_efficiency": "layout_refine",
        "eco_material": "material_refine",
    }
    return mapping.get(priority, "general_followup")


def _build_quote_followup_state(payload: dict[str, Any]) -> dict[str, Any]:
    post_quote_stage = _post_quote_stage(payload)
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    quote_version_summary = _quote_version_summary(payload)
    action_queue = _consultant_action_queue(payload)
    recommended_next_codes = [
        str(entry.get("code", "")).strip()
        for entry in action_queue[:3]
        if isinstance(entry, dict) and str(entry.get("code", "")).strip()
    ]
    return {
        "code": str(post_quote_stage.get("code", "")).strip() or "quote_followup_ready",
        "label": str(post_quote_stage.get("label", "")).strip() or "报价后跟进待开始",
        "status": "awaiting_confirmation" if payload.get("reference") else "awaiting_customer_feedback",
        "current_phase": "reference_quote_followup" if payload.get("reference") else "formal_quote_followup",
        "recommended_track": _quote_followup_track(payload),
        "current_version_status": "ready_to_send",
        "compare_version_status": "ready_after_confirmation" if payload.get("reference") else "ready_when_triggered",
        "followthrough_status": "ready_after_confirmation" if payload.get("reference") else "ready_after_acceptance",
        "recommended_next_codes": recommended_next_codes,
        "next_action_code": str(next_best_action.get("primary_action_code", "")).strip()
        or (recommended_next_codes[0] if recommended_next_codes else ""),
        "compare_action_code": str(next_best_action.get("secondary_action_code", "")).strip(),
        "followthrough_action_code": str(next_best_action.get("followthrough_action_code", "")).strip(),
        "next_version_label": str(quote_version_summary.get("next_version_label", "")).strip(),
    }


def _quote_followup_state(payload: dict[str, Any]) -> dict[str, Any]:
    existing = _normalize_quote_followup_state(payload.get("quote_followup_state"))
    if existing:
        return existing
    return _build_quote_followup_state(payload)


def _normalize_quote_feedback_signal(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "code",
        "label",
        "source",
        "recommended_objection_code",
        "recommended_followthrough_code",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    if "is_explicit" in raw:
        normalized["is_explicit"] = bool(raw.get("is_explicit"))
    return normalized


def _build_quote_feedback_signal(payload: dict[str, Any]) -> dict[str, Any]:
    priority = _customer_priority(payload)
    priority_label = _consultant_priority_label(priority)
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    objection_playbook = _objection_playbook(payload)
    if priority and priority_label:
        return {
            "code": priority,
            "label": priority_label,
            "source": "customer_priority",
            "is_explicit": True,
            "recommended_objection_code": str(objection_playbook.get("recommended_first_code", "")).strip(),
            "recommended_followthrough_code": str(next_best_action.get("followthrough_action_code", "")).strip(),
        }
    if payload.get("reference"):
        return {
            "code": "confirm_key_fields",
            "label": "待确认关键条件",
            "source": "reference_quote_stage",
            "is_explicit": False,
            "recommended_objection_code": str(objection_playbook.get("recommended_first_code", "")).strip(),
            "recommended_followthrough_code": str(next_best_action.get("followthrough_action_code", "")).strip(),
        }
    return {
        "code": "",
        "label": "",
        "source": "pending_customer_feedback",
        "is_explicit": False,
        "recommended_objection_code": str(objection_playbook.get("recommended_first_code", "")).strip(),
        "recommended_followthrough_code": str(next_best_action.get("followthrough_action_code", "")).strip(),
    }


def _quote_feedback_signal(payload: dict[str, Any]) -> dict[str, Any]:
    existing = _normalize_quote_feedback_signal(payload.get("quote_feedback_signal"))
    if existing:
        return existing
    return _build_quote_feedback_signal(payload)


def _normalize_quote_outcome(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        return {}
    normalized: dict[str, str] = {}
    for key in ("code", "label", "status", "result_stage", "next_target_code", "next_target_label"):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


def _build_quote_outcome(payload: dict[str, Any]) -> dict[str, str]:
    post_quote_stage = _post_quote_stage(payload)
    next_best_action = payload.get("next_best_action") or _derive_next_best_action(payload)
    stage_code = str(post_quote_stage.get("code", "")).strip()
    outcome_map = {
        "reference_quote_pending_confirmation": ("waiting_confirmation", "参考报价待确认", "reference_quote"),
        "formal_quote_waiting_reply": ("waiting_reply", "正式报价待回复", "formal_quote"),
        "formal_quote_waiting_budget_feedback": ("comparing", "正式报价进入预算比较", "formal_quote"),
        "formal_quote_waiting_finish_feedback": ("comparing", "正式报价进入效果比较", "formal_quote"),
        "formal_quote_waiting_storage_feedback": ("comparing", "正式报价进入收纳比较", "formal_quote"),
        "formal_quote_waiting_layout_feedback": ("comparing", "正式报价进入布局比较", "formal_quote"),
        "formal_quote_waiting_material_feedback": ("comparing", "正式报价进入材质比较", "formal_quote"),
    }
    code, label, result_stage = outcome_map.get(
        stage_code,
        (
            "waiting_confirmation" if payload.get("reference") else "waiting_reply",
            str(post_quote_stage.get("label", "")).strip() or ("参考报价待确认" if payload.get("reference") else "正式报价待回复"),
            "reference_quote" if payload.get("reference") else "formal_quote",
        ),
    )
    followthrough_code = str(next_best_action.get("followthrough_action_code", "")).strip()
    next_target_map = {
        "lock_formal_quote": ("formal_confirmation", "锁正式报价"),
        "schedule_store_visit": ("booked_visit", "约到店确认"),
        "request_design_deepening": ("deepen_request", "转深化/出图"),
        "confirm_layout_deepening": ("deepen_request", "转深化确认布局"),
        "confirm_material_and_deepen": ("deepen_request", "确认材质后深化"),
        "schedule_store_or_design_followup": ("general_followup", "约沟通推进"),
    }
    next_target_code, next_target_label = next_target_map.get(
        followthrough_code,
        ("general_followup", str(next_best_action.get("followthrough_action_label", "")).strip() or "继续跟进"),
    )
    return {
        "code": code,
        "label": label,
        "status": "active",
        "result_stage": result_stage,
        "next_target_code": next_target_code,
        "next_target_label": next_target_label,
    }


def _quote_outcome(payload: dict[str, Any]) -> dict[str, str]:
    existing = _normalize_quote_outcome(payload.get("quote_outcome"))
    if existing:
        return existing
    return _build_quote_outcome(payload)


def _build_consultant_handoff_plan(payload: dict[str, Any]) -> dict[str, Any]:
    priority = _customer_priority(payload)
    priority_label = _consultant_priority_label(priority)
    follow_up_hint = _consultant_follow_up_hint(priority)
    action_hint = _consultant_action_hint(priority)
    compare_hint = _consultant_compare_hint(priority)
    if not priority or not priority_label:
        return {}

    plan = {
        "priority": priority,
        "priority_label": priority_label,
        "follow_up_hint": follow_up_hint,
        "action_code": _consultant_action_code(priority),
        "action_hint": action_hint,
        "compare_code": _consultant_compare_code(priority),
        "compare_hint": compare_hint,
        "compare_version_title": _consultant_compare_version_title(priority),
        "compare_variable_summary": _consultant_compare_variable_summary(priority),
    }
    compare_variables = _consultant_compare_variables(priority)
    if compare_variables:
        plan["compare_variables"] = compare_variables
    keep_fixed_fields = _consultant_keep_fixed_fields(priority)
    if keep_fixed_fields:
        plan["keep_fixed_fields"] = keep_fixed_fields
    handoff_focus_note_parts = [f"客户当前更在意{priority_label}，接力时建议优先顺着这个重点往下收。"]
    if action_hint:
        handoff_focus_note_parts.append(action_hint)
    if compare_hint:
        handoff_focus_note_parts.append(compare_hint)
    compare_variable_summary = str(plan.get("compare_variable_summary", "")).strip()
    if compare_variable_summary:
        handoff_focus_note_parts.append(f"建议对比变量：{compare_variable_summary}")
    plan["handoff_focus_note"] = " ".join(part for part in handoff_focus_note_parts if part).strip()
    return {key: value for key, value in plan.items() if value}


def _consultant_handoff_plan(payload: dict[str, Any]) -> dict[str, Any]:
    existing = _normalize_consultant_handoff_plan(payload.get("consultant_handoff_plan"))
    if existing:
        return existing
    return _build_consultant_handoff_plan(payload)


def _consultant_action_outline_lines(payload: dict[str, Any], *, limit: int = 3) -> list[str]:
    lines: list[str] = []
    for index, entry in enumerate(_consultant_action_queue(payload)[:limit], start=1):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        text = str(entry.get("text", "")).strip()
        if not title or not text:
            continue
        try:
            rank = int(entry.get("rank"))
        except (TypeError, ValueError):
            rank = index
        prefix = "建议先做" if bool(entry.get("recommended")) else f"第 {rank} 步"
        lines.append(f"{prefix}：{title}。{text}")
    return lines


def _build_consultant_action_compact_summary(payload: dict[str, Any], *, limit: int = 3) -> str:
    parts: list[str] = []
    for index, entry in enumerate(_consultant_action_queue(payload)[:limit], start=1):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        if not title:
            continue
        try:
            rank = int(entry.get("rank"))
        except (TypeError, ValueError):
            rank = index
        parts.append(f"{rank}. {title}")
    if not parts:
        return ""
    return f"动作排序：{'；'.join(parts)}。"


def _augment_consultant_internal_summary(summary: str, payload: dict[str, Any]) -> str:
    plan = _consultant_handoff_plan(payload)
    priority_label = str(plan.get("priority_label", "")).strip()
    follow_up_hint = str(plan.get("follow_up_hint", "")).strip()
    action_hint = str(plan.get("action_hint", "")).strip()
    compare_hint = str(plan.get("compare_hint", "")).strip()
    compare_variable_summary = str(plan.get("compare_variable_summary", "")).strip()
    action_outline_lines = _consultant_action_outline_lines(payload)
    if not priority_label or not follow_up_hint:
        return summary
    prefix_lines = [f"客户当前更在意：{priority_label}", follow_up_hint]
    if action_hint:
        prefix_lines.append(action_hint)
    if compare_hint:
        prefix_lines.append(compare_hint)
    if compare_variable_summary:
        prefix_lines.append(f"建议对比变量：{compare_variable_summary}")
    if action_outline_lines:
        prefix_lines.append("动作排序：")
        prefix_lines.extend(action_outline_lines)
    prefix = "\n".join(prefix_lines)
    if prefix in summary:
        return summary
    return f"{prefix}\n\n{summary}".strip()


def _build_handoff_focus_note(payload: dict[str, Any]) -> str:
    return str(_consultant_handoff_plan(payload).get("handoff_focus_note", "")).strip()


def _derive_scenario_summary(payload: dict[str, Any]) -> str:
    combined = _combined_quote_text(payload)
    priority = _customer_priority(payload)
    if priority == "budget":
        return "适合先把主体功能和预算框架先锁住，再逐步看哪些细节值得升级。"
    if priority == "aesthetics":
        return "适合先把整体效果、门型层次和材质气质先定下来。"
    if priority == "storage":
        return "适合先把收纳容量和内部结构先定下来。"
    if priority == "space_efficiency":
        return "适合先把空间利用率和布局效率先定下来。"
    if priority == "eco_material":
        return "适合先把材质边界和使用感受先锁定。"
    if any(keyword in combined for keyword in ("儿童房", "儿童床", "半高床", "高架床", "错层床", "上下床")):
        return "适合先把儿童房的睡眠、收纳和动线一起定下来。"
    if any(keyword in combined for keyword in ("衣柜", "书柜", "玄关柜", "餐边柜", "电视柜", "柜体")):
        return "适合先把整面收纳结构和常用功能先定下来。"
    if "床" in combined:
        return "适合先把睡眠结构、尺寸和材质先锁定。"
    return "适合先按当前需求把结构和预算框架先定下来。"


def _derive_budget_adjustment_suggestions(payload: dict[str, Any]) -> list[str]:
    combined = _combined_quote_text(payload)
    priority = _customer_priority(payload)
    suggestions: list[str] = []
    if priority == "budget":
        suggestions.append("如果你现在最在意预算，我会先建议保留主体柜体和核心收纳，再看门型、材质层次和附加项哪些可以后置。")
    if any(keyword in combined for keyword in ("超深", "超常规进深")):
        suggestions.append("如果你想先把预算往下收，优先把超常规进深收回常规范围，通常比改整体长度更直接。")
    if any(keyword in combined for keyword in ("纹理连续", "岩板", "双面门", "抽屉", "灯带", "操作空区")):
        suggestions.append("如果先控预算，优先把纹理连续、专项材质或附加配置拆开看，先锁主体结构更稳。")
    suggestions.append("如果你想先把预算往下收，通常优先从门型、材质或附加项收一档，比直接改整体尺寸更容易控价。")
    suggestions.append("如果现在主要是做功课，也可以先保留这版结构方案，等门型或配置细化后再更新。")

    unique: list[str] = []
    seen: set[str] = set()
    for suggestion in suggestions:
        if suggestion not in seen:
            seen.add(suggestion)
            unique.append(suggestion)
    return unique[:3]


def _derive_upgrade_suggestion(payload: dict[str, Any]) -> str:
    combined = _combined_quote_text(payload)
    priority = _customer_priority(payload)
    if priority == "budget":
        return "如果后面预算有余量，再优先升级门型层次、材质质感或局部细节，会比一开始整套拉高更稳。"
    if priority == "aesthetics":
        return "如果你更看重整体效果，可优先升级门型层次、材质质感和局部连续纹理。"
    if priority == "storage":
        return "如果你更看重收纳效率，可优先升级内部结构和高频使用区的配置。"
    if any(keyword in combined for keyword in ("衣柜", "书柜", "玄关柜", "餐边柜", "电视柜")):
        return "如果你更想把效果往上提，可优先看门型层次、材质升级或局部连续纹理，不一定要整套重做。"
    if "床" in combined:
        return "如果你更想把效果往上提，可优先看围栏/梯体做法、材质层次或局部功能升级。"
    return "如果你更想把效果往上提，可优先升级材质层次、细节做法或局部配置。"


def _derive_option_set(payload: dict[str, Any]) -> list[dict[str, str]]:
    budget_suggestions = _derive_budget_adjustment_suggestions(payload)
    priority = _customer_priority(payload)
    if priority == "budget":
        return [
            {
                "level": "recommended",
                "title": "预算优先方案",
                "description": "先按当前真实报价锁主体结构，适合先把预算和核心功能稳住。",
            },
            {
                "level": "budget_friendly",
                "title": "主体先落地",
                "description": budget_suggestions[0].replace("主体柜体", "主体结构"),
            },
            {
                "level": "upgraded",
                "title": "预算有余量再升级",
                "description": _derive_upgrade_suggestion(payload),
            },
        ]
    if priority == "aesthetics":
        return [
            {
                "level": "recommended",
                "title": "效果优先方案",
                "description": "先按当前真实报价锁整体风格方向，适合继续细化门型层次和材质气质。",
            },
            {
                "level": "budget_friendly",
                "title": "效果不降太多的收法",
                "description": "如果要先控预算，优先少动整体比例和主体风格，只收附加层次和局部效果项。",
            },
            {
                "level": "upgraded",
                "title": "细节效果升级版",
                "description": _derive_upgrade_suggestion(payload),
            },
        ]
    if priority == "storage":
        return [
            {
                "level": "recommended",
                "title": "收纳优先方案",
                "description": "先按当前真实报价锁核心容量和高频使用区，适合继续细化内部结构。",
            },
            {
                "level": "budget_friendly",
                "title": "高频收纳先保留",
                "description": "如果先控预算，优先保留真正高频使用的收纳结构，弱化低频附加配置。",
            },
            {
                "level": "upgraded",
                "title": "内部结构升级版",
                "description": _derive_upgrade_suggestion(payload),
            },
        ]
    return [
        {
            "level": "recommended",
            "title": "当前确认方案",
            "description": "按当前尺寸、材质和做法继续深化，适合直接往下沟通。",
        },
        {
            "level": "budget_friendly",
            "title": "预算收一档",
            "description": budget_suggestions[0],
        },
        {
            "level": "upgraded",
            "title": "效果升级版",
            "description": _derive_upgrade_suggestion(payload),
        },
    ]


def _derive_next_best_action(payload: dict[str, Any]) -> dict[str, str]:
    priority = _customer_priority(payload)
    compare_plan = _compare_plan(payload)
    version_title = str(compare_plan.get("version_title", "")).strip() or "方案对比版"
    if payload.get("reference"):
        return {
            "code": "confirm_key_fields",
            "title": "先补关键条件，再转正式报价",
            "text": "下一步先把影响价格的关键条件补齐；补齐后直接从当前参考版转正式报价版，如果你愿意，这版也可以先保留做预算参考。",
            "card_text": "先补关键条件；补齐后转正式报价。",
            "primary_action_code": "confirm_key_fields",
            "primary_action_label": "补关键条件",
            "secondary_action_code": "upgrade_to_formal_quote",
            "secondary_action_label": "转正式报价",
            "followthrough_action_code": "lock_formal_quote",
            "followthrough_action_label": "锁正式报价",
            "followthrough_text": "关键条件补齐并确认无误后，下一步就直接锁正式报价，再往下推进。",
            "handoff_hint": "先确认影响价格的关键条件，补齐后直接切到正式报价版。",
        }

    action_map = {
        "budget": {
            "title": "先发当前版，再补预算对比",
            "text": f"下一步建议先发当前正式版锁住结果；如果客户继续压预算，再补一版{version_title}。",
            "card_text": f"先发当前版；如果客户继续压预算，再补一版{version_title}。",
            "secondary_action_code": "send_current_then_budget_compare",
            "secondary_action_label": f"补{version_title}",
            "followthrough_action_code": "schedule_store_visit",
            "followthrough_action_label": "约到店确认",
            "followthrough_text": "如果客户对当前区间接受，下一步优先约到店或约设计沟通，把预算边界和取舍一次收清。",
            "handoff_hint": "先把当前正式版发出去；客户继续压预算时，再做预算收一档对比。",
        },
        "aesthetics": {
            "title": "先发当前版，再补效果升级对比",
            "text": f"下一步建议先发当前正式版；如果客户想看更高一级效果，再补一版{version_title}。",
            "card_text": f"先发当前版；如果客户想看更高一级效果，再补一版{version_title}。",
            "secondary_action_code": "send_current_then_finish_upgrade_compare",
            "secondary_action_label": f"补{version_title}",
            "followthrough_action_code": "request_design_deepening",
            "followthrough_action_label": "转深化/出图",
            "followthrough_text": "如果客户认可方向，下一步优先转深化或出图前确认，把门型、材质和关键细节一次锁清。",
            "handoff_hint": "先把当前正式版发出去；客户想看效果升级时，再对比门型和材质表达。",
        },
        "storage": {
            "title": "先发当前版，再补收纳优化对比",
            "text": f"下一步建议先发当前正式版；如果客户想继续细化收纳，再补一版{version_title}。",
            "card_text": f"先发当前版；如果客户想继续细化收纳，再补一版{version_title}。",
            "secondary_action_code": "send_current_then_storage_compare",
            "secondary_action_label": f"补{version_title}",
            "followthrough_action_code": "confirm_layout_deepening",
            "followthrough_action_label": "转深化确认布局",
            "followthrough_text": "如果客户认可方向，下一步优先转深化确认布局和内部结构，再往下锁细节。",
            "handoff_hint": "先把当前正式版发出去；客户继续问收纳时，再对比内部结构优化版。",
        },
        "space_efficiency": {
            "title": "先发当前版，再补布局优化对比",
            "text": f"下一步建议先发当前正式版；如果客户想继续优化布局，再补一版{version_title}。",
            "card_text": f"先发当前版；如果客户想继续优化布局，再补一版{version_title}。",
            "secondary_action_code": "send_current_then_layout_compare",
            "secondary_action_label": f"补{version_title}",
            "followthrough_action_code": "confirm_layout_deepening",
            "followthrough_action_label": "转深化确认布局",
            "followthrough_text": "如果客户认可方向，下一步优先转深化确认布局和关键尺寸，再往下锁细节。",
            "handoff_hint": "先把当前正式版发出去；客户继续问空间利用时，再对比布局优化版。",
        },
        "eco_material": {
            "title": "先发当前版，再补材质替代对比",
            "text": f"下一步建议先发当前正式版；如果客户想继续比较材质边界，再补一版{version_title}。",
            "card_text": f"先发当前版；如果客户想继续比较材质边界，再补一版{version_title}。",
            "secondary_action_code": "send_current_then_material_compare",
            "secondary_action_label": f"补{version_title}",
            "followthrough_action_code": "confirm_material_and_deepen",
            "followthrough_action_label": "确认材质再深化",
            "followthrough_text": "如果客户认可方向，下一步优先确认材质边界和样式，再转深化或出图。",
            "handoff_hint": "先把当前正式版发出去；客户继续问材质边界时，再对比材质替代版。",
        },
    }

    selected = action_map.get(priority)
    if selected:
        return {
            "code": "compare_or_generate_card",
            "title": selected["title"],
            "text": selected["text"],
            "card_text": selected["card_text"],
            "primary_action_code": "send_current_quote",
            "primary_action_label": "先发当前版",
            "secondary_action_code": selected["secondary_action_code"],
            "secondary_action_label": selected["secondary_action_label"],
            "followthrough_action_code": selected["followthrough_action_code"],
            "followthrough_action_label": selected["followthrough_action_label"],
            "followthrough_text": selected["followthrough_text"],
            "handoff_hint": selected["handoff_hint"],
        }

    return {
        "code": "compare_or_generate_card",
        "title": "先发当前版，再看是否补对比",
        "text": f"下一步建议先发当前正式版；如客户还想继续比较，可以生成报价卡，或再补一版{version_title}。",
        "card_text": f"先发当前版；如需要，再生成报价卡或补一版{version_title}。",
        "primary_action_code": "send_current_quote",
        "primary_action_label": "先发当前版",
        "secondary_action_code": "offer_compare_version",
        "secondary_action_label": f"补{version_title}",
        "followthrough_action_code": "schedule_store_or_design_followup",
        "followthrough_action_label": "约沟通推进",
        "followthrough_text": "如果客户接受当前方向，下一步优先约一次沟通，把是否对比、到店还是转深化一次定下来。",
        "handoff_hint": "先把当前正式版发出去；如果客户还想继续比较，再补对比版或直接发报价卡。",
    }


def _derive_decision_risk_points(payload: dict[str, Any]) -> list[str]:
    risk_points = [
        "这次报价基于已确认的尺寸、材质和结构；其中任一项变化，价格都会同步更新。",
    ]
    if payload.get("reference"):
        risk_points.append("当前仍属于参考阶段，等关键条件补齐后，才能锁正式报价。")
    else:
        risk_points.append("如果后续增加灯带、抽屉、特殊门型、专项材质或超常规进深，价格需要按新条件重算。")
    safe_notes = _customer_safe_notes(payload)
    if safe_notes:
        risk_points.append(f"当前补充条件：{'；'.join(safe_notes[:2])}")
    return risk_points[:3]


def enrich_conversion_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(payload)
    if "quote_confidence" not in enriched:
        enriched["quote_confidence"] = "medium" if enriched.get("reference") else "high"
    if "quote_stage" not in enriched:
        enriched["quote_stage"] = "reference_quote_ready" if enriched.get("reference") else "formal_quote_ready"
    if "conversion_intent_level" not in enriched:
        enriched["conversion_intent_level"] = "medium" if enriched.get("reference") else "high"
    if "scenario_summary" not in enriched:
        enriched["scenario_summary"] = _derive_scenario_summary(enriched)
    if "budget_adjustment_suggestions" not in enriched:
        enriched["budget_adjustment_suggestions"] = _derive_budget_adjustment_suggestions(enriched)
    if "option_set" not in enriched:
        enriched["option_set"] = _derive_option_set(enriched)
    if "next_best_action" not in enriched:
        enriched["next_best_action"] = _derive_next_best_action(enriched)
    if "decision_risk_points" not in enriched:
        enriched["decision_risk_points"] = _derive_decision_risk_points(enriched)
    if "consultant_handoff_plan" not in enriched:
        enriched["consultant_handoff_plan"] = _build_consultant_handoff_plan(enriched)
    if "compare_plan" not in enriched:
        enriched["compare_plan"] = _build_compare_plan(enriched)
    if "follow_up_script_set" not in enriched:
        enriched["follow_up_script_set"] = _build_follow_up_script_set(enriched)
    if "post_quote_stage" not in enriched:
        enriched["post_quote_stage"] = _derive_post_quote_stage(enriched)
    if "quote_version_summary" not in enriched:
        enriched["quote_version_summary"] = _build_quote_version_summary(enriched)
    if "quote_version_actions" not in enriched:
        enriched["quote_version_actions"] = _build_quote_version_actions(enriched)
    if "objection_playbook" not in enriched:
        enriched["objection_playbook"] = _build_objection_playbook(enriched)
    if "consultant_quick_actions" not in enriched:
        enriched["consultant_quick_actions"] = _build_consultant_quick_actions(enriched)
    if "consultant_action_queue" not in enriched:
        enriched["consultant_action_queue"] = _build_consultant_action_queue(enriched)
    if "consultant_workbench" not in enriched:
        enriched["consultant_workbench"] = _build_consultant_workbench(enriched)
    if "quote_followup_state" not in enriched:
        enriched["quote_followup_state"] = _build_quote_followup_state(enriched)
    if "quote_feedback_signal" not in enriched:
        enriched["quote_feedback_signal"] = _build_quote_feedback_signal(enriched)
    if "quote_outcome" not in enriched:
        enriched["quote_outcome"] = _build_quote_outcome(enriched)
    return enriched


def render_customer_simple(payload: dict[str, Any]) -> str:
    items = payload["items"]
    multiple = len(items) > 1
    total_label = "参考总价（仅供参考）" if payload.get("reference") else "正式报价"
    total_value = str(payload.get("total", "")).strip()
    if not total_value:
        raise SystemExit("Payload.total is required")

    lines = [
        "这次我先按你现在给到的条件，给你一个参考报价。" if payload.get("reference") else "这次可以正式报价，我先把结果给你。",
    ]
    for index, item in enumerate(items):
        title = str(formalize_text(str(item.get("product", "")).strip()) or "").strip()
        confirmed = str(formalize_text(str(item.get("confirmed", "")).strip()) or "").strip()
        pricing_method = str(formalize_text(str(item.get("pricing_method", "")).strip()) or "").strip()
        subtotal = str(item.get("subtotal", "")).strip()
        if not title or not confirmed or not pricing_method or not subtotal:
            raise SystemExit(f"Item {index + 1} is missing required fields for customer output")

        label = f"产品{index + 1}" if multiple else "产品"
        lines.append(f"{label}：{title}")
        lines.append(f"已确认：{confirmed}")
        lines.append(f"这次{pricing_method if pricing_method.startswith('按') else f'按{pricing_method}'}。")
        if multiple:
            lines.append(f"小计：{subtotal}")

    lines.append(f"{total_label}：{total_value}")
    lines.append(f"适合场景：{str(payload.get('scenario_summary') or '先按当前需求把结构和预算框架先定下来。').strip()}")
    lines.append("关键前提：先按目前已经确认的尺寸、材质和做法计算。")
    lines.append("这次报价依据：先按目前已经确认的尺寸、材质和做法计算。")
    if _customer_priority(payload) == "budget":
        lines.append("这次我会先按更省预算的路径帮你看，优先保留真正影响使用的主体结构。")
    elif _customer_priority(payload) == "aesthetics":
        lines.append("这次我会先按效果优先的路径帮你看，优先保留更影响整体观感的做法。")
    elif _customer_priority(payload) == "storage":
        lines.append("这次我会先按收纳优先的路径帮你看，优先保留真正影响容量和使用效率的结构。")
    safe_notes = _customer_safe_notes(payload)
    if safe_notes:
        lines.append(f"补充：{'；'.join(safe_notes)}")
    budget_suggestions = payload.get("budget_adjustment_suggestions") or []
    if budget_suggestions:
        lines.append(f"如果你想先把预算往下收：{str(budget_suggestions[0]).strip()}")
    option_set = payload.get("option_set") or []
    upgraded_option = next(
        (entry for entry in option_set if isinstance(entry, dict) and str(entry.get("level", "")).strip() == "upgraded"),
        None,
    )
    if upgraded_option:
        lines.append(f"如果你更想把效果往上提：{str(upgraded_option.get('description', '')).strip()}")
    next_best_action = payload.get("next_best_action") or {}
    next_text = str(next_best_action.get("text", "")).strip()
    lines.append(f"下一步：{next_text or ('等关键条件补齐后，我再给你正式报价。' if payload.get('reference') else '如果后面尺寸、门型、结构或附加项还有调整，我再按新条件更新。')}")
    rendered = "\n".join(lines)
    if any(phrase in rendered for phrase in INTERNAL_PROCESS_PHRASES):
        raise SystemExit("Rendered customer output leaks internal process")
    return rendered


def build_customer_card_payload(payload: dict[str, Any]) -> dict[str, Any]:
    quote_card_payload = {
        "items": [],
        "total": str(payload.get("total", "")).strip(),
        "quote_confidence": str(payload.get("quote_confidence", "")).strip(),
        "quote_stage": str(payload.get("quote_stage", "")).strip(),
        "conversion_intent_level": str(payload.get("conversion_intent_level", "")).strip(),
        "scenario_summary": str(payload.get("scenario_summary", "")).strip(),
        "budget_adjustment_suggestions": [str(entry).strip() for entry in (payload.get("budget_adjustment_suggestions") or []) if str(entry).strip()],
        "option_set": [entry for entry in (payload.get("option_set") or []) if isinstance(entry, dict)],
        "decision_risk_points": [str(entry).strip() for entry in (payload.get("decision_risk_points") or []) if str(entry).strip()],
    }
    if payload.get("reference"):
        quote_card_payload["reference"] = True
    next_best_action = payload.get("next_best_action")
    if isinstance(next_best_action, dict) and next_best_action:
        quote_card_payload["next_best_action"] = next_best_action
    for item in payload.get("items", []):
        quote_card_payload["items"].append(
            {
                "product": item.get("product", ""),
                "confirmed": item.get("confirmed", ""),
                "pricing_method": item.get("pricing_method", ""),
                "calculation_steps": [str(step) for step in (item.get("calculation_steps") or [])[:2]],
                "subtotal": item.get("subtotal", ""),
            }
        )
    safe_notes = _customer_safe_notes(payload)
    if safe_notes:
        quote_card_payload["note"] = "；".join(safe_notes)
    return quote_card_payload


def item_lines(item: dict[str, Any], index: int, multiple: bool) -> list[str]:
    title = str(formalize_text(str(item.get("product", "")).strip()) or "").strip()
    confirmed = str(formalize_text(str(item.get("confirmed", "")).strip()) or "").strip()
    pricing_method = str(formalize_text(str(item.get("pricing_method", "")).strip()) or "").strip()
    subtotal = str(item.get("subtotal", "")).strip()
    steps = [str(formalize_text(str(step).strip()) or "").strip() for step in (item.get("calculation_steps") or [])]
    addendum_adjustments = [
        str(formalize_text(str(step).strip()) or "").strip() for step in (item.get("addendum_adjustments") or [])
    ]
    decisions = item.get("addendum_decisions") or {}
    structured_adjustments = [
        f"追加规则：{str(formalize_text(str(entry.get('title', '')).strip()) or '').strip()}；{str(formalize_text(str(entry.get('detail', '')).strip()) or '').strip()}".strip("；")
        for entry in decisions.get("adjustments", [])
    ]
    structured_constraints = [
        f"追加限制：{str(formalize_text(str(entry.get('title', '')).strip()) or '').strip()}；{str(formalize_text(str(entry.get('detail', '')).strip()) or '').strip()}".strip("；")
        for entry in decisions.get("constraints", [])
    ]
    structured_follow_ups = [
        f"追加确认：{str(formalize_text(str(entry.get('question', '')).strip()) or '').strip()}；{str(formalize_text(str(entry.get('detail', '')).strip()) or '').strip()}".strip("；")
        for entry in decisions.get("follow_up_questions", [])
    ]
    rendered_addendum_adjustments = addendum_adjustments if not decisions else []
    merged_steps = [
        step
        for step in [
            *steps,
            *rendered_addendum_adjustments,
            *structured_adjustments,
            *structured_constraints,
            *structured_follow_ups,
        ]
        if step
    ]
    if not title or not confirmed or not pricing_method or not subtotal or not merged_steps:
        raise SystemExit(
            f"Item {index + 1} is missing required fields: product, confirmed, pricing_method, calculation_steps, subtotal"
        )

    label = f"产品{index + 1}" if multiple else "产品"
    lines = [
        f"{label}：{title}",
        f"已确认：{confirmed}",
        f"这次{pricing_method if pricing_method.startswith('按') else f'按{pricing_method}'}。",
        "计算过程：",
    ]
    for step in merged_steps:
        lines.append(f"- {str(step).strip()}")
    lines.append(f"小计：{subtotal}")
    return lines


def render(payload: dict[str, Any]) -> str:
    items = payload["items"]
    multiple = len(items) > 1
    lines: list[str] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SystemExit(f"Item {index + 1} must be an object")
        if lines:
            lines.append("")
        lines.extend(item_lines(item, index, multiple))

    lines.append("")
    total_label = "参考总价（仅供参考）" if payload.get("reference") else "正式报价"
    total_value = str(payload.get("total", "")).strip()
    if not total_value:
        raise SystemExit("Payload.total is required")
    lines.append(f"{total_label}：{total_value}")

    note = str(formalize_text(str(payload.get("note", "")).strip()) or "").strip()
    addendum_notes = [str(formalize_text(str(note_item).strip()) or "").strip() for note_item in (payload.get("addendum_notes") or [])]
    merged_notes = [entry for entry in [note, *addendum_notes] if entry]
    if merged_notes:
        lines.append(f"补充：{'；'.join(merged_notes)}")

    rendered = "\n".join(lines)
    contract = validate_output_contract(rendered, reference=bool(payload.get("reference")))
    if not contract["passed"]:
        failed = [name for name, result in contract["assertions"].items() if not result["passed"]]
        raise SystemExit(f"Rendered quote violates output contract: {', '.join(failed)}")
    return rendered


def render_for_output_profile(
    payload: dict[str, Any],
    *,
    audience_role: str | None = None,
    output_profile: str | None = None,
) -> dict[str, Any]:
    payload = enrich_conversion_metadata(payload)
    resolved_role = _normalize_role(audience_role or str(payload.get("audience_role", "")).strip())
    resolved_profile = _resolve_output_profile(resolved_role, output_profile or str(payload.get("output_profile", "")).strip())

    internal_summary_input = str(payload.get("internal_summary", "")).strip()
    customer_forward_input = str(payload.get("customer_forward_text", "")).strip()

    if resolved_profile == "customer_simple":
        reply_text = customer_forward_input or render_customer_simple(payload)
        internal_summary = internal_summary_input
        customer_forward_text = reply_text
    elif resolved_profile == "designer_full":
        reply_text = internal_summary_input or render(payload)
        internal_summary = reply_text
        customer_forward_text = customer_forward_input
    elif resolved_profile == "consultant_dual":
        internal_summary = _augment_consultant_internal_summary(internal_summary_input or render(payload), payload)
        customer_forward_text = customer_forward_input or render_customer_simple(payload)
        reply_text = customer_forward_text
    else:
        reply_text = render(payload)
        internal_summary = internal_summary_input
        customer_forward_text = customer_forward_input

    prepared_payload = copy.deepcopy(payload)
    if resolved_role:
        prepared_payload["audience_role"] = resolved_role
    if resolved_profile != "legacy":
        prepared_payload["output_profile"] = resolved_profile
    if internal_summary:
        prepared_payload["internal_summary"] = internal_summary
    if customer_forward_text:
        prepared_payload["customer_forward_text"] = customer_forward_text

    quote_card_payload = None
    if resolved_profile in {"customer_simple", "consultant_dual"}:
        quote_card_payload = build_customer_card_payload(payload)
        prepared_payload["quote_card_payload"] = quote_card_payload

    return {
        "audience_role": resolved_role,
        "output_profile": resolved_profile,
        "reply_text": reply_text,
        "internal_summary": internal_summary,
        "customer_forward_text": customer_forward_text,
        "prepared_payload": prepared_payload,
        "quote_card_payload": quote_card_payload,
    }


def render_with_quote_card_follow_up(
    payload: dict[str, Any],
    *,
    context_json: str | None = None,
    channel: str | None = None,
    bundle_root: Path = DEFAULT_BUNDLE_ROOT,
    audience_role: str | None = None,
    output_profile: str | None = None,
    flow_state_root: Path = quote_flow_state.DEFAULT_FLOW_STATE_ROOT,
) -> str:
    render_bundle = render_for_output_profile(
        payload,
        audience_role=audience_role,
        output_profile=output_profile,
    )
    prepared_payload = render_bundle["prepared_payload"]
    reply_text = render_bundle["reply_text"]
    eligible_for_card = is_bundle_eligible(prepared_payload)

    if context_json and channel:
        context = resolve_conversation_context(context_json, channel=channel)
        if eligible_for_card:
            bundle = build_quote_result_bundle(
                prepared_payload=prepared_payload,
                reply_text=reply_text,
                conversation_id=context["conversation_id"],
            )
            store_latest_quote_result_bundle(bundle, cache_root=bundle_root)

        confirmed_items = [
            {
                "product": str(item.get("product", "")).strip(),
                "confirmed": str(item.get("confirmed", "")).strip(),
            }
            for item in prepared_payload.get("items", [])
            if isinstance(item, dict)
        ]
        product_names = "、".join(item["product"] for item in confirmed_items[:3] if item["product"]) or "当前报价"
        quote_kind = "reference" if prepared_payload.get("reference") else "formal"
        quote_flow_state.merge_quote_flow_state(
            context["conversation_id"],
            updates={
                "audience_role": render_bundle["audience_role"] or "customer",
                "confirmed_fields": {"items": confirmed_items},
                "missing_fields": list(prepared_payload.get("missing_fields", [])),
                "active_route": str(
                    prepared_payload.get("pricing_route", "") or prepared_payload.get("route", "") or ""
                ).strip(),
                "last_quote_kind": quote_kind,
                "last_formal_payload": prepared_payload if quote_kind == "formal" else {},
                "internal_summary": render_bundle["internal_summary"],
                "customer_forward_text": render_bundle["customer_forward_text"],
                "handoff_summary": " ".join(
                    entry
                    for entry in [
                        f"{product_names} 当前已生成{'参考' if quote_kind == 'reference' else '正式'}报价。",
                        _build_handoff_focus_note(prepared_payload),
                        _build_consultant_action_compact_summary(prepared_payload),
                        str((prepared_payload.get("quote_version_summary") or {}).get("version_transition_note", "")).strip(),
                        str((prepared_payload.get("quote_version_actions") or {}).get("next_version_offer_action", "")).strip(),
                        str((prepared_payload.get('next_best_action') or {}).get('text', '')).strip(),
                    ]
                    if str(entry).strip()
                ).strip(),
                "quote_confidence": str(prepared_payload.get("quote_confidence", "")).strip(),
                "quote_stage": str(prepared_payload.get("quote_stage", "")).strip(),
                "option_set": prepared_payload.get("option_set") or [],
                "budget_adjustment_suggestions": prepared_payload.get("budget_adjustment_suggestions") or [],
                "next_best_action": prepared_payload.get("next_best_action") or {},
                "decision_risk_points": prepared_payload.get("decision_risk_points") or [],
                "conversion_intent_level": str(prepared_payload.get("conversion_intent_level", "")).strip(),
                "consultant_handoff_plan": prepared_payload.get("consultant_handoff_plan") or {},
                "compare_plan": prepared_payload.get("compare_plan") or {},
                "follow_up_script_set": prepared_payload.get("follow_up_script_set") or {},
                "consultant_quick_actions": prepared_payload.get("consultant_quick_actions") or [],
                "consultant_action_queue": prepared_payload.get("consultant_action_queue") or [],
                "consultant_workbench": prepared_payload.get("consultant_workbench") or {},
                "quote_followup_state": prepared_payload.get("quote_followup_state") or {},
                "quote_feedback_signal": prepared_payload.get("quote_feedback_signal") or {},
                "quote_outcome": prepared_payload.get("quote_outcome") or {},
                "post_quote_stage": prepared_payload.get("post_quote_stage") or {},
                "quote_version_summary": prepared_payload.get("quote_version_summary") or {},
                "quote_version_actions": prepared_payload.get("quote_version_actions") or {},
                "objection_playbook": prepared_payload.get("objection_playbook") or {},
            },
            cache_root=flow_state_root,
        )

    return append_quote_card_prompt(reply_text, eligible_for_card=eligible_for_card)


def main() -> None:
    parser = argparse.ArgumentParser(description="Format Liangqin quote reply")
    parser.add_argument("--input-json", help="Quote payload JSON. If omitted, read from stdin.")
    parser.add_argument(
        "--addenda-root",
        default=str(Path(__file__).resolve().parent.parent / "references" / "addenda"),
        help="Directory containing active addendum layers.",
    )
    parser.add_argument("--disable-addenda", action="store_true", help="Skip applying addendum layers before rendering.")
    parser.add_argument("--context-json", help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", help="Current OpenClaw channel id, such as feishu or dingtalk-connector.")
    parser.add_argument("--audience-role", choices=["customer", "designer", "consultant"], help="Audience role.")
    parser.add_argument(
        "--output-profile",
        choices=["customer_simple", "designer_full", "consultant_dual"],
        help="Quote output profile.",
    )
    parser.add_argument(
        "--bundle-root",
        default=str(DEFAULT_BUNDLE_ROOT),
        help="Directory used to cache the latest quote result bundle for each conversation.",
    )
    parser.add_argument(
        "--flow-state-root",
        default=str(quote_flow_state.DEFAULT_FLOW_STATE_ROOT),
        help="Directory used to persist quote flow state for each conversation.",
    )
    args = parser.parse_args()

    raw = args.input_json if args.input_json is not None else sys.stdin.read()
    if not raw.strip():
        raise SystemExit("Quote payload is required")

    payload = load_payload(raw)
    payload = prepare_payload(
        payload,
        addenda_root=Path(args.addenda_root).expanduser().resolve(),
        disable_addenda=args.disable_addenda,
    )
    print(
        render_with_quote_card_follow_up(
            payload,
            context_json=args.context_json,
            channel=args.channel,
            bundle_root=Path(args.bundle_root).expanduser().resolve(),
            audience_role=args.audience_role,
            output_profile=args.output_profile,
            flow_state_root=Path(args.flow_state_root).expanduser().resolve(),
        )
    )


if __name__ == "__main__":
    main()
