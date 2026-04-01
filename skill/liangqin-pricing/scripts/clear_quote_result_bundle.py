#!/usr/bin/env python3
"""Clear the latest cached quote-card bundle for the current conversation."""

from __future__ import annotations

import argparse
from pathlib import Path

import quote_flow_state
import quote_result_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear the cached Liangqin quote bundle for the current conversation.")
    parser.add_argument("--context-json", required=True, help="Conversation info JSON from the current OpenClaw message.")
    parser.add_argument("--channel", required=True, help="Current OpenClaw channel id.")
    parser.add_argument(
        "--bundle-root",
        default=str(quote_result_bundle.DEFAULT_BUNDLE_ROOT),
        help="Directory containing latest quote result bundles.",
    )
    parser.add_argument(
        "--flow-state-root",
        default=str(quote_flow_state.DEFAULT_FLOW_STATE_ROOT),
        help="Directory containing saved quote flow states.",
    )
    args = parser.parse_args()

    context = quote_result_bundle.resolve_conversation_context(args.context_json, channel=args.channel)
    cleared = quote_result_bundle.clear_latest_quote_result_bundle(
        context["conversation_id"],
        cache_root=Path(args.bundle_root).expanduser().resolve(),
    )
    cleared_state = quote_flow_state.clear_quote_flow_state(
        context["conversation_id"],
        cache_root=Path(args.flow_state_root).expanduser().resolve(),
    )
    if cleared or cleared_state:
        print(f"Cleared cached quote context for {context['conversation_id']}")
    else:
        print(f"No cached quote context for {context['conversation_id']}")
