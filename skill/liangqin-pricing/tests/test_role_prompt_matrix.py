import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "handle_quote_message.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("handle_quote_message", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


ROLE_TO_PROFILE = {
    "customer": "customer_simple",
    "designer": "designer_full",
    "consultant": "consultant_dual",
}


class RolePromptMatrixTests(unittest.TestCase):
    def _context_json(self, role: str, case_id: str) -> str:
        sender_id = f"ou_matrix_{role}_{case_id}"
        return json.dumps(
            {
                "message_id": f"om_matrix_{role}_{case_id}",
                "sender_id": sender_id,
                "sender": sender_id,
                "timestamp": "Wed 2026-04-01 10:26 GMT+8",
            },
            ensure_ascii=False,
        )

    def _run_message(
        self,
        *,
        role: str,
        case_id: str,
        text: str,
        state_root: Path,
        bundle_root: Path,
        **kwargs,
    ) -> dict:
        return MODULE.handle_message(
            text=text,
            context_json=self._context_json(role, case_id),
            channel="feishu",
            role_override=role,
            state_root=state_root,
            bundle_root=bundle_root,
            disable_addenda=True,
            **kwargs,
        )

    def _assert_role_profile(self, result: dict, role: str) -> None:
        self.assertEqual(result["audience_role"], role)
        self.assertEqual(result["output_profile"], ROLE_TO_PROFILE[role])

    def _assert_non_quote_role_shape(self, result: dict, role: str) -> None:
        self._assert_role_profile(result, role)
        if role == "customer":
            self.assertEqual(result["internal_summary"], "")
            self.assertEqual(result["reply_text"], result["customer_forward_text"])
        elif role == "designer":
            self.assertTrue(result["internal_summary"])
            self.assertEqual(result["reply_text"], result["internal_summary"])
            self.assertEqual(result["customer_forward_text"], "")
        else:
            self.assertTrue(result["internal_summary"])
            self.assertTrue(result["customer_forward_text"])
            self.assertEqual(result["reply_text"], result["customer_forward_text"])

    def _assert_quote_role_shape(self, result: dict, role: str, total_text: str) -> None:
        self._assert_role_profile(result, role)
        self.assertEqual(result["handled_by"], "format_quote_reply")
        self.assertEqual(result["status"], "completed")
        if role == "customer":
            self.assertEqual(result["internal_summary"], "")
            self.assertTrue(result["customer_forward_text"])
            self.assertIn(result["customer_forward_text"], result["reply_text"])
            self.assertIn("关键前提：", result["customer_forward_text"])
            self.assertNotIn("计算过程：", result["customer_forward_text"])
            self.assertIn(total_text, result["customer_forward_text"])
        elif role == "designer":
            self.assertTrue(result["internal_summary"])
            self.assertIn(result["internal_summary"], result["reply_text"])
            self.assertEqual(result["customer_forward_text"], "")
            self.assertIn("计算过程：", result["internal_summary"])
            self.assertIn(total_text, result["internal_summary"])
        else:
            self.assertTrue(result["internal_summary"])
            self.assertTrue(result["customer_forward_text"])
            self.assertIn(result["customer_forward_text"], result["reply_text"])
            self.assertIn("计算过程：", result["internal_summary"])
            self.assertNotIn("计算过程：", result["customer_forward_text"])
            self.assertIn(total_text, result["internal_summary"])
            self.assertIn(total_text, result["customer_forward_text"])

    def _run_role_matrix(self, role: str) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            with self.subTest(role=role, case="cabinet_formal_quote"):
                result = self._run_message(
                    role=role,
                    case_id="cabinet_formal_quote",
                    text="我家次卧想做个北美黑胡桃木衣柜，长1.8米，高2.2米，深600，直接正式报价。",
                    state_root=root / "cabinet_formal_quote" / "states",
                    bundle_root=root / "cabinet_formal_quote" / "bundles",
                    execute_quote_when_ready=True,
                )
                self.assertEqual(result["pricing_route"], "cabinet_projection_area")
                self._assert_quote_role_shape(result, role, "正式报价：29225元")

            with self.subTest(role=role, case="modular_child_bed_formal_quote"):
                result = self._run_message(
                    role=role,
                    case_id="modular_child_bed_formal_quote",
                    text="做一张定制上下床，1.2米乘2米，北美白橡木，梯柜款，下层箱体床，胶囊围栏，围栏长2米高0.4米，梯柜踏步宽520，进深500，直接正式报价。",
                    state_root=root / "modular_child_bed_formal_quote" / "states",
                    bundle_root=root / "modular_child_bed_formal_quote" / "bundles",
                    execute_quote_when_ready=True,
                )
                self.assertEqual(result["pricing_route"], "modular_child_bed")
                self._assert_quote_role_shape(result, role, "正式报价：20275元")

            with self.subTest(role=role, case="adult_bed_formal_quote"):
                result = self._run_message(
                    role=role,
                    case_id="adult_bed_formal_quote",
                    text="抛物线架式床，1.8米乘2米，北美黑胡桃木，直接正式报价。",
                    state_root=root / "adult_bed_formal_quote" / "states",
                    bundle_root=root / "adult_bed_formal_quote" / "bundles",
                    execute_quote_when_ready=True,
                )
                self.assertEqual(result["pricing_route"], "bed_standard")
                self._assert_quote_role_shape(result, role, "正式报价：12980元")

            with self.subTest(role=role, case="catalog_unit_price_quote"):
                result = self._run_message(
                    role=role,
                    case_id="catalog_unit_price_quote",
                    text="升降桌，1.6米长，0.7米深，北美樱桃木，直接正式报价。",
                    state_root=root / "catalog_unit_price_quote" / "states",
                    bundle_root=root / "catalog_unit_price_quote" / "bundles",
                    execute_quote_when_ready=True,
                )
                self.assertEqual(result["pricing_route"], "catalog_unit_price")
                self._assert_quote_role_shape(result, role, "正式报价：5380元")

            with self.subTest(role=role, case="combo_incomplete_precheck"):
                result = self._run_message(
                    role=role,
                    case_id="combo_incomplete_precheck",
                    text=(
                        "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，胶囊围栏，围栏长2米高0.4米，"
                        "梯柜踏步宽520，进深500。床下前后双排衣柜，前后柜体互通形式，"
                        "前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                    ),
                    state_root=root / "combo_incomplete_precheck" / "states",
                    bundle_root=root / "combo_incomplete_precheck" / "bundles",
                    execute_quote_when_ready=True,
                )
                self.assertEqual(result["handled_by"], "precheck_quote")
                self.assertEqual(result["status"], "needs_input")
                self.assertEqual(result["pricing_route"], "modular_child_bed_combo")
                self.assertEqual(result["missing_fields"], ["rear_cabinet_length"])
                self.assertIn("后排", result["reply_text"])
                self._assert_non_quote_role_shape(result, role)

            with self.subTest(role=role, case="combo_follow_up_quote"):
                state_root = root / "combo_follow_up_quote" / "states"
                bundle_root = root / "combo_follow_up_quote" / "bundles"
                first = self._run_message(
                    role=role,
                    case_id="combo_follow_up_quote",
                    text=(
                        "一张半高梯柜上铺床1.2*2米床垫尺寸的，北美白蜡木，胶囊围栏，围栏长2米高0.4米，"
                        "梯柜踏步宽520，进深500。床下前后双排衣柜，前后柜体互通形式，"
                        "前面有门无背板的衣柜长2米高1.2米深450。直接正式报价。"
                    ),
                    state_root=state_root,
                    bundle_root=bundle_root,
                    execute_quote_when_ready=True,
                )
                second = self._run_message(
                    role=role,
                    case_id="combo_follow_up_quote",
                    text="后排也是长2米高1.2米深450，无门有背板。",
                    state_root=state_root,
                    bundle_root=bundle_root,
                    execute_quote_when_ready=True,
                )
                self.assertEqual(first["missing_fields"], ["rear_cabinet_length"])
                self.assertEqual(second["pricing_route"], "modular_child_bed_combo")
                self._assert_quote_role_shape(second, role, "正式报价：29309元")

            with self.subTest(role=role, case="addendum_quote_follow_up"):
                result = self._run_message(
                    role=role,
                    case_id="addendum_quote_follow_up",
                    text="北美黑胡桃木流云衣柜，长1.8米，高2.2米，深670，按正式报价怎么回更合适？",
                    state_root=root / "addendum_quote_follow_up" / "states",
                    bundle_root=root / "addendum_quote_follow_up" / "bundles",
                )
                self.assertEqual(result["handled_by"], "query_addendum_guidance")
                self.assertIn("柜门", result["reply_text"])
                self._assert_non_quote_role_shape(result, role)

            with self.subTest(role=role, case="rule_consultation"):
                result = self._run_message(
                    role=role,
                    case_id="rule_consultation",
                    text="常规拆装柜体高度1700以内默认做顶盖侧还是侧盖顶？",
                    state_root=root / "rule_consultation" / "states",
                    bundle_root=root / "rule_consultation" / "bundles",
                )
                self.assertEqual(result["handled_by"], "query_addendum_guidance")
                self.assertIn("默认顶盖侧", result["reply_text"])
                self._assert_non_quote_role_shape(result, role)

            with self.subTest(role=role, case="special_rule_detection"):
                result = self._run_message(
                    role=role,
                    case_id="special_rule_detection",
                    text="双面门这条是什么规则？",
                    state_root=root / "special_rule_detection" / "states",
                    bundle_root=root / "special_rule_detection" / "bundles",
                )
                self.assertEqual(result["handled_by"], "detect_special_cabinet_rule")
                self.assertIn("两边分别是什么门型", result["reply_text"])
                self._assert_non_quote_role_shape(result, role)

            with self.subTest(role=role, case="image_request_after_formal_quote"):
                state_root = root / "image_request_after_formal_quote" / "states"
                bundle_root = root / "image_request_after_formal_quote" / "bundles"
                self._run_message(
                    role=role,
                    case_id="image_request_after_formal_quote",
                    text="我家次卧想做个北美黑胡桃木衣柜，长1.8米，高2.2米，深600，直接正式报价。",
                    state_root=state_root,
                    bundle_root=bundle_root,
                    execute_quote_when_ready=True,
                )
                image_result = MODULE.handle_message(
                    text="生成图片",
                    context_json=self._context_json(role, "image_request_after_formal_quote"),
                    channel="feishu",
                    state_root=state_root,
                    bundle_root=bundle_root,
                    media_root=root / "image_request_after_formal_quote" / "media",
                    renderer=lambda **_: {
                        "image_path": str(root / "image_request_after_formal_quote" / "media" / "quote-card.png"),
                        "html_path": str(root / "image_request_after_formal_quote" / "media" / "quote-card.html"),
                        "bundle_path": str(root / "image_request_after_formal_quote" / "media" / "bundle.json"),
                        "json_path": str(root / "image_request_after_formal_quote" / "media" / "view-model.json"),
                        "width": 1200,
                        "height": 1600,
                    },
                )
                self._assert_role_profile(image_result, role)
                self.assertEqual(image_result["handled_by"], "generate_quote_card_reply")
                self.assertEqual(image_result["internal_summary"], "")
                self.assertEqual(image_result["reply_text"], image_result["customer_forward_text"])
                self.assertTrue(str(image_result["media_url"]).endswith("quote-card.png"))

    def test_customer_role_prompt_matrix(self) -> None:
        self._run_role_matrix("customer")

    def test_designer_role_prompt_matrix(self) -> None:
        self._run_role_matrix("designer")

    def test_consultant_role_prompt_matrix(self) -> None:
        self._run_role_matrix("consultant")


if __name__ == "__main__":
    unittest.main()
