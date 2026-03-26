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

    def test_current_suite_contains_expanded_child_bed_modular_matrix(self) -> None:
        payload = MODULE.load_suite(SUITE_PATH)
        child_bed_cases = [case for case in payload["cases"] if case.get("category") == "child-bed-modular"]
        child_bed_case_ids = {case.get("id") for case in child_bed_cases}

        self.assertGreaterEqual(len(child_bed_cases), 10)
        self.assertIn("loft-double-row-wardrobe-formal-quote", child_bed_case_ids)

    def test_build_reset_command_supports_feishu(self) -> None:
        command = MODULE.build_reset_command(Path("/tmp/skill/scripts"), include_feishu=True)
        self.assertEqual(command[-2:], ["--apply", "--include-feishu"])


if __name__ == "__main__":
    unittest.main()
