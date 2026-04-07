import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "route_quote_request.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("route_quote_request", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RouteQuoteRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context_json = json.dumps(
            {
                "message_id": "om_route_1001",
                "sender_id": "ou_route_123456",
                "sender": "ou_route_123456",
                "timestamp": "Wed 2026-04-01 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

    def test_routes_customer_quote_to_precheck_with_customer_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.route_message(
                text="我家次卧想做个北美白橡木衣柜，长1.8米，高2.2米，深600，先给我一个客户能看懂的报价。",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["output_profile"], "customer_simple")
        self.assertEqual(result["preferred_next_tool"], "precheck_quote")
        self.assertFalse(result["should_generate_quote_card"])
        self.assertFalse(result["should_clear_previous_context"])

    def test_routes_customer_precise_need_to_precheck_instead_of_addendum_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.route_message(
                text="我想定个书柜。",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["preferred_next_tool"], "precheck_quote")
        self.assertEqual(result["role_result"]["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["role_result"]["customer_strategy"], "precise_need")

    def test_routes_designer_structure_question_to_addendum_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.route_message(
                text="常规拆装柜体高度1700以内默认做顶盖侧还是侧盖顶？衣柜牙称高度一般多少，允许范围多大？",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["audience_role"], "designer")
        self.assertEqual(result["output_profile"], "designer_full")
        self.assertEqual(result["preferred_next_tool"], "query_addendum_guidance")
        self.assertEqual(result["detected_intent"], "rule_consultation")

    def test_routes_consultant_quote_to_precheck_with_dual_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.route_message(
                text="你先帮我整理一版发客户的话术：北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，按正式报价怎么回更合适？",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["audience_role"], "consultant")
        self.assertEqual(result["output_profile"], "consultant_dual")
        self.assertEqual(result["preferred_next_tool"], "query_addendum_guidance")
        self.assertEqual(result["detected_intent"], "quote_follow_up")

    def test_routes_image_request_to_quote_card_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            MODULE.quote_flow_state.store_quote_flow_state(
                MODULE.quote_flow_state.build_quote_flow_state(
                    conversation_id="agent:main:feishu:direct:ou_route_123456",
                    audience_role="consultant",
                    internal_summary="内部版",
                    customer_forward_text="客户版",
                ),
                cache_root=state_root,
            )
            MODULE.quote_result_bundle.store_latest_quote_result_bundle(
                {
                    "prepared_payload": {"items": [{"product": "流云衣柜"}], "total": "39,529 元"},
                    "reply_text": "客户版正式报价：39,529 元",
                    "quote_kind": "formal",
                    "conversation_id": "agent:main:feishu:direct:ou_route_123456",
                    "eligible_for_card": True,
                    "created_at": "2026-04-01T10:30:00+08:00",
                },
                cache_root=bundle_root,
            )

            result = MODULE.route_message(
                text="生成图片",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
            )

        self.assertTrue(result["should_generate_quote_card"])
        self.assertEqual(result["preferred_next_tool"], "generate_quote_card_reply")
        self.assertFalse(result["should_clear_previous_context"])
        self.assertEqual(result["output_profile"], "consultant_dual")

    def test_explicit_new_quote_can_clear_previous_context_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            conversation_id = "agent:main:feishu:direct:ou_route_123456"
            MODULE.quote_flow_state.store_quote_flow_state(
                MODULE.quote_flow_state.build_quote_flow_state(
                    conversation_id=conversation_id,
                    audience_role="consultant",
                    internal_summary="旧内部版",
                    customer_forward_text="旧客户版",
                    last_quote_kind="formal",
                ),
                cache_root=state_root,
            )
            MODULE.quote_result_bundle.store_latest_quote_result_bundle(
                {
                    "prepared_payload": {"items": [{"product": "旧报价"}], "total": "39,529 元"},
                    "reply_text": "旧报价",
                    "quote_kind": "formal",
                    "conversation_id": conversation_id,
                    "eligible_for_card": True,
                    "created_at": "2026-04-01T10:30:00+08:00",
                },
                cache_root=bundle_root,
            )

            result = MODULE.route_message(
                text="重新来一单，做个北美白橡木玄关柜，长1.6米，高2.2米，深600，先报价。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                apply_context_reset=True,
            )

            remaining_state = MODULE.quote_flow_state.load_quote_flow_state(conversation_id, cache_root=state_root)
            remaining_bundle = MODULE.quote_result_bundle.load_latest_quote_result_bundle(conversation_id, cache_root=bundle_root)

        self.assertTrue(result["should_clear_previous_context"])
        self.assertTrue(result["context_reset_applied"])
        self.assertIsNotNone(remaining_state)
        self.assertEqual(remaining_state["audience_role"], "customer")
        self.assertEqual(remaining_state["summaries"]["internal_summary"], "")
        self.assertEqual(remaining_state["summaries"]["customer_forward_text"], "")
        self.assertIsNone(remaining_bundle)

    def test_routes_size_spec_question_to_inquiry_reply_without_product_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.route_message(
                text="这款没有尺寸吗",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["inquiry_family"], "size_spec")
        self.assertEqual(result["preferred_next_tool"], "inquiry_reply")
        self.assertFalse(result["can_answer_directly"])
        self.assertTrue(result["needs_product_context"])

    def test_routes_material_boundary_question_to_material_config_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.route_message(
                text="良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["inquiry_family"], "material_config")
        self.assertEqual(result["preferred_next_tool"], "query_addendum_guidance")
        self.assertTrue(result["can_answer_directly"])
        self.assertFalse(result["needs_product_context"])


if __name__ == "__main__":
    unittest.main()
