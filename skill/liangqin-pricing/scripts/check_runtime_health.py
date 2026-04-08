#!/usr/bin/env python3
"""Diagnose whether the current Liangqin runtime install is complete and queryable."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the current Liangqin runtime install is complete.")
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parent.parent),
        help="Liangqin skill root directory to inspect.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["text", "json"],
        default="text",
        help="Render a human-readable report or raw JSON payload.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def inspect_runtime_health(skill_dir: Path) -> dict[str, Any]:
    resolved_skill_dir = skill_dir.expanduser().resolve()
    current_dir = resolved_skill_dir / "data" / "current"
    release_path = current_dir / "release.json"
    fallback_index_path = current_dir / "price-index.json"

    errors: list[str] = []
    warnings: list[str] = []
    recommended_actions: list[str] = []
    checks: list[dict[str, Any]] = []

    release_payload: dict[str, Any] | None = None
    price_index_payload: dict[str, Any] | None = None
    price_index_path = fallback_index_path

    if not resolved_skill_dir.exists():
        errors.append("skill 根目录不存在。")
        recommended_actions.append("确认另一个机器人实际加载的是哪份 liangqin-pricing 目录，再重新发布完整 skill。")

    checks.append(
        {
            "name": "skill_dir",
            "ok": resolved_skill_dir.exists(),
            "path": str(resolved_skill_dir),
            "detail": "skill 根目录存在" if resolved_skill_dir.exists() else "skill 根目录不存在",
        }
    )

    if release_path.exists():
        try:
            release_payload = _load_json(release_path)
        except Exception as exc:
            errors.append(f"release.json 读取失败：{exc}")
        else:
            configured_index_name = str(release_payload.get("price_index_file") or "price-index.json").strip() or "price-index.json"
            price_index_path = current_dir / configured_index_name
            if str(release_payload.get("status") or "").strip() != "active":
                warnings.append("当前 release 状态不是 active。")
    else:
        errors.append("缺少 data/current/release.json。")
        recommended_actions.append("先用 publish_skill.py 或 update_release.py 发布完整 skill，再让机器人加载。")

    checks.append(
        {
            "name": "release_json",
            "ok": release_payload is not None,
            "path": str(release_path),
            "detail": "release.json 可读取" if release_payload is not None else "release.json 缺失或损坏",
        }
    )

    if price_index_path.exists():
        try:
            price_index_payload = _load_json(price_index_path)
        except Exception as exc:
            errors.append(f"price-index.json 读取失败：{exc}")
        else:
            if not isinstance(price_index_payload.get("records"), list):
                errors.append("price-index.json 缺少 records[]。")
    else:
        errors.append(f"缺少价格索引文件：{price_index_path.name}")
        recommended_actions.append("这通常表示安装不完整，只同步了脚本但没有同步 data/current/price-index.json。")

    checks.append(
        {
            "name": "price_index",
            "ok": price_index_payload is not None and isinstance(price_index_payload.get("records"), list),
            "path": str(price_index_path),
            "detail": "价格索引可读取" if price_index_payload is not None and isinstance(price_index_payload.get("records"), list) else "价格索引缺失或损坏",
        }
    )

    records = price_index_payload.get("records", []) if isinstance(price_index_payload, dict) else []
    actual_record_count = len(records) if isinstance(records, list) else 0
    actual_queryable_count = sum(1 for record in records if isinstance(record, dict) and bool(record.get("is_queryable")))
    actual_price_count = sum(1 for record in records if isinstance(record, dict) and record.get("record_kind") == "price")

    if price_index_payload is not None and actual_record_count == 0:
        errors.append("price-index.json 已存在，但 records[] 为空。")
        recommended_actions.append("这不是正常运行状态，需要重新构建或重新发布当前版本数据。")
    elif price_index_payload is not None and actual_queryable_count == 0:
        errors.append("price-index.json 有内容，但没有任何可查询记录。")
        recommended_actions.append("这通常说明版本数据异常，建议重新运行 update_release.py 或重新发布 skill。")

    meta_record_count = price_index_payload.get("record_count") if isinstance(price_index_payload, dict) else None
    meta_queryable_count = price_index_payload.get("queryable_record_count") if isinstance(price_index_payload, dict) else None
    if isinstance(meta_record_count, int) and meta_record_count != actual_record_count:
        warnings.append(f"record_count 元数据与实际 records 数量不一致：{meta_record_count} != {actual_record_count}")
    if isinstance(meta_queryable_count, int) and meta_queryable_count != actual_queryable_count:
        warnings.append(
            f"queryable_record_count 元数据与实际可查询记录数不一致：{meta_queryable_count} != {actual_queryable_count}"
        )

    first_queryable = next(
        (
            {
                "product_code": str(record.get("product_code") or "").strip(),
                "name": str(record.get("name") or "").strip(),
                "pricing_mode": str(record.get("pricing_mode") or "").strip(),
            }
            for record in records
            if isinstance(record, dict) and bool(record.get("is_queryable"))
        ),
        None,
    )

    checks.append(
        {
            "name": "records_non_empty",
            "ok": actual_record_count > 0,
            "detail": f"records={actual_record_count}",
        }
    )
    checks.append(
        {
            "name": "queryable_records_non_empty",
            "ok": actual_queryable_count > 0,
            "detail": f"queryable_records={actual_queryable_count}",
        }
    )

    if not recommended_actions:
        recommended_actions.append("如果这里显示数据正常，但机器人仍说“价格索引为空”，优先排查它是否把“筛选没命中”误判成了“整份数据为空”。")

    status = "error" if errors else "ok"
    summary = (
        "当前运行环境数据完整，可正常用于报价。"
        if status == "ok"
        else "当前运行环境不完整或数据异常，机器人不应继续把它当成正常报价环境。"
    )

    return {
        "status": status,
        "summary": summary,
        "skill_dir": str(resolved_skill_dir),
        "current_dir": str(current_dir),
        "release_path": str(release_path),
        "price_index_path": str(price_index_path),
        "release": {
            "version": str((release_payload or {}).get("version") or "").strip(),
            "status": str((release_payload or {}).get("status") or "").strip(),
            "built_at": str((release_payload or {}).get("built_at") or "").strip(),
            "price_index_file": str((release_payload or {}).get("price_index_file") or "").strip(),
        },
        "counts": {
            "record_count_meta": meta_record_count,
            "record_count_actual": actual_record_count,
            "queryable_record_count_meta": meta_queryable_count,
            "queryable_record_count_actual": actual_queryable_count,
            "price_record_count_actual": actual_price_count,
        },
        "sample_queryable_record": first_queryable,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "recommended_actions": recommended_actions,
    }


def render_text_report(payload: dict[str, Any]) -> str:
    lines = [
        f"运行环境诊断：{payload['status']}",
        payload["summary"],
        f"skill_dir：{payload['skill_dir']}",
        f"当前版本：{payload['release'].get('version') or '未识别'}",
        f"版本状态：{payload['release'].get('status') or '未识别'}",
        f"价格索引：{payload['price_index_path']}",
        (
            "记录统计："
            f"records={payload['counts'].get('record_count_actual', 0)}，"
            f"queryable={payload['counts'].get('queryable_record_count_actual', 0)}，"
            f"price={payload['counts'].get('price_record_count_actual', 0)}"
        ),
    ]

    sample = payload.get("sample_queryable_record") or {}
    if sample:
        lines.append(
            "示例可查询记录："
            f"{sample.get('product_code') or '无编号'} / {sample.get('name') or '无名称'} / {sample.get('pricing_mode') or '未知模式'}"
        )

    if payload.get("warnings"):
        lines.append("警告：")
        lines.extend(f"- {item}" for item in payload["warnings"])

    if payload.get("errors"):
        lines.append("错误：")
        lines.extend(f"- {item}" for item in payload["errors"])

    if payload.get("recommended_actions"):
        lines.append("建议：")
        lines.extend(f"- {item}" for item in payload["recommended_actions"])

    if payload["status"] == "ok":
        lines.append("结论：如果另一个机器人仍说“当前版本没有价格数据”，更可能是它的筛选条件没命中，或把“没查到匹配记录”误判成了“整份数据为空”。")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = inspect_runtime_health(Path(args.skill_dir))
    if args.output_mode == "json":
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(render_text_report(payload))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
