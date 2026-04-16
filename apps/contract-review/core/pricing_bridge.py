from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


DEFAULT_CONFIDENCE_THRESHOLD = 0.85
CHILD_BED_OCR_CONFIDENCE_CAP = 0.84
CHILD_BED_KEYWORDS = ("儿童床", "上下床", "子母床", "高架床", "半高床", "错层床")

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "category": ("category", "product_category", "sheet", "product_type"),
    "series": ("series", "product_name", "product_series", "style", "model_name"),
    "material": ("material", "wood_material", "main_material"),
    "length": ("length", "cabinet_length", "table_length", "bed_length"),
    "depth": ("depth", "cabinet_depth", "table_depth"),
    "height": ("height", "cabinet_height", "table_height"),
    "width": ("width", "bed_width", "mattress_width", "table_width"),
    "quote_kind": ("quote_kind", "pricing_kind", "quote_mode"),
    "has_door": ("has_door", "door_presence"),
    "door_type": ("door_type", "door_style", "door_model"),
    "shape": ("shape", "cabinet_shape", "special_shape"),
    "bed_form": ("bed_form", "bed_type", "child_bed_form"),
    "access_style": ("access_style", "ladder_style", "access_mode"),
    "lower_bed_type": ("lower_bed_type", "lower_structure"),
    "guardrail_style": ("guardrail_style", "rail_style"),
    "guardrail_length": ("guardrail_length",),
    "guardrail_height": ("guardrail_height",),
    "access_height": ("access_height", "ladder_height"),
    "stair_width": ("stair_width",),
    "stair_depth": ("stair_depth",),
    "underbed_cabinet_mode": ("underbed_cabinet_mode", "underbed_mode"),
    "front_cabinet_length": ("front_cabinet_length",),
    "front_cabinet_height": ("front_cabinet_height",),
    "front_cabinet_depth": ("front_cabinet_depth",),
    "front_cabinet_mode": ("front_cabinet_mode",),
    "rear_cabinet_length": ("rear_cabinet_length",),
    "rear_cabinet_height": ("rear_cabinet_height",),
    "rear_cabinet_depth": ("rear_cabinet_depth",),
    "rear_cabinet_mode": ("rear_cabinet_mode",),
    "interconnected_rows": ("interconnected_rows",),
}

SENSITIVE_PRICING_FIELDS = {
    "category",
    "series",
    "material",
    "length",
    "depth",
    "height",
    "width",
    "quote_kind",
    "has_door",
    "door_type",
    "shape",
    "bed_form",
    "access_style",
    "lower_bed_type",
    "guardrail_style",
    "guardrail_length",
    "guardrail_height",
    "access_height",
    "stair_width",
    "stair_depth",
    "underbed_cabinet_mode",
    "front_cabinet_length",
    "front_cabinet_height",
    "front_cabinet_depth",
    "front_cabinet_mode",
    "rear_cabinet_length",
    "rear_cabinet_height",
    "rear_cabinet_depth",
    "rear_cabinet_mode",
    "interconnected_rows",
}

CHILD_BED_STRICT_OCR_FIELDS = {
    "quote_kind",
    "material",
    "length",
    "width",
    "bed_form",
    "access_style",
    "lower_bed_type",
    "guardrail_style",
    "guardrail_length",
    "guardrail_height",
    "access_height",
    "stair_width",
    "stair_depth",
    "underbed_cabinet_mode",
    "front_cabinet_length",
    "front_cabinet_height",
    "front_cabinet_depth",
    "front_cabinet_mode",
    "rear_cabinet_length",
    "rear_cabinet_height",
    "rear_cabinet_depth",
    "rear_cabinet_mode",
    "interconnected_rows",
}


