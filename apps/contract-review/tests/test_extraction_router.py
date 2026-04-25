import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from PyPDF2 import PdfWriter
except ModuleNotFoundError:  # pragma: no cover - optional test dependency
    PdfWriter = None


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

JOB_MODELS_PATH = CORE_ROOT / "job_models.py"
EXTRACTION_ROUTER_PATH = CORE_ROOT / "extraction_router.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


JOB_MODELS = load_module("contract_review_job_models_for_extraction_router", JOB_MODELS_PATH)
EXTRACTION_ROUTER = load_module("contract_review_extraction_router_for_tests", EXTRACTION_ROUTER_PATH)


@unittest.skipUnless(PdfWriter is not None, "PyPDF2 is required for extraction router tests")
class ExtractionRouterTests(unittest.TestCase):
    def test_extract_asset_reuses_cached_paddleocr_result_between_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache_root = root / "ocr-cache"
            source_path = root / "合同.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.add_blank_page(width=300, height=300)
            writer.add_blank_page(width=300, height=300)
            with source_path.open("wb") as handle:
                writer.write(handle)

            asset = JOB_MODELS.SourceAsset(
                asset_id="asset-001",
                source_path=str(source_path),
                relative_path="raw/case-001/合同.pdf",
                file_name="合同.pdf",
                extension=".pdf",
                media_kind="document",
                role_hint="primary_contract",
                text_preview=(
                    "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》）。"
                    "第3页 附件：《定制清单及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
                    "其他书桌 20260422005002 北美樱桃木 1 8800"
                ),
                metadata={"needs_ocr": True},
            )
            config = EXTRACTION_ROUTER.ExtractionConfig()

            def fake_extract(*_args, source_path: Path, job_dir: Path, **_kwargs):
                output_dir = job_dir / "normalized" / "ocr" / asset.asset_id
                page_dir = output_dir / "page-001"
                page_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "combined.md").write_text("图纸 OCR 尺寸 2000mm\n", encoding="utf-8")
                (page_dir / "result.json").write_text("{}", encoding="utf-8")
                EXTRACTION_ROUTER.write_json(
                    output_dir / "summary.json",
                    {
                        "asset_id": asset.asset_id,
                        "backend": "paddleocr",
                        "status": "succeeded",
                        "source_path": str(source_path),
                        "page_count": 1,
                        "markdown_path": str(output_dir / "combined.md"),
                        "pages": [
                            {
                                "page_no": 1,
                                "json_path": str(page_dir / "result.json"),
                                "markdown_dir": str(page_dir),
                                "markdown_text_length": 14,
                            }
                        ],
                    },
                )
                return {
                    "asset_id": asset.asset_id,
                    "status": "succeeded",
                    "backend": "paddleocr",
                    "reason": "ocr_completed",
                    "text_preview": "图纸 OCR 尺寸 2000mm",
                    "full_text": "图纸 OCR 尺寸 2000mm",
                    "text_extract_method": "paddleocr_pp_structurev3",
                    "output_dir": str(output_dir),
                    "markdown_path": str(output_dir / "combined.md"),
                    "json_path": str(output_dir / "summary.json"),
                    "page_count": 1,
                }

            first_job_dir = root / "runtime" / "job-001"
            second_job_dir = root / "runtime" / "job-002"
            first_job_dir.mkdir(parents=True)
            second_job_dir.mkdir(parents=True)

            with mock.patch.object(EXTRACTION_ROUTER, "_paddleocr_cache_root", return_value=cache_root):
                with mock.patch.object(EXTRACTION_ROUTER, "_extract_with_paddleocr", side_effect=fake_extract) as mock_extract:
                    first_record = EXTRACTION_ROUTER.extract_asset(
                        asset,
                        job_dir=first_job_dir,
                        config=config,
                    )
                    self.assertEqual(first_record["status"], "succeeded")
                    self.assertEqual(mock_extract.call_count, 1)

                with mock.patch.object(
                    EXTRACTION_ROUTER,
                    "_extract_with_paddleocr",
                    side_effect=AssertionError("cache hit should skip OCR execution"),
                ):
                    second_record = EXTRACTION_ROUTER.extract_asset(
                        asset,
                        job_dir=second_job_dir,
                        config=config,
                    )

            self.assertEqual(second_record["status"], "succeeded")
            self.assertEqual(second_record["reason"], "ocr_cache_hit")
            self.assertEqual(second_record["cache_status"], "hit")
            self.assertTrue((second_job_dir / "normalized" / "ocr" / asset.asset_id / "combined.md").exists())
            summary = json.loads(
                (second_job_dir / "normalized" / "ocr" / asset.asset_id / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["asset_id"], asset.asset_id)
            self.assertEqual(summary["page_count"], 1)

    def test_extract_asset_falls_back_to_project_venv_when_local_paddleocr_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "合同.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.add_blank_page(width=300, height=300)
            writer.add_blank_page(width=300, height=300)
            with source_path.open("wb") as handle:
                writer.write(handle)
            job_dir = root / "runtime" / "job-001"
            job_dir.mkdir(parents=True)

            asset = JOB_MODELS.SourceAsset(
                asset_id="asset-001",
                source_path=str(source_path),
                relative_path="raw/case-001/合同.pdf",
                file_name="合同.pdf",
                extension=".pdf",
                media_kind="document",
                role_hint="primary_contract",
                text_preview=(
                    "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》）。"
                    "第3页 附件：《定制清单及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
                    "其他书桌 20260422005002 北美樱桃木 1 8800"
                ),
                metadata={"needs_ocr": True},
            )
            config = EXTRACTION_ROUTER.ExtractionConfig()
            payload = {
                "asset_id": asset.asset_id,
                "status": "succeeded",
                "backend": "paddleocr",
                "reason": "ocr_completed",
                "text_preview": "图纸 OCR 尺寸 2000mm",
                "full_text": "图纸 OCR 尺寸 2000mm 深度 450mm",
                "text_extract_method": "paddleocr_pp_structurev3",
                "output_dir": str(job_dir / "normalized" / "ocr" / asset.asset_id),
                "markdown_path": str(job_dir / "normalized" / "ocr" / asset.asset_id / "combined.md"),
                "json_path": str(job_dir / "normalized" / "ocr" / asset.asset_id / "summary.json"),
                "page_count": 3,
            }

            original_import = __import__

            def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "paddleocr":
                    raise ModuleNotFoundError("No module named 'paddleocr'")
                return original_import(name, globals, locals, fromlist, level)

            with mock.patch("builtins.__import__", side_effect=fake_import):
                with mock.patch.object(
                    EXTRACTION_ROUTER,
                    "_project_paddleocr_python",
                    return_value=Path("/tmp/project-venv/bin/python"),
                ):
                    with mock.patch.object(EXTRACTION_ROUTER.subprocess, "run") as mock_run:
                        mock_run.return_value = subprocess.CompletedProcess(
                            args=["/tmp/project-venv/bin/python"],
                            returncode=0,
                            stdout=json.dumps(payload, ensure_ascii=False),
                            stderr="",
                        )

                        record = EXTRACTION_ROUTER.extract_asset(
                            asset,
                            job_dir=job_dir,
                            config=config,
                        )

            self.assertEqual(record["status"], "succeeded")
            self.assertEqual(record["execution_env"], "project_venv")
            self.assertEqual(record["text_preview"], "图纸 OCR 尺寸 2000mm")
            self.assertEqual(record["page_count"], 3)
            self.assertEqual(record["ocr_scope"], "attachment_pages_only")
            self.assertEqual(record["ocr_start_page"], 3)
            command = mock_run.call_args.args[0]
            self.assertEqual(command[0], "/tmp/project-venv/bin/python")
            self.assertIn("paddleocr_runner.py", command[1])
            self.assertEqual(command[3], asset.asset_id)
            self.assertTrue(command[5].endswith("asset-001-attachment-from-page-003.pdf"))
            self.assertNotEqual(command[5], str(source_path))

    def test_extract_asset_builds_compatible_page_payloads_from_mineru_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "合同.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.add_blank_page(width=300, height=300)
            writer.add_blank_page(width=300, height=300)
            with source_path.open("wb") as handle:
                writer.write(handle)
            job_dir = root / "runtime" / "job-001"
            job_dir.mkdir(parents=True)

            asset = JOB_MODELS.SourceAsset(
                asset_id="asset-001",
                source_path=str(source_path),
                relative_path="raw/case-001/合同.pdf",
                file_name="合同.pdf",
                extension=".pdf",
                media_kind="document",
                role_hint="primary_contract",
                text_preview=(
                    "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》）。"
                    "第3页 附件：《定制清单及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
                    "其他衣柜 20260333003003 北美樱桃木 1 36140"
                ),
                metadata={"needs_ocr": True},
            )
            config = EXTRACTION_ROUTER.ExtractionConfig(ocr_backend="mineru")

            def fake_run(command, **_kwargs):
                raw_output_dir = Path(command[4])
                raw_output_dir.mkdir(parents=True, exist_ok=True)
                (raw_output_dir / "合同.md").write_text("# 合同\n\n第17页 儿童房 其他衣柜\n", encoding="utf-8")
                EXTRACTION_ROUTER.write_json(
                    raw_output_dir / "合同_content_list.json",
                    [
                        {"page_idx": 0, "type": "text", "text": "儿童房 其他衣柜 20260333003003"},
                        {"page_idx": 0, "type": "text", "text": "长：2520mm 宽：600mm 高：2735mm", "bbox": [10, 20, 100, 40]},
                        {"page_idx": 1, "type": "table", "table_body": "<table><tr><td>右边五扇柜门使用大角度铰链</td></tr></table>"},
                    ],
                )
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

            with mock.patch.object(EXTRACTION_ROUTER, "_resolve_mineru_command", return_value=Path("/usr/local/bin/mineru")):
                with mock.patch.object(EXTRACTION_ROUTER.subprocess, "run", side_effect=fake_run) as mock_run:
                    record = EXTRACTION_ROUTER.extract_asset(
                        asset,
                        job_dir=job_dir,
                        config=config,
                    )

            self.assertEqual(record["status"], "succeeded")
            self.assertEqual(record["backend"], "mineru")
            self.assertEqual(record["text_extract_method"], "mineru_pipeline_auto")
            self.assertEqual(record["page_count"], 2)
            self.assertEqual(record["ocr_scope"], "attachment_pages_only")
            self.assertEqual(record["ocr_start_page"], 3)
            command = mock_run.call_args.args[0]
            self.assertEqual(command[0], "/usr/local/bin/mineru")
            self.assertEqual(command[1:5], ["-p", command[2], "-o", command[4]])
            self.assertTrue(command[2].endswith("asset-001-attachment-from-page-003.pdf"))

            summary = json.loads((job_dir / "normalized" / "ocr" / asset.asset_id / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["backend"], "mineru")
            self.assertEqual(summary["page_count"], 2)

            page_payload = json.loads(
                (job_dir / "normalized" / "ocr" / asset.asset_id / "page-001" / "result.json").read_text(encoding="utf-8")
            )
            self.assertIn("儿童房 其他衣柜 20260333003003", page_payload["overall_ocr_res"]["rec_texts"])
            self.assertIn("长：2520mm 宽：600mm 高：2735mm", page_payload["overall_ocr_res"]["rec_texts"])
            page_two_markdown = (
                job_dir / "normalized" / "ocr" / asset.asset_id / "page-002" / "page.md"
            ).read_text(encoding="utf-8")
            self.assertIn("右边五扇柜门使用大角度铰链", page_two_markdown)

    def test_extract_asset_returns_unavailable_when_mineru_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "图纸.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            with source_path.open("wb") as handle:
                writer.write(handle)

            asset = JOB_MODELS.SourceAsset(
                asset_id="asset-mineru-001",
                source_path=str(source_path),
                relative_path="raw/case-001/图纸.pdf",
                file_name="图纸.pdf",
                extension=".pdf",
                media_kind="document",
                role_hint="primary_contract",
                text_preview="第1页 合同正文",
                metadata={"needs_ocr": True},
            )

            with mock.patch.object(EXTRACTION_ROUTER, "_resolve_mineru_command", return_value=None):
                record = EXTRACTION_ROUTER.extract_asset(
                    asset,
                    job_dir=root / "runtime" / "job-001",
                    config=EXTRACTION_ROUTER.ExtractionConfig(ocr_backend="mineru"),
                )

            self.assertEqual(record["status"], "unavailable")
            self.assertEqual(record["backend"], "mineru")
            self.assertEqual(record["reason"], "mineru_not_installed")


if __name__ == "__main__":
    unittest.main()
