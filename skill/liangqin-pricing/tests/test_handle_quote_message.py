import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "handle_quote_message.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("handle_quote_message", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class HandleQuoteMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context_json = json.dumps(
            {
                "message_id": "om_handle_1001",
                "sender_id": "ou_handle_123456",
                "sender": "ou_handle_123456",
                "timestamp": "Wed 2026-04-01 10:26 GMT+8",
            },
            ensure_ascii=False,
        )
        self.conversation_id = "agent:main:feishu:direct:ou_handle_123456"

    def seed_existing_formal_quote(self, bundle_root: Path, state_root: Path, payload: dict) -> None:
        MODULE.quote_result_bundle.store_latest_quote_result_bundle(
            {
                "prepared_payload": payload,
                "reply_text": "旧正式报价",
                "quote_kind": "formal",
                "conversation_id": self.conversation_id,
                "eligible_for_card": True,
                "created_at": "2026-04-01T10:30:00+08:00",
                "audience_role": "consultant",
                "output_profile": "consultant_dual",
            },
            cache_root=bundle_root,
        )
        MODULE.quote_flow_state.store_quote_flow_state(
            MODULE.quote_flow_state.build_quote_flow_state(
                conversation_id=self.conversation_id,
                audience_role="consultant",
                last_quote_kind="formal",
                last_formal_payload=payload,
                internal_summary="旧内部版",
                customer_forward_text="旧客户版",
                confirmed_fields={"items": [{"product": payload["items"][0]["product"]}]},
            ),
            cache_root=state_root,
        )

    def test_formats_ready_quote_payload_with_consultant_dual_output(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="帮我整理一版发客户的话术，这个正式报价直接给我。",
                context_json=self.context_json,
                channel="feishu",
                quote_payload=payload,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["audience_role"], "consultant")
        self.assertEqual(result["output_profile"], "consultant_dual")
        self.assertIn("这次可以正式报价", result["reply_text"])
        self.assertIn("正式报价：34372.8元", result["internal_summary"])
        self.assertIn("如果你需要，我可以把这次报价整理成一张图片发到当前会话。", result["reply_text"])

    def test_generates_quote_card_when_message_requests_image(self) -> None:
        payload = {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "quote_card_payload": {
                "items": [
                    {
                        "product": "流云衣柜",
                        "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                        "subtotal": "34372.8元",
                    }
                ],
                "total": "34372.8元",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            conversation_id = "agent:main:feishu:direct:ou_handle_123456"
            MODULE.quote_result_bundle.store_latest_quote_result_bundle(
                {
                    "prepared_payload": payload,
                    "reply_text": "客户版正式报价：34372.8元",
                    "quote_kind": "formal",
                    "conversation_id": conversation_id,
                    "eligible_for_card": True,
                    "created_at": "2026-04-01T10:30:00+08:00",
                    "quote_card_payload": payload["quote_card_payload"],
                },
                cache_root=Path(tmpdir) / "bundles",
            )

            result = MODULE.handle_message(
                text="生成图片",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                media_root=Path(tmpdir) / "media",
                renderer=lambda **_: {
                    "image_path": str(Path(tmpdir) / "media" / "quote-card.png"),
                    "html_path": str(Path(tmpdir) / "media" / "quote-card.html"),
                    "bundle_path": str(Path(tmpdir) / "media" / "bundle.json"),
                    "json_path": str(Path(tmpdir) / "media" / "view-model.json"),
                    "width": 1200,
                    "height": 1600,
                },
            )

        self.assertEqual(result["handled_by"], "generate_quote_card_reply")
        self.assertIn("整理成图片", result["reply_text"])
        self.assertTrue(str(result["media_url"]).endswith("quote-card.png"))

    def test_executes_precheck_when_structured_args_are_available(self) -> None:
        precheck_args = {
            "category": "衣柜",
            "length": "1.8",
            "height": "2.2",
            "material": "北美黑胡桃木",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="我家次卧想做个衣柜，先给我报一下。",
                context_json=self.context_json,
                channel="feishu",
                precheck_args=precheck_args,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["handled_by"], "precheck_quote")
        self.assertEqual(result["status"], "ready_for_quote")
        self.assertEqual(result["pricing_route"], "cabinet")
        self.assertEqual(result["missing_fields"], [])
        self.assertIn("可以进入正式报价", result["reply_text"])

    def test_customer_precise_need_returns_guided_discovery_reply_for_bookcase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="我想定个书柜。",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "customer_guided_discovery")
        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "precise_need")
        self.assertEqual(result["response_stage"], "direction_confirm")
        self.assertIn("书柜方向", result["reply_text"])
        self.assertIn("不急着区分目录成品还是定制", result["reply_text"])
        self.assertIn("下一步我先只确认一个问题", result["reply_text"])
        self.assertEqual(result["question_code"], "customer.precise_need.goal")

    def test_customer_renovation_browse_returns_space_first_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="房子在装修，先过来看看。",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "customer_guided_discovery")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "renovation_browse")
        self.assertEqual(result["response_stage"], "direction_confirm")
        self.assertIn("装修前期", result["reply_text"])
        self.assertIn("最想先看哪个空间", result["reply_text"])
        self.assertEqual(result["question_code"], "customer.renovation_browse.space")

    def test_customer_guided_discovery_returns_goal_first_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="我也不知道做什么，就是想把儿童房利用起来。",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "customer_guided_discovery")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "guided_discovery")
        self.assertEqual(result["response_stage"], "proposal_range")
        self.assertIn("不急着帮你定具体家具", result["reply_text"])
        self.assertIn("预算区间", result["reply_text"])
        self.assertIn("主要是给谁用", result["reply_text"])
        self.assertEqual(result["question_code"], "customer.guided_discovery.user")

    def test_main_openclaw_reply_mode_prints_only_final_reply_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = MODULE.main(
                    [
                        "--text",
                        "儿童房还能怎么利用起来？",
                        "--context-json",
                        self.context_json,
                        "--channel",
                        "feishu",
                        "--state-root",
                        str(Path(tmpdir) / "states"),
                        "--bundle-root",
                        str(Path(tmpdir) / "bundles"),
                        "--disable-addenda",
                        "--output-mode",
                        "openclaw_reply",
                    ]
                )

        rendered = stdout.getvalue().strip()
        self.assertEqual(exit_code, 0)
        self.assertIn("不急着帮你定具体家具", rendered)
        self.assertIn("主要是给谁用", rendered)
        self.assertNotIn('"reply_text"', rendered)
        self.assertFalse(rendered.startswith("{"))

    def test_customer_default_message_still_uses_unified_guided_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="先问问看。",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "customer_guided_discovery")
        self.assertEqual(result["audience_role"], "customer")
        self.assertEqual(result["entry_mode"], "customer_guided_discovery")
        self.assertEqual(result["customer_strategy"], "default")
        self.assertIn("这种情况很常见", result["reply_text"])
        self.assertIn("你现在最想优先解决收纳、睡觉、学习，还是空间利用", result["reply_text"])
        self.assertEqual(result["question_code"], "customer.guided_discovery.goal")

    def test_customer_freeform_messages_keep_single_public_entry_and_single_next_question(self) -> None:
        cases = [
            ("想做个衣柜，不过还没确定内部怎么分。", "precise_need", "customer.precise_need.goal"),
            ("新房装修中，先做做功课。", "renovation_browse", "customer.renovation_browse.space"),
            ("儿童房还能怎么利用起来？", "guided_discovery", "customer.guided_discovery.user"),
            ("这个空间能做什么？", "guided_discovery", "customer.guided_discovery.goal"),
            ("先咨询一下。", "default", "customer.guided_discovery.goal"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, (text, expected_strategy, expected_question_code) in enumerate(cases, start=1):
                with self.subTest(text=text):
                    result = MODULE.handle_message(
                        text=text,
                        context_json=json.dumps(
                            {
                                "message_id": f"om_handle_matrix_{idx}",
                                "sender_id": f"ou_handle_matrix_{idx}",
                                "sender": f"ou_handle_matrix_{idx}",
                                "timestamp": "Wed 2026-04-01 10:26 GMT+8",
                            },
                            ensure_ascii=False,
                        ),
                        channel="feishu",
                        state_root=Path(tmpdir) / "states",
                        bundle_root=Path(tmpdir) / "bundles",
                        disable_addenda=True,
                    )

                    self.assertEqual(result["handled_by"], "customer_guided_discovery")
                    self.assertEqual(result["audience_role"], "customer")
                    self.assertEqual(result["entry_mode"], "customer_guided_discovery")
                    self.assertEqual(result["customer_strategy"], expected_strategy)
                    self.assertEqual(result["question_code"], expected_question_code)
                    self.assertEqual(result["missing_fields"], ["customer_guided_answer"])
                    self.assertIn("下一步我先只确认一个问题", result["reply_text"])

    def test_customer_guided_follow_up_uses_prior_signals_to_advance_next_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"

            first = MODULE.handle_message(
                text="我想定个书柜。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )
            second = MODULE.handle_message(
                text="更偏收纳。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["question_code"], "customer.precise_need.goal")
        self.assertEqual(second["handled_by"], "customer_guided_discovery")
        self.assertEqual(second["customer_strategy"], "precise_need")
        self.assertEqual(second["question_code"], "customer.precise_need.space")
        self.assertEqual(second["guided_turn_count"], 2)
        self.assertIn("继续按书柜方向帮你往下收", second["reply_text"])
        self.assertIn("放在哪个空间", second["reply_text"])

    def test_customer_guided_follow_up_can_augment_precheck_args_from_prior_product_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"

            first = MODULE.handle_message(
                text="我想定个书柜。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )
            second = MODULE.handle_message(
                text="樱桃木，长2米，高2.4米，深350。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
                execute_quote_when_ready=True,
            )

        self.assertEqual(first["handled_by"], "customer_guided_discovery")
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["pricing_route"], "cabinet_projection_area")
        self.assertIn("正式报价", second["reply_text"])

    def test_executes_projection_area_cabinet_quote_when_precheck_is_ready(self) -> None:
        precheck_args = {
            "category": "衣柜",
            "length": "1.8",
            "height": "2.2",
            "material": "北美樱桃木",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="次卧做个衣柜，1.8米长，2.2米高，北美樱桃木，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                precheck_args=precheck_args,
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "cabinet_projection_area")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：21701元", result["reply_text"])
        self.assertIn("投影面积计价", result["reply_text"])

    def test_infers_cabinet_precheck_args_from_natural_language_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="我家次卧想做个北美黑胡桃木衣柜，长1.8米，高2.2米，深600，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "cabinet_projection_area")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：29225元", result["reply_text"])
        self.assertIn("投影面积计价", result["reply_text"])

    def test_executes_modular_child_bed_quote_when_precheck_is_ready(self) -> None:
        precheck_args = {
            "category": "定制上下床",
            "quote_kind": "custom",
            "bed_form": "上下床",
            "width": "1.2",
            "length": "2",
            "material": "北美樱桃木",
            "access_style": "直梯",
            "access_height": "1.5",
            "lower_bed_type": "架式床",
            "guardrail_style": "篱笆围栏",
            "guardrail_length": "2",
            "guardrail_height": "0.4",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="这个定制上下床参数都齐了，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                precheck_args=precheck_args,
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "modular_child_bed")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：11736元", result["reply_text"])
        self.assertIn("模块化儿童床组合计价", result["reply_text"])

    def test_infers_modular_child_bed_precheck_args_from_natural_language_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="做一张定制上下床，1.2米乘2米，北美白橡木，梯柜款，下层箱体床，胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "modular_child_bed")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：20275元", result["reply_text"])
        self.assertIn("模块化儿童床组合计价", result["reply_text"])

    def test_executes_adult_bed_standard_quote_when_precheck_is_ready(self) -> None:
        precheck_args = {
            "category": "抛物线架式床",
            "width": "1.8",
            "length": "2",
            "material": "北美黑胡桃木",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="这张抛物线架式床参数齐了，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                precheck_args=precheck_args,
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "bed_standard")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：12980元", result["reply_text"])
        self.assertIn("床类标准规则计价", result["reply_text"])

    def test_infers_adult_bed_precheck_args_from_natural_language_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="抛物线架式床，1.8米乘2米，北美黑胡桃木，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "bed_standard")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：12980元", result["reply_text"])
        self.assertIn("床类标准规则计价", result["reply_text"])

    def test_executes_catalog_unit_price_quote_when_precheck_is_ready(self) -> None:
        precheck_args = {
            "category": "升降桌",
            "length": "1.6",
            "depth": "0.7",
            "material": "北美樱桃木",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="这张升降桌直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                precheck_args=precheck_args,
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "catalog_unit_price")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：5380元", result["reply_text"])
        self.assertIn("目录标准单价计价", result["reply_text"])

    def test_infers_catalog_precheck_args_from_natural_language_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="升降桌，1.6米长，0.7米深，北美樱桃木，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "catalog_unit_price")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：5380元", result["reply_text"])
        self.assertIn("目录标准单价计价", result["reply_text"])

    def test_infers_modular_child_bed_combo_precheck_args_from_natural_language_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text=(
                    "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，胶囊围栏，围栏长2米高0.4米，"
                    "梯柜踏步宽520，进深500。床下前后双排衣柜，前后柜体互通形式，"
                    "前面有门无背板的衣柜长2米高1.2米深450，后方无门有背板的衣柜也是长2米高1.2米深450。"
                    "直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(result["status"], "completed")
        self.assertIn("正式报价：29309元", result["reply_text"])
        self.assertIn("床下柜组合计价", result["reply_text"])

    def test_combo_natural_language_with_double_row_intent_but_missing_rear_specs_asks_rear_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text=(
                    "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，胶囊围栏，围栏长2米高0.4米，"
                    "梯柜踏步宽520，进深500。床下前后双排衣柜，前后柜体互通形式，"
                    "前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "precheck_quote")
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(result["missing_fields"], ["rear_cabinet_length"])
        self.assertIn("后排", result["reply_text"])

    def test_combo_follow_up_reuses_pending_precheck_state_and_completes_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，胶囊围栏，围栏长2米高0.4米，"
                    "梯柜踏步宽520，进深500。床下前后双排衣柜，前后柜体互通形式，"
                    "前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="后排也是长2米高1.2米深450，无门有背板。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["handled_by"], "precheck_quote")
        self.assertEqual(first["missing_fields"], ["rear_cabinet_length"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(second["status"], "completed")
        self.assertIn("正式报价：29309元", second["reply_text"])

    def test_consultant_combo_follow_up_keeps_consultant_dual_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "你先帮我整理一版发客户的话术：一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，"
                    "胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500。床下前后双排衣柜，"
                    "前后柜体互通形式，前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="后排也是长2米高1.2米深450，无门有背板。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["audience_role"], "consultant")
        self.assertEqual(first["output_profile"], "consultant_dual")
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "consultant")
        self.assertEqual(second["output_profile"], "consultant_dual")
        self.assertTrue(second["internal_summary"])
        self.assertTrue(second["customer_forward_text"])
        self.assertIn(second["customer_forward_text"], second["reply_text"])

    def test_customer_combo_follow_up_can_switch_to_consultant_output_without_losing_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，"
                    "胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500。床下前后双排衣柜，"
                    "前后柜体互通形式，前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                role_override="customer",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="后排也是长2米高1.2米深450，无门有背板。",
                context_json=self.context_json,
                channel="feishu",
                role_override="consultant",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["audience_role"], "customer")
        self.assertEqual(first["missing_fields"], ["rear_cabinet_length"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "consultant")
        self.assertEqual(second["output_profile"], "consultant_dual")
        self.assertTrue(second["internal_summary"])
        self.assertTrue(second["customer_forward_text"])
        self.assertIn("正式报价：29309元", second["customer_forward_text"])
        self.assertIn(second["customer_forward_text"], second["reply_text"])

    def test_designer_combo_follow_up_keeps_designer_full_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "设计师这边直接正式报价：一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，"
                    "胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500。床下前后双排衣柜，"
                    "前后柜体互通形式，前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="后排也是长2米高1.2米深450，无门有背板。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["audience_role"], "designer")
        self.assertEqual(first["output_profile"], "designer_full")
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "designer")
        self.assertEqual(second["output_profile"], "designer_full")
        self.assertTrue(second["internal_summary"])
        self.assertIn(second["internal_summary"], second["reply_text"])
        self.assertIn("计算过程：", second["reply_text"])
        self.assertIn("正式报价：29309元", second["reply_text"])

    def test_modular_child_bed_follow_up_reuses_pending_precheck_state_and_completes_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "做一张定制上下床，1.2米乘2米，北美白橡木，下层箱体床，"
                    "胶囊围栏，围栏长2米高0.4米，直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="梯柜款，梯柜踏步宽520，进深500。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["handled_by"], "precheck_quote")
        self.assertEqual(first["missing_fields"], ["access_style"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["pricing_route"], "modular_child_bed")
        self.assertEqual(second["status"], "completed")
        self.assertIn("正式报价：20275元", second["reply_text"])

    def test_cabinet_follow_up_reprices_from_formal_state_when_depth_is_corrected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text="我想做个北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="实际进深改成670。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["handled_by"], "format_quote_reply")
        self.assertEqual(first["pricing_route"], "cabinet_projection_area")
        self.assertIn("深0.6米", first["reply_text"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["pricing_route"], "cabinet_projection_area")
        self.assertEqual(second["status"], "completed")
        self.assertIn("深0.67米", second["reply_text"])
        self.assertIn("正式报价：29225元", second["reply_text"])

    def test_consultant_cabinet_formal_adjustment_keeps_consultant_dual_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text="你先帮我整理一版发客户的话术：北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="实际进深改成670。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["audience_role"], "consultant")
        self.assertEqual(first["output_profile"], "consultant_dual")
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "consultant")
        self.assertEqual(second["output_profile"], "consultant_dual")
        self.assertTrue(second["internal_summary"])
        self.assertTrue(second["customer_forward_text"])
        self.assertIn("深0.67米", second["internal_summary"])
        self.assertIn("正式报价：29225元", second["customer_forward_text"])
        self.assertIn(second["customer_forward_text"], second["reply_text"])

    def test_existing_formal_quote_can_be_re_rendered_after_role_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text="我想做个北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                role_override="designer",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="帮我切成顾问模式，整理一版发客户的话术。",
                context_json=self.context_json,
                channel="feishu",
                role_override="consultant",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["audience_role"], "designer")
        self.assertEqual(first["output_profile"], "designer_full")
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "consultant")
        self.assertEqual(second["output_profile"], "consultant_dual")
        self.assertTrue(second["internal_summary"])
        self.assertTrue(second["customer_forward_text"])
        self.assertIn("计算过程：", second["internal_summary"])
        self.assertNotIn("计算过程：", second["customer_forward_text"])
        self.assertIn("正式报价：29225元", second["customer_forward_text"])
        self.assertIn(second["customer_forward_text"], second["reply_text"])

    def test_explicit_new_quote_topic_clears_old_pending_state_and_manual_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，"
                    "胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500。床下前后双排衣柜，"
                    "前后柜体互通形式，前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                role_override="consultant",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="重新来一单，做个北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            latest_state = MODULE.quote_flow_state.load_quote_flow_state(self.conversation_id, cache_root=state_root)

        self.assertEqual(first["audience_role"], "consultant")
        self.assertEqual(first["missing_fields"], ["rear_cabinet_length"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "customer")
        self.assertEqual(second["output_profile"], "customer_simple")
        self.assertEqual(second["pricing_route"], "cabinet_projection_area")
        self.assertIn("正式报价：29225元", second["reply_text"])
        self.assertNotIn("床下后排柜体", second["reply_text"])
        self.assertIsNotNone(latest_state)
        self.assertIsNone(latest_state["manual_override"])
        self.assertEqual(latest_state["active_route"], "cabinet_projection_area")

    def test_broad_new_quote_with_conflicting_route_clears_old_pending_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text=(
                    "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，"
                    "胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500。床下前后双排衣柜，"
                    "前后柜体互通形式，前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                ),
                context_json=self.context_json,
                channel="feishu",
                role_override="consultant",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="做个北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            latest_state = MODULE.quote_flow_state.load_quote_flow_state(self.conversation_id, cache_root=state_root)

        self.assertEqual(first["audience_role"], "consultant")
        self.assertEqual(first["missing_fields"], ["rear_cabinet_length"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["audience_role"], "customer")
        self.assertEqual(second["output_profile"], "customer_simple")
        self.assertEqual(second["pricing_route"], "cabinet_projection_area")
        self.assertIn("正式报价：29225元", second["reply_text"])
        self.assertNotIn("床下后排柜体", second["reply_text"])
        self.assertIsNotNone(latest_state)
        self.assertIsNone(latest_state["manual_override"])
        self.assertEqual(latest_state["active_route"], "cabinet_projection_area")

    def test_cabinet_follow_up_reprices_from_formal_state_when_doors_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            first = MODULE.handle_message(
                text="我想做个北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

            second = MODULE.handle_message(
                text="这组其实不要门。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(first["handled_by"], "format_quote_reply")
        self.assertIn("带门", first["reply_text"])
        self.assertEqual(second["handled_by"], "format_quote_reply")
        self.assertEqual(second["pricing_route"], "cabinet_projection_area")
        self.assertEqual(second["status"], "completed")
        self.assertIn("不带门", second["reply_text"])
        self.assertNotIn("door_type=带门", second["reply_text"])

    def test_cabinet_follow_up_reprices_from_formal_state_when_doors_are_added_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            MODULE.handle_message(
                text="我想做个北美黑胡桃木衣柜，长1.8米，高2.2米，直接正式报价。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )
            removed = MODULE.handle_message(
                text="这组其实不要门。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )
            added_back = MODULE.handle_message(
                text="还是改成带门。",
                context_json=self.context_json,
                channel="feishu",
                execute_quote_when_ready=True,
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertIn("不带门", removed["reply_text"])
        self.assertEqual(added_back["handled_by"], "format_quote_reply")
        self.assertEqual(added_back["pricing_route"], "cabinet_projection_area")
        self.assertEqual(added_back["status"], "completed")
        self.assertIn("带门", added_back["reply_text"])
        self.assertNotIn("不带门", added_back["reply_text"])

    def test_executes_rock_slab_special_adjustment_from_base_quote_payload(self) -> None:
        payload = {
            "items": [
                {
                    "product": "玄关柜",
                    "confirmed": "北美白橡木，岩板台面",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础柜体价格 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="这个岩板台面专项价也直接算进去。",
                context_json=self.context_json,
                channel="feishu",
                quote_payload=payload,
                special_quote={
                    "special_rule": "rock_slab_countertop",
                    "slab_length": "1.8",
                },
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.rock_slab_countertop")
        self.assertIn("岩板台面加价", result["reply_text"])
        self.assertIn("正式报价：37000.8元", result["reply_text"])

    def test_executes_double_sided_door_special_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="双面门这条直接给正式报价。",
                context_json=self.context_json,
                channel="feishu",
                special_quote={
                    "special_rule": "double_sided_door",
                    "material": "北美黑胡桃木",
                    "depth": "0.6",
                    "side_a_family": "frame",
                    "side_b_family": "flat",
                },
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.double_sided_door")
        self.assertIn("正式报价：10410元", result["reply_text"])
        self.assertIn("双面门专项单价计价", result["reply_text"])

    def test_executes_operation_gap_special_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="操作空区这条直接给正式报价。",
                context_json=self.context_json,
                channel="feishu",
                special_quote={
                    "special_rule": "operation_gap",
                    "material": "北美黑胡桃木",
                    "width": "1.2",
                    "height": "0.6",
                },
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.operation_gap")
        self.assertIn("正式报价：1441.44元", result["reply_text"])
        self.assertIn("操作空区专项面积计价", result["reply_text"])

    def test_executes_hidden_rosewood_discount_special_quote(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="非见光玫瑰木折减这条直接给结果。",
                context_json=self.context_json,
                channel="feishu",
                special_quote={
                    "special_rule": "hidden_rosewood_discount",
                    "exposed_material": "北美黑胡桃木",
                    "base_unit_price": 8680,
                },
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.hidden_rosewood_discount")
        self.assertIn("正式报价：7378元/㎡", result["reply_text"])
        self.assertIn("折减计价", result["reply_text"])

    def test_continues_rock_slab_adjustment_from_existing_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "北美白橡木经典玄关柜",
                    "confirmed": "北美白橡木，长1.8米，高2.2米，深0.4米",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": [
                        "投影面积：1.8 × 2.2 = 3.96㎡",
                        "基础单价：8680 元/㎡",
                        "基础价格：3.96 × 8680 = 34372.8 元",
                    ],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "pricing_route": "cabinet_projection_area",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "bundles"
            state_root = Path(tmpdir) / "states"
            self.seed_existing_formal_quote(bundle_root, state_root, payload)

            result = MODULE.handle_message(
                text="这组柜子加岩板台面，岩板长度1.8，直接给我新版正式报价。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.rock_slab_countertop")
        self.assertIn("岩板台面加价", result["reply_text"])
        self.assertIn("正式报价：37000.8元", result["reply_text"])

    def test_continues_operation_gap_adjustment_from_existing_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "北美黑胡桃木电视柜",
                    "confirmed": "北美黑胡桃木，长2.2米，高1.85米，深0.45米",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": [
                        "投影面积：2.2 × 1.85 = 4.07㎡",
                        "基础单价：4880 元/㎡",
                        "基础价格：4.07 × 4880 = 19861.6 元",
                    ],
                    "subtotal": "19861.6元",
                }
            ],
            "total": "19861.6元",
            "pricing_route": "cabinet_projection_area",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "bundles"
            state_root = Path(tmpdir) / "states"
            self.seed_existing_formal_quote(bundle_root, state_root, payload)

            result = MODULE.handle_message(
                text="这单再加一个操作空区，宽1.2米，高0.6米，直接给新版报价。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.operation_gap")
        self.assertIn("操作空区专项面积计价", result["reply_text"])
        self.assertIn("正式报价：1441.44元", result["reply_text"])

    def test_continues_hidden_rosewood_discount_from_existing_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "北美黑胡桃木流云衣柜",
                    "confirmed": "北美黑胡桃木，长1.8米，高2.2米，深0.6米",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": [
                        "投影面积：1.8 × 2.2 = 3.96㎡",
                        "基础单价：8680 元/㎡",
                        "基础价格：3.96 × 8680 = 34372.8 元",
                    ],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "pricing_route": "cabinet_projection_area",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "bundles"
            state_root = Path(tmpdir) / "states"
            self.seed_existing_formal_quote(bundle_root, state_root, payload)

            result = MODULE.handle_message(
                text="这组柜体改成非见光玫瑰木，外露还是北美黑胡桃木，直接给我新版报价。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.hidden_rosewood_discount")
        self.assertIn("正式报价：7378元/㎡", result["reply_text"])

    def test_continues_double_sided_door_quote_from_existing_formal_quote(self) -> None:
        payload = {
            "items": [
                {
                    "product": "北美黑胡桃木玄关柜",
                    "confirmed": "北美黑胡桃木，长1.8米，高2.2米，深0.6米",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": [
                        "投影面积：1.8 × 2.2 = 3.96㎡",
                        "基础单价：8680 元/㎡",
                        "基础价格：3.96 × 8680 = 34372.8 元",
                    ],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
            "pricing_route": "cabinet_projection_area",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "bundles"
            state_root = Path(tmpdir) / "states"
            self.seed_existing_formal_quote(bundle_root, state_root, payload)

            result = MODULE.handle_message(
                text="这组柜体改成双面门，拼框/平板，深0.6米，直接给我新版报价。",
                context_json=self.context_json,
                channel="feishu",
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["pricing_route"], "special_adjustment.double_sided_door")
        self.assertIn("正式报价：10410元", result["reply_text"])

    def test_executes_addendum_guidance_with_consultant_dual_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="你先帮我整理一版发客户的话术：北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，按正式报价怎么回更合适？",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
            )

        self.assertEqual(result["handled_by"], "query_addendum_guidance")
        self.assertEqual(result["audience_role"], "consultant")
        self.assertEqual(result["output_profile"], "consultant_dual")
        self.assertTrue(result["internal_summary"])
        self.assertTrue(result["customer_forward_text"])
        self.assertEqual(result["reply_text"], result["customer_forward_text"])

    def test_size_spec_question_without_product_context_asks_for_product_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="这款没有尺寸吗",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "inquiry_reply")
        self.assertEqual(result["route_result"]["inquiry_family"], "size_spec")
        self.assertIn("产品名", result["reply_text"])
        self.assertIn("产品编号", result["reply_text"])
        self.assertEqual(result["missing_fields"], ["product_context"])

    def test_size_spec_question_with_product_context_can_answer_dimensions_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "states"
            bundle_root = Path(tmpdir) / "bundles"
            result = MODULE.handle_message(
                text="这款没有尺寸吗",
                context_json=self.context_json,
                channel="feishu",
                product_context={
                    "product_name": "穿衣镜",
                    "product_code": "YGP-01",
                },
                state_root=state_root,
                bundle_root=bundle_root,
                disable_addenda=True,
            )
            latest_state = MODULE.quote_flow_state.load_quote_flow_state(self.conversation_id, cache_root=state_root)

        self.assertEqual(result["handled_by"], "inquiry_reply")
        self.assertEqual(result["route_result"]["inquiry_family"], "size_spec")
        self.assertIn("长0.6米", result["reply_text"])
        self.assertIn("深0.12米", result["reply_text"])
        self.assertIn("高1.8米", result["reply_text"])
        self.assertEqual(result["missing_fields"], [])
        self.assertIsNotNone(latest_state)
        self.assertEqual(latest_state["active_inquiry_family"], "size_spec")
        self.assertEqual(latest_state["captured_product_context"]["product_code"], "YGP-01")

    def test_measurement_question_returns_measurement_guidance_instead_of_guided_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="怎么量尺寸",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "inquiry_reply")
        self.assertEqual(result["route_result"]["inquiry_family"], "measurement_installation")
        self.assertIn("总长", result["reply_text"])
        self.assertIn("总高", result["reply_text"])
        self.assertIn("进深", result["reply_text"])
        self.assertNotIn("收纳、睡觉、学习", result["reply_text"])

    def test_lead_time_question_uses_safe_boundary_then_asks_price_key_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="半高床定制的话上门测量，设计，制作安装大概要多久，什么价格",
                context_json=self.context_json,
                channel="feishu",
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "inquiry_reply")
        self.assertEqual(result["route_result"]["inquiry_family"], "lead_time_service")
        self.assertIn("要结合城市、排产和设计确认", result["reply_text"])
        self.assertIn("直梯、斜梯还是梯柜", result["reply_text"])

    def test_size_and_price_question_with_recent_catalog_candidate_explains_matching_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = MODULE.handle_message(
                text="这个4980的是什么尺寸的柜子？",
                context_json=self.context_json,
                channel="feishu",
                product_context={
                    "product_name": "升降桌",
                    "recent_catalog_candidates": [
                        {
                            "sheet": "书桌",
                            "product_code": "SZ-15",
                            "name": "升降桌",
                            "pricing_mode": "unit_price",
                            "dimensions": {
                                "length": 1.6,
                                "depth": 0.7,
                                "height": "620-1270",
                            },
                            "materials": {
                                "乌拉圭玫瑰木": 4980,
                            },
                        }
                    ],
                },
                state_root=Path(tmpdir) / "states",
                bundle_root=Path(tmpdir) / "bundles",
                disable_addenda=True,
            )

        self.assertEqual(result["handled_by"], "inquiry_reply")
        self.assertEqual(result["route_result"]["inquiry_family"], "size_spec")
        self.assertIn("长1.6米", result["reply_text"])
        self.assertIn("深0.7米", result["reply_text"])
        self.assertIn("4980", result["reply_text"])


if __name__ == "__main__":
    unittest.main()
