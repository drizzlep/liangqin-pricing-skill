#!/usr/bin/env python3
"""Reusable first-turn reply templates for ordinary customer quote guidance."""

from __future__ import annotations

from typing import Any


GOAL_FIRST_PRODUCTS = {
    "书柜",
    "衣柜",
    "玄关柜",
    "餐边柜",
    "电视柜",
    "柜子",
    "家具",
}


def select_primary_question(customer_strategy: str, signals: dict[str, list[str]]) -> tuple[str, str]:
    if customer_strategy == "precise_need":
        if not signals.get("goal"):
            return ("customer.precise_need.goal", "你这个更偏向展示，还是更偏向收纳？")
        if not signals.get("space"):
            return ("customer.precise_need.space", "这套大概是放在哪个空间？比如次卧、儿童房、书房，还是玄关？")
        return ("customer.precise_need.size", "你如果方便的话，先告诉我大概要做多长，我就能继续帮你收口。")

    if customer_strategy == "renovation_browse":
        if not signals.get("space"):
            return ("customer.renovation_browse.space", "你现在最想先看哪个空间？比如儿童房、次卧、客厅，还是玄关？")
        if not signals.get("goal"):
            return ("customer.renovation_browse.goal", "你更想先解决收纳、睡觉，还是学习功能？")
        return ("customer.renovation_browse.intent", "你现在是先了解预算方向，还是已经准备近期定下来？")

    if not signals.get("goal"):
        return ("customer.guided_discovery.goal", "你现在最想优先解决收纳、睡觉、学习，还是空间利用？")
    if not signals.get("user"):
        return ("customer.guided_discovery.user", "这套主要是给谁用的？比如一个孩子、两个孩子，还是大人和孩子一起用？")
    if not signals.get("space"):
        return ("customer.guided_discovery.space", "这大概是哪个空间？比如儿童房、次卧，还是书房？")
    return ("customer.guided_discovery.reference", "如果你手上有户型图、照片，或者房间面积，我可以继续帮你收得更准一点。")


def _base_copy(customer_strategy: str, signals: dict[str, list[str]], turn_index: int) -> tuple[str, str]:
    if customer_strategy == "precise_need":
        product = (signals.get("product") or ["这类定制家具"])[0]
        if turn_index > 1:
            return (
                f"收到，我继续按{product}方向帮你往下收。",
                "这样我就不重复问前面已经确认过的方向，继续补最关键的条件就行。",
            )
        if product in GOAL_FIRST_PRODUCTS:
            return (
                f"可以，先按{product}方向帮你看。",
                f"{product}这一步我先不急着区分目录成品还是定制，先确认你更偏展示、收纳，还是和其他功能做一体化，这对后面怎么报价更关键。",
            )
        return (
            f"可以，先按{product}方向帮你看。",
            f"{product}常见会分展示、收纳，或者和其他功能做一体化，价格差异会比较大。",
        )

    if customer_strategy == "renovation_browse":
        if turn_index > 1:
            return (
                "收到，我继续按装修前期的思路帮你收口。",
                "我会优先把空间、用途和预算方向一点点补齐，不会一下子让你报很多参数。",
            )
        return (
            "可以，我先按装修前期帮你梳理。",
            "这类需求通常会先从空间和用途判断方向，再慢慢收口到具体做法和预算。",
        )

    if turn_index > 1:
        return (
            "明白了，我继续顺着这个方向帮你缩小范围。",
            "我们先把最关键的信息一项项补齐，再慢慢逼近更准的方案和价格。",
        )

    return (
        "没问题，这种情况很常见，我先不急着帮你定具体家具。",
        "我们可以先从你想解决的问题入手，再收敛成更合适的方案方向。",
    )


def _range_hint(response_stage: str) -> str:
    if response_stage == "proposal_range":
        return "按你现在给到的信息，后面可以先收成一个比较宽的预算区间，再逐步逼近正式报价。"
    if response_stage == "reference_quote":
        return "你现在的信息已经接近可以给参考报价了，我再补一个关键条件就能继续往下推。"
    return ""


def render_customer_guidance_text(
    *,
    customer_strategy: str,
    response_stage: str,
    signals: dict[str, list[str]],
    next_question: str,
    turn_index: int = 1,
) -> str:
    guidance, solution = _base_copy(customer_strategy, signals, turn_index)
    lines = [guidance, solution]
    range_hint = _range_hint(response_stage)
    if range_hint:
        lines.append(range_hint)
    lines.append(f"下一步我先只确认一个问题：{next_question}")
    return "\n".join(lines)


def summarize_customer_guidance_template(
    *,
    customer_strategy: str,
    response_stage: str,
    signals: dict[str, list[str]],
    turn_index: int = 1,
) -> dict[str, Any]:
    question_code, next_question = select_primary_question(customer_strategy, signals)
    return {
        "question_code": question_code,
        "next_question": next_question,
        "reply_text": render_customer_guidance_text(
            customer_strategy=customer_strategy,
            response_stage=response_stage,
            signals=signals,
            next_question=next_question,
            turn_index=turn_index,
        ),
    }
