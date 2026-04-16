import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

CONTRACT_AUDIT_PATH = CORE_ROOT / "contract_audit.py"
JOB_MODELS_PATH = CORE_ROOT / "job_models.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTRACT_AUDIT = load_module("contract_review_contract_audit", CONTRACT_AUDIT_PATH)
JOB_MODELS = load_module("contract_review_job_models_for_contract_audit", JOB_MODELS_PATH)


class ContractAuditTests(unittest.TestCase):
    def test_extracts_contract_financials_notes_and_pricing_gaps(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-audit-001",
            batch_id="batch-audit",
            group_key="case-audit",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.docx",
                    relative_path="raw/case-audit/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称：书柜\n"
                        "长度：2400mm\n"
                        "高度：2100mm\n"
                        "费用合计：19800元\n"
                        "增项费用：拉手升级 600元\n"
                        "备注：见光面统一顺纹，现场避开踢脚线。\n"
                        "特殊说明：到顶封板需现场复尺。\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        result = CONTRACT_AUDIT.build_contract_audit_report(
            job=job,
            normalized_fields_payload={
                "field_count": 3,
                "fields": {
                    "product_category": {
                        "value": "书柜",
                        "confidence": 0.98,
                        "evidence_refs": [
                            {
                                "asset_id": "asset-001",
                                "file_name": "合同.docx",
                                "source_kind": "native_preview",
                                "text_extract_method": "docx_text",
                                "snippet": "产品名称：书柜",
                            }
                        ],
                    },
                    "length": {
                        "value": "2400mm",
                        "confidence": 0.96,
                        "evidence_refs": [
                            {
                                "asset_id": "asset-001",
                                "file_name": "合同.docx",
                                "source_kind": "native_preview",
                                "text_extract_method": "docx_text",
                                "snippet": "长度：2400mm",
                            }
                        ],
                    },
                    "height": {
                        "value": "2100mm",
                        "confidence": 0.96,
                        "evidence_refs": [
                            {
                                "asset_id": "asset-001",
                                "file_name": "合同.docx",
                                "source_kind": "native_preview",
                                "text_extract_method": "docx_text",
                                "snippet": "高度：2100mm",
                            }
                        ],
                    },
                },
            },
            pricing_bridge_payload={
                "status": "needs_input",
                "reason": "pricing_precheck_completed",
                "precheck_args": {
                    "category": "书柜",
                    "length": "2400mm",
                    "height": "2100mm",
                },
                "precheck_result": {
                    "next_required_field": "depth",
                    "ready_for_formal_quote": False,
                },
                "mapped_fields": {
                    "category": {"source_field": "product_category", "value": "书柜", "confidence": 0.98},
                    "length": {"source_field": "length", "value": "2400mm", "confidence": 0.96},
                    "height": {"source_field": "height", "value": "2100mm", "confidence": 0.96},
                },
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
        )

        self.assertEqual(result["financials"]["contract_total"]["value"], "19800元")
        self.assertEqual(result["financials"]["list_price_total"]["value"], "19800元")
        self.assertEqual(result["financials"]["add_on_items"][0]["amount"], "600元")
        self.assertIn("见光面统一顺纹", result["special_notes"][0]["text"])
        self.assertEqual(result["pricing_alignment"]["next_required_field"], "depth")
        self.assertIn("depth", result["pricing_alignment"]["missing_for_pricing"])
        self.assertEqual(result["financials"]["contract_total"]["evidence_refs"][0]["asset_id"], "asset-001")
        self.assertIn("费用合计：19800元", result["financials"]["contract_total"]["evidence_refs"][0]["snippet"])
        self.assertEqual(result["special_notes"][0]["evidence_refs"][0]["source_kind"], "native_preview")
        self.assertEqual(result["field_evidence_overview"]["product_category"]["value"], "书柜")
        self.assertEqual(result["field_evidence_overview"]["product_category"]["source_kinds"], ["native_preview"])

    def test_extracts_contract_total_from_spaced_contract_amount_label(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-audit-001b",
            batch_id="batch-audit",
            group_key="case-audit-real-contract",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.pdf",
                    relative_path="raw/case-audit-real-contract/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "客户合同 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》），"
                        "合同总 金额为人民币41085元（大写：肆万壹仟零捌拾伍元）。"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        result = CONTRACT_AUDIT.build_contract_audit_report(
            job=job,
            normalized_fields_payload={"field_count": 1, "fields": {"quote_kind": {"value": "custom", "confidence": 0.87}}},
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "category_missing_or_untrusted",
                "precheck_args": {"quote_kind": "custom"},
                "precheck_result": None,
                "mapped_fields": {"quote_kind": {"source_field": "quote_kind", "value": "custom", "confidence": 0.87}},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
        )

        self.assertEqual(result["financials"]["contract_total"]["value"], "41085元")
        self.assertIn("合同总 金额为人民币41085元", result["financials"]["contract_total"]["evidence_text"])
        self.assertEqual(result["financials"]["contract_total"]["source_kind"], "native_preview")

    def test_extracts_discount_fields_from_real_contract_attachment_page(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-audit-001c",
            batch_id="batch-audit",
            group_key="case-audit-discount",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.pdf",
                    relative_path="raw/case-audit-discount/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "附件： 产品名称 产品编号 材质 数量 费用合计（元） 其他衣柜 202603100003001 北美黑胡桃木 1 43708 "
                        "合计 43708 折扣 94折 折扣后合计 41085"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        result = CONTRACT_AUDIT.build_contract_audit_report(
            job=job,
            normalized_fields_payload={"field_count": 1, "fields": {"quote_kind": {"value": "custom", "confidence": 0.87}}},
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "category_missing_or_untrusted",
                "precheck_args": {"quote_kind": "custom"},
                "precheck_result": None,
                "mapped_fields": {"quote_kind": {"source_field": "quote_kind", "value": "custom", "confidence": 0.87}},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
        )

        self.assertEqual(result["financials"]["list_price_total"]["value"], "43708元")
        self.assertEqual(result["financials"]["discount_rate"]["value"], "94折")
        self.assertEqual(result["financials"]["discounted_total"]["value"], "41085元")

    def test_keeps_native_contract_total_when_ocr_markdown_only_covers_attachment_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown_path = Path(tmpdir) / "ocr.md"
            markdown_path.write_text(
                "附件： 产品名称 产品编号 材质 数量 费用合计（元） 其他餐边柜 20260379013001 北美白橡木 1 31631 "
                "定制组合餐边柜 20260379013002 北美白橡木 1 50828 合计 82459 折扣 98折 折扣后合计 80809",
                encoding="utf-8",
            )
            job = JOB_MODELS.ReviewJob(
                job_id="job-audit-ocr-merge",
                batch_id="batch-audit",
                group_key="case-audit-ocr-merge",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-001",
                        source_path="/tmp/fake.pdf",
                        relative_path="raw/case-audit-ocr-merge/合同.pdf",
                        file_name="合同.pdf",
                        extension=".pdf",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview=(
                            "客户合同 1.1甲方委托乙方定制家具，合同总 金额为人民币80809元。"
                            "\n\n[OCR补充]\n附件： 产品名称 产品编号 材质 数量 费用合计（元）"
                        ),
                        text_extract_method="native_plus_ocr",
                        metadata={"ocr_markdown_path": str(markdown_path), "ocr_status": "succeeded"},
                    )
                ],
            )

            result = CONTRACT_AUDIT.build_contract_audit_report(
                job=job,
                normalized_fields_payload={"field_count": 1, "fields": {"quote_kind": {"value": "custom", "confidence": 0.91}}},
                pricing_bridge_payload={
                    "status": "ready_for_formal_quote",
                    "reason": "pricing_precheck_completed",
                    "precheck_args": {"quote_kind": "custom"},
                    "precheck_result": {"ready_for_formal_quote": True},
                    "mapped_fields": {"quote_kind": {"source_field": "quote_kind", "value": "custom", "confidence": 0.91}},
                    "blocked_fields": [],
                    "withheld_source_fields": [],
                },
            )

        self.assertEqual(result["financials"]["contract_total"]["value"], "80809元")
        self.assertEqual(result["financials"]["list_price_total"]["value"], "82459元")
        self.assertEqual(result["financials"]["discounted_total"]["value"], "80809元")

    def test_flags_unmapped_high_confidence_contract_fields(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-audit-002",
            batch_id="batch-audit",
            group_key="case-audit-unmapped",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[],
        )

        result = CONTRACT_AUDIT.build_contract_audit_report(
            job=job,
            normalized_fields_payload={
                "field_count": 4,
                "fields": {
                    "product_category": {"value": "书柜", "confidence": 0.98},
                    "length": {"value": "2400mm", "confidence": 0.96},
                    "depth": {"value": "350mm", "confidence": 0.52},
                    "wood_material": {"value": "北美黑胡桃木", "confidence": 0.96},
                },
            },
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "sensitive_fields_below_confidence_threshold",
                "precheck_args": {
                    "category": "书柜",
                    "length": "2400mm",
                },
                "precheck_result": None,
                "mapped_fields": {
                    "category": {"source_field": "product_category", "value": "书柜", "confidence": 0.98},
                    "length": {"source_field": "length", "value": "2400mm", "confidence": 0.96},
                },
                "blocked_fields": ["material"],
                "withheld_source_fields": ["depth", "wood_material"],
            },
        )

        self.assertIn("wood_material", result["pricing_alignment"]["unmapped_high_confidence_fields"])
        self.assertIn("material", result["pricing_alignment"]["blocked_fields"])
        self.assertIn("depth", result["pricing_alignment"]["withheld_source_fields"])

    def test_prefers_full_ocr_markdown_content_over_preview_snippet(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            combined_path = Path(tmpdir) / "combined.md"
            combined_path.write_text(
                "尺寸备注：宽900mm，高2400mm。\n备注：现场复尺后下单。\n费用合计：5600元\n",
                encoding="utf-8",
            )

            job = JOB_MODELS.ReviewJob(
                job_id="job-audit-003",
                batch_id="batch-audit",
                group_key="case-audit-ocr",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-ocr-001",
                        source_path="/tmp/fake.png",
                        relative_path="raw/case-audit-ocr/尺寸图.png",
                        file_name="尺寸图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        text_preview="尺寸备注：宽900mm，高2400mm。",
                        text_extract_method="paddleocr_pp_structurev3",
                        metadata={
                            "ocr_status": "succeeded",
                            "ocr_markdown_path": str(combined_path),
                        },
                    )
                ],
            )

            result = CONTRACT_AUDIT.build_contract_audit_report(
                job=job,
                normalized_fields_payload={"field_count": 0, "fields": {}},
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "reason": "category_missing_or_untrusted",
                    "precheck_args": {},
                    "precheck_result": None,
                    "mapped_fields": {},
                    "blocked_fields": [],
                    "withheld_source_fields": [],
                },
            )

            self.assertEqual(result["financials"]["contract_total"]["value"], "5600元")
            self.assertTrue(any("现场复尺后下单" in item["text"] for item in result["special_notes"]))
            self.assertEqual(result["financials"]["contract_total"]["source_kind"], "ocr_markdown")
            self.assertEqual(
                result["financials"]["contract_total"]["evidence_refs"][0]["source_kind"],
                "ocr_markdown",
            )
            self.assertEqual(
                result["financials"]["contract_total"]["evidence_refs"][0]["ocr_markdown_path"],
                str(combined_path),
            )

    def test_detects_conflicts_between_native_and_ocr_field_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            combined_path = Path(tmpdir) / "combined.md"
            combined_path.write_text("长度：2500mm\n", encoding="utf-8")

            job = JOB_MODELS.ReviewJob(
                job_id="job-audit-004",
                batch_id="batch-audit",
                group_key="case-audit-conflict",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-doc-001",
                        source_path="/tmp/fake.docx",
                        relative_path="raw/case-audit-conflict/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="产品名称：书柜\n长度：2400mm\n",
                        text_extract_method="docx_text",
                    ),
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-ocr-002",
                        source_path="/tmp/fake.png",
                        relative_path="raw/case-audit-conflict/尺寸图.png",
                        file_name="尺寸图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        text_preview="长度：2500mm",
                        text_extract_method="paddleocr_pp_structurev3",
                        metadata={
                            "ocr_status": "succeeded",
                            "ocr_markdown_path": str(combined_path),
                        },
                    ),
                ],
            )

            result = CONTRACT_AUDIT.build_contract_audit_report(
                job=job,
                normalized_fields_payload={
                    "field_count": 2,
                    "fields": {
                        "product_category": {
                            "value": "书柜",
                            "confidence": 0.98,
                            "evidence_refs": [
                                {
                                    "asset_id": "asset-doc-001",
                                    "file_name": "合同.docx",
                                    "source_kind": "native_preview",
                                    "text_extract_method": "docx_text",
                                    "snippet": "产品名称：书柜",
                                }
                            ],
                        },
                        "length": {
                            "value": "2400mm",
                            "confidence": 0.95,
                            "evidence_refs": [
                                {
                                    "asset_id": "asset-doc-001",
                                    "file_name": "合同.docx",
                                    "source_kind": "native_preview",
                                    "text_extract_method": "docx_text",
                                    "snippet": "长度：2400mm",
                                }
                            ],
                        },
                    },
                },
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "reason": "category_missing_or_untrusted",
                    "precheck_args": {},
                    "precheck_result": None,
                    "mapped_fields": {},
                    "blocked_fields": [],
                    "withheld_source_fields": [],
                },
            )

            self.assertEqual(result["field_conflicts"][0]["field_name"], "length")
            self.assertEqual(sorted(result["field_conflicts"][0]["detected_values"]), ["2400mm", "2500mm"])
            self.assertEqual(result["field_conflicts"][0]["severity"], "high")
            self.assertIn("length_value_conflict_detected", result["risk_flags"])
            self.assertEqual(result["conflict_resolution_suggestions"][0]["field_name"], "length")
            self.assertEqual(result["conflict_resolution_suggestions"][0]["recommended_action"], "prefer_ocr_drawing")
            self.assertEqual(result["conflict_resolution_suggestions"][0]["priority"], "p1")

    def test_detects_high_risk_material_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            combined_path = Path(tmpdir) / "combined.md"
            combined_path.write_text("材质：北美黑胡桃木\n", encoding="utf-8")

            job = JOB_MODELS.ReviewJob(
                job_id="job-audit-005",
                batch_id="batch-audit",
                group_key="case-audit-material-conflict",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-doc-002",
                        source_path="/tmp/fake.docx",
                        relative_path="raw/case-audit-material-conflict/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="产品名称：书柜\n材质：北美白橡木\n",
                        text_extract_method="docx_text",
                    ),
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-ocr-003",
                        source_path="/tmp/fake.png",
                        relative_path="raw/case-audit-material-conflict/材质图.png",
                        file_name="材质图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        text_preview="材质：北美黑胡桃木",
                        text_extract_method="paddleocr_pp_structurev3",
                        metadata={
                            "ocr_status": "succeeded",
                            "ocr_markdown_path": str(combined_path),
                        },
                    ),
                ],
            )

            result = CONTRACT_AUDIT.build_contract_audit_report(
                job=job,
                normalized_fields_payload={"field_count": 0, "fields": {}},
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "reason": "category_missing_or_untrusted",
                    "precheck_args": {},
                    "precheck_result": None,
                    "mapped_fields": {},
                    "blocked_fields": [],
                    "withheld_source_fields": [],
                },
            )

            self.assertEqual(result["field_conflicts"][0]["field_name"], "wood_material")
            self.assertEqual(result["field_conflicts"][0]["severity"], "critical")
            self.assertIn("high_severity_field_conflict_detected", result["risk_flags"])
            self.assertEqual(result["conflict_resolution_suggestions"][0]["recommended_action"], "manual_review_required")
            self.assertEqual(result["conflict_resolution_suggestions"][0]["priority"], "p0")

    def test_detects_contract_total_conflict_with_critical_severity(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-audit-006",
            batch_id="batch-audit",
            group_key="case-audit-total-conflict",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-a.docx",
                    relative_path="raw/case-audit-total-conflict/合同A.docx",
                    file_name="合同A.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview="费用合计：19800元\n",
                    text_extract_method="docx_text",
                ),
                JOB_MODELS.SourceAsset(
                    asset_id="asset-002",
                    source_path="/tmp/fake-b.png",
                    relative_path="raw/case-audit-total-conflict/合同B.png",
                    file_name="合同B.png",
                    extension=".png",
                    media_kind="image",
                    role_hint="visual_attachment",
                    text_preview="费用合计：21800元\n",
                    text_extract_method="paddleocr_pp_structurev3",
                    metadata={"ocr_status": "succeeded"},
                ),
            ],
        )

        result = CONTRACT_AUDIT.build_contract_audit_report(
            job=job,
            normalized_fields_payload={"field_count": 0, "fields": {}},
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "category_missing_or_untrusted",
                "precheck_args": {},
                "precheck_result": None,
                "mapped_fields": {},
                "blocked_fields": [],
                "withheld_source_fields": [],
            },
        )

        total_conflict = next(item for item in result["field_conflicts"] if item["field_name"] == "contract_total")
        self.assertEqual(total_conflict["severity"], "critical")
        self.assertEqual(sorted(total_conflict["detected_values"]), ["19800元", "21800元"])
        total_suggestion = next(
            item for item in result["conflict_resolution_suggestions"] if item["field_name"] == "contract_total"
        )
        self.assertEqual(total_suggestion["recommended_action"], "manual_review_required")
        self.assertEqual(total_suggestion["priority"], "p0")

    def test_prefers_primary_contract_for_door_type_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            combined_path = Path(tmpdir) / "combined.md"
            combined_path.write_text("门型：铝框门\n", encoding="utf-8")

            job = JOB_MODELS.ReviewJob(
                job_id="job-audit-007",
                batch_id="batch-audit",
                group_key="case-audit-door-conflict",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-doc-003",
                        source_path="/tmp/fake.docx",
                        relative_path="raw/case-audit-door-conflict/合同.docx",
                        file_name="合同.docx",
                        extension=".docx",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="门型：平板门\n",
                        text_extract_method="docx_text",
                    ),
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-ocr-004",
                        source_path="/tmp/fake.png",
                        relative_path="raw/case-audit-door-conflict/门型图.png",
                        file_name="门型图.png",
                        extension=".png",
                        media_kind="image",
                        role_hint="visual_attachment",
                        text_preview="门型：铝框门",
                        text_extract_method="paddleocr_pp_structurev3",
                        metadata={
                            "ocr_status": "succeeded",
                            "ocr_markdown_path": str(combined_path),
                        },
                    ),
                ],
            )

            result = CONTRACT_AUDIT.build_contract_audit_report(
                job=job,
                normalized_fields_payload={"field_count": 0, "fields": {}},
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "reason": "category_missing_or_untrusted",
                    "precheck_args": {},
                    "precheck_result": None,
                    "mapped_fields": {},
                    "blocked_fields": [],
                    "withheld_source_fields": [],
                },
            )

            suggestion = next(
                item for item in result["conflict_resolution_suggestions"] if item["field_name"] == "door_type"
            )
            self.assertEqual(suggestion["recommended_action"], "prefer_primary_contract")
            self.assertEqual(suggestion["preferred_source_kind"], "native_preview")


if __name__ == "__main__":
    unittest.main()
