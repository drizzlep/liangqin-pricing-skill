from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DIMENSION_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?\s*(?:mm|毫米|cm|厘米|m|米))", flags=re.IGNORECASE)

FIELD_LABEL_HINTS: dict[str, tuple[str, ...]] = {
    "width": ("床垫宽度", "床宽", "内宽", "净宽"),
    "length": ("床垫长度", "床长", "内长", "净长"),
    "height": ("总高",),
    "guardrail_length": ("围栏总长度", "围栏长度", "护栏长度"),
    "guardrail_height": ("围栏高度", "护栏高度"),
    "access_height": ("垂直高度", "梯子高度", "上下床间距", "上层高度"),
    "stair_width": ("梯柜踏步宽度", "梯柜宽度", "踏步宽度"),
    "stair_depth": ("梯柜踏步深度", "梯柜进深", "梯柜深度"),
    "front_cabinet_length": ("前排柜体长度", "前排长度", "前柜长度"),
    "front_cabinet_height": ("前排柜体高度", "前排高度", "前柜高度"),
    "front_cabinet_depth": ("前排柜体进深", "前排进深", "前柜进深"),
    "rear_cabinet_length": ("后排柜体长度", "后排长度", "后柜长度"),
    "rear_cabinet_height": ("后排柜体高度", "后排高度", "后柜高度"),
    "rear_cabinet_depth": ("后排柜体进深", "后排进深", "后柜进深"),
}


def load_ocr_layout_analysis(json_path: str | Path | None) -> dict[str, Any]:
    path = Path(str(json_path or "")).expanduser()
    if not path.exists():
        return {}

    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {}

    page_payloads = _resolve_page_payloads(payload, base_path=path)
    if not page_payloads:
        page_payloads = [
            {
                "page_no": int(payload.get("page_index") or 0) + 1,
                "payload": payload,
            }
        ]

    blocks: list[dict[str, Any]] = []
    for entry in page_payloads:
        blocks.extend(_extract_text_blocks(entry["payload"], page_no=int(entry["page_no"])))

    if not blocks:
        return {}

    dimension_candidates = _build_dimension_candidates(blocks)
    field_candidates = _build_field_candidates(blocks, dimension_candidates)
    return {
        "page_count": len(page_payloads),
        "block_count": len(blocks),
        "combined_text": "\n".join(str(item["text"]) for item in blocks if str(item["text"]).strip()),
        "dimension_count": len(dimension_candidates),
        "dimension_candidates": dimension_candidates,
        "field_candidates": field_candidates,
    }


def _resolve_page_payloads(payload: dict[str, Any], *, base_path: Path) -> list[dict[str, Any]]:
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return []

    resolved: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        json_path = Path(str(page.get("json_path") or "")).expanduser()
        if not json_path.is_absolute():
            json_path = (base_path.parent / json_path).resolve()
        page_payload = _read_json(json_path)
        if not isinstance(page_payload, dict):
            continue
        resolved.append(
            {
                "page_no": int(page.get("page_no") or index),
                "payload": page_payload,
            }
        )
    return resolved


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _extract_text_blocks(payload: dict[str, Any], *, page_no: int) -> list[dict[str, Any]]:
    overall_ocr_res = payload.get("overall_ocr_res")
    if not isinstance(overall_ocr_res, dict):
        pruned_result = payload.get("prunedResult")
        overall_ocr_res = pruned_result if isinstance(pruned_result, dict) else {}

    texts = list(overall_ocr_res.get("rec_texts") or [])
    boxes = list(overall_ocr_res.get("rec_boxes") or [])
    polys = list(overall_ocr_res.get("rec_polys") or overall_ocr_res.get("dt_polys") or [])
    scores = list(overall_ocr_res.get("rec_scores") or [])

    blocks: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        normalized_text = str(text or "").strip()
        if not normalized_text:
            continue
        bbox = _coerce_bbox(boxes[index] if index < len(boxes) else None)
        if bbox is None:
            bbox = _coerce_bbox(polys[index] if index < len(polys) else None)
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        blocks.append(
            {
                "text": normalized_text,
                "page_no": page_no,
                "bbox": [left, top, right, bottom],
                "center_x": (left + right) / 2,
                "center_y": (top + bottom) / 2,
                "width": max(right - left, 1.0),
                "height": max(bottom - top, 1.0),
                "score": float(scores[index]) if index < len(scores) and scores[index] is not None else None,
            }
        )
    return blocks


