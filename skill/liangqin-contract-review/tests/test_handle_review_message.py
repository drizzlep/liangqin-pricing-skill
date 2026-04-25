from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from zipfile import ZipFile


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

MODULE_PATH = SCRIPTS_ROOT / "handle_review_message.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HANDLE_REVIEW_MESSAGE = load_module("liangqin_contract_review_handle_review_message", MODULE_PATH)


def write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    document_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>',
    ]
    for paragraph in paragraphs:
        document_xml.append(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>")
    document_xml.append("</w:body></w:document>")
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "".join(document_xml))


class HandleReviewMessageTests(unittest.TestCase):
    def test_inline_openclaw_metadata_builds_conversation_scoped_state_root_without_explicit_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.pdf"
            runtime_root = root / "runtime"
            contract_path.write_text("%PDF-1.4", encoding="utf-8")

            captured: dict[str, object] = {}
            original_main = HANDLE_REVIEW_MESSAGE.review_chat.main

            def fake_main(argv: list[str] | None = None) -> int:
                captured["argv"] = list(argv or [])
                return 0

            HANDLE_REVIEW_MESSAGE.review_chat.main = fake_main
            try:
                exit_code = HANDLE_REVIEW_MESSAGE.main(
                    [
                        "--text",
                        (
                            "Conversation info (untrusted metadata):\n"
                            "```json\n"
                            "{\n"
                            '  "chat_id": "03676533111017629",\n'
                            '  "message_id": "msgxvgkTNUXrudgmpBTzmICog==",\n'
                            '  "sender_id": "03676533111017629",\n'
                            '  "sender": "米田"\n'
                            "}\n"
                            "```\n\n"
                            "Sender (untrusted metadata):\n"
                            "```json\n"
                            "{\n"
                            '  "label": "米田 (03676533111017629)",\n'
                            '  "id": "03676533111017629",\n'
                            '  "name": "米田"\n'
                            "}\n"
                            "```\n\n"
                            "用良禽佳木检查审核这份 pdf 合同"
                        ),
                        "--input-path",
                        str(contract_path),
                        "--runtime-root",
                        str(runtime_root),
                    ]
                )
            finally:
                HANDLE_REVIEW_MESSAGE.review_chat.main = original_main

            self.assertEqual(exit_code, 0)
            forwarded_argv = list(captured["argv"])
            self.assertIn("--state-root", forwarded_argv)
            state_root = Path(forwarded_argv[forwarded_argv.index("--state-root") + 1])
            self.assertTrue(str(state_root).startswith(str(runtime_root.resolve())))
            self.assertIn("03676533111017629", str(state_root))
            forwarded_text = forwarded_argv[forwarded_argv.index("--text") + 1]
            self.assertNotIn("Conversation info", forwarded_text)
            self.assertIn("审核这份 pdf 合同", forwarded_text)

            batch_dir = Path(forwarded_argv[forwarded_argv.index("--batch-dir") + 1])
            manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_channel"], "openclaw")
            self.assertEqual(manifest["openclaw_context"]["context_source"], "inline_text_metadata")
            self.assertEqual(manifest["openclaw_context"]["channel_source"], "inline_text_fallback")
            self.assertEqual(manifest["openclaw_context"]["conversation_slug"], "03676533111017629")

    def test_resolve_app_root_supports_bundled_skill_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script_path = root / "liangqin-contract-review" / "scripts" / "handle_review_message.py"
            bundled_app_root = root / "liangqin-contract-review" / "apps" / "contract-review"
            script_path.parent.mkdir(parents=True)
            bundled_app_root.mkdir(parents=True)
            script_path.write_text("# test\n", encoding="utf-8")

            resolved = HANDLE_REVIEW_MESSAGE._resolve_app_root(script_path)

            self.assertEqual(resolved.resolve(), bundled_app_root.resolve())

    def test_single_input_file_is_wrapped_into_temp_batch_before_review_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.docx"
            runtime_root = root / "runtime"
            write_minimal_docx(contract_path, ["甲方：客户A", "费用合计：19800元"])

            captured: dict[str, object] = {}
            original_main = HANDLE_REVIEW_MESSAGE.review_chat.main

            def fake_main(argv: list[str] | None = None) -> int:
                captured["argv"] = list(argv or [])
                return 0

            HANDLE_REVIEW_MESSAGE.review_chat.main = fake_main
            try:
                exit_code = HANDLE_REVIEW_MESSAGE.main(
                    [
                        "--text",
                        "审这份合同",
                        "--input-path",
                        str(contract_path),
                        "--runtime-root",
                        str(runtime_root),
                    ]
                )
            finally:
                HANDLE_REVIEW_MESSAGE.review_chat.main = original_main

            self.assertEqual(exit_code, 0)
            forwarded_argv = list(captured["argv"])
            self.assertIn("--batch-dir", forwarded_argv)
            batch_dir = Path(forwarded_argv[forwarded_argv.index("--batch-dir") + 1])
            self.assertTrue(batch_dir.exists())
            manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_type"], "openclaw_attachment_batch")
            self.assertEqual(manifest["source_channel"], "openclaw")
            self.assertEqual(manifest["jobs"][0]["job_key"], "合同")
            staged_path = batch_dir / manifest["jobs"][0]["paths"][0]
            self.assertTrue(staged_path.exists())
            self.assertEqual(staged_path.resolve(), contract_path.resolve())

    def test_directory_input_expands_each_contract_file_into_separate_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_dir = root / "contracts"
            source_dir.mkdir(parents=True)
            runtime_root = root / "runtime"
            write_minimal_docx(source_dir / "合同A.docx", ["甲方：客户A"])
            (source_dir / "合同B.pdf").write_text("%PDF-1.4", encoding="utf-8")
            (source_dir / "notes.txt").write_text("ignore", encoding="utf-8")

            captured: dict[str, object] = {}
            original_main = HANDLE_REVIEW_MESSAGE.review_chat.main

            def fake_main(argv: list[str] | None = None) -> int:
                captured["argv"] = list(argv or [])
                return 0

            HANDLE_REVIEW_MESSAGE.review_chat.main = fake_main
            try:
                exit_code = HANDLE_REVIEW_MESSAGE.main(
                    [
                        "--text",
                        "检查这批合同",
                        "--input-path",
                        str(source_dir),
                        "--runtime-root",
                        str(runtime_root),
                    ]
                )
            finally:
                HANDLE_REVIEW_MESSAGE.review_chat.main = original_main

            self.assertEqual(exit_code, 0)
            forwarded_argv = list(captured["argv"])
            batch_dir = Path(forwarded_argv[forwarded_argv.index("--batch-dir") + 1])
            manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["jobs"]), 2)
            self.assertEqual(
                [item["job_key"] for item in manifest["jobs"]],
                ["合同A", "合同B"],
            )

    def test_context_json_and_channel_build_conversation_scoped_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.docx"
            runtime_root = root / "runtime"
            write_minimal_docx(contract_path, ["甲方：客户A", "费用合计：19800元"])

            captured: dict[str, object] = {}
            original_main = HANDLE_REVIEW_MESSAGE.review_chat.main

            def fake_main(argv: list[str] | None = None) -> int:
                captured["argv"] = list(argv or [])
                return 0

            HANDLE_REVIEW_MESSAGE.review_chat.main = fake_main
            try:
                exit_code = HANDLE_REVIEW_MESSAGE.main(
                    [
                        "--text",
                        "审这份合同",
                        "--input-path",
                        str(contract_path),
                        "--runtime-root",
                        str(runtime_root),
                        "--channel",
                        "dingtalk-connector",
                        "--context-json",
                        json.dumps(
                            {
                                "sender_id": "user-001",
                                "message_id": "msg-001",
                                "group_channel": "ding-group-001",
                                "is_group_chat": True,
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
            finally:
                HANDLE_REVIEW_MESSAGE.review_chat.main = original_main

            self.assertEqual(exit_code, 0)
            forwarded_argv = list(captured["argv"])
            self.assertIn("--state-root", forwarded_argv)
            state_root = Path(forwarded_argv[forwarded_argv.index("--state-root") + 1])
            self.assertTrue(str(state_root).startswith(str(runtime_root.resolve())))
            self.assertIn("ding-group-001", str(state_root))

    def test_text_mode_emits_precheck_status_before_review_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.docx"
            runtime_root = root / "runtime"
            write_minimal_docx(contract_path, ["甲方：客户A", "费用合计：19800元"])

            original_main = HANDLE_REVIEW_MESSAGE.review_chat.main

            def fake_main(argv: list[str] | None = None) -> int:
                return 0

            HANDLE_REVIEW_MESSAGE.review_chat.main = fake_main
            try:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = HANDLE_REVIEW_MESSAGE.main(
                        [
                            "--text",
                            "审这份合同",
                            "--input-path",
                            str(contract_path),
                            "--runtime-root",
                            str(runtime_root),
                        ]
                    )
            finally:
                HANDLE_REVIEW_MESSAGE.review_chat.main = original_main

            self.assertEqual(exit_code, 0)
            self.assertIn("正在预检中", stdout.getvalue())
            self.assertIn("报价系统做金额与字段对账", stdout.getvalue())

    def test_fresh_review_request_without_input_does_not_fallback_to_previous_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_root = root / "runtime"

            original_main = HANDLE_REVIEW_MESSAGE.review_chat.main

            def fake_main(argv: list[str] | None = None) -> int:
                raise AssertionError("fresh review request without attachment should not call review_chat")

            HANDLE_REVIEW_MESSAGE.review_chat.main = fake_main
            try:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = HANDLE_REVIEW_MESSAGE.main(
                        [
                            "--text",
                            "请审核这份合同",
                            "--runtime-root",
                            str(runtime_root),
                        ]
                    )
            finally:
                HANDLE_REVIEW_MESSAGE.review_chat.main = original_main

            self.assertEqual(exit_code, 0)
            self.assertIn("没有收到新的合同附件", stdout.getvalue())
            self.assertIn("--input-path", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