def bridge_contract_to_pricing_precheck(
    normalized_fields: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    mapping = map_contract_fields_to_precheck_args(
        normalized_fields,
        min_confidence=min_confidence,
    )
    precheck_args = mapping["precheck_args"]

    if not str(precheck_args.get("category") or "").strip():
        return {
            "status": "manual_confirmation_required",
            "reason": "category_missing_or_untrusted",
            "precheck_args": precheck_args,
            "precheck_result": None,
            "mapped_fields": mapping["mapped_fields"],
            "blocked_fields": mapping["blocked_fields"],
            "withheld_source_fields": mapping["withheld_source_fields"],
            "strict_ocr_blocked_fields": mapping["strict_ocr_blocked_fields"],
            "confidence_overrides": mapping["confidence_overrides"],
        }

    if mapping["blocked_fields"]:
        return {
            "status": "manual_confirmation_required",
            "reason": "sensitive_fields_below_confidence_threshold",
            "precheck_args": precheck_args,
            "precheck_result": None,
            "mapped_fields": mapping["mapped_fields"],
            "blocked_fields": mapping["blocked_fields"],
            "withheld_source_fields": mapping["withheld_source_fields"],
            "strict_ocr_blocked_fields": mapping["strict_ocr_blocked_fields"],
            "confidence_overrides": mapping["confidence_overrides"],
        }

    precheck_result = run_liangqin_pricing_precheck(precheck_args)
    status = "ready_for_formal_quote" if precheck_result.get("ready_for_formal_quote") else "needs_input"
    return {
        "status": status,
        "reason": "pricing_precheck_completed",
        "precheck_args": precheck_args,
        "precheck_result": precheck_result,
        "mapped_fields": mapping["mapped_fields"],
        "blocked_fields": mapping["blocked_fields"],
        "withheld_source_fields": mapping["withheld_source_fields"],
        "strict_ocr_blocked_fields": mapping["strict_ocr_blocked_fields"],
        "confidence_overrides": mapping["confidence_overrides"],
    }


def map_contract_fields_to_precheck_args(
    normalized_fields: dict[str, Any],
    *,
    min_confidence: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    fields_payload = _resolve_fields_payload(normalized_fields)
    precheck_args: dict[str, Any] = {}
    mapped_fields: dict[str, dict[str, Any]] = {}
    blocked_fields: list[str] = []
    withheld_source_fields: list[str] = []
    strict_ocr_blocked_fields: list[str] = []
    confidence_overrides: list[dict[str, Any]] = []

    for target_field, aliases in FIELD_ALIASES.items():
        source_name, field_payload = _pick_field_payload(fields_payload, aliases)
        if source_name is None:
            continue

        value, confidence = _extract_value_and_confidence(field_payload)
        if _is_blank(value):
            continue
        effective_confidence = confidence
        strict_ocr_override = False
        if _should_apply_child_bed_ocr_cap(
            target_field=target_field,
            field_payload=field_payload,
            precheck_args=precheck_args,
        ):
            effective_confidence = min(effective_confidence, CHILD_BED_OCR_CONFIDENCE_CAP)
            if effective_confidence < confidence:
                strict_ocr_override = True
                confidence_overrides.append(
                    {
                        "target_field": target_field,
                        "source_field": source_name,
                        "reason": "child_bed_ocr_requires_manual_confirmation",
                        "original_confidence": round(confidence, 2),
                        "effective_confidence": round(effective_confidence, 2),
                    }
                )
        if effective_confidence < min_confidence:
            withheld_source_fields.append(source_name)
            if target_field in SENSITIVE_PRICING_FIELDS:
                blocked_fields.append(target_field)
            if strict_ocr_override:
                strict_ocr_blocked_fields.append(target_field)
            continue

        normalized_value = _normalize_value_for_pricing(target_field, value)
        precheck_args[target_field] = normalized_value
        mapped_fields[target_field] = {
            "source_field": source_name,
            "value": normalized_value,
            "confidence": effective_confidence,
        }

    _apply_underbed_mode_fallback(precheck_args, mapped_fields)
    _apply_table_depth_fallback(precheck_args, mapped_fields)
    _apply_cabinet_depth_fallback_from_width(precheck_args, mapped_fields)

    return {
        "precheck_args": precheck_args,
        "mapped_fields": mapped_fields,
        "blocked_fields": sorted(set(blocked_fields)),
        "withheld_source_fields": sorted(set(withheld_source_fields)),
        "strict_ocr_blocked_fields": sorted(set(strict_ocr_blocked_fields)),
        "confidence_overrides": confidence_overrides,
    }


def run_liangqin_pricing_precheck(precheck_args: dict[str, Any]) -> dict[str, Any]:
    module = _load_handle_quote_message_module()
    return module._run_precheck(precheck_args)


def _resolve_fields_payload(normalized_fields: dict[str, Any]) -> dict[str, Any]:
    fields_payload = normalized_fields.get("fields")
    if isinstance(fields_payload, dict):
        return fields_payload
    return normalized_fields


def _pick_field_payload(fields_payload: dict[str, Any], aliases: tuple[str, ...]) -> tuple[str | None, Any]:
    for alias in aliases:
        if alias in fields_payload:
            return alias, fields_payload[alias]
    return None, None


def _extract_value_and_confidence(payload: Any) -> tuple[Any, float]:
    if isinstance(payload, dict):
        return payload.get("value"), _to_confidence(payload.get("confidence"))
    return payload, 1.0


def _to_confidence(value: Any) -> float:
    try:
        if value is None or value == "":
            return 1.0
        return float(value)
    except (TypeError, ValueError):
        return 1.0


def _normalize_value_for_pricing(target_field: str, value: Any) -> Any:
    if isinstance(value, bool):
        if target_field == "has_door":
            return "yes" if value else "no"
        return value
    if target_field in {"interconnected_rows", "approximate_only"}:
        return bool(value)
    return str(value).strip()


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _apply_underbed_mode_fallback(
    precheck_args: dict[str, Any],
    mapped_fields: dict[str, dict[str, Any]],
) -> None:
    if precheck_args.get("front_cabinet_mode"):
        return
    if not precheck_args.get("underbed_cabinet_mode"):
        return
    if any(precheck_args.get(field) for field in ("rear_cabinet_length", "rear_cabinet_height", "rear_cabinet_depth", "rear_cabinet_mode")):
        return
    if not all(precheck_args.get(field) for field in ("front_cabinet_length", "front_cabinet_height", "front_cabinet_depth")):
        return

    fallback_value = precheck_args["underbed_cabinet_mode"]
    precheck_args["front_cabinet_mode"] = fallback_value

    underbed_mapping = mapped_fields.get("underbed_cabinet_mode", {})
    mapped_fields["front_cabinet_mode"] = {
        "source_field": underbed_mapping.get("source_field", "underbed_cabinet_mode"),
        "value": fallback_value,
        "confidence": underbed_mapping.get("confidence", 1.0),
        "fallback_from": "underbed_cabinet_mode",
    }


def _should_apply_child_bed_ocr_cap(
    *,
    target_field: str,
    field_payload: Any,
    precheck_args: dict[str, Any],
) -> bool:
    if target_field not in CHILD_BED_STRICT_OCR_FIELDS:
        return False
    if not _is_child_bed_context(target_field=target_field, precheck_args=precheck_args):
        return False
    return _is_ocr_only_field_payload(field_payload)


def _is_child_bed_context(*, target_field: str, precheck_args: dict[str, Any]) -> bool:
    if target_field in CHILD_BED_STRICT_OCR_FIELDS - {"quote_kind", "material", "length", "width"}:
        return True
    category = str(precheck_args.get("category") or "").strip()
    if not category:
        return False
    return any(keyword in category for keyword in CHILD_BED_KEYWORDS)


def _is_ocr_only_field_payload(field_payload: Any) -> bool:
    if not isinstance(field_payload, dict):
        return False
    evidence_refs = [item for item in list(field_payload.get("evidence_refs") or []) if isinstance(item, dict)]
    if not evidence_refs:
        return False
    source_kinds = {str(item.get("source_kind") or "").strip() for item in evidence_refs}
    source_kinds.discard("")
    if not source_kinds:
        return False
    return all(source_kind.startswith("ocr") for source_kind in source_kinds)


def _apply_table_depth_fallback(
    precheck_args: dict[str, Any],
    mapped_fields: dict[str, dict[str, Any]],
) -> None:
    category = str(precheck_args.get("category") or "").strip()
    if not category:
        return

    precheck_quote = _load_precheck_quote_module()
    normalized_type = precheck_quote.normalize_category_label(category)
    if normalized_type != "table" and "桌" not in category:
        return
    if precheck_args.get("depth") or not precheck_args.get("width"):
        return

    fallback_value = precheck_args["width"]
    precheck_args["depth"] = fallback_value
    width_mapping = mapped_fields.get("width", {})
    mapped_fields["depth"] = {
        "source_field": width_mapping.get("source_field", "width"),
        "value": fallback_value,
        "confidence": width_mapping.get("confidence", 1.0),
        "fallback_from": "width",
    }


def _apply_cabinet_depth_fallback_from_width(
    precheck_args: dict[str, Any],
    mapped_fields: dict[str, dict[str, Any]],
) -> None:
    category = str(precheck_args.get("category") or "").strip()
    if not category:
        return
    if precheck_args.get("depth") or not precheck_args.get("width"):
        return

    precheck_quote = _load_precheck_quote_module()
    normalized_type = precheck_quote.normalize_category_label(category)
    if normalized_type != "cabinet" and "柜" not in category:
        return

    fallback_value = precheck_args["width"]
    precheck_args["depth"] = fallback_value
    width_mapping = mapped_fields.get("width", {})
    mapped_fields["depth"] = {
        "source_field": width_mapping.get("source_field", "width"),
        "value": fallback_value,
        "confidence": width_mapping.get("confidence", 1.0),
        "fallback_from": "width",
    }


def _load_handle_quote_message_module():
    scripts_dir = (
        Path(__file__).resolve().parents[3] / "skill" / "liangqin-pricing" / "scripts"
    )
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("handle_quote_message")


def _load_precheck_quote_module():
    scripts_dir = (
        Path(__file__).resolve().parents[3] / "skill" / "liangqin-pricing" / "scripts"
    )
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("precheck_quote")
