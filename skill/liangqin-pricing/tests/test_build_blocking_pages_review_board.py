import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_blocking_pages_review_board.py"
SPEC = importlib.util.spec_from_file_location("build_blocking_pages_review_board", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildBlockingPagesReviewBoardTests(unittest.TestCase):
    def test_collect_blocking_pages_merges_unknown_pages_and_empty_ocr_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            (report_dir / "quality-sample-board.json").write_text(
                json.dumps(
                    {
                        "samples": [
                            {
                                "source_title": "图示页",
                                "source_page": 2,
                                "source_local_path": "/tmp/a.pdf",
                                "ocr": {"status": "empty"},
                            },
                            {
                                "source_title": "另一个空页",
                                "source_page": 3,
                                "source_local_path": "/tmp/b.pdf",
                                "ocr": {"status": "empty"},
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rules_candidate = {
                "pages": [
                    {
                        "source_title": "图示页",
                        "source_page": 2,
                        "source_local_path": "/tmp/a.pdf",
                        "extract_method": "unknown",
                    },
                    {
                        "source_title": "普通页",
                        "source_page": 1,
                        "source_local_path": "/tmp/c.pdf",
                        "extract_method": "text_layer",
                    },
                ]
            }

            pages = MODULE.collect_blocking_pages(rules_candidate, report_dir)

        self.assertEqual(len(pages), 2)
        reasons = {page["source_title"]: page["_blocking_reason"] for page in pages}
        self.assertEqual(reasons["图示页"], "PDF 文字层为空；PaddleOCR 抽样为空")
        self.assertEqual(reasons["另一个空页"], "PaddleOCR 抽样为空")

    def test_infer_default_decision_uses_human_friendly_categories(self) -> None:
        high_risk = {
            "source_title": "岩板",
            "image_count": 5,
            "ocr": {"status": "succeeded", "text": "岩板尺寸限制必须确认，报价需要另算。" * 5},
        }
        image_only = {"source_title": "图示", "image_count": 4, "ocr": {"status": "empty", "text": ""}}

        self.assertEqual(MODULE.infer_default_decision(high_risk)[0], "暂缓激活")
        self.assertEqual(MODULE.infer_default_decision(image_only)[0], "必须看图")

    def test_render_html_contains_review_choices_and_filter_without_source_pollution(self) -> None:
        model = {
            "candidate_layer": "online",
            "candidate_status": "PAUSED",
            "html_path": "/tmp/blocking-pages-review-board.html",
            "blocking_page_count": 1,
            "ocr_status_counts": {"empty": 1},
            "image_status_counts": {"succeeded": 1},
            "summary": "阻断页复核包",
            "pages": [
                {
                    "source_title": "图示页",
                    "source_page": 2,
                    "_blocking_reason": "PDF 文字层为空",
                    "default_decision": "必须看图",
                    "default_decision_reason": "图片较多，需要人工看截图。",
                    "image_count": 4,
                    "ocr": {"status": "empty", "text": "", "char_count": 0},
                    "image": {"status": "succeeded", "path": "/tmp/page.png"},
                }
            ],
        }

        html = MODULE.render_html(model)

        self.assertIn("这些页先看完，再决定能不能激活线上版", html)
        self.assertIn("不影响规则", html)
        self.assertIn("OCR 可用", html)
        self.assertIn("必须看图", html)
        self.assertIn("暂缓激活", html)
        self.assertNotIn("https://alidocs2", html)
        self.assertNotIn("Signature=", html)


if __name__ == "__main__":
    unittest.main()
