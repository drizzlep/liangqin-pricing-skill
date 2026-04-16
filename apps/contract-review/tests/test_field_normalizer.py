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

FIELD_NORMALIZER_PATH = CORE_ROOT / "field_normalizer.py"
JOB_MODELS_PATH = CORE_ROOT / "job_models.py"
PRICING_BRIDGE_PATH = CORE_ROOT / "pricing_bridge.py"
PRODUCT_CODE_UTILS_PATH = CORE_ROOT / "product_code_utils.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FIELD_NORMALIZER = load_module("contract_review_field_normalizer", FIELD_NORMALIZER_PATH)
JOB_MODELS = load_module("contract_review_job_models_for_normalizer", JOB_MODELS_PATH)
PRICING_BRIDGE = load_module("contract_review_pricing_bridge_for_normalizer", PRICING_BRIDGE_PATH)
PRODUCT_CODE_UTILS = load_module("contract_review_product_code_utils_for_normalizer", PRODUCT_CODE_UTILS_PATH)
TEMPLATE_LEARNING_PATH = CORE_ROOT / "template_learning.py"
TEMPLATE_LEARNING = load_module("contract_review_template_learning_for_normalizer", TEMPLATE_LEARNING_PATH)


class FieldNormalizerTests(unittest.TestCase):
    def test_normalizer_extracts_modular_child_bed_fields(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-bed-001",
            batch_id="batch-bed",
            group_key="case-bed",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.docx",
                    relative_path="raw/case-bed/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称：儿童上下床\n"
                        "本单按定制执行\n"
                        "床形态：上下床\n"
                        "上层出入方式：直梯\n"
                        "下层结构：箱体床\n"
                        "围栏样式：篱笆围栏\n"
                        "床垫宽度：900mm\n"
                        "床垫长度：2000mm\n"
                        "材质：乌拉圭玫瑰木\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]

        self.assertEqual(fields["product_category"]["value"], "儿童上下床")
        self.assertEqual(fields["quote_kind"]["value"], "custom")
        self.assertEqual(fields["bed_form"]["value"], "上下床")
        self.assertEqual(fields["access_style"]["value"], "直梯")
        self.assertEqual(fields["lower_bed_type"]["value"], "箱体床")
        self.assertEqual(fields["guardrail_style"]["value"], "篱笆围栏")
        self.assertEqual(fields["width"]["value"], "900mm")
        self.assertEqual(fields["length"]["value"], "2000mm")
        self.assertEqual(fields["wood_material"]["value"], "乌拉圭玫瑰木")

    def test_normalized_modular_child_bed_fields_can_pass_pricing_precheck(self) -> None:
        result = PRICING_BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "儿童上下床", "confidence": 0.98},
                "quote_kind": {"value": "custom", "confidence": 0.95},
                "bed_form": {"value": "上下床", "confidence": 0.96},
                "access_style": {"value": "直梯", "confidence": 0.96},
                "lower_bed_type": {"value": "箱体床", "confidence": 0.96},
                "guardrail_style": {"value": "篱笆围栏", "confidence": 0.96},
                "width": {"value": "900mm", "confidence": 0.95},
                "length": {"value": "2000mm", "confidence": 0.95},
                "wood_material": {"value": "乌拉圭玫瑰木", "confidence": 0.95},
            }
        )

        self.assertEqual(result["status"], "ready_for_formal_quote")
        self.assertEqual(result["precheck_result"]["pricing_route"], "modular_child_bed")
        self.assertTrue(result["precheck_result"]["ready_for_formal_quote"])

    def test_normalizer_extracts_cabinet_door_fields(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-cabinet-001",
            batch_id="batch-cabinet",
            group_key="case-cabinet",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.docx",
                    relative_path="raw/case-cabinet/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称：玄关柜\n"
                        "长度：1800mm\n"
                        "进深：400mm\n"
                        "高度：2100mm\n"
                        "材质：北美白橡木\n"
                        "柜体形式：带门\n"
                        "门型：平板门\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]

        self.assertEqual(fields["product_category"]["value"], "玄关柜")
        self.assertEqual(fields["has_door"]["value"], "yes")
        self.assertEqual(fields["door_type"]["value"], "平板门")

    def test_normalizer_extracts_real_contract_cabinet_fields_from_pdf_preview(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-real-cabinet-001",
            batch_id="batch-real",
            group_key="case-real-cabinet",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-real-cabinet.pdf",
                    relative_path="raw/case-real-cabinet/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第13页 产品名称 其他衣柜 材质 北美黑胡桃木 费用合计（元） 43708 折扣后合计 41085\n"
                        "第14页 主卧 其他衣柜 尺寸 长：2300mm 宽：600mm 高：2575mm "
                        "柜门扣手均为通长扣手"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]

        self.assertEqual(fields["product_category"]["value"], "衣柜")
        self.assertEqual(fields["wood_material"]["value"], "北美黑胡桃木")
        self.assertEqual(fields["length"]["value"], "2300mm")
        self.assertEqual(fields["width"]["value"], "600mm")
        self.assertEqual(fields["height"]["value"], "2575mm")

    def test_normalizer_scans_attachment_section_only_when_contract_body_repeats_before_it(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-attachment-focus-001",
            batch_id="batch-real",
            group_key="case-attachment-focus",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-attachment-focus.pdf",
                    relative_path="raw/case-attachment-focus/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》），合同总金额为人民币41085元。"
                        "第13页 附件：《定制清单及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
                        "其他衣柜 20260350004003 北美黑胡桃木 1 41085 "
                        "第14页 主卧 其他衣柜 202603500 04003 尺寸 长：2300mm 宽：600mm 高：2575mm"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]

        self.assertEqual(fields["product_category"]["value"], "衣柜")
        self.assertEqual(fields["wood_material"]["value"], "北美黑胡桃木")
        self.assertEqual(fields["length"]["value"], "2300mm")
        self.assertEqual(fields["width"]["value"], "600mm")
        self.assertEqual(fields["height"]["value"], "2575mm")

    def test_normalizer_prefers_specific_model_from_single_product_contract_preview(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-real-bed-001",
            batch_id="batch-real",
            group_key="case-real-bed",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-real-bed.pdf",
                    relative_path="raw/case-real-bed/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第13页 20260379009客户合同 产品名称 华夫格软包 箱体床 20260379009001 "
                        "材质 北美樱桃木 合计 8200 折扣后合计 8200 "
                        "第14页 主卧 华夫格软包 箱体床 202603790 09001 "
                        "尺寸 长：1560mm 宽：2120mm 高：1050mm"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)

        self.assertEqual(normalized["fields"]["product_category"]["value"], "华夫格软包箱体床")

    def test_product_code_counter_ignores_contract_number_but_keeps_multi_product_contracts(self) -> None:
        single_text = (
            "第13页 20260379009客户合同 产品名称 华夫格软包箱体床 20260379009001 "
            "第14页 主卧 华夫格软包箱体床 202603790 09001"
        )
        multi_text = (
            "第13页 20260350004客户合同 产品名称 经典床头柜 120260350004001 "
            "其他床 20260350004002 经典带门书柜 20260350004003 经典双屉书桌 20260350004004"
        )
        multi_text_with_prefixed_quantity = (
            "第13页 20260418001客户合同 产品名称 其他斗柜 20260418001001 "
            "经典床头柜 320260418001002 合计14980"
        )

        self.assertEqual(PRODUCT_CODE_UTILS.count_unique_product_codes(single_text), 1)
        self.assertEqual(PRODUCT_CODE_UTILS.count_unique_product_codes(multi_text), 4)
        self.assertEqual(PRODUCT_CODE_UTILS.count_unique_product_codes(multi_text_with_prefixed_quantity), 2)

    def test_normalized_half_loft_combo_fields_can_pass_pricing_precheck(self) -> None:
        result = PRICING_BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "高架床", "confidence": 0.98},
                "quote_kind": {"value": "custom", "confidence": 0.96},
                "bed_form": {"value": "高架床", "confidence": 0.96},
                "access_style": {"value": "梯柜", "confidence": 0.96},
                "guardrail_style": {"value": "胶囊围栏", "confidence": 0.96},
                "guardrail_length": {"value": "1800mm", "confidence": 0.95},
                "guardrail_height": {"value": "320mm", "confidence": 0.95},
                "stair_width": {"value": "500mm", "confidence": 0.95},
                "stair_depth": {"value": "900mm", "confidence": 0.95},
                "width": {"value": "1200mm", "confidence": 0.95},
                "length": {"value": "2000mm", "confidence": 0.95},
                "wood_material": {"value": "北美白蜡木", "confidence": 0.95},
                "front_cabinet_length": {"value": "1600mm", "confidence": 0.95},
                "front_cabinet_height": {"value": "1600mm", "confidence": 0.95},
                "front_cabinet_depth": {"value": "450mm", "confidence": 0.95},
                "front_cabinet_mode": {"value": "有门无背板", "confidence": 0.95},
            }
        )

        self.assertEqual(result["status"], "ready_for_formal_quote")
        self.assertEqual(result["precheck_result"]["pricing_route"], "modular_child_bed_combo")
        self.assertTrue(result["precheck_result"]["ready_for_formal_quote"])

    def test_normalizer_can_use_template_alias_to_fill_missing_field(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-template-alias-001",
            batch_id="batch-template",
            group_key="case-template-alias",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-template.docx",
                    relative_path="raw/case-template-alias/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品型号：经典八斗柜\n"
                        "长度：1300mm\n"
                        "进深：450mm\n"
                        "高度：1000mm\n"
                        "材质：北美黑胡桃木\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            lookup_fingerprint = TEMPLATE_LEARNING.build_template_lookup_fingerprint(job=job)
            template_payload = {
                "template_id": "tpl-alias",
                "template_fingerprint": "tpl-alias-full",
                "template_lookup_fingerprint": lookup_fingerprint,
                "field_aliases": {
                    "product_category": {
                        "labels": ["产品型号"],
                        "confirmed_values": ["经典八斗柜"],
                    }
                },
                "preferred_evidence_order": ["native_preview", "ocr_markdown", "ocr_preview", "ocr_unknown"],
                "common_conflict_rules": [],
                "trust_score": 0.85,
                "learning_version": 1,
            }
            template_dir = runtime_root / "templates"
            template_dir.mkdir(parents=True)
            (template_dir / "tpl-alias.json").write_text(json.dumps(template_payload, ensure_ascii=False), encoding="utf-8")

            normalized = FIELD_NORMALIZER.normalize_job_fields(job, template_runtime_root=runtime_root)

        self.assertEqual(normalized["fields"]["product_category"]["value"], "经典八斗柜")
        self.assertGreaterEqual(normalized["fields"]["product_category"]["confidence"], 0.84)
        self.assertEqual(normalized["template_profile"]["template_id"], "tpl-alias")

    def test_normalizer_can_prefer_template_evidence_order_for_conflicting_dimension(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-template-order-001",
            batch_id="batch-template",
            group_key="case-template-order",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-native",
                    source_path="/tmp/fake-native.docx",
                    relative_path="raw/case-template-order/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview="产品名称：半高床\n床垫宽度：1100mm\n",
                    text_extract_method="docx_text",
                ),
                JOB_MODELS.SourceAsset(
                    asset_id="asset-ocr",
                    source_path="/tmp/fake-ocr.png",
                    relative_path="raw/case-template-order/图纸.png",
                    file_name="图纸.png",
                    extension=".png",
                    media_kind="image",
                    role_hint="visual_attachment",
                    text_preview="产品名称：半高床\n床垫宽度：1200mm\n",
                    text_extract_method="paddleocr_pp_structurev3",
                    metadata={"ocr_status": "succeeded", "ocr_markdown_path": "/tmp/fake-ocr.md"},
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            lookup_fingerprint = TEMPLATE_LEARNING.build_template_lookup_fingerprint(job=job)
            template_payload = {
                "template_id": "tpl-order",
                "template_fingerprint": "tpl-order-full",
                "template_lookup_fingerprint": lookup_fingerprint,
                "field_aliases": {},
                "preferred_evidence_order": ["ocr_markdown", "native_preview", "ocr_preview", "ocr_unknown"],
                "common_conflict_rules": [],
                "trust_score": 0.88,
                "learning_version": 1,
            }
            template_dir = runtime_root / "templates"
            template_dir.mkdir(parents=True)
            (template_dir / "tpl-order.json").write_text(json.dumps(template_payload, ensure_ascii=False), encoding="utf-8")

            normalized = FIELD_NORMALIZER.normalize_job_fields(job, template_runtime_root=runtime_root)

        self.assertEqual(normalized["fields"]["width"]["value"], "1200mm")
        self.assertEqual(normalized["template_profile"]["template_id"], "tpl-order")

    def test_normalizer_prefers_primary_child_bed_drawing_over_other_views(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-child-bed-drawing-001",
            batch_id="batch-child-bed",
            group_key="case-child-bed-drawing",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-contract",
                    source_path="/tmp/fake-contract.docx",
                    relative_path="raw/case-child-bed-drawing/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview="产品名称：高架床\n本单按定制执行\n材质：北美白橡木\n",
                    text_extract_method="docx_text",
                ),
                JOB_MODELS.SourceAsset(
                    asset_id="asset-render",
                    source_path="/tmp/fake-render.png",
                    relative_path="raw/case-child-bed-drawing/效果图.png",
                    file_name="效果图.png",
                    extension=".png",
                    media_kind="image",
                    role_hint="visual_attachment",
                    text_preview="高架床 透视效果图 床垫宽度：1200mm",
                    text_extract_method="paddleocr_pp_structurev3",
                    metadata={"ocr_status": "succeeded", "ocr_markdown_path": "/tmp/fake-render.md"},
                ),
                JOB_MODELS.SourceAsset(
                    asset_id="asset-main-drawing",
                    source_path="/tmp/fake-main-drawing.png",
                    relative_path="raw/case-child-bed-drawing/大尺寸图.png",
                    file_name="大尺寸图.png",
                    extension=".png",
                    media_kind="image",
                    role_hint="visual_attachment",
                    text_preview=(
                        "大尺寸图\n"
                        "床形态：高架床\n"
                        "上层出入方式：梯柜\n"
                        "围栏样式：胶囊围栏\n"
                        "床垫宽度：1080mm\n"
                        "床垫长度：2096mm\n"
                        "围栏高度：400mm\n"
                        "梯柜踏步宽度：500mm\n"
                        "梯柜进深：900mm\n"
                        "总高：2715mm\n"
                    ),
                    text_extract_method="paddleocr_pp_structurev3",
                    metadata={"ocr_status": "succeeded", "ocr_markdown_path": "/tmp/fake-main-drawing.md"},
                ),
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]
        child_bed_analysis = normalized["child_bed_analysis"]

        self.assertEqual(child_bed_analysis["primary_drawing_asset_id"], "asset-main-drawing")
        self.assertEqual(fields["width"]["value"], "1080mm")
        self.assertEqual(fields["width"]["evidence_refs"][0]["asset_id"], "asset-main-drawing")
        self.assertEqual(fields["access_style"]["value"], "梯柜")
        self.assertIn("width", child_bed_analysis["main_drawing_field_hits"])
        self.assertFalse(child_bed_analysis["requires_primary_drawing_review"])

    def test_normalizer_can_use_ocr_layout_json_for_primary_child_bed_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_dir = root / "normalized" / "ocr" / "asset-main-drawing"
            page_dir = output_dir / "page-001"
            page_dir.mkdir(parents=True)

            summary_path = output_dir / "summary.json"
            page_json_path = page_dir / "result.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "asset_id": "asset-main-drawing",
                        "backend": "paddleocr",
                        "status": "succeeded",
                        "source_path": str(root / "大尺寸图.png"),
                        "page_count": 1,
                        "markdown_path": str(output_dir / "combined.md"),
                        "pages": [
                            {
                                "page_no": 1,
                                "json_path": str(page_json_path),
                                "markdown_dir": str(page_dir),
                                "markdown_text_length": 0,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            page_json_path.write_text(
                json.dumps(
                    {
                        "input_path": str(root / "大尺寸图.png"),
                        "page_index": 0,
                        "model_settings": {"use_doc_preprocessor": False},
                        "overall_ocr_res": {
                            "rec_texts": [
                                "床形态",
                                "高架床",
                                "上层出入方式",
                                "梯柜",
                                "床垫宽度",
                                "1080mm",
                                "床垫长度",
                                "2096mm",
                                "梯柜踏步宽度",
                                "500mm",
                                "梯柜进深",
                                "900mm",
                                "围栏高度",
                                "400mm",
                                "总高",
                                "2715mm",
                            ],
                            "rec_boxes": [
                                [80, 60, 180, 95],
                                [200, 58, 320, 97],
                                [80, 110, 220, 145],
                                [240, 108, 340, 147],
                                [80, 190, 240, 225],
                                [260, 188, 360, 227],
                                [80, 250, 240, 285],
                                [260, 248, 360, 287],
                                [80, 320, 280, 355],
                                [300, 318, 390, 357],
                                [80, 380, 240, 415],
                                [260, 378, 350, 417],
                                [460, 200, 580, 235],
                                [600, 198, 690, 237],
                                [460, 270, 540, 305],
                                [560, 268, 660, 307],
                            ],
                            "rec_scores": [0.99] * 16,
                            "rec_polys": [],
                            "dt_polys": [],
                            "text_det_params": {},
                            "text_type": "general",
                            "text_rec_score_thresh": 0,
                            "return_word_box": False,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            job = JOB_MODELS.ReviewJob(
                job_id="job-child-bed-layout-001",
                batch_id="batch-child-bed",
                group_key="case-child-bed-layout",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-contract",
                        source_path="/tmp/fake-contract.docx",
                        relative_path="raw/case-child-bed-layout/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="产品名称：高架床\n本单按定制执行\n材质：北美白橡木\n",
                        text_extract_method="docx_text",
                    ),
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-main-drawing",
                        source_path=str(root / "大尺寸图.png"),
                        relative_path="raw/case-child-bed-layout/大尺寸图.png",
                        file_name="大尺寸图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        text_preview=(
                            "大尺寸图\n"
                            "床形态：高架床\n"
                            "上层出入方式：梯柜\n"
                            "1080mm 2096mm 500mm 900mm 400mm 2715mm\n"
                        ),
                        text_extract_method="paddleocr_pp_structurev3",
                        metadata={"ocr_status": "succeeded", "ocr_json_path": str(summary_path)},
                    ),
                ],
            )

            normalized = FIELD_NORMALIZER.normalize_job_fields(job)
            fields = normalized["fields"]
            child_bed_analysis = normalized["child_bed_analysis"]

        self.assertEqual(fields["width"]["value"], "1080mm")
        self.assertEqual(fields["length"]["value"], "2096mm")
        self.assertEqual(fields["stair_width"]["value"], "500mm")
        self.assertEqual(fields["stair_depth"]["value"], "900mm")
        self.assertEqual(fields["height"]["value"], "2715mm")
        self.assertEqual(fields["width"]["evidence_refs"][0]["asset_id"], "asset-main-drawing")
        self.assertEqual(fields["width"]["evidence_refs"][0]["evidence_type"], "ocr_layout")
        self.assertIn("width", child_bed_analysis["main_drawing_field_hits"])
        self.assertIn("length", child_bed_analysis["main_drawing_field_hits"])
        self.assertFalse(child_bed_analysis["requires_primary_drawing_review"])

    def test_normalizer_extracts_half_loft_combo_fields(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-combo-001",
            batch_id="batch-combo",
            group_key="case-combo",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-combo.docx",
                    relative_path="raw/case-combo/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称：高架床\n"
                        "本单按定制执行\n"
                        "床形态：高架床\n"
                        "上层出入方式：梯柜\n"
                        "围栏样式：胶囊围栏\n"
                        "围栏长度：1800mm\n"
                        "围栏高度：320mm\n"
                        "梯柜踏步宽度：500mm\n"
                        "梯柜进深：900mm\n"
                        "床垫宽度：1200mm\n"
                        "床垫长度：2000mm\n"
                        "材质：北美白蜡木\n"
                        "前排柜体长度：1600mm\n"
                        "前排柜体高度：1600mm\n"
                        "前排柜体进深：450mm\n"
                        "前排柜体结构：有门无背板\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]

        self.assertEqual(fields["bed_form"]["value"], "高架床")
        self.assertEqual(fields["access_style"]["value"], "梯柜")
        self.assertEqual(fields["guardrail_length"]["value"], "1800mm")
        self.assertEqual(fields["stair_width"]["value"], "500mm")
        self.assertEqual(fields["front_cabinet_mode"]["value"], "有门无背板")
        self.assertEqual(fields["front_cabinet_depth"]["value"], "450mm")

    def test_normalizer_extracts_dual_row_combo_fields_from_row_segments(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-combo-002",
            batch_id="batch-combo",
            group_key="case-combo-dual",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-combo-dual.docx",
                    relative_path="raw/case-combo-dual/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称：半高床\n"
                        "本单按定制执行\n"
                        "床形态：半高床\n"
                        "上层出入方式：梯柜\n"
                        "围栏样式：胶囊围栏\n"
                        "围栏长度：2000mm\n"
                        "围栏高度：400mm\n"
                        "梯柜踏步宽度：520mm\n"
                        "梯柜进深：500mm\n"
                        "床垫宽度：1200mm\n"
                        "床垫长度：2000mm\n"
                        "材质：乌拉圭玫瑰木\n"
                        "床下前后双排互通\n"
                        "前排：长度 2000mm，高度 1200mm，进深 450mm，有门无背板。\n"
                        "后排：长度 1800mm，高度 1200mm，进深 450mm，无门有背板。\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        normalized = FIELD_NORMALIZER.normalize_job_fields(job)
        fields = normalized["fields"]

        self.assertTrue(fields["interconnected_rows"]["value"])
        self.assertEqual(fields["front_cabinet_length"]["value"], "2000mm")
        self.assertEqual(fields["front_cabinet_height"]["value"], "1200mm")
        self.assertEqual(fields["front_cabinet_depth"]["value"], "450mm")
        self.assertEqual(fields["front_cabinet_mode"]["value"], "有门无背板")
        self.assertEqual(fields["rear_cabinet_length"]["value"], "1800mm")
        self.assertEqual(fields["rear_cabinet_height"]["value"], "1200mm")
        self.assertEqual(fields["rear_cabinet_depth"]["value"], "450mm")
        self.assertEqual(fields["rear_cabinet_mode"]["value"], "无门有背板")

    def test_bridge_can_use_generic_underbed_mode_for_single_front_row(self) -> None:
        result = PRICING_BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "半高床", "confidence": 0.98},
                "quote_kind": {"value": "custom", "confidence": 0.96},
                "bed_form": {"value": "半高床", "confidence": 0.96},
                "access_style": {"value": "梯柜", "confidence": 0.96},
                "guardrail_style": {"value": "胶囊围栏", "confidence": 0.96},
                "guardrail_length": {"value": "2000mm", "confidence": 0.95},
                "guardrail_height": {"value": "400mm", "confidence": 0.95},
                "stair_width": {"value": "520mm", "confidence": 0.95},
                "stair_depth": {"value": "500mm", "confidence": 0.95},
                "width": {"value": "1200mm", "confidence": 0.95},
                "length": {"value": "2000mm", "confidence": 0.95},
                "wood_material": {"value": "乌拉圭玫瑰木", "confidence": 0.95},
                "front_cabinet_length": {"value": "1800mm", "confidence": 0.95},
                "front_cabinet_height": {"value": "1200mm", "confidence": 0.95},
                "front_cabinet_depth": {"value": "450mm", "confidence": 0.95},
                "underbed_cabinet_mode": {"value": "有门无背板", "confidence": 0.94},
            }
        )

        self.assertEqual(result["status"], "ready_for_formal_quote")
        self.assertEqual(result["precheck_result"]["pricing_route"], "modular_child_bed_combo")
        self.assertEqual(result["precheck_args"]["front_cabinet_mode"], "有门无背板")


if __name__ == "__main__":
    unittest.main()
