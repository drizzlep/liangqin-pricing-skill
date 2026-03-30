#!/usr/bin/env python3
"""Build an independent addendum layer from one designer rule source."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


_RUNTIME_BUILDER_MODULE: Any | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a standalone designer addendum layer without mutating base rules.")
    parser.add_argument("--rules-source", required=True, help="Path to the addendum source file (docx/pdf).")
    parser.add_argument("--layer-id", required=True, help="Stable layer id, for example designer-manual-a.")
    parser.add_argument("--layer-name", required=True, help="Human readable layer name.")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parent.parent), help="Skill root directory.")
    parser.add_argument("--status", default="ACTIVE", choices=["ACTIVE", "PAUSED"], help="Layer status.")
    return parser.parse_args(argv)


def slugify_layer_id(layer_id: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in layer_id).strip("-")
    return slug or "designer-addendum"


def run_step(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def relativize_path(path: Path, *, manifest_dir: Path) -> str:
    try:
        return os.path.relpath(path, start=manifest_dir)
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)


def build_seed_knowledge_layer(*, layer_id: str, layer_name: str) -> dict[str, Any]:
    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "entries": [],
    }


def build_status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "unresolved")).strip() or "unresolved"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def normalize_publish_text(text: Any) -> str:
    return re.sub(r"[\W_]+", "", str(text)).lower()


def normalize_sentence(text: Any) -> str:
    return " ".join(str(text).replace("\r", "\n").split())


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def resolve_publish_target(status: str) -> str:
    normalized = str(status).strip().lower()
    if normalized == "runtime_hard_rule" or normalized.startswith("runtime_"):
        return "runtime"
    if normalized == "knowledge_ready" or normalized.startswith("knowledge_"):
        return "knowledge"
    if normalized in {"covered_existing", "excluded_background"}:
        return "none"
    return "manual_review"


def build_publish_target_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        target = str(entry.get("publish_target", "manual_review")).strip() or "manual_review"
        counts[target] = counts.get(target, 0) + 1
    return dict(sorted(counts.items()))


def finalize_coverage_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        normalized_entry = dict(entry)
        normalized_entry["publish_target"] = resolve_publish_target(str(normalized_entry.get("status", "")))
        entries.append(normalized_entry)

    finalized = dict(payload)
    finalized["entries"] = entries
    finalized["entry_count"] = len(entries)
    finalized["status_counts"] = build_status_counts(entries)
    finalized["publish_target_counts"] = build_publish_target_counts(entries)
    return finalized


def entry_matches_override(entry: dict[str, Any], override: dict[str, Any]) -> bool:
    page = override.get("page")
    if page is not None and entry.get("page") != page:
        return False
    current_status = str(override.get("current_status", "")).strip()
    if current_status and str(entry.get("status", "")).strip() != current_status:
        return False
    domain = str(override.get("domain", "")).strip()
    if domain and str(entry.get("domain", "")).strip() != domain:
        return False
    topic = str(entry.get("topic", ""))
    topic_exact = str(override.get("topic", "")).strip()
    if topic_exact and topic != topic_exact:
        return False
    topic_contains = str(override.get("topic_contains", "")).strip()
    if topic_contains and topic_contains not in topic:
        return False
    summary = str(entry.get("summary", ""))
    summary_contains = str(override.get("summary_contains", "")).strip()
    if summary_contains and summary_contains not in summary:
        return False
    return True


def apply_coverage_ledger_overrides(payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    entries = [dict(entry) for entry in payload.get("entries", []) if isinstance(entry, dict)]

    for override in overrides.get("overrides", []):
        if not isinstance(override, dict):
            continue
        update_fields = {
            key: value
            for key, value in override.items()
            if key not in {"page", "current_status", "domain", "topic", "topic_contains", "summary_contains"} and value is not None
        }
        if not update_fields:
            continue
        for entry in entries:
            if entry_matches_override(entry, override):
                entry.update(update_fields)

    for extra_entry in overrides.get("append_entries", []):
        if isinstance(extra_entry, dict):
            entries.append(dict(extra_entry))

    payload = dict(payload)
    payload["entries"] = entries
    payload["entry_count"] = len(entries)
    payload["status_counts"] = build_status_counts(entries)
    return payload


def publish_text_matches(left: Any, right: Any) -> bool:
    left_normalized = normalize_publish_text(left)
    right_normalized = normalize_publish_text(right)
    if len(left_normalized) < 4 or len(right_normalized) < 4:
        return False
    shorter, longer = sorted((left_normalized, right_normalized), key=len)
    return shorter in longer


def runtime_rule_matches_ledger_entry(rule: dict[str, Any], ledger_entry: dict[str, Any]) -> bool:
    rule_texts = [
        rule.get("title", ""),
        rule.get("normalized_rule", ""),
        rule.get("detail", ""),
        rule.get("source_heading", ""),
    ]
    ledger_texts = [
        ledger_entry.get("topic", ""),
        ledger_entry.get("summary", ""),
    ]
    return any(
        publish_text_matches(rule_text, ledger_text)
        for rule_text in rule_texts
        for ledger_text in ledger_texts
    )


def load_runtime_builder_module() -> Any:
    global _RUNTIME_BUILDER_MODULE
    if _RUNTIME_BUILDER_MODULE is not None:
        return _RUNTIME_BUILDER_MODULE

    builder_path = Path(__file__).resolve().parent / "build_addendum_runtime_rules.py"
    spec = importlib.util.spec_from_file_location("build_addendum_runtime_rules_for_overrides", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runtime builder helpers from {builder_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _RUNTIME_BUILDER_MODULE = module
    return module


def normalize_runtime_terms(values: Any) -> list[str]:
    terms: list[str] = []
    for value in values or []:
        cleaned = normalize_sentence(value).strip(" -—:：,.，。")
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
    return terms


def merge_runtime_terms(*groups: Any) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for term in normalize_runtime_terms(group):
            if term not in merged:
                merged.append(term)
    return merged


def normalize_runtime_rule(rule: dict[str, Any]) -> dict[str, Any]:
    builder = load_runtime_builder_module()

    normalized = dict(rule)
    domain = normalize_sentence(normalized.get("domain", "general")).strip() or "general"
    title = builder.strip_leading_marker(builder.normalize_text(str(normalized.get("title", "")))).strip() or "追加规则"
    detail = builder.clean_runtime_detail(str(normalized.get("detail", "")), domain)
    tags = normalize_runtime_terms(normalized.get("tags", []))
    response_kind = normalize_sentence(normalized.get("response_kind", "")).strip()
    combined_text = " ".join([title, detail, *tags])
    action_type = normalize_sentence(normalized.get("action_type", "")).strip() or builder.classify_action_type(
        combined_text,
        response_kind=response_kind,
    )

    existing_required_fields = normalize_runtime_terms(normalized.get("required_fields", []))
    inferred_required_fields = builder.infer_required_fields(" ".join([title, detail, *tags]))
    required_fields = merge_runtime_terms(existing_required_fields, inferred_required_fields)

    derived_specific, derived_generic = builder.split_match_terms(title, detail, tags, required_fields)
    existing_trigger_terms = normalize_runtime_terms(normalized.get("trigger_terms", []))
    promoted_specific_terms = [term for term in existing_trigger_terms if builder.is_specific_phrase(term)]
    promoted_generic_terms = [term for term in existing_trigger_terms if term not in promoted_specific_terms]
    match_terms_specific = merge_runtime_terms(normalized.get("match_terms_specific", []), derived_specific, promoted_specific_terms)
    match_terms_generic = merge_runtime_terms(normalized.get("match_terms_generic", []), derived_generic, promoted_generic_terms)
    trigger_terms = merge_runtime_terms(existing_trigger_terms, match_terms_specific, match_terms_generic)

    user_summary = normalize_sentence(normalized.get("user_summary", "")).strip() or builder.build_user_summary(
        title=title,
        detail=detail,
        action_type=action_type,
    )
    question_template = normalize_sentence(normalized.get("question_template", "")).strip() or builder.build_question_template(
        title=title,
        detail=detail,
        required_fields=required_fields,
        domain=domain,
    )
    evidence_level = normalize_sentence(normalized.get("evidence_level", "")).strip() or "hard_rule"

    normalized["page"] = int(normalized.get("page", 0) or 0)
    normalized["domain"] = domain
    normalized["action_type"] = action_type
    normalized["title"] = title
    normalized["detail"] = detail
    normalized["trigger_terms"] = trigger_terms
    normalized["match_terms_specific"] = match_terms_specific
    normalized["match_terms_generic"] = match_terms_generic
    normalized["required_fields"] = required_fields
    normalized["tags"] = tags
    normalized["source_heading"] = normalize_sentence(normalized.get("source_heading", "")).strip()
    normalized["normalized_rule"] = normalize_sentence(normalized.get("normalized_rule", "")).strip()
    normalized["response_kind"] = response_kind
    normalized["user_summary"] = user_summary
    normalized["question_template"] = question_template
    normalized["evidence_level"] = evidence_level
    return normalized


def build_published_runtime_rules(runtime_payload: dict[str, Any], coverage_ledger: dict[str, Any]) -> dict[str, Any]:
    rules = [dict(rule) for rule in runtime_payload.get("rules", []) if isinstance(rule, dict)]
    approved_entries = [
        entry
        for entry in coverage_ledger.get("entries", [])
        if isinstance(entry, dict) and str(entry.get("publish_target", "")) == "runtime"
    ]
    approved_by_page: dict[int, list[dict[str, Any]]] = {}
    rule_count_by_page: dict[int, int] = {}

    for entry in approved_entries:
        page = int(entry.get("page", 0) or 0)
        approved_by_page.setdefault(page, []).append(entry)
    for rule in rules:
        page = int(rule.get("page", 0) or 0)
        rule_count_by_page[page] = rule_count_by_page.get(page, 0) + 1

    published_rules: list[dict[str, Any]] = []
    for rule in rules:
        page = int(rule.get("page", 0) or 0)
        page_entries = approved_by_page.get(page, [])
        if not page_entries:
            continue
        if len(page_entries) == 1 and rule_count_by_page.get(page, 0) == 1:
            published_rules.append(rule)
            continue
        if any(runtime_rule_matches_ledger_entry(rule, ledger_entry) for ledger_entry in page_entries):
            published_rules.append(rule)

    published_payload = dict(runtime_payload)
    published_payload["rules"] = published_rules
    published_payload["rule_count"] = len(published_rules)
    return published_payload


def apply_runtime_rules_overrides(payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    replace_rules = overrides.get("replace_rules", [])
    if isinstance(replace_rules, list) and replace_rules:
        payload = dict(payload)
        payload["rules"] = [normalize_runtime_rule(dict(rule)) for rule in replace_rules if isinstance(rule, dict)]
        payload["rule_count"] = len(payload["rules"])
        return payload
    return payload


def extract_labeled_terms(summary: str) -> list[str]:
    match = re.search(r"识别标签[:：]\s*([^。；;]+)", summary)
    if not match:
        return []
    label_text = match.group(1)
    return [
        part.strip()
        for part in re.split(r"[，,、/]", label_text)
        if part.strip() and part.strip() != "待分类"
    ]


def clean_knowledge_summary(summary: Any, *, topic: str) -> str:
    text = normalize_sentence(summary)
    if not text:
        return topic
    if "提示：" in text:
        prefix, remainder = text.split("提示：", 1)
        if len(prefix) <= 20:
            text = remainder
    elif "提示:" in text:
        prefix, remainder = text.split("提示:", 1)
        if len(prefix) <= 20:
            text = remainder
    if "关键信息：" in text:
        text = text.split("关键信息：", 1)[1]
    elif "关键信息:" in text:
        text = text.split("关键信息:", 1)[1]

    segments: list[str] = []
    for raw_segment in re.split(r"[；;|]", text):
        segment = raw_segment.strip(" -—:：,.，。")
        if not segment:
            continue
        if "本段主要" in segment or "识别标签" in segment:
            continue
        if not contains_cjk(segment):
            continue
        if segment not in segments:
            segments.append(segment)

    if segments:
        return "；".join(segments[:3])
    return text or topic


def derive_knowledge_trigger_terms(entry: dict[str, Any], *, topic: str, answerable_summary: str) -> list[str]:
    candidates: list[str] = []

    def add(term: Any) -> None:
        normalized = normalize_sentence(term).strip(" -—:：,.，。")
        if not normalized or normalized in candidates:
            return
        if len(normalized) > 24 or not contains_cjk(normalized):
            return
        candidates.append(normalized)

    add(topic)
    for label in extract_labeled_terms(str(entry.get("summary", ""))):
        add(label)
    for chunk in re.split(r"[；;，,、/]", answerable_summary):
        add(chunk)
    return candidates


def build_knowledge_answer_lead(*, topic: str, answerable_summary: str, note: str, evidence_level: str) -> str:
    if evidence_level == "hard_rule":
        return ""
    combined = " ".join([topic, answerable_summary, note])
    if any(keyword in combined for keyword in ("下单", "图纸", "备注", "收费")):
        return "这页目前更适合作为下单和图纸备注提示来用，但还没到完全可程序化的程度。"
    if any(keyword in combined for keyword in ("安装", "底装", "侧装", "使用方式")):
        return "如果是问安装方式，这块目前能给到比较稳定的使用指引，但更适合作为知识层提示来理解。"
    if any(keyword in combined for keyword in ("结构", "节点", "凹槽", "内退", "复盘")):
        return "这块目前更适合作为结构复盘提示来理解。"
    if any(keyword in combined for keyword in ("系列", "型号", "几款", "区分")):
        return "如果是问这组怎么区分，目前能稳定确认到的是系列级别信息。"
    return "这块目前有比较明确的补充口径，但更适合作为知识层提示来理解。"


def build_knowledge_do_not_overclaim(*, note: str, evidence_level: str) -> str:
    normalized_note = normalize_sentence(note).strip()
    if evidence_level == "hard_rule":
        return normalized_note
    if normalized_note:
        return normalized_note
    return "目前只能作为提示理解，不能直接当成已经完全程序化的硬规则；没有明确证据的部分就直接说不知道。"


def normalize_knowledge_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    topic = normalize_sentence(normalized.get("topic", "")).strip()
    answerable_summary = normalize_sentence(normalized.get("answerable_summary", "")).strip()
    evidence_level = normalize_sentence(normalized.get("evidence_level", "high_confidence_review")).strip() or "high_confidence_review"
    note = normalize_sentence(normalized.get("do_not_overclaim", "")).strip()
    answer_lead = normalize_sentence(normalized.get("answer_lead", "")).strip()

    source_pages: list[int] = []
    for page in normalized.get("source_pages", []):
        try:
            parsed = int(page)
        except (TypeError, ValueError):
            continue
        if parsed not in source_pages:
            source_pages.append(parsed)

    trigger_terms: list[str] = []
    for term in normalized.get("trigger_terms", []):
        cleaned = normalize_sentence(term).strip(" -—:：,.，。")
        if cleaned and cleaned not in trigger_terms:
            trigger_terms.append(cleaned)

    normalized["topic"] = topic
    normalized["answerable_summary"] = answerable_summary or topic
    normalized["evidence_level"] = evidence_level
    normalized["source_pages"] = source_pages
    normalized["trigger_terms"] = trigger_terms
    normalized["answer_lead"] = answer_lead or build_knowledge_answer_lead(
        topic=topic,
        answerable_summary=normalized["answerable_summary"],
        note=note,
        evidence_level=evidence_level,
    )
    normalized["do_not_overclaim"] = build_knowledge_do_not_overclaim(note=note, evidence_level=evidence_level)
    return normalized


def build_knowledge_entry_from_ledger(entry: dict[str, Any]) -> dict[str, Any]:
    page = int(entry.get("page", 0) or 0)
    topic = normalize_sentence(entry.get("topic", "")).strip() or normalize_sentence(entry.get("summary", "")).strip()
    topic = topic or f"第{page}页追加说明"
    answerable_summary = clean_knowledge_summary(entry.get("summary", ""), topic=topic)
    evidence_level = "hard_rule" if "hard" in str(entry.get("status", "")).lower() else "high_confidence_review"
    knowledge_entry = {
        "topic": topic,
        "answerable_summary": answerable_summary,
        "evidence_level": evidence_level,
        "source_pages": [page] if page else [],
        "trigger_terms": derive_knowledge_trigger_terms(entry, topic=topic, answerable_summary=answerable_summary),
        "do_not_overclaim": normalize_sentence(entry.get("note", "")).strip(),
    }
    return normalize_knowledge_entry(knowledge_entry)


def knowledge_entry_matches_override(entry: dict[str, Any], override: dict[str, Any]) -> bool:
    page = override.get("page")
    if page is not None and page not in set(entry.get("source_pages", [])):
        return False
    current_evidence_level = str(override.get("current_evidence_level", "")).strip()
    if current_evidence_level and str(entry.get("evidence_level", "")).strip() != current_evidence_level:
        return False
    topic = str(entry.get("topic", ""))
    topic_exact = str(override.get("topic", "")).strip()
    if topic_exact and topic != topic_exact:
        return False
    topic_contains = str(override.get("topic_contains", "")).strip()
    if topic_contains and topic_contains not in topic:
        return False
    summary_contains = str(override.get("answerable_summary_contains", override.get("summary_contains", ""))).strip()
    if summary_contains and summary_contains not in str(entry.get("answerable_summary", "")):
        return False
    return True


def apply_knowledge_layer_overrides(payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    replace_entries = overrides.get("replace_entries", [])
    if isinstance(replace_entries, list) and replace_entries:
        payload = dict(payload)
        payload["entries"] = [normalize_knowledge_entry(dict(entry)) for entry in replace_entries if isinstance(entry, dict)]
        return payload

    entries = [normalize_knowledge_entry(dict(entry)) for entry in payload.get("entries", []) if isinstance(entry, dict)]

    for override in overrides.get("overrides", []):
        if not isinstance(override, dict):
            continue
        update_fields = {
            key: value
            for key, value in override.items()
            if key not in {"page", "current_evidence_level", "topic", "topic_contains", "answerable_summary_contains", "summary_contains"}
            and value is not None
        }
        if not update_fields:
            continue
        for entry in entries:
            if knowledge_entry_matches_override(entry, override):
                entry.update(update_fields)
                normalized_entry = normalize_knowledge_entry(entry)
                entry.clear()
                entry.update(normalized_entry)

    for extra_entry in overrides.get("append_entries", []):
        if isinstance(extra_entry, dict):
            entries.append(normalize_knowledge_entry(dict(extra_entry)))

    payload = dict(payload)
    payload["entries"] = entries
    return payload


def build_published_knowledge_layer(*, layer_id: str, layer_name: str, coverage_ledger: dict[str, Any]) -> dict[str, Any]:
    grouped_entries: dict[str, dict[str, Any]] = {}

    for entry in coverage_ledger.get("entries", []):
        if not isinstance(entry, dict) or str(entry.get("publish_target", "")) != "knowledge":
            continue
        knowledge_entry = build_knowledge_entry_from_ledger(entry)
        key = normalize_publish_text(knowledge_entry["topic"]) or normalize_publish_text(knowledge_entry["answerable_summary"])
        existing = grouped_entries.get(key)
        if existing is None:
            grouped_entries[key] = normalize_knowledge_entry(knowledge_entry)
            continue
        for page in knowledge_entry["source_pages"]:
            if page not in existing["source_pages"]:
                existing["source_pages"].append(page)
        for term in knowledge_entry["trigger_terms"]:
            if term not in existing["trigger_terms"]:
                existing["trigger_terms"].append(term)
        if len(knowledge_entry["answerable_summary"]) > len(existing["answerable_summary"]):
            existing["answerable_summary"] = knowledge_entry["answerable_summary"]
        if knowledge_entry["do_not_overclaim"] and not existing["do_not_overclaim"]:
            existing["do_not_overclaim"] = knowledge_entry["do_not_overclaim"]
        if knowledge_entry.get("answer_lead") and not existing.get("answer_lead"):
            existing["answer_lead"] = knowledge_entry["answer_lead"]

    entries = sorted(
        [normalize_knowledge_entry(entry) for entry in grouped_entries.values()],
        key=lambda item: (item["source_pages"][0] if item["source_pages"] else 0, str(item["topic"])),
    )
    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "entries": entries,
    }


def build_seed_coverage_ledger(
    *,
    layer_id: str,
    layer_name: str,
    index_path: Path,
    runtime_rules_path: Path,
    audit_csv_path: Path | None = None,
) -> dict[str, Any]:
    if audit_csv_path and audit_csv_path.exists():
        entries: list[dict[str, Any]] = []
        with audit_csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                pricing_relevant = str(row.get("pricing_relevant", "")).strip().lower() == "true"
                source_status = str(row.get("status", "")).strip()
                if source_status == "included_runtime":
                    status = "runtime_hard_rule"
                elif source_status == "excluded_non_pricing":
                    status = "excluded_background"
                else:
                    status = "unresolved"
                entries.append(
                    {
                        "page": int(row.get("page", "0") or 0),
                        "topic": str(row.get("clean_title", "")).strip() or str(row.get("heading", "")).strip(),
                        "status": status,
                        "domain": row.get("domain"),
                        "pricing_relevant": pricing_relevant,
                        "rule_type": row.get("rule_type"),
                        "summary": str(row.get("normalized_rule", "")).strip(),
                        "note": str(row.get("reason", "")).strip(),
                        "source": "pdf_coverage_audit",
                    }
                )

        return {
            "layer_id": layer_id,
            "layer_name": layer_name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "entry_count": len(entries),
            "status_counts": build_status_counts(entries),
            "entries": entries,
        }

    index_payload = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"entries": []}
    runtime_payload = json.loads(runtime_rules_path.read_text(encoding="utf-8")) if runtime_rules_path.exists() else {"rules": []}
    runtime_titles = {str(rule.get("title", "")).strip() for rule in runtime_payload.get("rules", []) if str(rule.get("title", "")).strip()}

    entries: list[dict[str, Any]] = []
    for entry in index_payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("clean_title", "")).strip()
        normalized_rule = str(entry.get("normalized_rule", "")).strip()
        pricing_relevant = bool(entry.get("pricing_relevant"))
        if title and title in runtime_titles:
            status = "runtime_hard_rule"
        elif pricing_relevant:
            status = "unresolved"
        else:
            status = "excluded_background"
        entries.append(
            {
                "page": entry.get("page"),
                "topic": title or str(entry.get("heading", "")).strip(),
                "status": status,
                "domain": entry.get("domain"),
                "summary": normalized_rule,
                "source": "rules_index_seed",
            }
        )

    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(entries),
        "status_counts": build_status_counts(entries),
        "entries": entries,
    }


def build_layer_manifest(
    *,
    layer_id: str,
    layer_name: str,
    source_file: Path,
    candidate_path: Path,
    index_path: Path,
    runtime_rules_path: Path,
    runtime_rules_overrides_path: Path | None,
    knowledge_layer_path: Path,
    knowledge_layer_overrides_path: Path | None,
    coverage_ledger_path: Path,
    coverage_ledger_overrides_path: Path | None,
    source_markdown_path: Path,
    drafts_dir: Path,
    manifest_dir: Path,
    status: str = "ACTIVE",
) -> dict[str, object]:
    drafts_manifest_path = drafts_dir / "manifest.json"
    drafts_manifest = {}
    if drafts_manifest_path.exists():
        drafts_manifest = json.loads(drafts_manifest_path.read_text(encoding="utf-8"))

    artifacts: dict[str, str] = {
        "rules_candidate_file": relativize_path(candidate_path, manifest_dir=manifest_dir),
        "rules_index_file": relativize_path(index_path, manifest_dir=manifest_dir),
        "runtime_rules_file": relativize_path(runtime_rules_path, manifest_dir=manifest_dir),
        "knowledge_layer_file": relativize_path(knowledge_layer_path, manifest_dir=manifest_dir),
        "coverage_ledger_file": relativize_path(coverage_ledger_path, manifest_dir=manifest_dir),
        "rules_source_markdown_file": relativize_path(source_markdown_path, manifest_dir=manifest_dir),
        "rules_drafts_dir": relativize_path(drafts_dir, manifest_dir=manifest_dir),
        "rules_drafts_manifest_file": relativize_path(drafts_manifest_path, manifest_dir=manifest_dir),
    }
    if runtime_rules_overrides_path and runtime_rules_overrides_path.exists():
        artifacts["runtime_rules_overrides_file"] = relativize_path(
            runtime_rules_overrides_path,
            manifest_dir=manifest_dir,
        )
    if knowledge_layer_overrides_path and knowledge_layer_overrides_path.exists():
        artifacts["knowledge_layer_overrides_file"] = relativize_path(
            knowledge_layer_overrides_path,
            manifest_dir=manifest_dir,
        )
    if coverage_ledger_overrides_path and coverage_ledger_overrides_path.exists():
        artifacts["coverage_ledger_overrides_file"] = relativize_path(
            coverage_ledger_overrides_path,
            manifest_dir=manifest_dir,
        )

    return {
        "layer_id": layer_id,
        "layer_name": layer_name,
        "status": status,
        "source_file": relativize_path(source_file, manifest_dir=manifest_dir),
        "mutates_base_rules": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "artifacts": artifacts,
        "draft_domains": drafts_manifest.get("domains", []),
    }


def write_manifest(output_dir: Path, manifest: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    temp_path = manifest_path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, manifest_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    scripts_dir = skill_dir / "scripts"
    addenda_root = skill_dir / "references" / "addenda"
    archived_root = skill_dir / "sources" / "archived" / "addenda"
    reports_root = skill_dir / "reports" / "addenda"

    layer_slug = slugify_layer_id(args.layer_id)
    source_path = Path(args.rules_source).expanduser().resolve()
    archived_dir = archived_root / layer_slug
    archived_dir.mkdir(parents=True, exist_ok=True)
    archived_source = archived_dir / source_path.name
    shutil.copy2(source_path, archived_source)

    reports_dir = reports_root / layer_slug
    reports_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = reports_dir / "rules-candidate.json"
    source_markdown_path = reports_dir / "rules-source.md"
    index_path = reports_dir / "rules-index.json"
    index_markdown_path = reports_dir / "rules-index.md"
    runtime_rules_path = reports_dir / "runtime-rules.json"
    runtime_rules_overrides_path = reports_dir / "runtime-rules-overrides.json"
    knowledge_layer_path = reports_dir / "knowledge-layer.json"
    knowledge_layer_overrides_path = reports_dir / "knowledge-layer-overrides.json"
    coverage_ledger_path = reports_dir / "coverage-ledger.json"
    coverage_ledger_overrides_path = reports_dir / "coverage-ledger-overrides.json"
    drafts_dir = reports_dir / "rules-drafts"

    run_step(
        [
            sys.executable,
            str(scripts_dir / "extract_rules_candidate.py"),
            "--input",
            str(source_path),
            "--output",
            str(candidate_path),
            "--markdown-output",
            str(source_markdown_path),
        ]
    )
    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_rules_index.py"),
            "--input",
            str(candidate_path),
            "--output",
            str(index_path),
            "--markdown-output",
            str(index_markdown_path),
        ]
    )
    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_addendum_runtime_rules.py"),
            "--input",
            str(index_path),
            "--output",
            str(runtime_rules_path),
            "--layer-id",
            args.layer_id,
            "--layer-name",
            args.layer_name,
        ]
    )
    run_step(
        [
            sys.executable,
            str(scripts_dir / "build_rules_drafts.py"),
            "--input",
            str(index_path),
            "--output-dir",
            str(drafts_dir),
        ]
    )

    raw_runtime_payload = json.loads(runtime_rules_path.read_text(encoding="utf-8")) if runtime_rules_path.exists() else {}
    coverage_ledger_payload = finalize_coverage_ledger(
        apply_coverage_ledger_overrides(
            build_seed_coverage_ledger(
                layer_id=args.layer_id,
                layer_name=args.layer_name,
                index_path=index_path,
                runtime_rules_path=runtime_rules_path,
                audit_csv_path=reports_dir / "pdf-coverage-audit.csv",
            ),
            json.loads((reports_dir / "coverage-ledger-overrides.json").read_text(encoding="utf-8"))
            if (reports_dir / "coverage-ledger-overrides.json").exists()
            else {},
        )
    )
    write_json(coverage_ledger_path, coverage_ledger_payload)
    write_json(
        runtime_rules_path,
        apply_runtime_rules_overrides(
            build_published_runtime_rules(raw_runtime_payload, coverage_ledger_payload),
            json.loads(runtime_rules_overrides_path.read_text(encoding="utf-8"))
            if runtime_rules_overrides_path.exists()
            else {},
        ),
    )
    write_json(
        knowledge_layer_path,
        apply_knowledge_layer_overrides(
            build_published_knowledge_layer(
                layer_id=args.layer_id,
                layer_name=args.layer_name,
                coverage_ledger=coverage_ledger_payload,
            ),
            json.loads(knowledge_layer_overrides_path.read_text(encoding="utf-8"))
            if knowledge_layer_overrides_path.exists()
            else {},
        ),
    )

    layer_dir = addenda_root / layer_slug
    manifest = build_layer_manifest(
        layer_id=args.layer_id,
        layer_name=args.layer_name,
        source_file=archived_source,
        candidate_path=candidate_path,
        index_path=index_path,
        runtime_rules_path=runtime_rules_path,
        runtime_rules_overrides_path=runtime_rules_overrides_path,
        knowledge_layer_path=knowledge_layer_path,
        knowledge_layer_overrides_path=knowledge_layer_overrides_path,
        coverage_ledger_path=coverage_ledger_path,
        coverage_ledger_overrides_path=coverage_ledger_overrides_path,
        source_markdown_path=source_markdown_path,
        drafts_dir=drafts_dir,
        manifest_dir=layer_dir,
        status=args.status,
    )
    write_manifest(layer_dir, manifest)

    print(f"Built addendum layer at {layer_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
