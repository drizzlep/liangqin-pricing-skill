import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

JOB_MODELS_PATH = CORE_ROOT / "job_models.py"
REVIEW_PIPELINE_PATH = CORE_ROOT / "review_pipeline.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


JOB_MODELS = load_module("contract_review_job_models_for_review_pipeline", JOB_MODELS_PATH)
REVIEW_PIPELINE = load_module("contract_review_review_pipeline_for_tests", REVIEW_PIPELINE_PATH)


class ReviewPipelineTests(unittest.TestCase):
    def test_count_unique_product_codes_ignores_contract_number(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-single-code",
            batch_id="batch",
            group_key="case-single",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/contract.pdf",
                    relative_path="raw/case-single/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第13页 20990040009演示合同 产品名称 华夫格软包箱体床 20990040009001 "
                        "第14页 主卧 华夫格软包箱体床 209900400 09001"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        self.assertEqual(REVIEW_PIPELINE._count_unique_product_codes(job), 1)

    def test_count_unique_product_codes_keeps_multi_product_contract(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-multi-code",
            batch_id="batch",
            group_key="case-multi",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/contract.pdf",
                    relative_path="raw/case-multi/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第13页 20990010004演示合同 产品名称 经典床头柜 120990010004001 "
                        "其他床 20990010004002 经典带门书柜 20990010004003 经典双屉书桌 20990010004004"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        self.assertEqual(REVIEW_PIPELINE._count_unique_product_codes(job), 4)

    def test_run_review_job_applies_mattress_bed_fallback_for_single_contract(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-single-bed",
            batch_id="batch",
            group_key="case-single-bed",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/contract.pdf",
                    relative_path="raw/case-single-bed/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第1页 合同总金额为人民币8200元。"
                        " 第13页 附件：产品名称 产品编号 材质 数量 费用合计（元） 华夫格软包箱体床20990040009001 北美樱桃木 1 8200 合计 8200 折扣 100折 折扣后合计 8200。"
                        " 第14页 主卧 华夫格软包箱体床 20990040009001 北美樱桃木 尺寸 长：1560mm 宽：2120mm 高：1050mm。"
                        " 注明：床垫尺寸1.5*2米，床垫厚度建议20cm。"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=Path(tmpdir),
            )
            review_payload = json.loads((Path(tmpdir) / "output" / "review.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["pricing_total"], "8200元")
        self.assertEqual(payload["pricing_route"], "bed_mattress_area_fallback")
        self.assertEqual(payload["pricing_compare_best_match_diff"], "0元")
        self.assertEqual(review_payload["formal_quote"]["pricing_total"], "8200元")
        self.assertEqual(review_payload["formal_quote"]["pricing_route"], "bed_mattress_area_fallback")
        self.assertEqual(review_payload["pricing_compare"]["best_match_diff"], "0元")

    def test_run_review_job_applies_explicit_catalog_code_fallback_for_single_contract(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-explicit-code-bed",
            batch_id="batch",
            group_key="case-explicit-code-bed",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/contract.pdf",
                    relative_path="raw/case-explicit-code-bed/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第1页 合同总金额为人民币12545元。"
                        " 第13页 附件：产品名称 产品编号 材质 数量 费用合计（元） 支腿架式床20990050001001 北美黑胡桃木 1 12934 合计 12934 折扣 97折 折扣后合计 12545。"
                        " 第14页 主卧 支腿架式床 20990050001001 北美黑胡桃木 尺寸 长：2000mm 宽：1800mm 高：150mm。"
                        " 注明：在标准 JSC-03 基础上更改，更改如下：床头板封死；床腿加高50mm；排骨架下潜30mm。"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=Path(tmpdir),
            )
            review_payload = json.loads((Path(tmpdir) / "output" / "review.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["pricing_total"], "11800元")
        self.assertEqual(payload["pricing_route"], "explicit_catalog_code_fallback")
        self.assertEqual(payload["pricing_compare_best_match_diff"], "745元")
        self.assertEqual(review_payload["formal_quote"]["fallback_strategy"], "explicit_catalog_code")
        self.assertEqual(review_payload["formal_quote"]["fallback_detail"]["matched_product_code"], "JSC-03")
        self.assertEqual(review_payload["formal_quote"]["pricing_total"], "11800元")

    def test_run_review_job_scales_single_contract_quote_by_quantity(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-single-quantity",
            batch_id="batch",
            group_key="case-single-quantity",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/contract.pdf",
                    relative_path="raw/case-single-quantity/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第1页 合同总金额为人民币5000元。"
                        " 第13页 附件：产品名称 产品编号 材质 数量 费用合计（元） 新Y椅20990060006001 北美黑胡桃木 2 5000 合计 5000。"
                        " 第14页 客厅 新Y椅 20990060006001 北美黑胡桃木 尺寸 长：mm 宽：mm 高：mm 2 注明：黑胡桃新Y椅。"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=Path(tmpdir),
            )
            review_payload = json.loads((Path(tmpdir) / "output" / "review.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["pricing_total"], "5200元")
        self.assertEqual(review_payload["formal_quote"]["quantity_multiplier"], 2)
        self.assertEqual(review_payload["formal_quote"]["prepared_payload"]["total"], "5200元")
        self.assertIn("数量：2", review_payload["formal_quote"]["prepared_payload"]["items"][0]["calculation_steps"])

    def test_run_review_job_prefers_cabinet_fallback_when_list_price_is_closer(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-single-cabinet-fallback",
            batch_id="batch",
            group_key="case-single-cabinet-fallback",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/contract.pdf",
                    relative_path="raw/case-single-cabinet-fallback/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第1页 合同总金额为人民币21611元。"
                        " 第13页 附件：产品名称 产品编号 材质 数量 费用合计（元） 定制组合书柜20990070003001 乌拉圭玫瑰木 1 24013 合计 24013 折扣 90折 折扣后合计 21611。"
                        " 第14页 书房 定制组合书柜 20990070003001 乌拉圭玫瑰木 尺寸 长：2165mm 宽：450mm 高：2500mm。"
                        " 第16页 外尺寸如图，玻璃为超白玻璃。"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = REVIEW_PIPELINE.run_review_job(
                job,
                job_dir=Path(tmpdir),
            )
            review_payload = json.loads((Path(tmpdir) / "output" / "review.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["pricing_total"], "24326元")
        self.assertEqual(payload["pricing_compare_best_match_target"], "list_price_total")
        self.assertEqual(payload["pricing_compare_best_match_diff"], "313元")
        self.assertEqual(review_payload["formal_quote"]["pricing_route"], "cabinet_projection_area_fallback")
        self.assertEqual(review_payload["formal_quote"]["fallback_strategy"], "generic_cabinet_projection_profile")
        self.assertEqual(review_payload["formal_quote"]["fallback_detail"]["matched_product_code"], "SG-11")


if __name__ == "__main__":
    unittest.main()
