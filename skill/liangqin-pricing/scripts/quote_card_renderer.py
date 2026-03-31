#!/usr/bin/env python3
"""Render Liangqin quote card HTML and JPG exports."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSET_SOURCE_DIR = SKILL_DIR / "quote-card-assets"
DEFAULT_MEDIA_ROOT = Path.home() / ".openclaw" / "media" / "quote-cards"
CARD_WIDTH = 1080
CARD_HEIGHT = 1920
PLAYWRIGHT_NODE_PATH_CANDIDATES = [
    Path.home() / ".openclaw" / "workspace" / "skills" / "gstack" / "node_modules",
    Path.home() / ".openclaw" / "extensions" / "dingtalk-connector" / "node_modules",
    Path.home() / ".openclaw" / "extensions" / "openclaw-lark" / "node_modules",
]


def _slugify(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value).strip("_") or "conversation"


def _timestamp_segment(value: str | None) -> str:
    if value:
        try:
            return datetime.fromisoformat(value).strftime("%Y%m%dT%H%M%S")
        except ValueError:
            pass
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")


def _split_basis_line(line: str) -> tuple[str, str]:
    if "：" in line:
        label, detail = line.split("：", 1)
        return label.strip(), detail.strip()
    if ":" in line:
        label, detail = line.split(":", 1)
        return label.strip(), detail.strip()
    return "说明", line.strip()


def _render_notes_section(notes_list: list[str]) -> str:
    if not notes_list:
        return ""
    notes_markup = "".join([f"<li>{escape(note)}</li>" for note in notes_list])
    return (
        '<section class="quote-card-export__section quote-card-export__section--notes">'
        '<div class="quote-card-export__section-head">'
        "<span>补充说明</span>"
        "</div>"
        f'<ul class="quote-card-export__notes">{notes_markup}</ul>'
        "</section>"
    )


def _render_multi_detail_section(view_model: dict[str, Any]) -> str:
    detail_cards = view_model.get("detail_cards") or []
    if not detail_cards:
        basis_markup = "".join(
            [
                (
                    '<li class="quote-card-export__basis-item">'
                    f"<span>{escape(label)}</span>"
                    f"<strong>{escape(detail)}</strong>"
                    "</li>"
                )
                for label, detail in [_split_basis_line(str(line)) for line in view_model.get("key_basis_lines") or []]
            ]
        )
        return (
            '<section class="quote-card-export__section">'
            '<div class="quote-card-export__section-head">'
            "<span>关键依据</span>"
            "</div>"
            f'<ul class="quote-card-export__basis">{basis_markup}</ul>'
            "</section>"
        )

    detail_markup = "".join(
        [
            (
                '<article class="quote-card-export__detail-card">'
                '<header class="quote-card-export__detail-card-head">'
                '<div class="quote-card-export__detail-card-title">'
                f"<strong>{escape(str(card.get('name', '')).strip())}</strong>"
                f"<span>{escape(str(card.get('meta', '')).strip())}</span>"
                "</div>"
                "</header>"
                '<ul class="quote-card-export__detail-card-lines">'
                + "".join(
                    f"<li>{escape(str(highlight).strip())}</li>" for highlight in (card.get("highlights") or []) if str(highlight).strip()
                )
                + "</ul>"
                "</article>"
            )
            for card in detail_cards
        ]
    )
    return (
        '<section class="quote-card-export__section">'
        '<div class="quote-card-export__section-head">'
        f"<span>报价明细</span><span>{len(detail_cards)} 项</span>"
        "</div>"
        f'<div class="quote-card-export__detail-cards">{detail_markup}</div>'
        "</section>"
    )


def _copytree_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _prepare_assets(export_dir: Path) -> None:
    _copytree_if_exists(ASSET_SOURCE_DIR / "assets", export_dir / "assets")
    for file_name in ["tokens.css", "quote-card-export.css"]:
        source = ASSET_SOURCE_DIR / file_name
        if source.exists():
            shutil.copy2(source, export_dir / file_name)


def _resolve_playwright_node_path() -> str:
    for candidate in PLAYWRIGHT_NODE_PATH_CANDIDATES:
        if (candidate / "playwright" / "package.json").exists():
            return str(candidate)
    raise FileNotFoundError("Could not find an installed playwright package under ~/.openclaw")


def build_quote_card_html(view_model: dict[str, Any]) -> str:
    quote_badge = escape(str(view_model.get("quote_badge", "")).strip())
    headline = escape(str(view_model.get("headline", "")).strip())
    quote_total = escape(str(view_model.get("quote_total", "")).strip())
    confirmed_text = escape(str(view_model.get("confirmed_text", "")).strip())
    overflow_hint = escape(str(view_model.get("overflow_hint", "")).strip())
    hero_image = str(view_model.get("hero_image", "")).strip()
    hero_class = "quote-card-export__hero quote-card-export__hero--image" if hero_image else "quote-card-export__hero quote-card-export__hero--fallback"
    hero_media = f'<div class="quote-card-export__hero-media" style="background-image: url({json.dumps(hero_image)});"></div>' if hero_image else ""

    item_rows = view_model.get("item_rows") or []
    item_rows_markup = "".join(
        [
            (
                '<li class="quote-card-export__row">'
                f'<div class="quote-card-export__row-main"><strong>{escape(str(row.get("name", "")).strip())}</strong>'
                f'<span>{escape(str(row.get("meta", "")).strip())}</span></div>'
                f'<span class="quote-card-export__row-amount">{escape(str(row.get("amount", "")).strip())}</span>'
                "</li>"
            )
            for row in item_rows
        ]
    )
    basis_markup = "".join(
        [
            (
                '<li class="quote-card-export__basis-item">'
                f"<span>{escape(label)}</span>"
                f"<strong>{escape(detail)}</strong>"
                "</li>"
            )
            for label, detail in [_split_basis_line(str(line)) for line in view_model.get("key_basis_lines") or []]
        ]
    )
    notes_list = [str(entry).strip() for entry in view_model.get("notes") or [] if str(entry).strip()]
    if overflow_hint:
        notes_list.append(overflow_hint)
    is_multi_layout = len(item_rows) > 1 and bool(view_model.get("detail_cards"))
    detail_or_basis_section = _render_multi_detail_section(view_model) if is_multi_layout else (
        '<section class="quote-card-export__section">'
        '<div class="quote-card-export__section-head">'
        "<span>关键依据</span>"
        "</div>"
        f'<ul class="quote-card-export__basis">{basis_markup}</ul>'
        "</section>"
    )
    notes_section = _render_notes_section(notes_list)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={CARD_WIDTH}, initial-scale=1.0" />
    <title>{headline or "良禽佳木报价卡"}</title>
    <link rel="stylesheet" href="./tokens.css" />
    <link rel="stylesheet" href="./quote-card-export.css" />
  </head>
  <body class="quote-card-export-page">
    <main class="quote-card-export">
      <section class="{hero_class}">
        {hero_media}
        <div class="quote-card-export__hero-top">
          <span class="quote-card-export__logo-frame">
            <img src="./assets/brand/liangqinjiamu-logo-horizontal.svg" alt="良禽佳木标志" />
          </span>
          <span class="quote-card-export__badge">{quote_badge}</span>
        </div>
      </section>

      <section class="quote-card-export__body">
        <header class="quote-card-export__header">
          <div class="quote-card-export__title-block">
            <span class="quote-card-export__overline">Liangqinjiamu Quote Card</span>
            <h1>{headline}</h1>
          </div>
          <div class="quote-card-export__amount">
            <span>最终报价</span>
            <strong>{quote_total}</strong>
          </div>
        </header>

        <section class="quote-card-export__section">
          <div class="quote-card-export__section-head">
            <span>已确认条件</span>
          </div>
          <p class="quote-card-export__confirmed">{confirmed_text or "完整计算过程以本条文字报价为准。"}</p>
        </section>

        <section class="quote-card-export__section">
          <div class="quote-card-export__section-head">
            <span>报价清单</span>
            <span>{len(item_rows)} 项</span>
          </div>
          <ul class="quote-card-export__rows">{item_rows_markup}</ul>
        </section>

        {detail_or_basis_section}
        {notes_section}
      </section>
    </main>
  </body>
</html>
"""


