#!/usr/bin/env python3
"""Build domain-specific draft markdown files from a rules index."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


DOMAIN_CONFIG = {
    "cabinet": {
        "title": "柜体类规则草稿",
        "reference_hint": "references/current/rules-cabinet.md",
        "keywords": ["衣柜", "书柜", "玄关柜", "电视柜", "餐边柜"],
    },
    "bed": {
        "title": "床类规则草稿",
        "reference_hint": "references/current/rules-beds.md",
        "keywords": ["架式床", "箱体床", "儿童床", "榻榻米"],
    },
    "table": {
        "title": "桌类规则草稿",
        "reference_hint": "references/current/rules-tables.md",
        "keywords": ["餐桌", "书桌", "挂墙桌", "书桌柜"],
    },
    "accessory": {
        "title": "配件类规则草稿",
        "reference_hint": "references/current/rules-accessories.md",
        "keywords": ["拉手", "灯带", "开关", "轨道插座"],
    },
    "door_panel": {
        "title": "门板类规则草稿",
        "reference_hint": "references/current/rules-components.md",
        "keywords": ["拼框门", "平板门", "玻璃门", "格栅门"],
    },
    "material": {
        "title": "材质类规则草稿",
        "reference_hint": "references/current/rules-components.md",
        "keywords": ["木材", "材质", "黑胡桃", "樱桃木"],
    },
    "general": {
        "title": "通用规则草稿",
        "reference_hint": "references/current/rules-overview.md",
        "keywords": ["通用", "总则", "默认规则"],
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build domain draft markdown files from rules-index JSON.")
    parser.add_argument("--input", required=True, help="Path to rules-index JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory to write domain drafts.")
    return parser.parse_args(argv)


def normalize_entry(entry: dict[str, object]) -> dict[str, object]:
    return {
        "page": int(entry.get("page", 1)),
        "domain": str(entry.get("domain", "general")),
        "clean_title": str(entry.get("clean_title", "待人工复核规则")),
        "excerpt": str(entry.get("excerpt", "")),
        "rule_type": str(entry.get("rule_type", "narrative_rule")),
        "relevance_score": int(entry.get("relevance_score", 0)),
        "pricing_relevant": bool(entry.get("pricing_relevant", False)),
        "tags": [str(tag) for tag in entry.get("tags", [])],
    }


def build_domain_payload(index: dict[str, object], domain: str) -> dict[str, object]:
    config = DOMAIN_CONFIG[domain]
    entries = [
        normalize_entry(entry)
        for entry in index.get("entries", [])
        if isinstance(entry, dict) and entry.get("domain") == domain and entry.get("pricing_relevant")
    ]
    entries.sort(key=lambda item: (-item["relevance_score"], item["page"], item["clean_title"]))
    return {
        "domain": domain,
        "title": config["title"],
        "reference_hint": config["reference_hint"],
        "keywords": config["keywords"],
        "entry_count": len(entries),
        "entries": entries,
    }


def render_domain_markdown(payload: dict[str, object]) -> str:
    domain = str(payload["domain"])
    config = DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG["general"])
    lines = [
        f"# {payload.get('title', config['title'])}",
        "",
        f"- 参考现有规则文件：`{payload.get('reference_hint', config['reference_hint'])}`",
        f"- 高相关候选条目数：{payload['entry_count']}",
        f"- 适用关键词：{', '.join(payload.get('keywords', config['keywords']))}",
        "",
        "## 候选规则",
        "",
    ]
    entries = payload["entries"]
    if not entries:
        lines.append("暂无高相关候选条目。")
        lines.append("")
        return "\n".join(lines)

    for entry in entries:
        lines.extend(
            [
                f"### p{entry['page']} · {entry['clean_title']}",
                "",
                f"- rule_type: {entry['rule_type']}",
                f"- relevance_score: {entry['relevance_score']}",
                f"- tags: {', '.join(entry['tags'])}",
                "",
                entry["excerpt"],
                "",
            ]
        )
    return "\n".join(lines)


def build_manifest(payloads: list[dict[str, object]]) -> dict[str, object]:
    active = [payload for payload in payloads if payload["entry_count"] > 0]
    return {
        "domain_count": len(active),
        "domains": [
            {
                "domain": payload["domain"],
                "entry_count": payload["entry_count"],
                "reference_hint": payload["reference_hint"],
                "filename": f"rules-draft-{payload['domain']}.md",
            }
            for payload in active
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    index = json.loads(input_path.read_text(encoding="utf-8"))
    payloads = [build_domain_payload(index, domain) for domain in DOMAIN_CONFIG]

    for payload in payloads:
        if payload["entry_count"] == 0:
            continue
        output_path = output_dir / f"rules-draft-{payload['domain']}.md"
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        temp_path.write_text(render_domain_markdown(payload), encoding="utf-8")
        os.replace(temp_path, output_path)

    manifest = build_manifest(payloads)
    manifest_path = output_dir / "manifest.json"
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    with temp_manifest.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_manifest, manifest_path)

    print(f"Wrote {manifest['domain_count']} domain drafts to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
