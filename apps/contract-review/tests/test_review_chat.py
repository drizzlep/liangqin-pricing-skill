import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
CLI_ROOT = APP_ROOT / "cli"
for root in (CORE_ROOT, CLI_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

MODULE_PATH = CLI_ROOT / "review_chat.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REVIEW_CHAT = load_module("contract_review_review_chat_cli", MODULE_PATH)


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


class ReviewChatTests(unittest.TestCase):
    def test_chat_returns_single_follow_up_question_when_required_field_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：床",
                    "本单按成品执行",
                    "长度：2000mm",
                    "材质：北美白蜡木",
                    "费用合计：8200元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )

        self.assertEqual(payload["handled_by"], "contract_review_chat")
        self.assertEqual(payload["review_card"]["priority"], "p1")
        self.assertIn("宽度", payload["reply_text"])
        self.assertEqual(payload["next_question"], "请先核对这份合同的宽度（width）。")

    def test_chat_can_mark_last_job_as_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )
            payload = REVIEW_CHAT.run(
                [
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--text",
                    "标记已核对",
                    "--output-mode",
                    "json",
                ]
            )

            feedback_path = root / "runtime" / "jobs" / "batch-chat-001" / "output" / "review-feedback.json"
            self.assertTrue(feedback_path.exists())
            saved = json.loads(feedback_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["action"], "marked_reviewed")
        self.assertEqual(saved["human_decision"], "reviewed")

    def test_chat_mark_reviewed_can_capture_root_cause_and_corrected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )
            payload = REVIEW_CHAT.run(
                [
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--text",
                    "标记已核对 结论=确认问题 原因=template_alias_missing 字段=product_category:书柜,width:1500mm",
                    "--output-mode",
                    "json",
                ]
            )

            feedback_path = root / "runtime" / "jobs" / "batch-chat-001" / "output" / "review-feedback.json"
            self.assertTrue(feedback_path.exists())
            saved = json.loads(feedback_path.read_text(encoding="utf-8"))
            template_files = list((root / "runtime" / "templates").glob("*.json"))
            self.assertEqual(len(template_files), 1)
            template_profile = json.loads(template_files[0].read_text(encoding="utf-8"))

        self.assertEqual(payload["action"], "marked_reviewed")
        self.assertEqual(saved["human_decision"], "confirmed")
        self.assertEqual(saved["confirmed_root_cause"], "template_alias_missing")
        self.assertEqual(saved["corrected_fields"]["product_category"], "书柜")
        self.assertEqual(saved["corrected_fields"]["width"], "1500mm")
        self.assertEqual(saved["template_profile_update"]["learned_field_names"], ["product_category", "width"])
        self.assertIn("template_alias_missing", payload["reply_text"])
        self.assertEqual(template_profile["human_decision_breakdown"]["confirmed"], 1)
        self.assertIn("1500mm", template_profile["field_aliases"]["width"]["confirmed_values"])

    def test_chat_can_execute_template_quick_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )
            dashboard = json.loads(
                (root / "runtime" / "batches" / "batch-chat" / "batch-dashboard.json").read_text(encoding="utf-8")
            )
            action_id = dashboard["template_learning_top_templates"][0]["quick_actions"][0]["action_id"]
            payload = REVIEW_CHAT.run(
                [
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--text",
                    f"执行模板快捷动作 {action_id}",
                    "--output-mode",
                    "json",
                ]
            )
            feedback_path = root / "runtime" / "jobs" / "batch-chat-001" / "output" / "review-feedback.json"
            saved = json.loads(feedback_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["action"], "executed_template_quick_action")
        self.assertEqual(payload["quick_action"]["action_id"], action_id)
        self.assertEqual(saved["job_id"], "batch-chat-001")
        self.assertIn("已执行模板快捷动作", payload["reply_text"])


if __name__ == "__main__":
    unittest.main()
