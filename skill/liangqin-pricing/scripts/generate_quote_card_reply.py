#!/usr/bin/env python3
"""Generate a quote-card image reply for the current OpenClaw conversation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

import quote_card_adapter
import quote_card_renderer
import quote_result_bundle


def generate_quote_card_reply(
    *,
    context_json: str,
    channel: str,
    bundle_root: Path = quote_result_bundle.DEFAULT_BUNDLE_ROOT,
    media_root: Path = quote_card_renderer.DEFAULT_MEDIA_ROOT,
    hero_image: str | None = None,
    renderer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    context = quote_result_bundle.resolve_conversation_context(context_json, channel=channel)
    bundle = quote_result_bundle.load_latest_quote_result_bundle(context["conversation_id"], cache_root=bundle_root)
    if not bundle or not bundle.get("eligible_for_card"):
        return {"text": quote_result_bundle.NO_BUNDLE_MESSAGE}

    view_model = quote_card_adapter.adapt_quote_card_payload(
        bundle.get("quote_card_payload") or bundle["prepared_payload"],
        hero_image=hero_image,
    )
    render = renderer or quote_card_renderer.render_quote_card_export
    export = render(view_model=view_model, bundle=bundle, output_root=media_root, hero_image=hero_image)
    return {
        "text": "这次报价已经整理成图片发到当前会话，完整计算过程仍以文字报价为准。",
        "media_url": export["image_path"],
        "html_path": export["html_path"],
        "json_path": export.get("json_path", ""),
        "bundle_path": export["bundle_path"],
        "width": export["width"],
        "height": export["height"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Liangqin quote-card reply")
    parser.add_argument("--context-json", required=True, help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", required=True, help="Current OpenClaw channel id, such as feishu or dingtalk-connector.")
    parser.add_argument(
        "--bundle-root",
        default=str(quote_result_bundle.DEFAULT_BUNDLE_ROOT),
        help="Directory containing latest quote result bundles.",
    )
    parser.add_argument(
        "--media-root",
        default=str(quote_card_renderer.DEFAULT_MEDIA_ROOT),
        help="Output directory for rendered quote-card media.",
    )
    parser.add_argument("--hero-image", help="Optional local hero image path for the quote card.")
    args = parser.parse_args()

    reply = generate_quote_card_reply(
        context_json=args.context_json,
        channel=args.channel,
        bundle_root=Path(args.bundle_root).expanduser().resolve(),
        media_root=Path(args.media_root).expanduser().resolve(),
        hero_image=args.hero_image,
    )
    print(reply["text"])
    media_url = str(reply.get("media_url", "")).strip()
    if media_url:
        print(f"MEDIA:{media_url}")


if __name__ == "__main__":
    main()