def write_quote_card_export(
    *,
    view_model: dict[str, Any],
    bundle: dict[str, Any],
    output_root: Path = DEFAULT_MEDIA_ROOT,
    hero_image: str | None = None,
) -> dict[str, Any]:
    conversation_id = str(bundle.get("conversation_id", "")).strip() or "conversation"
    export_dir = output_root / _slugify(conversation_id) / _timestamp_segment(str(bundle.get("created_at", "")).strip())
    export_dir.mkdir(parents=True, exist_ok=True)
    _prepare_assets(export_dir)

    working_view_model = dict(view_model)
    if hero_image:
        source = Path(hero_image).expanduser()
        if source.exists():
            hero_target = export_dir / source.name
            shutil.copy2(source, hero_target)
            working_view_model["hero_image"] = f"./{hero_target.name}"

    html_path = export_dir / "quote-card.html"
    json_path = export_dir / "quote-card.json"
    bundle_path = export_dir / "quote-result-bundle.json"
    image_path = export_dir / "quote-card.jpg"

    html_path.write_text(build_quote_card_html(working_view_model), encoding="utf-8")
    json_path.write_text(json.dumps(working_view_model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "image_path": str(image_path),
        "html_path": str(html_path),
        "json_path": str(json_path),
        "bundle_path": str(bundle_path),
        "width": CARD_WIDTH,
        "height": CARD_HEIGHT,
    }


def render_html_to_jpg(html_path: Path, image_path: Path, *, width: int = CARD_WIDTH, height: int = CARD_HEIGHT) -> None:
    script_path = SCRIPT_DIR / "render_quote_card_playwright.mjs"
    env = dict(os.environ)
    playwright_node_path = _resolve_playwright_node_path()
    env["NODE_PATH"] = playwright_node_path if not env.get("NODE_PATH") else f"{playwright_node_path}:{env['NODE_PATH']}"
    subprocess.run(
        [
            "node",
            str(script_path),
            str(html_path),
            str(image_path),
            str(width),
            str(height),
        ],
        check=True,
        cwd=SKILL_DIR,
        env=env,
    )


def render_quote_card_export(
    *,
    view_model: dict[str, Any],
    bundle: dict[str, Any],
    output_root: Path = DEFAULT_MEDIA_ROOT,
    hero_image: str | None = None,
) -> dict[str, Any]:
    result = write_quote_card_export(view_model=view_model, bundle=bundle, output_root=output_root, hero_image=hero_image)
    render_html_to_jpg(Path(result["html_path"]), Path(result["image_path"]), width=result["width"], height=result["height"])
    return result
