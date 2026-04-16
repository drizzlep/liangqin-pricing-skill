from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from batch_runtime import ensure_dir, read_json, write_json


LEARNING_VERSION = 1
DEFAULT_EVIDENCE_ORDER = ["native_preview", "ocr_markdown", "ocr_preview", "ocr_unknown"]


def build_template_profile(
    *,
    job: Any,
    normalized_fields_payload: dict[str, Any],
    review_analysis: dict[str, Any],
    runtime_root: Path,
) -> dict[str, Any]:
    fingerprint = build_template_fingerprint(job=job, normalized_fields_payload=normalized_fields_payload)
    template_id = f"tpl-{fingerprint[:8]}"
    profile_path = _template_profile_path(runtime_root, template_id)
    profile = read_json(profile_path) if profile_path.exists() else _new_profile(template_id=template_id, fingerprint=fingerprint)

    profile["template_fingerprint"] = fingerprint
    profile["template_lookup_fingerprint"] = build_template_lookup_fingerprint(job=job)
    profile["learning_version"] = LEARNING_VERSION
    profile["observed_job_count"] = int(profile.get("observed_job_count") or 0) + 1
    profile["last_job_id"] = str(job.job_id)
    profile["last_seen_at"] = _now_iso()
    profile["trusted_sections"] = _extract_trusted_sections(job)
    profile["preferred_evidence_order"] = list(profile.get("preferred_evidence_order") or DEFAULT_EVIDENCE_ORDER)
    profile["field_aliases"] = _merge_field_aliases(
        profile.get("field_aliases") or {},
        normalized_fields_payload.get("fields") or {},
    )
    profile["common_conflict_rules"] = _merge_common_conflict_rules(
        existing_rules=profile.get("common_conflict_rules") or [],
        issues=review_analysis.get("issues") or [],
    )
    profile["observed_issue_breakdown"] = _merge_issue_breakdown(
        existing=profile.get("observed_issue_breakdown") or {},
        issues=review_analysis.get("issues") or [],
    )
    profile["trust_score"] = _compute_trust_score(profile)

    write_json(profile_path, profile)
    return profile


def build_template_fingerprint(*, job: Any, normalized_fields_payload: dict[str, Any]) -> str:
    payload = _build_lookup_fingerprint_payload(job)
    payload["normalized_field_names"] = sorted((normalized_fields_payload.get("fields") or {}).keys())
    digest = hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:16]


def build_template_lookup_fingerprint(*, job: Any) -> str:
    payload = _build_lookup_fingerprint_payload(job)
    digest = hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:16]


def find_template_profile(*, job: Any, runtime_root: Path) -> dict[str, Any] | None:
    template_dir = runtime_root / "templates"
    if not template_dir.exists():
        return None
    lookup_fingerprint = build_template_lookup_fingerprint(job=job)
    best_profile: dict[str, Any] | None = None
    best_score = -1.0
    for path in sorted(template_dir.glob("*.json")):
        profile = read_json(path)
        if str(profile.get("template_lookup_fingerprint") or "").strip() != lookup_fingerprint:
            continue
        score = float(profile.get("trust_score") or 0.0)
        if score > best_score:
            best_profile = profile
            best_score = score
    return best_profile


def _build_lookup_fingerprint_payload(job: Any) -> dict[str, Any]:
    asset_shapes = [
        {
            "extension": str(getattr(asset, "extension", "") or ""),
            "media_kind": str(getattr(asset, "media_kind", "") or ""),
            "role_hint": str(getattr(asset, "role_hint", "") or ""),
        }
        for asset in getattr(job, "assets", []) or []
    ]
    label_tokens = sorted(_extract_label_tokens(getattr(asset, "text_preview", "")) for asset in getattr(job, "assets", []) or [])
    return {
        "asset_shapes": asset_shapes,
        "label_tokens": [token for group in label_tokens for token in group],
    }


def apply_review_feedback(feedback_payload: dict[str, Any], *, runtime_root: Path) -> dict[str, Any]:
    template_id = str(feedback_payload.get("template_id") or "").strip()
    if not template_id:
        raise ValueError("review feedback requires template_id")

    profile_path = _template_profile_path(runtime_root, template_id)
    if not profile_path.exists():
        raise FileNotFoundError(f"template profile not found: {template_id}")

    profile = read_json(profile_path)
    profile["feedback_count"] = int(profile.get("feedback_count") or 0) + 1
    profile["last_feedback_at"] = _now_iso()
    human_decision = str(feedback_payload.get("human_decision") or "").strip()
    if human_decision:
        decision_breakdown = dict(profile.get("human_decision_breakdown") or {})
        decision_breakdown[human_decision] = int(decision_breakdown.get(human_decision) or 0) + 1
        profile["human_decision_breakdown"] = decision_breakdown

    corrected_fields = feedback_payload.get("corrected_fields") or {}
    if isinstance(corrected_fields, dict):
        field_aliases = profile.get("field_aliases") or {}
        for field_name, value in corrected_fields.items():
            entry = dict(field_aliases.get(field_name) or {"labels": [], "confirmed_values": []})
            confirmed_values = list(entry.get("confirmed_values") or [])
            text = str(value or "").strip()
            if text and text not in confirmed_values:
                confirmed_values.append(text)
            entry["confirmed_values"] = confirmed_values
            field_aliases[field_name] = entry
        profile["field_aliases"] = field_aliases

    issue_code = str(feedback_payload.get("issue_code") or "").strip()
    root_cause = str(feedback_payload.get("confirmed_root_cause") or "").strip()
    if issue_code:
        feedback_issue_breakdown = dict(profile.get("feedback_issue_breakdown") or {})
        issue_entry = dict(feedback_issue_breakdown.get(issue_code) or {})
        issue_entry["feedback_count"] = int(issue_entry.get("feedback_count") or 0) + 1
        if human_decision:
            counter_key = f"{human_decision}_count"
            issue_entry[counter_key] = int(issue_entry.get(counter_key) or 0) + 1
        if root_cause:
            issue_entry["last_root_cause"] = root_cause
        feedback_issue_breakdown[issue_code] = issue_entry
        profile["feedback_issue_breakdown"] = feedback_issue_breakdown

    if issue_code and root_cause:
        rules = list(profile.get("common_conflict_rules") or [])
        matched = False
        for item in rules:
            if str(item.get("issue_code") or "").strip() == issue_code and str(item.get("root_cause") or "").strip() == root_cause:
                item["count"] = int(item.get("count") or 0) + 1
                matched = True
                break
        if not matched:
            rules.append({"issue_code": issue_code, "count": 1, "root_cause": root_cause})
        rules.sort(
            key=lambda item: (
                -int(item.get("count") or 0),
                0 if str(item.get("root_cause") or "").strip() else 1,
                str(item.get("issue_code") or ""),
            )
        )
        profile["common_conflict_rules"] = rules

    profile["trust_score"] = _compute_trust_score(profile)
    write_json(profile_path, profile)
    return profile


