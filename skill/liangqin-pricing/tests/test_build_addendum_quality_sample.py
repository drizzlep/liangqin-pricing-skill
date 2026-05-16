import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_addendum_quality_sample.py"
SPEC = importlib.util.spec_from_file_location("build_addendum_quality_sample", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildAddendumQualitySampleTests(unittest.TestCase):
    def test_select_page_samples_prioritizes_pages_that_need_human_review(self) -> None:
        pages = [
            {
                "source_title": "扫描页",
                "source_page": 1,
                "source_local_path": "/tmp/a.pdf",
                "extract_method": "unknown",
                "image_count": 2,
                "raw_text": "",
            },
            {
                "source_title": "图示页",
                "source_page": 2,
                "source_local_path": "/tmp/b.pdf",
                "extract_method": "text_layer",
                "image_count": 6,
                "raw_text": "柜体尺寸限制，必须确认。",
            },
            {
                "source_title": "短文字页",
                "source_page": 3,
                "source_local_path": "/tmp/c.pdf",
                "extract_method": "text_layer",
                "image_count": 1,
                "raw_text": "图示",
            },
            {
                "source_title": "普通页",
                "source_page": 4,
                "source_local_path": "/tmp/d.pdf",
                "extract_method": "text_layer",
                "image_count": 0,
                "raw_text": "这是一段足够长的普通文字，用来做稳定性抽查。" * 8,
            },
        ]

        samples = MODULE.select_page_samples(pages, sample_size=4)
        reason_text = "\n".join(" / ".join(sample.get("_sample_reasons", [])) for sample in samples)

        self.assertEqual(samples[0]["source_title"], "扫描页")
        self.assertIn("PDF 文字层没有读到内容", reason_text)
        self.assertIn("图片较多", reason_text)
        self.assertIn("文字很少", reason_text)

    def test_quality_verdict_blocks_when_unknown_pages_exist(self) -> None:
        pages = [{"extract_method": "unknown"}, {"extract_method": "text_layer"}]

        verdict, summary = MODULE.quality_verdict([], pages)

        self.assertEqual(verdict, "needs_review")
        self.assertIn("没有读到内容", summary)

    def test_quality_verdict_accepts_closed_unknown_page_ledger(self) -> None:
        pages = [{"extract_method": "unknown"}, {"extract_method": "text_layer"}]
        closure = {"exists": True, "unknown_page_count": 1, "unresolved_count": 0}

        verdict, summary = MODULE.quality_verdict([], pages, closure)

        self.assertEqual(verdict, "full_document_closed")
        self.assertIn("已全部写入", summary)

    def test_render_html_is_human_facing_and_not_technical_table_first(self) -> None:
        model = {
            "candidate_layer": "online",
            "html_path": "/tmp/quality-sample-board.html",
            "verdict": "needs_review",
            "summary": "有 1 页 PDF 文字层没有读到内容。",
            "page_count": 2,
            "unknown_page_count": 1,
            "image_heavy_count": 1,
            "ocr_checked_count": 1,
            "ocr_status_counts": {"succeeded": 1},
            "samples": [
                {
                    "source_title": "扫描页",
                    "source_page": 1,
                    "extract_method": "unknown",
                    "image_count": 2,
                    "raw_text": "",
                    "_sample_reasons": ["PDF 文字层没有读到内容"],
                    "ocr": {"status": "succeeded", "text": "OCR 文本", "char_count": 4},
                }
            ],
        }

        html = MODULE.render_html(model)

        self.assertIn("先确认文字有没有读靠谱，再谈接进报价", html)
        self.assertIn("需要先复核", html)
        self.assertIn("PaddleOCR 抽样结果", html)
        self.assertNotIn("<script", html)

    def test_build_model_reads_candidate_manifest_without_running_ocr_or_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts_dir = root / "scripts"
            report_dir = root / "reports" / "addenda" / "online"
            layer_dir = root / "references" / "addenda" / "online"
            scripts_dir.mkdir(parents=True)
            report_dir.mkdir(parents=True)
            layer_dir.mkdir(parents=True)
            (scripts_dir / "compare_addendum_layers.py").write_text(
                (Path(__file__).resolve().parents[1] / "scripts" / "compare_addendum_layers.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (scripts_dir / "extract_rules_candidate.py").write_text(
                (Path(__file__).resolve().parents[1] / "scripts" / "extract_rules_candidate.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (report_dir / "rules-candidate.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "source_title": "扫描页",
                                "source_page": 1,
                                "source_local_path": "/tmp/a.pdf",
                                "extract_method": "unknown",
                                "image_count": 1,
                                "raw_text": "",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "online",
                        "status": "PAUSED",
                        "artifacts": {
                            "rules_candidate_file": "../../../reports/addenda/online/rules-candidate.json"
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_model(
                skill_dir=root,
                candidate_layer="online",
                sample_size=4,
                run_ocr=False,
                ocr_sample_size=0,
                render_sample_size=0,
                skip_render=True,
                lang="ch",
                device="cpu",
            )

        self.assertEqual(model["candidate_layer"], "online")
        self.assertEqual(model["verdict"], "needs_review")
        self.assertEqual(model["unknown_page_count"], 1)

    def test_build_model_uses_unknown_page_closure_to_unpause_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts_dir = root / "scripts"
            report_dir = root / "reports" / "addenda" / "online"
            layer_dir = root / "references" / "addenda" / "online"
            scripts_dir.mkdir(parents=True)
            report_dir.mkdir(parents=True)
            layer_dir.mkdir(parents=True)
            (scripts_dir / "compare_addendum_layers.py").write_text(
                (Path(__file__).resolve().parents[1] / "scripts" / "compare_addendum_layers.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (scripts_dir / "extract_rules_candidate.py").write_text(
                (Path(__file__).resolve().parents[1] / "scripts" / "extract_rules_candidate.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (report_dir / "rules-candidate.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "source_title": "扫描页",
                                "source_page": 1,
                                "source_local_path": "/tmp/a.pdf",
                                "extract_method": "unknown",
                                "image_count": 1,
                                "raw_text": "",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (report_dir / "unknown-page-resolution-ledger.json").write_text(
                json.dumps(
                    {
                        "unknown_page_count": 1,
                        "resolution_counts": {"manual_source_only": 1},
                        "entries": [{"resolution_status": "manual_source_only"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "online",
                        "status": "ACTIVE",
                        "artifacts": {
                            "rules_candidate_file": "../../../reports/addenda/online/rules-candidate.json"
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_model(
                skill_dir=root,
                candidate_layer="online",
                sample_size=4,
                run_ocr=False,
                ocr_sample_size=0,
                render_sample_size=0,
                skip_render=True,
                lang="ch",
                device="cpu",
            )

        self.assertEqual(model["verdict"], "full_document_closed")
        self.assertEqual(model["unknown_page_closure"]["unresolved_count"], 0)


if __name__ == "__main__":
    unittest.main()
