import csv
import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_pdf_block_review.py"
SPEC = importlib.util.spec_from_file_location("build_pdf_block_review", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildPdfBlockReviewTests(unittest.TestCase):
    def test_cluster_text_observations_groups_far_apart_regions(self) -> None:
        observations = [
            {"text": "柜体投影面积", "bbox": (20, 20, 160, 40), "source": "vision", "confidence": 0.95},
            {"text": "不足1.6㎡按1.6㎡", "bbox": (24, 70, 220, 40), "source": "vision", "confidence": 0.92},
            {"text": "可选色样", "bbox": (540, 520, 120, 40), "source": "vision", "confidence": 0.9},
            {"text": "极光白", "bbox": (550, 570, 90, 34), "source": "vision", "confidence": 0.9},
        ]

        blocks = MODULE.cluster_text_observations(observations, image_width=800, image_height=1000)

        self.assertEqual(len(blocks), 2)
        self.assertIn("柜体投影面积", blocks[0]["text"])
        self.assertIn("可选色样", blocks[1]["text"])

    def test_build_block_ledger_row_preserves_three_text_channels(self) -> None:
        row = MODULE.build_block_ledger_row(
            page_number=49,
            block_id="p049-b01",
            block_type="diagram_text",
            bbox=(10, 20, 300, 160),
            source_image_path="artifacts/p049-b01.png",
            text_pdf_layer="窄边风格",
            text_ocr_basic="门盖牙称与顶挡条",
            text_ocr_vision="最少需要留出15mm",
        )

        self.assertEqual(row["page"], 49)
        self.assertEqual(row["block_id"], "p049-b01")
        self.assertIn("窄边风格", row["text_merged"])
        self.assertTrue(row["has_dimension_signal"])
        self.assertTrue(row["has_structure_signal"])
        self.assertTrue(row["needs_manual_review"])

    def test_classify_block_coverage_marks_known_summary_page_as_covered_non_runtime(self) -> None:
        block_row = MODULE.build_block_ledger_row(
            page_number=191,
            block_id="p191-b01",
            block_type="table_region",
            bbox=(0, 0, 500, 200),
            source_image_path="artifacts/p191-b01.png",
            text_pdf_layer="",
            text_ocr_basic="铝框平开门尺寸限制快速检索表",
            text_ocr_vision="针式铰链铝框门 铝框岩板门",
        )
        references = {
            "runtime_entries": [],
            "audit_entries": [],
            "rule_index_entries": [],
            "review_note_entries": [
                {
                    "pages": {191, 192},
                    "title": "铝框平开门快速检索表",
                    "text": "p191-p192 已经通过门型规则簇重写补入 runtime",
                }
            ],
        }

        coverage = MODULE.classify_block_coverage(block_row, references)

        self.assertEqual(coverage["coverage_status"], "covered_non_runtime")
        self.assertEqual(coverage["best_match_target"], "review_note")

    def test_classify_block_coverage_keeps_manual_priority_page_for_manual_judgement(self) -> None:
        block_row = MODULE.build_block_ledger_row(
            page_number=49,
            block_id="p049-b01",
            block_type="diagram_text",
            bbox=(0, 0, 500, 200),
            source_image_path="artifacts/p049-b01.png",
            text_pdf_layer="窄边风格",
            text_ocr_basic="门盖牙称与顶挡条",
            text_ocr_vision="最少需要留出15mm",
        )
        references = {
            "runtime_entries": [],
            "audit_entries": [
                {
                    "page": 49,
                    "title": "窄边风格——拆装注意事项",
                    "text": "门盖牙称与顶挡条时最少需要留出15mm",
                    "status": "manual_review",
                }
            ],
            "rule_index_entries": [],
            "review_note_entries": [
                {
                    "pages": {49, 50},
                    "title": "p49/p50",
                    "text": "p49/p50 相关页已先落地其中最清晰的一条硬约束，其余图示和结构说明继续保留人工复核。",
                }
            ],
        }

        coverage = MODULE.classify_block_coverage(block_row, references)

        self.assertIn(coverage["coverage_status"], {"needs_manual_judgement", "new_candidate_rule"})

    def test_write_review_outputs_writes_csv_and_markdown(self) -> None:
        ledger_rows = [
            MODULE.build_block_ledger_row(
                page_number=50,
                block_id="p050-b01",
                block_type="diagram_text",
                bbox=(10, 10, 200, 120),
                source_image_path="artifacts/p050-b01.png",
                text_pdf_layer="",
                text_ocr_basic="窄边风格",
                text_ocr_vision="门盖牙称与顶挡条时最少需要留出15mm",
            )
        ]
        coverage_rows = [
            {
                "page": 50,
                "block_id": "p050-b01",
                "normalized_text": ledger_rows[0]["normalized_text"],
                "display_text": "",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": False,
                "matched_runtime": True,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "runtime",
                "best_match_title": "窄边风格拆装时门盖牙称与顶挡条最少留出15mm",
                "best_match_score": 0.94,
                "coverage_status": "covered_runtime",
                "reason": "与 runtime 标题高度相似",
            }
        ]
        page_summary_rows = [
            {
                "page": 50,
                "page_image_path": "artifacts/page-050.png",
                "pdf_text_chars": 20,
                "basic_observation_count": 3,
                "vision_observation_count": 2,
                "block_count": 1,
                "needs_manual_review": True,
                "basic_ocr_error": "",
                "vision_ocr_error": "vision ocr timed out for page-050.png",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            MODULE.write_review_outputs(
                output_dir=output_dir,
                ledger_rows=ledger_rows,
                coverage_rows=coverage_rows,
                source_file="/tmp/rules.pdf",
                page_count=427,
                page_summary_rows=page_summary_rows,
            )

            ledger_path = output_dir / "pdf-block-ledger.csv"
            coverage_path = output_dir / "pdf-block-coverage.csv"
            page_summary_path = output_dir / "pdf-page-summary.csv"
            report_path = output_dir / "pdf-block-review-report.md"
            conclusion_path = output_dir / "pdf-block-review-conclusion.md"

            with ledger_path.open(encoding="utf-8") as handle:
                ledger_csv = list(csv.DictReader(handle))
            with coverage_path.open(encoding="utf-8") as handle:
                coverage_csv = list(csv.DictReader(handle))
            with page_summary_path.open(encoding="utf-8") as handle:
                page_summary_csv = list(csv.DictReader(handle))
            report_markdown = report_path.read_text(encoding="utf-8")
            conclusion_markdown = conclusion_path.read_text(encoding="utf-8")

        self.assertEqual(len(ledger_csv), 1)
        self.assertEqual(len(coverage_csv), 1)
        self.assertEqual(page_summary_csv[0]["vision_ocr_error"], "vision ocr timed out for page-050.png")
        self.assertIn("总页数", report_markdown)
        self.assertIn("p50 / p050-b01", report_markdown)
        self.assertIn("## OCR 异常页", report_markdown)
        self.assertIn("PDF 图片 OCR 复盘结论", conclusion_markdown)

    def test_classify_block_coverage_marks_noise_review_page_as_background(self) -> None:
        block_row = MODULE.build_block_ledger_row(
            page_number=284,
            block_id="p284-b01",
            block_type="body_text",
            bbox=(0, 0, 400, 300),
            source_image_path="artifacts/p284-b01.png",
            text_pdf_layer="",
            text_ocr_basic="2onj2 QGWwouztisf2",
            text_ocr_vision="UGIGELIC SUG GXfLIOLGIUSLA",
        )
        references = {
            "runtime_entries": [],
            "audit_entries": [],
            "rule_index_entries": [],
            "review_note_entries": [
                {
                    "pages": {284},
                    "title": "噪声或背景说明",
                    "text": "p284 结论: 继续排除在 runtime 之外，属于噪声或背景说明。",
                }
            ],
        }

        coverage = MODULE.classify_block_coverage(block_row, references)

        self.assertEqual(coverage["coverage_status"], "non_rule_background")

    def test_classify_block_coverage_keeps_low_signal_ocr_noise_as_background(self) -> None:
        block_row = MODULE.build_block_ledger_row(
            page_number=2,
            block_id="p002-b01",
            block_type="body_text",
            bbox=(0, 0, 400, 300),
            source_image_path="artifacts/p002-b01.png",
            text_pdf_layer="",
            text_ocr_basic="土 YY 斑 荔 闭 坚 产 粒",
            text_ocr_vision="Aooq-pgaeq",
        )
        references = {
            "runtime_entries": [],
            "audit_entries": [],
            "rule_index_entries": [],
            "review_note_entries": [],
        }

        coverage = MODULE.classify_block_coverage(block_row, references)

        self.assertEqual(coverage["coverage_status"], "non_rule_background")

    def test_load_reference_layers_reads_existing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "runtime-rules.json").write_text(
                json.dumps({"rules": [{"page": 50, "title": "窄边风格", "detail": "门盖牙称"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (base / "pdf-coverage-audit.csv").write_text(
                "status,page,domain,rule_type,relevance_score,pricing_relevant,clean_title,heading,tags,excerpt,normalized_rule,runtime_title,runtime_action,reason\n"
                "manual_review,49,cabinet,formula,6,True,窄边风格,窄边风格,柜体,门盖牙称,说明,,,人工复核\n",
                encoding="utf-8",
            )
            (base / "rules-index.json").write_text(
                json.dumps({"entries": [{"page": 49, "clean_title": "窄边风格", "excerpt": "门盖牙称"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (base / "pdf-gap-review-after-door-panel-rewrite.md").write_text(
                "# 复核\n- `p191`, `p192` 已通过结构化规则覆盖\n",
                encoding="utf-8",
            )
            (base / "p49-p50-manual-review.csv").write_text(
                "page,block_id,manual_readable_text,interpretation,recommended_status,next_action\n"
                "50,p050-b06,窄边风格——拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm,明确硬规则，现有 runtime 已覆盖,covered_runtime,无需新增\n",
                encoding="utf-8",
            )

            references = MODULE.load_reference_layers(base)

        self.assertEqual(len(references["runtime_entries"]), 1)
        self.assertEqual(len(references["audit_entries"]), 1)
        self.assertEqual(len(references["rule_index_entries"]), 1)
        self.assertEqual(references["review_note_entries"][0]["pages"], {191, 192})
        self.assertIn((50, "p050-b06"), references["manual_review_entries"])

    def test_classify_block_coverage_prefers_manual_review_override(self) -> None:
        block_row = MODULE.build_block_ledger_row(
            page_number=50,
            block_id="p050-b06",
            block_type="diagram_text",
            bbox=(0, 0, 500, 200),
            source_image_path="artifacts/p050-b06.png",
            text_pdf_layer="",
            text_ocr_basic="窄边风格",
            text_ocr_vision="门盖牙称与顶挡条时最少需要留出15mm",
        )
        references = {
            "runtime_entries": [],
            "audit_entries": [],
            "rule_index_entries": [],
            "review_note_entries": [],
            "manual_review_entries": {
                (50, "p050-b06"): {
                    "page": 50,
                    "block_id": "p050-b06",
                    "manual_readable_text": "窄边风格——拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm",
                    "interpretation": "明确硬规则，现有 runtime 已覆盖",
                    "recommended_status": "covered_runtime",
                    "next_action": "无需新增",
                    "source_file": "p49-p50-manual-review.csv",
                }
            },
        }

        coverage = MODULE.classify_block_coverage(block_row, references)

        self.assertEqual(coverage["coverage_status"], "covered_runtime")
        self.assertEqual(coverage["best_match_target"], "manual_review")
        self.assertEqual(coverage["display_text"], "窄边风格——拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm")
        self.assertTrue(coverage["manual_override_applied"])

    def test_render_report_markdown_uses_manual_summary_and_excludes_resolved_manual_blocks_from_high_risk(self) -> None:
        ledger_rows = [
            MODULE.build_block_ledger_row(
                page_number=50,
                block_id="p050-b06",
                block_type="diagram_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p050-b06.png",
                text_pdf_layer="",
                text_ocr_basic="Ky",
                text_ocr_vision="Le",
            ),
            MODULE.build_block_ledger_row(
                page_number=50,
                block_id="p050-b01",
                block_type="diagram_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p050-b01.png",
                text_pdf_layer="",
                text_ocr_basic="Ky",
                text_ocr_vision="",
            ),
            MODULE.build_block_ledger_row(
                page_number=148,
                block_id="p148-b01",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p148-b01.png",
                text_pdf_layer="",
                text_ocr_basic="德利丰 6mm",
                text_ocr_vision="A1级防火材料",
            ),
        ]
        coverage_rows = [
            {
                "page": 50,
                "block_id": "p050-b06",
                "normalized_text": ledger_rows[0]["normalized_text"],
                "display_text": "窄边风格——拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm",
                "manual_interpretation": "明确硬规则，现有 runtime 已覆盖",
                "manual_next_action": "无需新增",
                "manual_source_file": "p49-p50-manual-review.csv",
                "manual_override_applied": True,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "manual_review",
                "best_match_title": "窄边风格——拆装注意事项",
                "best_match_score": 1.0,
                "coverage_status": "covered_runtime",
                "reason": "明确硬规则，现有 runtime 已覆盖",
            },
            {
                "page": 50,
                "block_id": "p050-b01",
                "normalized_text": ledger_rows[1]["normalized_text"],
                "display_text": "",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": False,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "",
                "best_match_title": "",
                "best_match_score": 0.0,
                "coverage_status": "needs_manual_judgement",
                "reason": "当前块有规则相关信号，但匹配结果不足以自动归类。",
            },
            {
                "page": 148,
                "block_id": "p148-b01",
                "normalized_text": ledger_rows[2]["normalized_text"],
                "display_text": "",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": False,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "",
                "best_match_title": "",
                "best_match_score": 0.0,
                "coverage_status": "needs_manual_judgement",
                "reason": "当前块有规则相关信号，但匹配结果不足以自动归类。",
            },
        ]
        page_summary_rows = [
            {
                "page": 44,
                "page_image_path": "artifacts/page-044.png",
                "pdf_text_chars": 0,
                "basic_observation_count": 0,
                "vision_observation_count": 0,
                "block_count": 1,
                "needs_manual_review": False,
                "basic_ocr_error": "",
                "vision_ocr_error": "vision ocr timed out for page-044.png",
            }
        ]

        markdown = MODULE.render_report_markdown(
            source_file="/tmp/rules.pdf",
            page_count=427,
            ledger_rows=ledger_rows,
            coverage_rows=coverage_rows,
            page_summary_rows=page_summary_rows,
        )

        self.assertIn("## 人工复核已定性图块", markdown)
        self.assertIn("窄边风格--拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm", markdown)
        self.assertNotIn("p50 / p050-b06：covered_runtime / Ky", markdown)
        self.assertIn("p50 / p050-b01：needs_manual_judgement", markdown)
        high_risk_section = markdown.split("## 高风险复杂页清单", 1)[1].split("## 非阻塞已知项", 1)[0]
        self.assertNotIn("p148 / p148-b01：needs_manual_judgement", high_risk_section)
        self.assertIn("## 非阻塞已知项", markdown)
        self.assertIn("p148 / p148-b01：needs_manual_judgement", markdown.split("## 非阻塞已知项", 1)[1])
        self.assertIn("## OCR 异常页", markdown)
        self.assertIn("p44：vision=vision ocr timed out for page-044.png", markdown)

    def test_run_subprocess_with_timeout_kills_process_group_without_blocking(self) -> None:
        process = mock.Mock()
        process.pid = 4321
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["vision_ocr"], timeout=60),
            subprocess.TimeoutExpired(cmd=["vision_ocr"], timeout=1),
        ]
        process.kill = mock.Mock()

        with mock.patch.object(MODULE.subprocess, "Popen", return_value=process):
            with mock.patch.object(MODULE.os, "killpg") as killpg:
                with self.assertRaisesRegex(RuntimeError, "vision ocr timed out"):
                    MODULE.run_subprocess_with_timeout(
                        ["/tmp/fake-vision-ocr", "/tmp/page.png"],
                        timeout_seconds=60,
                        timeout_label="vision ocr",
                        timeout_target="/tmp/page.png",
                    )

        killpg.assert_called_once_with(4321, MODULE.signal.SIGKILL)
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_count, 2)

    def test_render_review_conclusion_markdown_excludes_non_blocking_known_blocks_from_remaining_risk(self) -> None:
        ledger_rows = [
            MODULE.build_block_ledger_row(
                page_number=148,
                block_id="p148-b01",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p148-b01.png",
                text_pdf_layer="",
                text_ocr_basic="德利丰 6mm",
                text_ocr_vision="A1级防火",
            ),
            MODULE.build_block_ledger_row(
                page_number=288,
                block_id="p288-b01",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p288-b01.png",
                text_pdf_layer="",
                text_ocr_basic="灯带开关",
                text_ocr_vision="优先选用有线开关",
            ),
            MODULE.build_block_ledger_row(
                page_number=49,
                block_id="p049-b04",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p049-b04.png",
                text_pdf_layer="",
                text_ocr_basic="直角圆边-窄边高柜",
                text_ocr_vision="",
            ),
            MODULE.build_block_ledger_row(
                page_number=49,
                block_id="p049-b05",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p049-b05.png",
                text_pdf_layer="",
                text_ocr_basic="凹槽内退尺寸",
                text_ocr_vision="20/8/12",
            ),
            MODULE.build_block_ledger_row(
                page_number=50,
                block_id="p050-b06",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p050-b06.png",
                text_pdf_layer="",
                text_ocr_basic="窄边风格",
                text_ocr_vision="最少留出15mm",
            ),
            MODULE.build_block_ledger_row(
                page_number=50,
                block_id="p050-b07",
                block_type="body_text",
                bbox=(0, 0, 300, 120),
                source_image_path="artifacts/p050-b07.png",
                text_pdf_layer="",
                text_ocr_basic="窄边风格",
                text_ocr_vision="最少留出15mm",
            ),
        ]
        coverage_rows = [
            {
                "page": 148,
                "block_id": "p148-b01",
                "normalized_text": ledger_rows[0]["normalized_text"],
                "display_text": "",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": False,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "",
                "best_match_title": "",
                "best_match_score": 0.0,
                "coverage_status": "needs_manual_judgement",
                "reason": "",
            },
            {
                "page": 288,
                "block_id": "p288-b01",
                "normalized_text": ledger_rows[1]["normalized_text"],
                "display_text": "",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": False,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "",
                "best_match_title": "",
                "best_match_score": 0.0,
                "coverage_status": "new_candidate_rule",
                "reason": "",
            },
            {
                "page": 49,
                "block_id": "p049-b04",
                "normalized_text": ledger_rows[2]["normalized_text"],
                "display_text": "直角圆边-窄边高柜",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": True,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "manual_review",
                "best_match_title": "",
                "best_match_score": 1.0,
                "coverage_status": "needs_manual_judgement",
                "reason": "",
            },
            {
                "page": 49,
                "block_id": "p049-b05",
                "normalized_text": ledger_rows[3]["normalized_text"],
                "display_text": "直角圆边-窄边高柜；凹槽内退尺寸",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": True,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "manual_review",
                "best_match_title": "",
                "best_match_score": 1.0,
                "coverage_status": "needs_manual_judgement",
                "reason": "",
            },
            {
                "page": 50,
                "block_id": "p050-b06",
                "normalized_text": ledger_rows[4]["normalized_text"],
                "display_text": "窄边风格——拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": True,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "manual_review",
                "best_match_title": "",
                "best_match_score": 1.0,
                "coverage_status": "covered_runtime",
                "reason": "",
            },
            {
                "page": 50,
                "block_id": "p050-b07",
                "normalized_text": ledger_rows[5]["normalized_text"],
                "display_text": "窄边风格——拆装注意事项；门盖牙称与顶挡条时最少需要留出15mm",
                "manual_interpretation": "",
                "manual_next_action": "",
                "manual_source_file": "",
                "manual_override_applied": True,
                "matched_runtime": False,
                "matched_audit": False,
                "matched_rule_index": False,
                "matched_review_note": False,
                "best_match_target": "manual_review",
                "best_match_title": "",
                "best_match_score": 1.0,
                "coverage_status": "covered_runtime",
                "reason": "",
            },
        ]

        markdown = MODULE.render_review_conclusion_markdown(
            source_file="/tmp/rules.pdf",
            ledger_rows=ledger_rows,
            coverage_rows=coverage_rows,
        )

        self.assertIn("remaining_high_risk: 1", markdown)
        self.assertNotIn("p148 / p148-b01", markdown.split("## 剩余风险", 1)[1])
        self.assertIn("p288 / p288-b01", markdown)

    def test_extract_vision_observations_propagates_timeout_runtime_error(self) -> None:
        with mock.patch.object(MODULE, "ensure_vision_ocr_binary", return_value=Path("/tmp/fake-vision-ocr")):
            with mock.patch.object(
                MODULE,
                "run_subprocess_with_timeout",
                side_effect=RuntimeError("vision ocr timed out for /tmp/page.png"),
            ):
                with self.assertRaisesRegex(RuntimeError, "vision ocr timed out"):
                    MODULE.extract_vision_observations(Path("/tmp/page.png"))


if __name__ == "__main__":
    unittest.main()