def _coerce_bbox(raw_box: Any) -> list[float] | None:
    if not isinstance(raw_box, (list, tuple)) or not raw_box:
        return None

    if len(raw_box) == 4 and all(isinstance(item, (int, float)) for item in raw_box):
        left, top, right, bottom = [float(item) for item in raw_box]
        return [min(left, right), min(top, bottom), max(left, right), max(top, bottom)]

    points: list[tuple[float, float]] = []
    for item in raw_box:
        if isinstance(item, (list, tuple)) and len(item) >= 2 and all(isinstance(value, (int, float)) for value in item[:2]):
            points.append((float(item[0]), float(item[1])))
    if not points:
        return None

    xs = [item[0] for item in points]
    ys = [item[1] for item in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _build_dimension_candidates(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for block in blocks:
        text = str(block["text"])
        normalized_text = _normalize_text(text)
        for match in DIMENSION_PATTERN.finditer(text):
            value = str(match.group(1) or "").strip()
            if not value:
                continue
            candidates.append(
                {
                    "value": value,
                    "page_no": block["page_no"],
                    "bbox": list(block["bbox"]),
                    "center_x": float(block["center_x"]),
                    "center_y": float(block["center_y"]),
                    "width": float(block["width"]),
                    "height": float(block["height"]),
                    "text": text,
                    "normalized_text": normalized_text,
                    "score": block.get("score"),
                }
            )
    return candidates


def _build_field_candidates(
    blocks: list[dict[str, Any]],
    dimension_candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    field_candidates: dict[str, dict[str, Any]] = {}
    for field_name, labels in FIELD_LABEL_HINTS.items():
        best_candidate: dict[str, Any] | None = None

        for block in blocks:
            direct_candidate = _match_direct_field_candidate(block, field_name=field_name, labels=labels)
            if direct_candidate and (best_candidate is None or float(direct_candidate["score"]) > float(best_candidate["score"])):
                best_candidate = direct_candidate

        if best_candidate is None:
            label_blocks = [block for block in blocks if _contains_any_label(block["text"], labels)]
            for dimension_candidate in dimension_candidates:
                candidate = _match_nearby_field_candidate(
                    dimension_candidate,
                    field_name=field_name,
                    labels=labels,
                    label_blocks=label_blocks,
                )
                if candidate and (best_candidate is None or float(candidate["score"]) > float(best_candidate["score"])):
                    best_candidate = candidate

        if best_candidate is not None:
            field_candidates[field_name] = best_candidate
    return field_candidates


def _match_direct_field_candidate(
    block: dict[str, Any],
    *,
    field_name: str,
    labels: tuple[str, ...],
) -> dict[str, Any] | None:
    normalized_text = _normalize_text(block["text"])
    for label in labels:
        if label not in normalized_text:
            continue
        pattern = re.compile(rf"{re.escape(label)}[:：\s]*([0-9]+(?:\.[0-9]+)?\s*(?:mm|毫米|cm|厘米|m|米))", flags=re.IGNORECASE)
        match = pattern.search(block["text"])
        if not match:
            continue
        return {
            "field_name": field_name,
            "value": str(match.group(1)).strip(),
            "label": label,
            "label_text": block["text"],
            "page_no": block["page_no"],
            "bbox": list(block["bbox"]),
            "score": 160.0 + len(label),
            "match_type": "inline_label",
        }
    return None


def _match_nearby_field_candidate(
    dimension_candidate: dict[str, Any],
    *,
    field_name: str,
    labels: tuple[str, ...],
    label_blocks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best_label: dict[str, Any] | None = None
    best_score = 0.0
    for label_block in label_blocks:
        score = _score_label_near_dimension(label_block, dimension_candidate)
        if score > best_score:
            best_score = score
            best_label = label_block

    if best_label is None or best_score < 70:
        return None

    label_text = str(best_label["text"])
    matched_label = next((label for label in labels if label in _normalize_text(label_text)), labels[0])
    return {
        "field_name": field_name,
        "value": str(dimension_candidate["value"]).strip(),
        "label": matched_label,
        "label_text": label_text,
        "page_no": int(dimension_candidate["page_no"]),
        "bbox": list(dimension_candidate["bbox"]),
        "score": round(best_score, 2),
        "match_type": "nearby_label",
    }


def _score_label_near_dimension(label_block: dict[str, Any], dimension_candidate: dict[str, Any]) -> float:
    if int(label_block["page_no"]) != int(dimension_candidate["page_no"]):
        return 0.0

    x_gap = abs(float(label_block["center_x"]) - float(dimension_candidate["center_x"]))
    y_gap = abs(float(label_block["center_y"]) - float(dimension_candidate["center_y"]))
    same_row = y_gap <= max(float(label_block["height"]), float(dimension_candidate["height"])) * 1.1
    same_column = x_gap <= max(float(label_block["width"]), float(dimension_candidate["width"])) * 1.4
    label_left_of_dimension = float(label_block["bbox"][0]) <= float(dimension_candidate["bbox"][0])
    label_above_dimension = float(label_block["bbox"][1]) <= float(dimension_candidate["bbox"][1])

    score = 0.0
    if same_row and label_left_of_dimension:
        score += 120.0
        score -= min(x_gap / 8.0, 30.0)
    elif same_row:
        score += 80.0
        score -= min(x_gap / 10.0, 25.0)

    if same_column and label_above_dimension:
        score += 90.0
        score -= min(y_gap / 8.0, 25.0)
    elif same_column:
        score += 50.0
        score -= min(y_gap / 10.0, 20.0)

    score -= min((x_gap + y_gap) / 60.0, 20.0)
    return score


def _contains_any_label(text: str, labels: tuple[str, ...]) -> bool:
    normalized_text = _normalize_text(text)
    return any(label in normalized_text for label in labels)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()
