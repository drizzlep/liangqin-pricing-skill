import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

ADAPTER_PATH = APP_ROOT / "adapters" / "manual_batch.py"
CLI_PATH = APP_ROOT / "cli" / "manual_batch.py"
REVIEW_PIPELINE_PATH = CORE_ROOT / "review_pipeline.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ADAPTER = load_module("contract_review_manual_batch", ADAPTER_PATH)
CLI = load_module("contract_review_manual_batch_cli", CLI_PATH)
REVIEW_PIPELINE = load_module("contract_review_review_pipeline", REVIEW_PIPELINE_PATH)


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


class ManualBatchTests(unittest.TestCase):
    def test_cli_parse_args_supports_force_ocr_for_documents_flag(self) -> None:
        args = CLI.parse_args(
            [
                "--batch-dir",
                "/tmp/batch",
                "--force-ocr-for-documents",
            ]
        )

        self.assertTrue(args.force_ocr_for_documents)

    def test_build_review_jobs_autodiscovers_subdirs_and_direct_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_dir = Path(tmpdir)
            raw_dir = batch_dir / "raw"
            (raw_dir / "case-001").mkdir(parents=True)
            write_minimal_docx(raw_dir / "case-001" / "合同.docx", ["甲方：客户A", "产品名称"])
            (raw_dir / "单独合同.pdf").write_text("%PDF-1.4", encoding="utf-8")

            batch_plan = ADAPTER.build_review_jobs(batch_dir)

        self.assertEqual(batch_plan.batch_id, batch_dir.name)
        self.assertEqual(len(batch_plan.jobs), 2)
        self.assertEqual(batch_plan.jobs[0].group_key, "case-001")
        self.assertEqual(batch_plan.jobs[1].group_key, "单独合同")
        self.assertEqual(batch_plan.jobs[0].assets[0].text_extract_method, "docx_text")
        self.assertIn("甲方：客户A", batch_plan.jobs[0].assets[0].text_preview)

    def test_build_review_jobs_supports_flat_batch_directory_without_raw(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_dir = Path(tmpdir)
            write_minimal_docx(batch_dir / "合同A.docx", ["甲方：客户A", "产品名称"])
            (batch_dir / "合同B.pdf").write_text("%PDF-1.4", encoding="utf-8")

            batch_plan = ADAPTER.build_review_jobs(batch_dir)

        self.assertEqual(len(batch_plan.jobs), 2)
        self.assertEqual(batch_plan.jobs[0].group_key, "合同A")
        self.assertEqual(batch_plan.jobs[1].group_key, "合同B")

    def test_build_review_jobs_keeps_symlink_relative_path_inside_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as sourcedir:
            batch_dir = Path(tmpdir)
            raw_dir = batch_dir / "raw"
            raw_dir.mkdir(parents=True)
            source_file = Path(sourcedir) / "合同.pdf"
            source_file.write_text("%PDF-1.4", encoding="utf-8")
            link_path = raw_dir / "合同.pdf"
            link_path.symlink_to(source_file)

            original_extract = ADAPTER.extract_text_preview
            ADAPTER.extract_text_preview = lambda path: ("第1页 合同总金额 19800元", "pdf_text_layer")
            try:
                batch_plan = ADAPTER.build_review_jobs(batch_dir)
            finally:
                ADAPTER.extract_text_preview = original_extract

        asset = batch_plan.jobs[0].assets[0]
        self.assertEqual(asset.relative_path, "raw/合同.pdf")

    def test_build_review_jobs_marks_primary_contract_pdf_for_ocr_even_with_native_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_dir = Path(tmpdir)
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            pdf_path = raw_dir / "合同.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 fake")

            original_extract = ADAPTER.extract_text_preview
            ADAPTER.extract_text_preview = lambda path: ("第1页 合同总金额 19800元", "pdf_text_layer")
            try:
                batch_plan = ADAPTER.build_review_jobs(batch_dir)
            finally:
                ADAPTER.extract_text_preview = original_extract

        asset = batch_plan.jobs[0].assets[0]
        self.assertEqual(asset.text_extract_method, "pdf_text_layer")
        self.assertTrue(asset.metadata["preview_available"])
        self.assertTrue(asset.metadata["needs_ocr"])

    def test_cli_writes_batch_summary_and_job_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-001"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "甲方：客户A",
                    "乙方：北京良禽佳木家居有限公司",
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-001",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            summary = CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            batch_summary_path = runtime_root / "batches" / "batch-001" / "batch-summary.json"
            review_json_path = runtime_root / "jobs" / "batch-001-001" / "output" / "review.json"
            review_markdown_path = runtime_root / "jobs" / "batch-001-001" / "output" / "review.md"
            source_assets_path = runtime_root / "jobs" / "batch-001-001" / "normalized" / "source-assets.json"
            normalized_fields_path = runtime_root / "jobs" / "batch-001-001" / "normalized" / "normalized-fields.json"
            pricing_precheck_path = runtime_root / "jobs" / "batch-001-001" / "output" / "pricing-precheck.json"
            formal_quote_path = runtime_root / "jobs" / "batch-001-001" / "output" / "formal-quote.json"
            pricing_compare_path = runtime_root / "jobs" / "batch-001-001" / "output" / "pricing-compare.json"
            batch_pricing_compare_path = runtime_root / "batches" / "batch-001" / "pricing-compare.json"
            batch_pricing_diagnosis_path = runtime_root / "batches" / "batch-001" / "pricing-compare-diagnosis.json"

            self.assertTrue(batch_summary_path.exists())
            self.assertTrue(review_json_path.exists())
            self.assertTrue(review_markdown_path.exists())
            self.assertTrue(source_assets_path.exists())
            self.assertTrue(normalized_fields_path.exists())
            self.assertTrue(pricing_precheck_path.exists())
            self.assertTrue(formal_quote_path.exists())
            self.assertTrue(pricing_compare_path.exists())
            self.assertTrue(batch_pricing_compare_path.exists())
            self.assertTrue(batch_pricing_diagnosis_path.exists())

            review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
            normalized_fields_payload = json.loads(normalized_fields_path.read_text(encoding="utf-8"))
            pricing_precheck_payload = json.loads(pricing_precheck_path.read_text(encoding="utf-8"))
            formal_quote_payload = json.loads(formal_quote_path.read_text(encoding="utf-8"))
            pricing_compare_payload = json.loads(pricing_compare_path.read_text(encoding="utf-8"))
            batch_pricing_compare_payload = json.loads(batch_pricing_compare_path.read_text(encoding="utf-8"))
            batch_pricing_diagnosis_payload = json.loads(batch_pricing_diagnosis_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["job_count"], 1)
            self.assertEqual(review_payload["job_id"], "batch-001-001")
            self.assertEqual(review_payload["summary"]["primary_contract_count"], 1)
            self.assertEqual(review_payload["status"], "manual_review_required")
            self.assertEqual(normalized_fields_payload["fields"]["product_category"]["value"], "书柜")
            self.assertEqual(pricing_precheck_payload["status"], "ready_for_formal_quote")
            self.assertEqual(pricing_precheck_payload["precheck_args"]["category"], "书柜")
            self.assertEqual(review_payload["contract_audit"]["financials"]["contract_total"]["value"], "19800元")
            self.assertIn(formal_quote_payload["status"], {"completed", "failed"})
            if formal_quote_payload["status"] == "completed":
                self.assertTrue(str(formal_quote_payload["pricing_total"]).endswith("元"))
                self.assertEqual(pricing_compare_payload["pricing_total"], formal_quote_payload["pricing_total"])
                self.assertIn(
                    pricing_compare_payload["match_band"],
                    {"exact_match", "close_match", "approximate_match", "mismatch"},
                )
            else:
                self.assertEqual(pricing_compare_payload["status"], "skipped")
            self.assertEqual(batch_pricing_compare_payload["item_count"], 1)
            self.assertEqual(batch_pricing_compare_payload["items"][0]["job_id"], "batch-001-001")
            self.assertEqual(batch_pricing_diagnosis_payload["item_count"], 1)
            self.assertEqual(batch_pricing_diagnosis_payload["items"][0]["job_id"], "batch-001-001")

    def test_cli_marks_visual_assets_as_ocr_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-visual"
            raw_dir = batch_dir / "raw" / "case-visual"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                ["甲方：客户A", "乙方：北京良禽佳木家居有限公司", "产品名称"],
            )
            (raw_dir / "尺寸图纸.png").write_bytes(b"fake-image")
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-visual",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            review_json_path = runtime_root / "jobs" / "batch-visual-001" / "output" / "review.json"
            replay_json_path = runtime_root / "jobs" / "batch-visual-001" / "output" / "replay.json"
            review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
            replay_payload = json.loads(replay_json_path.read_text(encoding="utf-8"))

            finding_codes = {item["code"] for item in review_payload["findings"]}
            self.assertIn("job.visual_assets_need_ocr", finding_codes)
            self.assertEqual(review_payload["automation_state"], "ocr_or_vision_required")
            self.assertIn("visual_assets_present", review_payload["summary"]["risk_flags"])
            self.assertEqual(replay_payload["status"], "blocked")
            self.assertIn("OCR", replay_payload["reason"])

    def test_cli_generates_ready_pricing_precheck_for_modular_child_bed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-bed"
            raw_dir = batch_dir / "raw" / "case-bed"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：儿童上下床",
                    "本单按定制执行",
                    "床形态：上下床",
                    "上层出入方式：直梯",
                    "下层结构：箱体床",
                    "围栏样式：篱笆围栏",
                    "床垫宽度：900mm",
                    "床垫长度：2000mm",
                    "材质：乌拉圭玫瑰木",
                ],
            )
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-bed",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            pricing_precheck_path = runtime_root / "jobs" / "batch-bed-001" / "output" / "pricing-precheck.json"
            normalized_fields_path = runtime_root / "jobs" / "batch-bed-001" / "normalized" / "normalized-fields.json"
            pricing_precheck_payload = json.loads(pricing_precheck_path.read_text(encoding="utf-8"))
            normalized_fields_payload = json.loads(normalized_fields_path.read_text(encoding="utf-8"))

            self.assertEqual(pricing_precheck_payload["status"], "ready_for_formal_quote")
            self.assertEqual(pricing_precheck_payload["precheck_result"]["pricing_route"], "modular_child_bed")
            self.assertEqual(normalized_fields_payload["fields"]["bed_form"]["value"], "上下床")
            self.assertEqual(normalized_fields_payload["fields"]["access_style"]["value"], "直梯")

    def test_cli_writes_multi_product_split_output_for_multi_product_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-split"
            raw_dir = batch_dir / "raw" / "case-split"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "附件： 产品名称 产品编号 材质 数量 费用合计（元） 其他斗柜 20990020001001 北美黑胡桃木 1 12400 经典床头柜 320990020001002 北美黑胡桃木 1 2580 合计 14980",
                    "主卧 其他斗柜 209900200 01001北美黑胡桃木 无色哑光木蜡油尺寸 长：1300mm 宽：450mm 高：1000mm",
                    "主卧 经典床头柜 3 209900200 01002北美黑胡桃木 无色哑光木蜡油尺寸 长：450mm 宽：400mm 高：500mm",
                ],
            )
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-split",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            product_split_path = runtime_root / "jobs" / "batch-split-001" / "output" / "product-split.json"
            self.assertTrue(product_split_path.exists())
            product_split_payload = json.loads(product_split_path.read_text(encoding="utf-8"))
            self.assertEqual(product_split_payload["item_count"], 2)
            self.assertEqual(product_split_payload["items"][0]["product_name"], "其他斗柜")
            self.assertEqual(product_split_payload["items"][1]["product_name"], "经典床头柜")
            self.assertEqual(product_split_payload["items"][0]["detail_resolution"]["status"], "detail_page_linked")

    def test_cli_generates_ready_pricing_precheck_for_half_loft_combo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-combo"
            raw_dir = batch_dir / "raw" / "case-combo"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：高架床",
                    "本单按定制执行",
                    "床形态：高架床",
                    "上层出入方式：梯柜",
                    "围栏样式：胶囊围栏",
                    "围栏长度：1800mm",
                    "围栏高度：320mm",
                    "梯柜踏步宽度：500mm",
                    "梯柜进深：900mm",
                    "床垫宽度：1200mm",
                    "床垫长度：2000mm",
                    "材质：北美白蜡木",
                    "前排柜体长度：1600mm",
                    "前排柜体高度：1600mm",
                    "前排柜体进深：450mm",
                    "前排柜体结构：有门无背板",
                ],
            )
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-combo",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            pricing_precheck_path = runtime_root / "jobs" / "batch-combo-001" / "output" / "pricing-precheck.json"
            normalized_fields_path = runtime_root / "jobs" / "batch-combo-001" / "normalized" / "normalized-fields.json"
            pricing_precheck_payload = json.loads(pricing_precheck_path.read_text(encoding="utf-8"))
            normalized_fields_payload = json.loads(normalized_fields_path.read_text(encoding="utf-8"))

            self.assertEqual(pricing_precheck_payload["status"], "ready_for_formal_quote")
            self.assertEqual(pricing_precheck_payload["precheck_result"]["pricing_route"], "modular_child_bed_combo")
            self.assertEqual(normalized_fields_payload["fields"]["front_cabinet_mode"]["value"], "有门无背板")
            self.assertEqual(normalized_fields_payload["fields"]["stair_depth"]["value"], "900mm")

    def test_cli_generates_ready_pricing_precheck_for_dual_row_half_loft_combo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-combo-dual"
            raw_dir = batch_dir / "raw" / "case-combo-dual"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：半高床",
                    "本单按定制执行",
                    "床形态：半高床",
                    "上层出入方式：梯柜",
                    "围栏样式：胶囊围栏",
                    "围栏长度：2000mm",
                    "围栏高度：400mm",
                    "梯柜踏步宽度：520mm",
                    "梯柜进深：500mm",
                    "床垫宽度：1200mm",
                    "床垫长度：2000mm",
                    "材质：乌拉圭玫瑰木",
                    "床下前后双排互通",
                    "前排：长度 2000mm，高度 1200mm，进深 450mm，有门无背板。",
                    "后排：长度 1800mm，高度 1200mm，进深 450mm，无门有背板。",
                ],
            )
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-combo-dual",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            pricing_precheck_path = runtime_root / "jobs" / "batch-combo-dual-001" / "output" / "pricing-precheck.json"
            normalized_fields_path = runtime_root / "jobs" / "batch-combo-dual-001" / "normalized" / "normalized-fields.json"
            pricing_precheck_payload = json.loads(pricing_precheck_path.read_text(encoding="utf-8"))
            normalized_fields_payload = json.loads(normalized_fields_path.read_text(encoding="utf-8"))

            self.assertEqual(pricing_precheck_payload["status"], "ready_for_formal_quote")
            self.assertEqual(pricing_precheck_payload["precheck_result"]["pricing_route"], "modular_child_bed_combo")
            self.assertTrue(normalized_fields_payload["fields"]["interconnected_rows"]["value"])
            self.assertEqual(normalized_fields_payload["fields"]["rear_cabinet_mode"]["value"], "无门有背板")
            self.assertEqual(normalized_fields_payload["fields"]["rear_cabinet_length"]["value"], "1800mm")

    def test_run_review_job_marks_ocr_assets_as_ready_when_paddleocr_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.docx"
            image_path = root / "尺寸图.png"
            write_minimal_docx(contract_path, ["甲方：客户A", "产品名称", "费用合计（元）"])
            image_path.write_bytes(b"fake-image")

            job = ADAPTER.ReviewJob(
                job_id="batch-ocr-001",
                batch_id="batch-ocr",
                group_key="case-ocr",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    ADAPTER.SourceAsset(
                        asset_id="asset-001",
                        source_path=str(contract_path),
                        relative_path="raw/case-ocr/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="甲方：客户A 产品名称 费用合计（元）",
                        text_extract_method="docx_text",
                        metadata={
                            "preview_available": True,
                            "needs_ocr": False,
                            "staged_input_path": str(contract_path),
                        },
                    ),
                    ADAPTER.SourceAsset(
                        asset_id="asset-002",
                        source_path=str(image_path),
                        relative_path="raw/case-ocr/尺寸图.png",
                        file_name="尺寸图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        metadata={
                            "preview_available": False,
                            "needs_ocr": True,
                            "staged_input_path": str(image_path),
                        },
                    ),
                ],
            )
            job_dir = root / "runtime" / "jobs" / job.job_id
            (job_dir / "normalized").mkdir(parents=True)
            (job_dir / "output").mkdir(parents=True)

            def fake_ocr_extractor(asset, *, source_path, job_dir, config):
                output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
                output_dir.mkdir(parents=True, exist_ok=True)
                markdown_path = output_dir / "combined.md"
                json_path = output_dir / "summary.json"
                markdown_path.write_text(
                    "尺寸备注：宽900mm，高2400mm。\n备注：现场复尺后下单。\n费用合计：5600元\n",
                    encoding="utf-8",
                )
                json_path.write_text(
                    json.dumps(
                        {
                            "backend": "paddleocr",
                            "status": "succeeded",
                            "pages": 1,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                return {
                    "asset_id": asset.asset_id,
                    "status": "succeeded",
                    "backend": "paddleocr",
                    "text_preview": "尺寸备注：宽900mm，高2400mm。",
                    "text_extract_method": "paddleocr_pp_structurev3",
                    "output_dir": str(output_dir),
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                    "page_count": 1,
                }

            REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=job_dir,
                extraction_config=REVIEW_PIPELINE.ExtractionConfig(ocr_backend="paddleocr"),
                ocr_extractor=fake_ocr_extractor,
            )

            review_json_path = job_dir / "output" / "review.json"
            replay_json_path = job_dir / "output" / "replay.json"
            extraction_json_path = job_dir / "normalized" / "extraction-results.json"
            review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
            replay_payload = json.loads(replay_json_path.read_text(encoding="utf-8"))
            extraction_payload = json.loads(extraction_json_path.read_text(encoding="utf-8"))
            extraction_by_id = {item["asset_id"]: item for item in extraction_payload["assets"]}

            finding_codes = {item["code"] for item in review_payload["findings"]}
            self.assertNotIn("job.visual_assets_need_ocr", finding_codes)
            self.assertEqual(review_payload["automation_state"], "ocr_evidence_ready")
            self.assertEqual(review_payload["summary"]["ocr_completed_asset_count"], 1)
            self.assertEqual(extraction_by_id["asset-002"]["status"], "succeeded")
            self.assertEqual(review_payload["contract_audit"]["financials"]["contract_total"]["value"], "5600元")
            self.assertEqual(
                review_payload["contract_audit"]["financials"]["contract_total"]["evidence_refs"][0]["source_kind"],
                "ocr_markdown",
            )
            self.assertTrue(
                any("现场复尺后下单" in item["text"] for item in review_payload["contract_audit"]["special_notes"])
            )
            self.assertEqual(replay_payload["status"], "blocked")
            self.assertIn("已完成 OCR", replay_payload["reason"])
            review_markdown = (job_dir / "output" / "review.md").read_text(encoding="utf-8")
            self.assertIn("source=ocr_markdown", review_markdown)
            self.assertIn("evidence_refs=1", review_markdown)

    def test_run_review_job_reports_field_conflict_between_native_and_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.docx"
            image_path = root / "尺寸图.png"
            write_minimal_docx(contract_path, ["产品名称：书柜", "长度：2400mm", "本单按定制执行"])
            image_path.write_bytes(b"fake-image")

            job = ADAPTER.ReviewJob(
                job_id="batch-conflict-001",
                batch_id="batch-conflict",
                group_key="case-conflict",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    ADAPTER.SourceAsset(
                        asset_id="asset-001",
                        source_path=str(contract_path),
                        relative_path="raw/case-conflict/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="产品名称：书柜 长度：2400mm 本单按定制执行",
                        text_extract_method="docx_text",
                        metadata={
                            "preview_available": True,
                            "needs_ocr": False,
                            "staged_input_path": str(contract_path),
                        },
                    ),
                    ADAPTER.SourceAsset(
                        asset_id="asset-002",
                        source_path=str(image_path),
                        relative_path="raw/case-conflict/尺寸图.png",
                        file_name="尺寸图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        metadata={
                            "preview_available": False,
                            "needs_ocr": True,
                            "staged_input_path": str(image_path),
                        },
                    ),
                ],
            )
            job_dir = root / "runtime" / "jobs" / job.job_id
            (job_dir / "normalized").mkdir(parents=True)
            (job_dir / "output").mkdir(parents=True)

            def fake_ocr_extractor(asset, *, source_path, job_dir, config):
                output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
                output_dir.mkdir(parents=True, exist_ok=True)
                markdown_path = output_dir / "combined.md"
                json_path = output_dir / "summary.json"
                markdown_path.write_text("长度：2500mm\n", encoding="utf-8")
                json_path.write_text(
                    json.dumps(
                        {
                            "backend": "paddleocr",
                            "status": "succeeded",
                            "pages": 1,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                return {
                    "asset_id": asset.asset_id,
                    "status": "succeeded",
                    "backend": "paddleocr",
                    "text_preview": "长度：2500mm",
                    "text_extract_method": "paddleocr_pp_structurev3",
                    "output_dir": str(output_dir),
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                    "page_count": 1,
                }

            REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=job_dir,
                extraction_config=REVIEW_PIPELINE.ExtractionConfig(ocr_backend="paddleocr"),
                ocr_extractor=fake_ocr_extractor,
            )

            review_payload = json.loads((job_dir / "output" / "review.json").read_text(encoding="utf-8"))
            review_markdown = (job_dir / "output" / "review.md").read_text(encoding="utf-8")

            self.assertEqual(review_payload["contract_audit"]["field_conflicts"][0]["field_name"], "length")
            self.assertIn("length_value_conflict_detected", review_payload["contract_audit"]["risk_flags"])
            self.assertEqual(review_payload["contract_audit"]["field_conflicts"][0]["severity"], "high")
            self.assertEqual(
                review_payload["contract_audit"]["conflict_resolution_suggestions"][0]["recommended_action"],
                "prefer_ocr_drawing",
            )
            self.assertIn("field_conflicts", review_markdown)
            self.assertIn("severity=high", review_markdown)
            self.assertIn("prefer_ocr_drawing", review_markdown)

    def test_run_review_job_prefers_ocr_full_text_over_truncated_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.docx"
            write_minimal_docx(contract_path, ["产品名称：书柜"])

            job = ADAPTER.ReviewJob(
                job_id="batch-ocr-fulltext-001",
                batch_id="batch-ocr-fulltext",
                group_key="case-ocr-fulltext",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    ADAPTER.SourceAsset(
                        asset_id="asset-001",
                        source_path=str(contract_path),
                        relative_path="raw/case-ocr-fulltext/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="产品名称：书柜",
                        text_extract_method="docx_text",
                        metadata={
                            "preview_available": True,
                            "needs_ocr": True,
                            "staged_input_path": str(contract_path),
                        },
                    ),
                ],
            )
            job_dir = root / "runtime" / "jobs" / job.job_id
            (job_dir / "normalized").mkdir(parents=True)
            (job_dir / "output").mkdir(parents=True)

            def fake_ocr_extractor(asset, *, source_path, job_dir, config):
                output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
                output_dir.mkdir(parents=True, exist_ok=True)
                markdown_path = output_dir / "combined.md"
                json_path = output_dir / "summary.json"
                full_text = (
                    "第13页 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
                    "经典带门书柜 20990010004003 北美樱桃木 1 11952 "
                    "第18页 儿童房 经典带门书柜 209900100 04003北美樱桃木 尺寸 长：1800mm 宽：350mm 高：2100mm"
                )
                markdown_path.write_text(full_text, encoding="utf-8")
                json_path.write_text(
                    json.dumps({"backend": "paddleocr", "status": "succeeded", "pages": 2}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return {
                    "asset_id": asset.asset_id,
                    "status": "succeeded",
                    "backend": "paddleocr",
                    "text_preview": "经典带门书柜 20990010004003",
                    "full_text": full_text,
                    "text_extract_method": "paddleocr_pp_structurev3",
                    "output_dir": str(output_dir),
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                    "page_count": 2,
                }

            REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=job_dir,
                extraction_config=REVIEW_PIPELINE.ExtractionConfig(ocr_backend="paddleocr", force_ocr_for_documents=True),
                ocr_extractor=fake_ocr_extractor,
            )

            review_payload = json.loads((job_dir / "output" / "review.json").read_text(encoding="utf-8"))
            normalized_fields = json.loads((job_dir / "normalized" / "normalized-fields.json").read_text(encoding="utf-8"))
            self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "经典带门书柜")
            self.assertEqual(normalized_fields["fields"]["length"]["value"], "1800mm")

    def test_run_review_job_merges_native_and_ocr_text_for_document_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            contract_path = root / "合同.pdf"
            contract_path.write_bytes(b"%PDF-1.4 fake")

            job = ADAPTER.ReviewJob(
                job_id="batch-ocr-merge-001",
                batch_id="batch-ocr-merge",
                group_key="case-ocr-merge",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    ADAPTER.SourceAsset(
                        asset_id="asset-001",
                        source_path=str(contract_path),
                        relative_path="raw/case-ocr-merge/合同.pdf",
                        file_name="合同.pdf",
                        extension=".pdf",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="第1页 合同总金额 19000元",
                        text_extract_method="pdf_text_layer",
                        metadata={
                            "preview_available": True,
                            "needs_ocr": True,
                            "staged_input_path": str(contract_path),
                        },
                    ),
                ],
            )
            job_dir = root / "runtime" / "jobs" / job.job_id
            (job_dir / "normalized").mkdir(parents=True)
            (job_dir / "output").mkdir(parents=True)

            def fake_ocr_extractor(asset, *, source_path, job_dir, config):
                output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
                output_dir.mkdir(parents=True, exist_ok=True)
                markdown_path = output_dir / "combined.md"
                json_path = output_dir / "summary.json"
                full_text = "第14页 附件：《定制清单及设计图纸》 儿童房 其他书桌 尺寸 长：2580mm 宽：900mm 高：1080mm"
                markdown_path.write_text(full_text, encoding="utf-8")
                json_path.write_text(
                    json.dumps({"backend": "paddleocr", "status": "succeeded", "pages": 1}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return {
                    "asset_id": asset.asset_id,
                    "status": "succeeded",
                    "backend": "paddleocr",
                    "text_preview": "其他书桌 尺寸 长：2580mm",
                    "full_text": full_text,
                    "text_extract_method": "paddleocr_pp_structurev3",
                    "output_dir": str(output_dir),
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                    "page_count": 1,
                }

            REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=job_dir,
                extraction_config=REVIEW_PIPELINE.ExtractionConfig(ocr_backend="paddleocr"),
                ocr_extractor=fake_ocr_extractor,
            )

            asset = job.assets[0]
            self.assertEqual(asset.text_extract_method, "native_plus_ocr")
            self.assertIn("合同总金额 19000元", asset.text_preview)
            self.assertIn("[OCR补充]", asset.text_preview)
            self.assertIn("其他书桌 尺寸 长：2580mm", asset.text_preview)

    def test_cli_outputs_contract_audit_summary_with_notes_and_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-audit"
            raw_dir = batch_dir / "raw" / "case-audit"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "本单按定制执行",
                    "长度：2400mm",
                    "高度：2100mm",
                    "费用合计：19800元",
                    "增项费用：拉手升级 600元",
                    "备注：见光面统一顺纹，现场避开踢脚线。",
                    "特殊说明：到顶封板需现场复尺。",
                ],
            )
            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-audit",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"

            CLI.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(runtime_root),
                    "--ocr-backend",
                    "disabled",
                    "--output-mode",
                    "json",
                ]
            )

            review_json_path = runtime_root / "jobs" / "batch-audit-001" / "output" / "review.json"
            review_markdown_path = runtime_root / "jobs" / "batch-audit-001" / "output" / "review.md"
            review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
            review_markdown = review_markdown_path.read_text(encoding="utf-8")

            self.assertEqual(review_payload["contract_audit"]["financials"]["contract_total"]["value"], "19800元")
            self.assertEqual(review_payload["contract_audit"]["financials"]["add_on_items"][0]["amount"], "600元")
            self.assertEqual(review_payload["contract_audit"]["pricing_alignment"]["next_required_field"], "depth")
            self.assertIn("depth", review_payload["contract_audit"]["pricing_alignment"]["missing_for_pricing"])
            self.assertIn("见光面统一顺纹", review_markdown)
            self.assertIn("合同审核摘要", review_markdown)

    def test_cli_sorts_batch_summary_by_review_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-priority"
            raw_dir = batch_dir / "raw"

            normal_dir = raw_dir / "case-01-normal"
            normal_dir.mkdir(parents=True)
            write_minimal_docx(
                normal_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "本单按定制执行",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "费用合计：19800元",
                ],
            )

            p1_dir = raw_dir / "case-02-p1"
            p1_dir.mkdir(parents=True)
            write_minimal_docx(
                p1_dir / "合同-A.docx",
                [
                    "产品名称：书柜",
                    "本单按定制执行",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                ],
            )
            write_minimal_docx(
                p1_dir / "合同-B.docx",
                [
                    "产品名称：书柜",
                    "本单按定制执行",
                    "长度：2500mm",
                    "进深：350mm",
                    "高度：2100mm",
                ],
            )

            p0_dir = raw_dir / "case-03-p0"
            p0_dir.mkdir(parents=True)
            write_minimal_docx(
                p0_dir / "合同-A.docx",
                [
                    "产品名称：书柜",
                    "本单按定制执行",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "费用合计：19800元",
                ],
            )
            write_minimal_docx(
                p0_dir / "合同-B.docx",
                [
                    "产品名称：书柜",
                    "本单按定制执行",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "费用合计：20800元",
                ],
            )

            manifest = {
                "source_type": "manual_batch",
                "source_channel": "manual",
                "source_batch_id": "batch-priority",
                "requested_actions": ["audit", "replay"],
            }
            (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            runtime_root = root / "runtime"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                summary = CLI.run(
                    [
                        "--batch-dir",
                        str(batch_dir),
                        "--runtime-root",
                        str(runtime_root),
                        "--ocr-backend",
                        "disabled",
                        "--output-mode",
                        "text",
                    ]
                )

            self.assertEqual(
                [item["job_id"] for item in summary["jobs"]],
                ["batch-priority-003", "batch-priority-002", "batch-priority-001"],
            )
            self.assertEqual(
                [item["review_priority"] for item in summary["jobs"]],
                ["p0", "p1", "normal"],
            )
            self.assertEqual(summary["jobs"][0]["review_priority_reason"], "contract_total:manual_review_required")
            self.assertEqual(summary["jobs"][1]["review_priority_reason"], "length:prefer_primary_contract")
            self.assertEqual(summary["jobs"][2]["review_priority_reason"], "")

            batch_summary_payload = json.loads(
                (runtime_root / "batches" / "batch-priority" / "batch-summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [item["review_priority"] for item in batch_summary_payload["jobs"]],
                ["p0", "p1", "normal"],
            )

            queue_json_path = runtime_root / "batches" / "batch-priority" / "manual-review-queue.json"
            queue_md_path = runtime_root / "batches" / "batch-priority" / "manual-review-queue.md"
            self.assertTrue(queue_json_path.exists())
            self.assertTrue(queue_md_path.exists())

            queue_payload = json.loads(queue_json_path.read_text(encoding="utf-8"))
            self.assertEqual(queue_payload["batch_id"], "batch-priority")
            self.assertEqual(queue_payload["queue_count"], 3)
            self.assertEqual(
                [item["job_id"] for item in queue_payload["items"]],
                ["batch-priority-003", "batch-priority-002", "batch-priority-001"],
            )
            self.assertEqual(queue_payload["items"][0]["conflict_fields"], ["contract_total"])
            self.assertEqual(queue_payload["items"][0]["manual_review_reasons"][0], "contract_total:manual_review_required")
            self.assertEqual(queue_payload["items"][1]["conflict_fields"], ["length"])
            self.assertEqual(queue_payload["items"][1]["manual_review_reasons"][0], "length:prefer_primary_contract")
            self.assertEqual(queue_payload["items"][2]["conflict_fields"], [])

            queue_markdown = queue_md_path.read_text(encoding="utf-8")
            self.assertIn("人工复核队列", queue_markdown)
            self.assertIn("contract_total:manual_review_required", queue_markdown)
            self.assertIn("length:prefer_primary_contract", queue_markdown)

            dashboard_json_path = runtime_root / "batches" / "batch-priority" / "batch-dashboard.json"
            dashboard_md_path = runtime_root / "batches" / "batch-priority" / "batch-dashboard.md"
            diagnosis_json_path = runtime_root / "batches" / "batch-priority" / "pricing-compare-diagnosis.json"
            diagnosis_md_path = runtime_root / "batches" / "batch-priority" / "pricing-compare-diagnosis.md"
            self.assertTrue(dashboard_json_path.exists())
            self.assertTrue(dashboard_md_path.exists())
            self.assertTrue(diagnosis_json_path.exists())
            self.assertTrue(diagnosis_md_path.exists())

            dashboard_payload = json.loads(dashboard_json_path.read_text(encoding="utf-8"))
            self.assertEqual(dashboard_payload["batch_id"], "batch-priority")
            self.assertEqual(dashboard_payload["job_count"], 3)
            self.assertEqual(dashboard_payload["review_priority_breakdown"]["p0"], 1)
            self.assertEqual(dashboard_payload["review_priority_breakdown"]["p1"], 1)
            self.assertEqual(dashboard_payload["review_priority_breakdown"]["normal"], 1)
            self.assertEqual(
                dashboard_payload["top_priority_job_ids"],
                ["batch-priority-003", "batch-priority-002", "batch-priority-001"],
            )
            self.assertEqual(dashboard_payload["manual_queue_count"], 3)
            self.assertEqual(dashboard_payload["ocr_blocked_count"], 0)
            self.assertIn("pricing_compare_breakdown", dashboard_payload)

            dashboard_markdown = dashboard_md_path.read_text(encoding="utf-8")
            self.assertIn("批次首页", dashboard_markdown)
            self.assertIn("top_priority_job_ids", dashboard_markdown)
            self.assertIn("batch-priority-003", dashboard_markdown)
            self.assertIn("报价对比分布", dashboard_markdown)

            diagnosis_payload = json.loads(diagnosis_json_path.read_text(encoding="utf-8"))
            self.assertEqual(diagnosis_payload["batch_id"], "batch-priority")
            self.assertEqual(diagnosis_payload["item_count"], 3)
            diagnosis_markdown = diagnosis_md_path.read_text(encoding="utf-8")
            self.assertIn("报价诊断", diagnosis_markdown)
            self.assertIn("逐单诊断", diagnosis_markdown)

            output = stdout.getvalue()
            self.assertIn("priority=p0", output)
            self.assertIn("priority=p1", output)
            self.assertIn("priority=normal", output)
            self.assertLess(output.index("batch-priority-003"), output.index("batch-priority-002"))
            self.assertLess(output.index("batch-priority-002"), output.index("batch-priority-001"))


if __name__ == "__main__":
    unittest.main()
