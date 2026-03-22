import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_openclaw_prompt_suite.py"
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

    def test_filter_cases_respects_case_ids_and_limit(self) -> None:
        cases = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        filtered = MODULE.filter_cases(cases, ["b", "c"], 1)
        self.assertEqual(filtered, [{"id": "b"}])

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


if __name__ == "__main__":
    unittest.main()