def _new_profile(*, template_id: str, fingerprint: str) -> dict[str, Any]:
    return {
        "template_id": template_id,
        "template_fingerprint": fingerprint,
        "template_lookup_fingerprint": "",
        "trusted_sections": [],
        "field_aliases": {},
        "common_conflict_rules": [],
        "observed_issue_breakdown": {},
        "feedback_issue_breakdown": {},
        "preferred_evidence_order": list(DEFAULT_EVIDENCE_ORDER),
        "learning_version": LEARNING_VERSION,
        "observed_job_count": 0,
        "feedback_count": 0,
        "human_decision_breakdown": {},
        "trust_score": 0.5,
        "created_at": _now_iso(),
    }


def _template_profile_path(runtime_root: Path, template_id: str) -> Path:
    return ensure_dir(runtime_root / "templates") / f"{template_id}.json"


def _extract_label_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"(^|[\n\s])([^\n：:]{1,16})[:：]", str(text or "")):
        token = str(match.group(2) or "").strip()
        if token:
            tokens.append(token)
    return sorted(set(tokens))


def _extract_trusted_sections(job: Any) -> list[str]:
    sections = []
    for asset in getattr(job, "assets", []) or []:
        preview = str(getattr(asset, "text_preview", "") or "").strip()
        if not preview:
            continue
        sections.append(f"{getattr(asset, 'role_hint', '')}:{getattr(asset, 'text_extract_method', '') or 'unknown'}")
    return sorted(set(sections))


def _merge_field_aliases(existing: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    merged = {key: dict(value) for key, value in existing.items()}
    for field_name, payload in fields.items():
        entry = dict(merged.get(field_name) or {"labels": [], "confirmed_values": []})
        labels = set(entry.get("labels") or [])
        for ref in list((payload or {}).get("evidence_refs") or []):
            snippet = str(ref.get("snippet") or "").strip()
            label = _label_from_snippet(snippet)
            if label:
                labels.add(label)
        entry["labels"] = sorted(labels)
        entry["confirmed_values"] = list(entry.get("confirmed_values") or [])
        merged[field_name] = entry
    return merged


def _merge_common_conflict_rules(*, existing_rules: list[dict[str, Any]], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[tuple[str, str]] = Counter()
    merged_rules: list[dict[str, Any]] = []
    for item in existing_rules:
        key = (str(item.get("issue_code") or "").strip(), str(item.get("root_cause") or "").strip())
        counter[key] += int(item.get("count") or 0)
    for issue in issues:
        issue_code = str(issue.get("issue_code") or "").strip()
        if not issue_code:
            continue
        counter[(issue_code, str(issue.get("root_cause") or "").strip())] += 1
    for (issue_code, root_cause), count in counter.most_common():
        merged_rules.append(
            {
                "issue_code": issue_code,
                "count": count,
                "root_cause": root_cause,
            }
        )
    return merged_rules


def _merge_issue_breakdown(*, existing: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, int]:
    breakdown = {str(key): int(value or 0) for key, value in existing.items() if str(key).strip()}
    for issue in issues:
        issue_code = str(issue.get("issue_code") or "").strip()
        if not issue_code:
            continue
        breakdown[issue_code] = breakdown.get(issue_code, 0) + 1
    return breakdown


def _label_from_snippet(snippet: str) -> str:
    match = re.match(r"\s*([^：:]{1,20})[:：]", str(snippet or ""))
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _compute_trust_score(profile: dict[str, Any]) -> float:
    observed = max(int(profile.get("observed_job_count") or 0), 1)
    feedback = int(profile.get("feedback_count") or 0)
    decision_breakdown = profile.get("human_decision_breakdown") or {}
    positive_feedback = (
        int(decision_breakdown.get("reviewed") or 0)
        + int(decision_breakdown.get("confirmed") or 0)
    )
    false_positive_feedback = int(decision_breakdown.get("false_positive") or 0)
    conflict_weight = sum(int(item.get("count") or 0) for item in profile.get("common_conflict_rules") or [])
    score = (
        0.5
        + min(feedback, 5) * 0.02
        + min(positive_feedback, 5) * 0.03
        - min(false_positive_feedback, 5) * 0.05
        - min(conflict_weight / observed, 4) * 0.04
    )
    return round(max(0.0, min(0.99, score)), 2)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
