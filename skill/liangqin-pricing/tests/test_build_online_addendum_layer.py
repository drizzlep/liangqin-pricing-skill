import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_online_addendum_layer.py"
SPEC = importlib.util.spec_from_file_location("build_online_addendum_layer", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)

EXTRACT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_rules_candidate.py"
EXTRACT_SPEC = importlib.util.spec_from_file_location("extract_rules_candidate", EXTRACT_PATH)
EXTRACT = importlib.util.module_from_spec(EXTRACT_SPEC)
assert EXTRACT_SPEC and EXTRACT_SPEC.loader
EXTRACT_SPEC.loader.exec_module(EXTRACT)


class BuildOnlineAddendumLayerTests(unittest.TestCase):
    def test_build_combined_candidate_payload_from_markdown_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            markdown_dir = root / "markdown"
            markdown_dir.mkdir()
            doc_path = markdown_dir / "0001__纹理连续.md"
            doc_path.write_text(
                "# 纹理连续说明\n\n流云门板纹理连续超过0.9m时，需要确认门板长度和门型。\n",
                encoding="utf-8",
            )
            (root / "snapshot-manifest.json").write_text(
                json.dumps(
                    {
                        "workspace": "space-a",
                        "artifacts": [
                            {
                                "snapshot_type": "markdown",
                                "contentType": "ALIDOC",
                                "name": "纹理连续说明",
                                "nodeId": "node-a",
                                "path": "<root>/1.材料/纹理连续说明",
                                "local_path": str(doc_path),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.build_combined_candidate_payload(
                snapshot_dir=root,
                extract_module=EXTRACT,
                ocr_min_chars=-1,
            )

        self.assertEqual(payload["source_format"], "dingtalk_workspace_snapshot")
        self.assertEqual(payload["ocr_backend"], "disabled")
        self.assertEqual(payload["processed_artifact_count"], 1)
        self.assertEqual(payload["skipped_artifact_count"], 0)
        self.assertTrue(payload["sections"])
        section = payload["sections"][0]
        self.assertEqual(section["source_path"], "<root>/1.材料/纹理连续说明")
        self.assertEqual(section["source_title"], "纹理连续说明")
        self.assertEqual(section["source_node_id"], "node-a")
        self.assertEqual(section["source_page"], 1)
        self.assertEqual(section["extract_method"], "dingtalk_markdown")

    def test_build_combined_candidate_payload_passes_paddleocr_options_to_pdf_extractor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = root / "manual.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 fake")
            (root / "snapshot-manifest.json").write_text(
                json.dumps(
                    {
                        "workspace": "space-a",
                        "artifacts": [
                            {
                                "snapshot_type": "pdf",
                                "contentType": "PDF",
                                "name": "设计师手册",
                                "nodeId": "node-pdf",
                                "path": "<root>/manual.pdf",
                                "local_path": str(pdf_path),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            class FakeExtractModule:
                seen_kwargs: dict[str, object] = {}

                @staticmethod
                def build_candidate_payload(path: Path, **kwargs: object) -> dict[str, object]:
                    FakeExtractModule.seen_kwargs = kwargs
                    return {
                        "pages": [
                            {
                                "page": 1,
                                "extract_method": "hybrid",
                                "raw_text": "Paddle recovered",
                            }
                        ],
                        "sections": [
                            {
                                "page": 1,
                                "heading": "1.规则",
                                "content": [],
                                "extract_method": "hybrid",
                            }
                        ],
                    }

            payload = MODULE.build_combined_candidate_payload(
                snapshot_dir=root,
                extract_module=FakeExtractModule,
                ocr_min_chars=80,
                ocr_backend="paddleocr",
                paddleocr_lang="ch",
                paddleocr_device="cpu",
            )

        self.assertEqual(payload["ocr_backend"], "paddleocr")
        self.assertEqual(FakeExtractModule.seen_kwargs["ocr_backend"], "paddleocr")
        self.assertEqual(FakeExtractModule.seen_kwargs["paddleocr_lang"], "ch")
        self.assertEqual(FakeExtractModule.seen_kwargs["paddleocr_device"], "cpu")
        self.assertEqual(payload["pages"][0]["source_title"], "设计师手册")


if __name__ == "__main__":
    unittest.main()
