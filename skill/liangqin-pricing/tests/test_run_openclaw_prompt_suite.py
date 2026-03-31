import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_openclaw_prompt_suite.py"
SUITE_PATH = Path(__file__).resolve().parents[1] / "references" / "current" / "openclaw-prompt-suite.json"
SPEC = importlib.util.spec_from_file_location("run_openclaw_prompt_suite", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RunOpenClawPromptSuiteTests(unittest.TestCase):
    def test_load_suite_requires_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suite.json"
            path.write_text(json.dumps({"cases": [{"id": "a"}]}, ensure_ascii=False), encoding="utf-8")
            payload = MODULE.load_suite(path)
        self.assertEqual(len(payload["cases"]), 1)

    def test_filter_cases_respects_case_ids_category_and_limit(self) -> None:
        cases = [
            {"id": "a", "category": "smoke"},
            {"id": "b", "category": "child-bed-modular"},
            {"id": "c", "category": "child-bed-modular"},
        ]
        filtered = MODULE.filter_cases(cases, ["b", "c"], ["child-bed-modular"], 1)
        self.assertEqual(filtered, [{"id": "b", "category": "child-bed-modular"}])

    def test_evaluate_text_detects_missing_and_forbidden_keywords(self) -> None:
        result = MODULE.evaluate_text("正式报价，含超深15%", ["正式报价", "超深", "北美黑胡桃木"], ["参考总价"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_expected_keywords"], ["北美黑胡桃木"])
        self.assertEqual(result["missing_expected_any_groups"], [])
        self.assertEqual(result["forbidden_keyword_hits"], [])

    def test_evaluate_text_supports_expected_any_keyword_groups(self) -> None:
        result = MODULE.evaluate_text(
            "请先确认左开还是右开。",
            [],
            [],
            [["开启方式", "左开", "右开"]],
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["missing_expected_any_groups"], [])

    def test_evaluate_validation_assertions_reports_output_contract_and_boundary_status(self) -> None:
        text = (
            "产品：流云衣柜\n已确认：北美黑胡桃木\n这次按投影面积计价。\n计算过程：\n"
            "- 基础价格 = 1.8 × 2.2 × 8680 = 34372.8\n小计：34372.8元\n\n正式报价：34372.8元"
        )
        evaluation = MODULE.evaluate_text(text, ["正式报价"], ["BLUMOTION"])

        assertion_results = MODULE.evaluate_validation_assertions(
            text=text,
            evaluation=evaluation,
            assertion_names=["output_contract_pass", "no_boundary_pollution", "formula_correct"],
        )

        self.assertTrue(assertion_results["output_contract_pass"]["passed"])
        self.assertTrue(assertion_results["no_boundary_pollution"]["passed"])
        self.assertTrue(assertion_results["formula_correct"]["passed"])

    def test_extract_json_payload_reads_last_json_body(self) -> None:
        raw = "[plugins] registered\n{\"result\": {\"payloads\": [{\"text\": \"hello\"}]}}"
        payload = MODULE.extract_json_payload(raw)
        self.assertEqual(payload["result"]["payloads"][0]["text"], "hello")

    def test_is_incomplete_text_detects_tool_call_end_turn_and_trailing_colon(self) -> None:
        self.assertTrue(MODULE.is_incomplete_text(""))
        self.assertTrue(MODULE.is_incomplete_text("<end_turn>"))
        self.assertTrue(MODULE.is_incomplete_text("[TOOL_CALL]\n{tool => \"exec\"}"))
        self.assertTrue(MODULE.is_incomplete_text("好的，我来先确认一下："))
        self.assertFalse(MODULE.is_incomplete_text("请告诉我后排柜体进深是多少？"))

    def test_run_case_retries_incomplete_output_once(self) -> None:
        outputs = [
            SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='{"result":{"payloads":[{"text":"<end_turn>"}]}}',
            ),
            SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='{"result":{"payloads":[{"text":"请告诉我后排柜体进深是多少？"}]}}',
            ),
        ]

        def fake_run_step(_command):
            return outputs.pop(0)

        original = MODULE.run_step
        MODULE.run_step = fake_run_step
        try:
            result = MODULE.run_case(
                {
                    "id": "rear-depth",
                    "category": "child-bed-modular",
                    "message": "后排进深缺失",
                    "expected_keywords": ["后排", "进深"],
                },
                thinking="minimal",
                timeout=30,
                max_retries=1,
            )
        finally:
            MODULE.run_step = original

        self.assertEqual(result["attempt_count"], 2)
        self.assertTrue(result["evaluation"]["passed"])
        self.assertIn("后排柜体进深", result["final_text"])

    def test_run_case_repeats_same_case_and_fails_if_any_run_fails(self) -> None:
        outputs = [
            SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='{"result":{"payloads":[{"text":"现有良禽资料里没有明确写到，建议联系设计师确认。"}]}}',
            ),
            SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='{"result":{"payloads":[{"text":"BLUMOTION 阻尼铰链和抽屉导轨都可以作为参考。"}]}}',
            ),
        ]

        def fake_run_step(_command):
            return outputs.pop(0)

        original = MODULE.run_step
        MODULE.run_step = fake_run_step
        try:
            result = MODULE.run_case(
                {
                    "id": "hardware-boundary",
                    "category": "negative",
                    "message": "良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？",
                    "expected_any_keywords": [["现有良禽资料", "资料里没有明确"]],
                    "forbidden_keywords": ["BLUMOTION", "抽屉导轨"],
                    "repeat_count": 2,
                },
                thinking="minimal",
                timeout=30,
                max_retries=0,
            )
        finally:
            MODULE.run_step = original

        self.assertEqual(result["run_count"], 2)
        self.assertFalse(result["evaluation"]["passed"])
        self.assertEqual(len(result["runs"]), 2)
        self.assertIn("BLUMOTION", result["runs"][1]["evaluation"]["forbidden_keyword_hits"])

    def test_run_case_records_validation_assertions(self) -> None:
        outputs = [
            SimpleNamespace(
                returncode=0,
                stderr="",
                stdout='{"result":{"payloads":[{"text":"产品：流云衣柜\\n已确认：北美黑胡桃木\\n这次按投影面积计价。\\n计算过程：\\n- 基础价格 = 1.8 × 2.2 × 8680 = 34372.8\\n小计：34372.8元\\n\\n正式报价：34372.8元"}]}}',
            )
        ]

        def fake_run_step(_command):
            return outputs.pop(0)

        original = MODULE.run_step
        MODULE.run_step = fake_run_step
        try:
            result = MODULE.run_case(
                {
                    "id": "formal-quote-contract",
                    "category": "smoke",
                    "message": "流云衣柜正式报价",
                    "expected_keywords": ["正式报价"],
                    "validation_assertions": ["output_contract_pass", "formula_correct"],
                },
                thinking="minimal",
                timeout=30,
                max_retries=0,
            )
        finally:
            MODULE.run_step = original

        self.assertTrue(result["evaluation"]["validation_assertions"]["output_contract_pass"]["passed"])
        self.assertTrue(result["evaluation"]["validation_assertions"]["formula_correct"]["passed"])

    def test_current_suite_contains_expanded_child_bed_modular_matrix(self) -> None:
        payload = MODULE.load_suite(SUITE_PATH)
        child_bed_cases = [case for case in payload["cases"] if case.get("category") == "child-bed-modular"]
        child_bed_case_ids = {case.get("id") for case in child_bed_cases}

        self.assertGreaterEqual(len(child_bed_cases), 10)
        self.assertIn("loft-double-row-wardrobe-formal-quote", child_bed_case_ids)

    def test_current_suite_contains_hardware_boundary_negative_case(self) -> None:
        payload = MODULE.load_suite(SUITE_PATH)
        case_map = {case.get("id"): case for case in payload["cases"]}

        self.assertIn("hardware-brand-boundary-no-pollution", case_map)
        self.assertGreaterEqual(int(case_map["hardware-brand-boundary-no-pollution"].get("repeat_count", 0)), 3)

    def test_build_reset_command_supports_feishu(self) -> None:
        command = MODULE.build_reset_command(Path("/tmp/skill/scripts"), include_feishu=True)
        self.assertEqual(command[-2:], ["--apply", "--include-feishu"])


if __name__ == "__main__":
    unittest.main()
