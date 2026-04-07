import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quote_flow_state.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("quote_flow_state", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QuoteFlowStateTests(unittest.TestCase):
    def test_store_and_load_round_trip(self) -> None:
        state = MODULE.build_quote_flow_state(
            conversation_id="agent:main:feishu:direct:ou_123456",
            audience_role="consultant",
            manual_override="consultant",
            entry_mode="consultant_handoff",
            confirmed_fields={"items": [{"product": "流云衣柜", "confirmed": "白橡木，1.8×2.2×0.6"}]},
            missing_fields=["door_type"],
            active_route="cabinet",
            last_quote_kind="formal",
            internal_summary="内部完整版",
            customer_forward_text="客户版",
            handoff_summary="已补齐尺寸，待确认门型。",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            MODULE.store_quote_flow_state(state, cache_root=root)
            loaded = MODULE.load_quote_flow_state(state["conversation_id"], cache_root=root)

        self.assertEqual(loaded["audience_role"], "consultant")
        self.assertEqual(loaded["manual_override"], "consultant")
        self.assertEqual(loaded["summaries"]["customer_forward_text"], "客户版")
        self.assertEqual(loaded["last_payload"]["last_quote_kind"], "formal")

    def test_merge_preserves_manual_override_and_updates_latest_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            conversation_id = "agent:main:feishu:direct:ou_123456"
            MODULE.store_quote_flow_state(
                MODULE.build_quote_flow_state(
                    conversation_id=conversation_id,
                    audience_role="consultant",
                    manual_override="consultant",
                    entry_mode="manual_override",
                    internal_summary="旧摘要",
                ),
                cache_root=root,
            )

            merged = MODULE.merge_quote_flow_state(
                conversation_id,
                updates={
                    "audience_role": "consultant",
                    "internal_summary": "新摘要",
                    "missing_fields": ["material"],
                },
                cache_root=root,
            )

        self.assertEqual(merged["manual_override"], "consultant")
        self.assertEqual(merged["summaries"]["internal_summary"], "新摘要")
        self.assertEqual(merged["missing_fields"], ["material"])

    def test_clear_removes_saved_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            conversation_id = "agent:main:feishu:direct:ou_123456"
            MODULE.store_quote_flow_state(
                MODULE.build_quote_flow_state(conversation_id=conversation_id),
                cache_root=root,
            )

            self.assertTrue(MODULE.clear_quote_flow_state(conversation_id, cache_root=root))
            self.assertIsNone(MODULE.load_quote_flow_state(conversation_id, cache_root=root))

    def test_state_round_trip_includes_inquiry_family_and_product_context(self) -> None:
        state = MODULE.build_quote_flow_state(
            conversation_id="agent:main:feishu:direct:ou_123456",
            audience_role="customer",
            active_route="size_spec",
            confirmed_fields={"last_product": "穿衣镜"},
            handoff_summary="已回复目录尺寸，待确认是否继续报价。",
            active_inquiry_family="size_spec",
            captured_product_context={"product_name": "穿衣镜", "product_code": "YGP-01"},
            last_non_quote_reply="这款目录尺寸是长0.6米、深0.12米、高1.8米。",
            last_safe_boundary_reason="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            MODULE.store_quote_flow_state(state, cache_root=root)
            loaded = MODULE.load_quote_flow_state(state["conversation_id"], cache_root=root)

        self.assertEqual(loaded["active_inquiry_family"], "size_spec")
        self.assertEqual(loaded["captured_product_context"]["product_code"], "YGP-01")
        self.assertIn("目录尺寸", loaded["last_non_quote_reply"])


if __name__ == "__main__":
    unittest.main()
