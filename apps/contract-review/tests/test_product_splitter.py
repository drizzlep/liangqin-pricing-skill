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
MODULE_PATH = CORE_ROOT / "product_splitter.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


JOB_MODELS = load_module("contract_review_job_models_for_splitter", JOB_MODELS_PATH)
PRODUCT_SPLITTER = load_module("contract_review_product_splitter", MODULE_PATH)


class ProductSplitterTests(unittest.TestCase):
    def test_extract_product_line_items_ignores_trailing_contract_declaration_pages(self) -> None:
        preview = (
            "第13页 20260350004客户合同 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
            "经典床头柜 120260350004001 北美樱桃木 1 1780 合计 1780 "
            "第14页 儿童房 经典床头柜 1 202603500 04001北美樱桃木 无色哑光木蜡油尺寸 长：450mm 宽：400mm 高：500mm "
            "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》），合同总金额为人民币1780元。 "
            "第2页 其他条款"
        )

        items = PRODUCT_SPLITTER.extract_product_line_items(preview)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_name"], "经典床头柜")
        self.assertIn("长：450mm", items[0]["detail_snippet"])
        self.assertNotIn("甲方委托乙方定制家具", items[0]["detail_snippet"])

    def test_extract_product_line_items_from_multi_product_preview(self) -> None:
        preview = (
            "第13页 20260418001客户合同 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
            "其他斗柜 20260418001001 北美黑胡桃木 1 12400 "
            "经典床头柜 320260418001002 北美黑胡桃木 1 2580 合计 14980 "
            "第14页 主卧 其他斗柜 202604180 01001北美黑胡桃木 尺寸 长：1300mm 宽：450mm 高：1000mm "
            "第19页 主卧 经典床头柜 3 202604180 01002北美黑胡桃木 尺寸 长：450mm 宽：400mm 高：500mm"
        )

        items = PRODUCT_SPLITTER.extract_product_line_items(preview)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["product_name"], "其他斗柜")
        self.assertEqual(items[0]["product_code"], "20260418001001")
        self.assertEqual(items[0]["line_total"], "12400元")
        self.assertEqual(items[1]["product_name"], "经典床头柜")
        self.assertEqual(items[1]["product_code"], "20260418001002")
        self.assertIn("长：450mm", items[1]["detail_snippet"])

    def test_extract_product_line_items_preserves_plus_in_combo_name(self) -> None:
        preview = (
            "产品名称 产品编号 材质 数量 费用合计（元） "
            "经典榻榻米+衣柜组合 20260229002002 北美白橡木 1 14760 合计 14760 "
            "次卧 经典榻榻米+衣柜组合 20260229002002 北美白橡木 尺寸 长：2000mm 宽：1500mm 高：400mm "
        )

        items = PRODUCT_SPLITTER.extract_product_line_items(preview)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_name"], "经典榻榻米+衣柜组合")
        self.assertEqual(items[0]["product_code"], "20260229002002")

    def test_extract_product_line_items_uses_structured_detail_blocks_after_product_info_attachment(self) -> None:
        preview = (
            "第1页 合同首页 1.1甲方委托乙方定制家具。"
            "第13页 附件：《产品信息及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
            "升级经典无腰线衣柜 20260229002001 北美白橡木 1 36936 "
            "经典榻榻米+衣柜组合 20260229002002 北美白橡木 1 14760 合计 51696 "
            "交货地点 联系电话 交货日期 2026年05月31日 "
            "福建省宁德市 次卧 升级经典无腰线衣柜 20260229002001 北美白橡木 无色哑光木蜡油 "
            "尺寸 长：2090mm 宽：600mm 高：2770mm 1 注明："
            "1.次卧白橡木拼框门衣柜，直角直边。"
            "2.柜内五组抽拉挂衣杆，柜体后方避让90*25mm。 "
            "福建省宁德市 次卧 经典榻榻米+衣柜组合 20260229002002 北美白橡木 无色哑光木蜡油 "
            "尺寸 长：2000mm 宽：1500mm 高：400mm 1 注明："
            "1.次卧白橡木榻榻米；1.5*2m床垫。"
            "2.榻榻米靠外侧安排抽屉，平装盖板+侧开排骨架。"
            "尺寸图 抽屉下沉125mm，贴墙预留10mm走线。"
        )

        items = PRODUCT_SPLITTER.extract_product_line_items(preview)

        self.assertEqual(len(items), 2)
        wardrobe_item = items[0]
        combo_item = items[1]
        self.assertEqual(wardrobe_item["product_code"], "20260229002001")
        self.assertIn("长：2090mm", wardrobe_item["detail_snippet"])
        self.assertIn("柜内五组抽拉挂衣杆", wardrobe_item["detail_snippet"])
        self.assertNotIn("长：2000mm", wardrobe_item["detail_snippet"])
        self.assertNotIn("榻榻米靠外侧安排抽屉", wardrobe_item["detail_snippet"])

        self.assertEqual(combo_item["product_code"], "20260229002002")
        self.assertIn("长：2000mm", combo_item["detail_snippet"])
        self.assertIn("尺寸图 抽屉下沉125mm", combo_item["detail_snippet"])
        self.assertNotIn("长：2090mm", combo_item["detail_snippet"])
        self.assertNotIn("柜内五组抽拉挂衣杆", combo_item["detail_snippet"])
        self.assertEqual(combo_item["detail_resolution"]["anchor_method"], "structured_product_block")
        self.assertEqual(combo_item["detail_resolution"]["evidence_scope"], "detail_block")

    def test_extract_product_line_items_exposes_detail_page_numbers_for_fixed_multi_product_template(self) -> None:
        preview = (
            "第13页 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
            "其他床 20260391004001 北美樱桃木 1 16312 "
            "其他衣柜 20260391004002 北美樱桃木 1 23288 "
            "其他 20260391004003 北美樱桃木 1 16256 "
            "其他儿童床 20260391004004 北美樱桃木 1 20560 "
            "其他衣柜 20260391004005 北美樱桃木 1 34142 "
            "流云衣柜 20260391004006 北美樱桃木 1 35574 合计 146132 "
            "第14页 次卧 其他床 202603910 04001北美樱桃木 尺寸 长：1800mm 宽：2560mm 高：300mm "
            "第17页 次卧 其他衣柜 202603910 04002北美樱桃木 尺寸 长：1435mm 宽：610mm 高：2760mm "
            "第23页 次卧 其他 202603910 04003北美樱桃木 尺寸 长：1435mm 宽：610mm 高：2760mm "
            "第29页 儿童房 其他儿童床 202603910 04004北美樱桃木 尺寸 长：1380mm 宽：2568mm 高：1885mm "
            "第32页 儿童房 其他衣柜 202603910 04005北美樱桃木 尺寸 长：2100mm 宽：600mm 高：2675mm "
            "第37页 主卧 流云衣柜 202603910 04006北美樱桃木 尺寸 长：2200mm 宽：610mm 高：2750mm"
        )

        items = PRODUCT_SPLITTER.extract_product_line_items(preview)

        self.assertEqual(len(items), 6)
        self.assertEqual(
            [item["detail_resolution"]["detail_page_no"] for item in items],
            [14, 17, 23, 29, 32, 37],
        )
        self.assertTrue(
            all(item["detail_resolution"]["anchor_method"] == "page_marker" for item in items)
        )
        self.assertTrue(
            all(item["detail_resolution"]["evidence_scope"] == "detail_only" for item in items)
        )

    def test_extract_product_line_items_prefers_local_ocr_table_block_for_detail(self) -> None:
        preview = (
            "第35页 合同内容 [OCR补充]"
            "<table><tr><td>湖南省长沙市</td><td>主卧 其他床 202603550 03003</td>"
            "<td>北美黑胡桃木</td><td>尺寸 长：2132mm 宽：2067mm 高：1mm</td></tr>"
            "<tr><td>注明：</td><td colspan='4'>主卧黑胡桃2米标准款支腿架式床。</td></tr></table>"
            "<table><tr><td>湖南省长沙市</td><td>主卧 经典床头柜 3 202603550 03004</td>"
            "<td>北美黑胡桃木</td><td>尺寸 长：450mm 宽：400mm 高：500mm</td></tr>"
            "<tr><td>注明：</td><td colspan='4'>主卧黑胡桃标准款经典床头柜3。</td></tr></table>"
        )

        snippet = PRODUCT_SPLITTER._extract_best_detail_snippet(
            preview,
            "20260355003004",
            product_name="经典床头柜",
        )

        self.assertIn("经典床头柜 3", snippet)
        self.assertIn("长：450mm", snippet)
        self.assertNotIn("长：2132mm", snippet)

    def test_extract_product_line_items_without_detail_page_keeps_empty_detail_snippet(self) -> None:
        preview = (
            "第13页 20260350004客户合同 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
            "经典带门书柜 20260350004003 北美樱桃木 1 11952 "
            "经典双屉书桌 20260350004004 北美樱桃木 1 3880 合计 15832 "
            "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》），合同总金额为人民币15832元。"
        )

        items = PRODUCT_SPLITTER.extract_product_line_items(preview)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["detail_snippet"], "")
        self.assertEqual(items[1]["detail_snippet"], "")
        self.assertEqual(items[0]["detail_resolution"]["status"], "missing_detail_in_source_text")
        self.assertEqual(items[1]["detail_resolution"]["status"], "missing_detail_in_source_text")

    def test_build_multi_product_split_review_generates_per_item_results(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-split-001",
            batch_id="batch-split",
            group_key="case-split",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-split.pdf",
                    relative_path="raw/case-split/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "第13页 20260418001客户合同 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
                        "其他斗柜 20260418001001 北美黑胡桃木 1 12400 "
                        "经典床头柜 320260418001002 北美黑胡桃木 1 2580 合计 14980 "
                        "第14页 主卧 其他斗柜 202604180 01001北美黑胡桃木 无色哑光木蜡油尺寸 长：1300mm 宽：450mm 高：1000mm "
                        "第19页 主卧 经典床头柜 3 202604180 01002北美黑胡桃木 无色哑光木蜡油尺寸 长：450mm 宽：400mm 高：500mm"
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = PRODUCT_SPLITTER.build_multi_product_split_review(
                job,
                runtime_root=Path(tmpdir),
            )

        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["items"][0]["product_name"], "其他斗柜")
        self.assertEqual(payload["items"][0]["pricing_precheck"]["status"], "ready_for_formal_quote")
        self.assertEqual(payload["items"][0]["formal_quote"]["status"], "completed")
        self.assertEqual(payload["items"][0]["formal_quote"]["fallback_strategy"], "generic_cabinet_projection_profile")
        self.assertEqual(payload["items"][0]["split_status"], "compared")
        self.assertEqual(payload["items"][1]["product_name"], "经典床头柜")
        self.assertEqual(payload["items"][1]["pricing_precheck"]["status"], "ready_for_formal_quote")
        self.assertEqual(payload["items"][1]["normalized_fields"]["fields"]["product_category"]["value"], "经典床头柜3")
        self.assertEqual(payload["items"][1]["formal_quote"]["status"], "completed")
        self.assertEqual(payload["items"][1]["split_status"], "compared")
        self.assertEqual(payload["status_breakdown"]["compared"], 2)

    def test_force_line_item_fields_preserves_specific_category_and_overrides_material(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "经典床头柜3", "confidence": 0.9},
                "wood_material": {"value": "质小板凳 白蜡木材质小板凳", "confidence": 0.95},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="经典床头柜",
            material="北美黑胡桃木",
            quote_kind="",
            detail_snippet="",
        )

        self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "经典床头柜3")
        self.assertEqual(normalized_fields["fields"]["wood_material"]["value"], "北美黑胡桃木")

    def test_force_line_item_fields_refines_generic_chest_from_detail_snippet(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他斗柜", "confidence": 0.9},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他斗柜",
            material="北美黑胡桃木",
            quote_kind="standard",
            detail_snippet="主卧床头斗柜，整体圆角圆边，共八个 抽屉，明装金属拉手。",
        )

        self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "经典八斗柜")
        self.assertEqual(normalized_fields["fields"]["quote_kind"]["value"], "standard")

    def test_force_line_item_fields_normalizes_generic_cabinet_category_for_pricing(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他书柜", "confidence": 0.9},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他书柜",
            material="北美黑胡桃木",
            quote_kind="",
            detail_snippet="客厅黑胡桃书柜，玻璃平开门。",
        )

        self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "书柜")

    def test_force_line_item_fields_marks_generic_other_cabinet_as_custom_when_dimensions_are_present(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他衣柜", "confidence": 0.9},
                "length": {"value": "1980mm", "confidence": 0.92},
                "width": {"value": "620mm", "confidence": 0.92},
                "height": {"value": "2350mm", "confidence": 0.92},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他衣柜",
            material="北美黑胡桃木",
            quote_kind="",
            detail_snippet="主卧 其他衣柜 尺寸 长：1980mm 宽：620mm 高：2350mm",
        )

        self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "衣柜")
        self.assertEqual(normalized_fields["fields"]["quote_kind"]["value"], "custom")

    def test_force_line_item_fields_prefers_line_name_when_current_category_is_wrong_generic(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "床", "confidence": 0.88},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他斗柜",
            material="北美黑胡桃木",
            quote_kind="",
            detail_snippet="主卧床头斗柜，共八个抽屉。",
        )

        self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "经典八斗柜")

    def test_force_line_item_fields_marks_generic_other_bed_as_custom_when_dimensions_are_present(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他床", "confidence": 0.88},
                "length": {"value": "2132mm", "confidence": 0.92},
                "width": {"value": "2067mm", "confidence": 0.92},
                "height": {"value": "1100mm", "confidence": 0.92},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他床",
            material="北美黑胡桃木",
            quote_kind="",
            detail_snippet="主卧 其他床 尺寸 长：2132mm 宽：2067mm 高：1100mm",
        )

        self.assertEqual(normalized_fields["fields"]["quote_kind"]["value"], "custom")

    def test_force_line_item_fields_refines_generic_bed_from_detail_snippet(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "架式床", "confidence": 0.88},
            }
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="支腿架式床",
            material="北美黑胡桃木",
            quote_kind="standard",
            detail_snippet="长辈房黑胡桃床垫尺寸1.5米标准款支腿架式床。",
        )

        self.assertEqual(normalized_fields["fields"]["product_category"]["value"], "支腿架式床")
        self.assertEqual(normalized_fields["fields"]["quote_kind"]["value"], "standard")

    def test_other_child_bed_keeps_primary_drawing_gate_after_defaulting_to_custom(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他儿童床", "confidence": 0.96},
                "length": {"value": "2096mm", "confidence": 0.96},
                "width": {"value": "1080mm", "confidence": 0.96},
            },
            "child_bed_analysis": {
                "is_child_bed": True,
                "primary_drawing_asset_id": "asset-main-drawing",
                "primary_drawing_file_name": "大尺寸图.png",
                "requires_primary_drawing_review": True,
                "review_reason": "child_bed_primary_drawing_fields_incomplete",
                "review_block_fields": ["bed_form", "width", "length"],
            },
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他儿童床",
            material="北美白橡木",
            quote_kind="",
            detail_snippet="儿童房 其他儿童床 尺寸 长：2096mm 宽：1080mm 高：1800mm",
        )

        bridge_payload = PRODUCT_SPLITTER.bridge_contract_to_pricing_precheck(normalized_fields)

        self.assertEqual(normalized_fields["fields"]["quote_kind"]["value"], "custom")
        self.assertEqual(bridge_payload["status"], "manual_confirmation_required")
        self.assertEqual(bridge_payload["reason"], "child_bed_primary_drawing_review_required")

    def test_force_line_item_fields_builds_child_bed_route_hint_from_detail_snippet(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他儿童床", "confidence": 0.96},
                "length": {"value": "1380mm", "confidence": 0.95},
                "width": {"value": "2568mm", "confidence": 0.95},
                "height": {"value": "1885mm", "confidence": 0.95},
            },
            "child_bed_analysis": {
                "is_child_bed": True,
                "requires_primary_drawing_review": True,
                "review_reason": "child_bed_primary_drawing_not_stable",
                "review_block_fields": ["bed_form", "width", "length", "access_style"],
            },
        }

        PRODUCT_SPLITTER._force_line_item_fields(
            normalized_fields,
            product_name="其他儿童床",
            material="北美樱桃木",
            quote_kind="",
            detail_snippet=(
                "儿童房 其他儿童床 尺寸 长：1380mm 宽：2568mm 高：1885mm "
                "下床床垫建议尺寸：1300*2000mm，上床建议床垫尺寸：1200*2000mm。"
                "下床为侧翻箱体床。"
            ),
        )

        self.assertEqual(normalized_fields["fields"]["bed_form"]["value"], "上下床")
        self.assertEqual(normalized_fields["fields"]["lower_bed_type"]["value"], "箱体床")
        self.assertEqual(normalized_fields["route_evidence"]["recommended_route"], "modular_child_bed")
        self.assertEqual(normalized_fields["child_bed_analysis"]["suggested_pricing_route"], "modular_child_bed")

    def test_merge_parent_child_bed_context_brings_open_grid_stair_cabinet_hint_into_split_item(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他儿童床", "confidence": 0.96},
                "bed_form": {"value": "上下床", "confidence": 0.9},
                "access_style": {"value": "梯柜", "confidence": 0.9},
                "lower_bed_type": {"value": "箱体床", "confidence": 0.9},
            },
            "child_bed_analysis": {
                "is_child_bed": True,
                "suggested_pricing_route": "modular_child_bed",
            },
            "route_evidence": {
                "recommended_route": "modular_child_bed",
                "candidates": [
                    {
                        "route": "modular_child_bed",
                        "score": 10,
                        "signals": ["上下床", "箱体床"],
                        "evidence_snippets": ["下床为侧翻箱体床，上下铺结构"],
                        "source_asset_ids": ["split"],
                        "inferred_overrides": {"bed_form": "上下床", "lower_bed_type": "箱体床"},
                    }
                ],
            },
        }
        parent_normalized_fields = {
            "child_bed_analysis": {
                "is_child_bed": True,
                "stair_storage_mode": "open_grid",
                "stair_storage_signals": ["开放格", "无抽屉"],
                "stair_storage_evidence_snippets": ["图下注：左侧开放格梯柜，无抽屉，层板可调"],
                "stair_storage_source_asset_ids": ["asset-visual"],
            }
        }

        PRODUCT_SPLITTER._merge_parent_child_bed_context(
            normalized_fields=normalized_fields,
            parent_normalized_fields=parent_normalized_fields,
            line_item={
                "product_code": "20260391004004",
                "product_name": "其他儿童床",
                "detail_snippet": "儿童房 其他儿童床，下床为侧翻箱体床。",
            },
            child_bed_product_codes={"20260391004004"},
        )

        self.assertEqual(normalized_fields["child_bed_analysis"]["stair_storage_mode"], "open_grid")
        self.assertIn("开放格", normalized_fields["child_bed_analysis"]["stair_storage_signals"])
        route_candidate = normalized_fields["route_evidence"]["candidates"][0]
        self.assertEqual(route_candidate["inferred_overrides"]["stair_storage_mode"], "open_grid")
        self.assertTrue(
            any("左侧开放格梯柜" in item for item in route_candidate["evidence_snippets"])
        )

    def test_enrich_line_items_with_ocr_page_text_appends_following_dimension_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ocr_root = Path(tmpdir) / "ocr"
            for page_no, texts in (
                (1, ["儿童房 其他儿童床 202603910 04004", "下床为侧翻箱体床", "效果图"]),
                (2, ["上床床垫尺寸1200*2000mm", "1370.0mm", "450.0mm", "尺寸图"]),
                (3, ["下床床垫尺寸1300*2000mm", "566.7mm", "566.7mm", "566.7mm", "尺寸图"]),
                (4, ["儿童房 其他衣柜 202603910 04005", "效果图"]),
            ):
                page_dir = ocr_root / f"page-{page_no:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "page_index": page_no - 1,
                            "overall_ocr_res": {"rec_texts": texts},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            job = JOB_MODELS.ReviewJob(
                job_id="job-split-ocr-001",
                batch_id="batch-split",
                group_key="case-split-ocr",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-001",
                        source_path="/tmp/fake-split.pdf",
                        relative_path="raw/case-split/合同.pdf",
                        file_name="合同.pdf",
                        extension=".pdf",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="",
                        text_extract_method="native_plus_ocr",
                        metadata={"ocr_output_dir": str(ocr_root), "ocr_start_page": 29},
                    )
                ],
            )
            line_items = [
                {
                    "product_name": "其他儿童床",
                    "product_code": "20260391004004",
                    "detail_snippet": "第29页 儿童房 其他儿童床 202603910 04004 下床为侧翻箱体床",
                    "detail_resolution": {
                        "status": "detail_page_linked",
                        "detail_page_no": 29,
                        "anchor_method": "page_marker",
                        "anchor_confidence": "high",
                        "linked_contract_page_range": {"start": 29, "end": 29},
                        "stop_reason": "detail_only",
                        "evidence_scope": "detail_only",
                    },
                }
            ]

            PRODUCT_SPLITTER._enrich_line_items_with_ocr_page_text(job, line_items)

        self.assertIn("上床床垫尺寸1200*2000mm", line_items[0]["detail_snippet"])
        self.assertIn("566.7mm", line_items[0]["detail_snippet"])
        self.assertNotIn("04005", line_items[0]["detail_snippet"])
        self.assertEqual(line_items[0]["detail_resolution"]["detail_page_no"], 29)
        self.assertEqual(line_items[0]["detail_resolution"]["anchor_method"], "page_marker")
        self.assertEqual(
            line_items[0]["detail_resolution"]["linked_contract_page_range"],
            {"start": 29, "end": 31},
        )
        self.assertEqual(
            line_items[0]["detail_resolution"]["stop_reason"],
            "ocr_pages_exhausted",
        )
        self.assertEqual(line_items[0]["detail_resolution"]["evidence_scope"], "detail_plus_linked_pages")
        self.assertEqual(line_items[0]["boundary_start_page"], 29)
        self.assertEqual(line_items[0]["boundary_end_page"], 31)

    def test_enrich_line_items_with_ocr_page_text_uses_detail_page_mapping_when_code_is_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ocr_root = Path(tmpdir) / "ocr"
            for page_no, texts in (
                (
                    1,
                    [
                        "附件",
                        "其他儿童床 20260391004004 北美樱桃木 1 20560",
                        "其他衣柜 20260391004005 北美樱桃木 1 34142",
                    ],
                ),
                (
                    17,
                    [
                        "儿童房 其他儿童床",
                        "202603910",
                        "宽：2568mm",
                        "04004",
                        "长：1380mm",
                        "高：1885mm",
                        "下床为侧翻箱体床",
                    ],
                ),
                (18, ["1280.0mm", "400.0mm", "1380.0mm", "尺寸图"]),
                (
                    19,
                    [
                        "上床床垫尺寸1200*2000mm",
                        "下床床垫尺寸1300*2000mm",
                        "566.7mm",
                        "566.7mm",
                        "566.7mm",
                        "450.0mm",
                        "尺寸图",
                    ],
                ),
                (20, ["儿童房 其他衣柜 202603910 04005", "效果图"]),
            ):
                page_dir = ocr_root / f"page-{page_no:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "page_index": page_no - 1,
                            "overall_ocr_res": {"rec_texts": texts},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            job = JOB_MODELS.ReviewJob(
                job_id="job-split-ocr-002",
                batch_id="batch-split",
                group_key="case-split-ocr-page-map",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-001",
                        source_path="/tmp/fake-split.pdf",
                        relative_path="raw/case-split/合同.pdf",
                        file_name="合同.pdf",
                        extension=".pdf",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="",
                        text_extract_method="native_plus_ocr",
                        metadata={"ocr_output_dir": str(ocr_root), "ocr_start_page": 13},
                    )
                ],
            )
            line_items = [
                {
                    "product_name": "其他儿童床",
                    "product_code": "20260391004004",
                    "detail_snippet": "第29页 儿童房 其他儿童床 202603910 04004 下床为侧翻箱体床",
                    "detail_resolution": {
                        "status": "detail_page_linked",
                        "detail_page_no": 29,
                        "anchor_method": "page_marker",
                        "anchor_confidence": "high",
                        "linked_contract_page_range": {"start": 29, "end": 29},
                        "stop_reason": "detail_only",
                        "evidence_scope": "detail_only",
                    },
                }
            ]

            PRODUCT_SPLITTER._enrich_line_items_with_ocr_page_text(job, line_items)

        self.assertIn("上床床垫尺寸1200*2000mm", line_items[0]["detail_snippet"])
        self.assertIn("566.7mm", line_items[0]["detail_snippet"])
        self.assertNotIn("20560", line_items[0]["detail_snippet"])
        self.assertNotIn("04005", line_items[0]["detail_snippet"])
        self.assertEqual(line_items[0]["detail_resolution"]["detail_page_no"], 29)
        self.assertEqual(line_items[0]["detail_resolution"]["anchor_method"], "page_marker")

    def test_enrich_line_items_with_ocr_page_text_uses_code_name_fallback_and_skips_catalog_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ocr_root = Path(tmpdir) / "ocr"
            for page_no, texts in (
                (
                    1,
                    [
                        "附件",
                        "产品名称 产品编号 材质 数量 费用合计",
                        "其他衣柜 20260391004005 北美樱桃木 1 34142",
                    ],
                ),
                (
                    2,
                    [
                        "儿童房 其他衣柜 20260391004005",
                        "北美樱桃木",
                        "尺寸 长：2100mm 宽：600mm 高：2675mm",
                        "注明：流云门开启方式为按弹开启",
                        "效果图",
                    ],
                ),
                (3, ["外部尺寸", "2100.0mm", "600.0mm", "2675.0mm", "尺寸图"]),
            ):
                page_dir = ocr_root / f"page-{page_no:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "page_index": page_no - 1,
                            "overall_ocr_res": {"rec_texts": texts},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            job = JOB_MODELS.ReviewJob(
                job_id="job-split-ocr-003",
                batch_id="batch-split",
                group_key="case-split-ocr-fallback",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-001",
                        source_path="/tmp/fake-split.pdf",
                        relative_path="raw/case-split/合同.pdf",
                        file_name="合同.pdf",
                        extension=".pdf",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="",
                        text_extract_method="native_plus_ocr",
                        metadata={"ocr_output_dir": str(ocr_root), "ocr_start_page": 13},
                    )
                ],
            )
            line_items = [
                {
                    "product_name": "其他衣柜",
                    "product_code": "20260391004005",
                    "detail_snippet": "",
                    "detail_resolution": {
                        "status": "missing_detail_in_source_text",
                        "detail_page_no": None,
                        "anchor_method": "",
                        "anchor_confidence": "low",
                        "linked_contract_page_range": {"start": None, "end": None},
                        "stop_reason": "detail_anchor_missing",
                        "evidence_scope": "none",
                    },
                }
            ]

            PRODUCT_SPLITTER._enrich_line_items_with_ocr_page_text(job, line_items)

        self.assertIn("儿童房 其他衣柜 20260391004005", line_items[0]["detail_snippet"])
        self.assertNotIn("产品名称 产品编号 材质 数量 费用合计", line_items[0]["detail_snippet"])
        self.assertEqual(line_items[0]["detail_resolution"]["detail_page_no"], 14)
        self.assertEqual(line_items[0]["detail_resolution"]["anchor_method"], "code_name_fallback")
        self.assertEqual(line_items[0]["boundary_start_page"], 14)
        self.assertEqual(line_items[0]["boundary_end_page"], 15)

    def test_enrich_line_items_with_ocr_page_text_stops_after_two_non_context_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ocr_root = Path(tmpdir) / "ocr"
            for page_no, texts in (
                (
                    1,
                    [
                        "次卧 其他床 20260391004001",
                        "北美樱桃木",
                        "尺寸 长：1800mm 宽：2560mm 高：300mm",
                        "注明：无需避让踢脚线",
                        "效果图",
                    ],
                ),
                (2, ["俯视图", "1800.0mm", "2560.0mm", "300.0mm", "尺寸图"]),
                (3, ["20260391004客户合同", "页眉", "普通说明页"]),
                (4, ["客户签章", "普通文本", "无尺寸"]),
                (5, ["外部尺寸", "999.0mm", "888.0mm", "777.0mm", "尺寸图"]),
            ):
                page_dir = ocr_root / f"page-{page_no:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "page_index": page_no - 1,
                            "overall_ocr_res": {"rec_texts": texts},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            job = JOB_MODELS.ReviewJob(
                job_id="job-split-ocr-004",
                batch_id="batch-split",
                group_key="case-split-ocr-stop",
                source_type="manual_batch",
                source_channel="manual",
                requested_actions=["audit", "replay"],
                assets=[
                    JOB_MODELS.SourceAsset(
                        asset_id="asset-001",
                        source_path="/tmp/fake-split.pdf",
                        relative_path="raw/case-split/合同.pdf",
                        file_name="合同.pdf",
                        extension=".pdf",
                        media_kind="document",
                        role_hint="primary_contract",
                        text_preview="",
                        text_extract_method="native_plus_ocr",
                        metadata={"ocr_output_dir": str(ocr_root), "ocr_start_page": 14},
                    )
                ],
            )
            line_items = [
                {
                    "product_name": "其他床",
                    "product_code": "20260391004001",
                    "detail_snippet": "第14页 次卧 其他床 202603910 04001",
                    "detail_resolution": {
                        "status": "detail_page_linked",
                        "detail_page_no": 14,
                        "anchor_method": "page_marker",
                        "anchor_confidence": "high",
                        "linked_contract_page_range": {"start": 14, "end": 14},
                        "stop_reason": "detail_only",
                        "evidence_scope": "detail_only",
                    },
                }
            ]

            PRODUCT_SPLITTER._enrich_line_items_with_ocr_page_text(job, line_items)

        self.assertIn("俯视图", line_items[0]["detail_snippet"])
        self.assertNotIn("999.0mm", line_items[0]["detail_snippet"])
        self.assertEqual(
            line_items[0]["detail_resolution"]["linked_contract_page_range"],
            {"start": 14, "end": 15},
        )
        self.assertEqual(line_items[0]["detail_resolution"]["stop_reason"], "two_non_context_pages")
        self.assertEqual(line_items[0]["boundary_end_page"], 15)


    def test_manual_split_field_override_can_promote_child_bed_confirmation(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "其他儿童床", "confidence": 0.96},
                "wood_material": {"value": "北美樱桃木", "confidence": 0.96},
                "quote_kind": {"value": "custom", "confidence": 0.95},
                "length": {
                    "value": "1380mm",
                    "confidence": 0.84,
                    "evidence_refs": [{"asset_id": "asset-ocr", "source_kind": "ocr_text"}],
                },
                "width": {
                    "value": "2568mm",
                    "confidence": 0.84,
                    "evidence_refs": [{"asset_id": "asset-ocr", "source_kind": "ocr_text"}],
                },
                "height": {
                    "value": "1885mm",
                    "confidence": 0.84,
                    "evidence_refs": [{"asset_id": "asset-ocr", "source_kind": "ocr_text"}],
                },
            },
            "child_bed_analysis": {
                "is_child_bed": True,
                "primary_drawing_asset_id": "asset-ocr",
                "primary_drawing_file_name": "儿童床尺寸图.png",
                "primary_drawing_confidence": "medium",
                "requires_primary_drawing_review": True,
                "review_reason": "child_bed_primary_drawing_not_stable",
                "review_block_fields": ["bed_form", "width", "length", "access_style"],
            },
            "route_evidence": {
                "recommended_route": "modular_child_bed",
                "candidates": [
                    {
                        "route": "modular_child_bed",
                        "score": 10,
                        "signals": ["上下床", "箱体床"],
                        "evidence_snippets": ["图下注：下床为侧翻箱体床，上下铺结构"],
                        "source_asset_ids": ["asset-ocr"],
                        "inferred_overrides": {"bed_form": "上下床", "lower_bed_type": "箱体床"},
                    }
                ],
            },
        }
        job = JOB_MODELS.ReviewJob(
            job_id="job-manual-override-001",
            batch_id="batch-manual-override",
            group_key="case-manual-override",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[],
            metadata={
                "manual_split_field_overrides": {
                    "04004": {
                        "confirmed": True,
                        "confirmed_route": "modular_child_bed",
                        "field_values": {
                            "bed_form": "上下床",
                            "access_style": "梯柜",
                            "lower_bed_type": "箱体床",
                            "length": "1380mm",
                            "width": "2568mm",
                            "height": "1885mm",
                        },
                    }
                }
            },
        )

        PRODUCT_SPLITTER._apply_manual_split_field_overrides(
            job=job,
            line_item={
                "product_code": "20260391004004",
                "detail_snippet": "儿童房 其他儿童床 尺寸 长：1380mm 宽：2568mm 高：1885mm，下床为侧翻箱体床。",
            },
            normalized_fields=normalized_fields,
        )

        bridge_payload = PRODUCT_SPLITTER.bridge_contract_to_pricing_precheck(normalized_fields)

        self.assertEqual(normalized_fields["fields"]["access_style"]["value"], "梯柜")
        self.assertEqual(normalized_fields["fields"]["length"]["confidence"], 1.0)
        self.assertEqual(
            normalized_fields["fields"]["length"]["evidence_refs"][0]["source_kind"],
            "manual_confirmation",
        )
        self.assertFalse(normalized_fields["child_bed_analysis"]["requires_primary_drawing_review"])
        self.assertEqual(normalized_fields["child_bed_analysis"]["primary_drawing_confidence"], "high")
        self.assertEqual(
            normalized_fields["route_evidence"]["candidates"][0]["inferred_overrides"]["access_style"],
            "梯柜",
        )
        self.assertNotEqual(bridge_payload["reason"], "child_bed_primary_drawing_review_required")
        self.assertNotIn("access_style", bridge_payload["blocked_fields"])
        self.assertNotIn("width", bridge_payload["blocked_fields"])
        self.assertNotIn("length", bridge_payload["blocked_fields"])

    def test_build_nearest_catalog_variant_precheck_args_picks_closest_standard_desk_variant(self) -> None:
        refined = PRODUCT_SPLITTER._build_nearest_catalog_variant_precheck_args(
            {
                "category": "经典双屉书桌",
                "material": "北美樱桃木",
                "length": "1300mm",
                "width": "600mm",
                "depth": "600mm",
                "height": "780mm",
            },
            line_total="3880元",
        )

        assert refined is not None
        self.assertEqual(refined["precheck_args"]["category"], "经典双屉书桌")
        self.assertEqual(refined["precheck_args"]["length"], "1400mm")
        self.assertNotIn("depth", refined["precheck_args"])
        self.assertNotIn("height", refined["precheck_args"])
        self.assertEqual(refined["detail"]["matched_product_code"], "SZ-02")
        self.assertEqual(refined["detail"]["material_price"], 4080)

    def test_build_generic_bed_candidate_precheck_args_prefers_classic_box_bed_from_mattress_size(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_bed_candidate_precheck_args(
            {
                "category": "其他床",
                "material": "北美樱桃木",
                "length": "2107mm",
                "width": "1301mm",
                "height": "1100mm",
            },
            detail_snippet="床垫尺寸为2000*1200，床垫厚度建议170~220mm，排骨架内嵌3公分。",
            line_total="8162元",
        )

        assert refined is not None
        self.assertEqual(refined["precheck_args"]["category"], "经典箱体床")
        self.assertEqual(refined["precheck_args"]["length"], "2000mm")
        self.assertEqual(refined["precheck_args"]["width"], "1200mm")
        self.assertEqual(refined["precheck_args"]["quote_kind"], "standard")
        self.assertEqual(refined["detail"]["candidate_quote_total"], "7600元")

    def test_build_generic_tatami_quote_payload_estimates_low_platform_other_bed(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_tatami_quote_payload(
            {
                "category": "其他床",
                "material": "北美樱桃木",
                "length": "1800mm",
                "width": "2560mm",
                "height": "300mm",
                "quote_kind": "custom",
            },
            detail_snippet="次卧 其他床 尺寸 长：1800mm 宽：2560mm 高：300mm",
            line_total="16312元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "TTM-01")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "16965元")
        self.assertEqual(refined["quote_payload"]["pricing_route"], "tatami_projection_area_fallback")

    def test_extract_mattress_dimensions_supports_decimal_meter_notation(self) -> None:
        dims = PRODUCT_SPLITTER._extract_mattress_dimensions("床垫尺寸1.5*2米，床垫厚度建议20cm")

        self.assertEqual(dims, {"length": "2000mm", "width": "1500mm"})

    def test_extract_mattress_dimensions_supports_labeled_width_length_phrase(self) -> None:
        dims = PRODUCT_SPLITTER._extract_mattress_dimensions("需要搭配 1.3m宽，2.4m长 的床垫。")

        self.assertEqual(dims, {"length": "2400mm", "width": "1300mm"})

    def test_retry_generic_bed_with_tatami_fallback_accepts_missing_product_failure(self) -> None:
        refined = PRODUCT_SPLITTER._retry_generic_bed_with_tatami_fallback(
            pricing_bridge_payload={
                "precheck_args": {
                    "category": "其他床",
                    "material": "北美樱桃木",
                    "length": "1800mm",
                    "width": "2560mm",
                    "height": "300mm",
                    "quote_kind": "custom",
                }
            },
            formal_quote_payload={
                "status": "failed",
                "reason": "formal_quote_execution_failed",
                "error": "未找到产品：其他床",
                "pricing_route": "",
            },
            detail_snippet="次卧 其他床 尺寸 长：1800mm 宽：2560mm 高：300mm",
            line_total="16312元",
        )

        assert refined is not None
        self.assertEqual(refined["pricing_total"], "16965元")
        self.assertEqual(refined["fallback_strategy"], "generic_tatami_projection_profile")

    def test_retry_modular_child_bed_with_dimension_probe_can_match_line_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            refined = PRODUCT_SPLITTER._retry_modular_child_bed_with_dimension_probe(
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "precheck_args": {
                        "category": "其他儿童床",
                        "material": "北美樱桃木",
                        "quote_kind": "custom",
                        "bed_form": "上下床",
                        "lower_bed_type": "箱体床",
                    },
                    "child_bed_analysis": {
                        "is_child_bed": True,
                        "suggested_pricing_route": "modular_child_bed",
                        "stair_storage_mode": "open_grid",
                    },
                    "route_evidence": {
                        "recommended_route": "modular_child_bed",
                        "candidates": [{"route": "modular_child_bed", "score": 12}],
                    },
                },
                detail_snippet=(
                    "儿童房 其他儿童床 下床为侧翻箱体床 "
                    "上床床垫尺寸1200*2000mm 下床床垫尺寸1300*2000mm "
                    "400.0mm 1370.0mm 1380.0mm 450.0mm 472.0mm "
                    "566.7mm 566.7mm 566.7mm 尺寸图"
                ),
                line_total="20560元",
                job_id="probe-child-bed",
                runtime_root=Path(tmpdir),
            )

        assert refined is not None
        self.assertEqual(refined["fallback_strategy"], "modular_child_bed_dimension_probe")
        self.assertTrue(str(refined["pricing_total"]).endswith("元"))
        self.assertLessEqual(abs(float(refined["pricing_total_value"]) - 20560.0), 200.0)

    def test_build_generic_stool_candidate_quote_payload_prefers_square_stool_for_small_stool(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_stool_candidate_quote_payload(
            {
                "category": "小板凳",
                "material": "白蜡木",
            },
            detail_snippet="白蜡木材质小板凳",
            line_total="99元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["candidate_category"], "方凳")
        self.assertEqual(refined["detail"]["matched_product_code"], "DZ-02")
        self.assertEqual(refined["detail"]["candidate_quote_total"], "101元")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "101元")
        self.assertEqual(refined["quote_payload"]["status"], "completed")

    def test_build_generic_stool_candidate_quote_payload_prefers_exact_match_for_beauty_stool(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_stool_candidate_quote_payload(
            {
                "category": "美人凳",
                "material": "北美黑胡桃木",
                "length": "500mm",
                "width": "300mm",
                "height": "430mm",
            },
            detail_snippet="主卧黑胡桃标准款美人凳。",
            line_total="1200元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "TD-04")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "1200元")

    def test_build_generic_cabinet_projection_quote_payload_estimates_shoe_cabinet(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_cabinet_projection_quote_payload(
            {
                "category": "其他玄关柜",
                "material": "乌拉圭玫瑰木",
                "length": "2330 mm",
                "height": "1210 mm",
                "width": "400 mm",
            },
            detail_snippet="玄关乌拉圭玫瑰木鞋柜，门型骨格线柜门，换鞋凳内嵌。",
            line_total="12296.86元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["profile_key"], "玄关柜")
        self.assertEqual(refined["detail"]["matched_product_code"], "XGG-01")
        self.assertEqual(refined["detail"]["candidate_quote_total"], "12634元")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "12634元")
        self.assertEqual(refined["quote_payload"]["pricing_route"], "cabinet_projection_area_fallback")

    def test_build_generic_cabinet_projection_quote_payload_prefers_glass_door_candidate_when_detail_mentions_glass(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_cabinet_projection_quote_payload(
            {
                "category": "其他书柜",
                "material": "北美黑胡桃木",
                "length": "2620mm",
                "height": "2250mm",
                "width": "320mm",
                "depth": "320mm",
            },
            detail_snippet="客厅黑胡桃书柜，拼框玻璃平开门，玻璃推拉门，上翻展板门。",
            line_total="37989.52元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "SG-11")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "39412元")

    def test_build_generic_cabinet_projection_quote_payload_avoids_sliding_wardrobe_when_detail_mentions_hinges(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_cabinet_projection_quote_payload(
            {
                "category": "其他衣柜",
                "material": "北美樱桃木",
                "length": "2520mm",
                "height": "2735mm",
                "width": "600mm",
                "depth": "600mm",
                "quote_kind": "custom",
            },
            detail_snippet=(
                "儿童房其他衣柜，右边五扇柜门使用大角度铰链，盖板使用随意停，"
                "柜门上下都需要装门碰，柜体靠墙避让踢脚线。"
            ),
            line_total="36140元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "YG-22")
        self.assertEqual(refined["detail"]["candidate_category"], "升级经典门衣柜")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "37812元")

    def test_build_generic_cabinet_projection_quote_payload_infers_bookshelf_profile_for_bare_other_category(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_cabinet_projection_quote_payload(
            {
                "category": "其他",
                "material": "北美樱桃木",
                "length": "1435mm",
                "height": "2760mm",
                "width": "610mm",
                "depth": "610mm",
                "quote_kind": "custom",
            },
            detail_snippet="次卧 其他 北美樱桃木 尺寸 长：1435mm 宽：610mm 高：2760mm 直角圆边",
            line_total="16256元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["profile_key"], "书柜")
        self.assertEqual(refined["detail"]["matched_product_code"], "SG-01")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "16595元")

    def test_retry_generic_cabinet_with_projection_fallback_prefers_closer_semantic_candidate_over_completed_formal_quote(self) -> None:
        refined = PRODUCT_SPLITTER._retry_generic_cabinet_with_projection_fallback(
            pricing_bridge_payload={
                "precheck_args": {
                    "category": "书柜",
                    "material": "北美黑胡桃木",
                    "length": "2620 mm",
                    "height": "2250 mm",
                    "width": "320 mm",
                    "depth": "320 mm",
                }
            },
            formal_quote_payload={
                "status": "completed",
                "pricing_route": "cabinet_projection_area",
                "pricing_total": "33512元",
            },
            detail_snippet=(
                "客厅黑胡桃书柜。门型：①直角拼框玻璃平开门，玻璃：超白玻璃，开启方式：通长扣手。"
                "②玻璃推拉门，玻璃：超白玻璃。③上翻回收展板门。"
            ),
            line_total="37989.52元",
        )

        assert refined is not None
        self.assertEqual(refined["pricing_total"], "39412元")
        self.assertEqual(refined["fallback_detail"]["matched_product_code"], "SG-11")
        self.assertEqual(refined["pricing_route"], "cabinet_projection_area_fallback")

    def test_build_dining_cabinet_combo_quote_payload_prefers_unit_price_combo_for_long_custom_sideboard(self) -> None:
        refined = PRODUCT_SPLITTER._build_dining_cabinet_combo_quote_payload(
            {
                "category": "其他餐边柜",
                "material": "北美白橡木",
                "length": "3404mm",
                "height": "2295mm",
                "depth": "330mm",
                "quote_kind": "custom",
            },
            detail_snippet="客厅 其他餐边柜 尺寸 长：3404mm 宽：330mm 高：2295mm",
            line_total="31631元",
        )

        assert refined is not None
        self.assertEqual(refined["quote_payload"]["pricing_total"], "31680元")
        self.assertEqual(refined["detail"]["candidate_quote_diff"], "49元")
        self.assertEqual(refined["detail"]["combo_count"], 3)

    def test_retry_dining_cabinet_combo_with_unit_candidates_prefers_closer_combo_than_projection_area(self) -> None:
        refined = PRODUCT_SPLITTER._retry_dining_cabinet_combo_with_unit_candidates(
            pricing_bridge_payload={
                "precheck_args": {
                    "category": "其他餐边柜",
                    "material": "北美白橡木",
                    "length": "3404mm",
                    "height": "2295mm",
                    "depth": "330mm",
                    "quote_kind": "custom",
                }
            },
            formal_quote_payload={
                "status": "completed",
                "pricing_route": "cabinet_projection_area_fallback",
                "pricing_total": "45200元",
            },
            detail_snippet="客厅 其他餐边柜 尺寸 长：3404mm 宽：330mm 高：2295mm",
            line_total="31631元",
        )

        assert refined is not None
        self.assertEqual(refined["pricing_total"], "31680元")
        self.assertEqual(refined["fallback_strategy"], "dining_cabinet_unit_price_combo")

    def test_build_standard_bed_mattress_quote_payload_scales_princess_bed_by_mattress_size(self) -> None:
        refined = PRODUCT_SPLITTER._build_standard_bed_mattress_quote_payload(
            {
                "category": "公主床",
                "material": "北美樱桃木",
                "length": "2087mm",
                "width": "1289mm",
                "height": "1000mm",
                "quote_kind": "standard",
            },
            detail_snippet="女儿房樱桃木1.2米标准款公主床，适配床垫1200*2000，建议床垫厚度50-100mm。",
            line_total="5440元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "ETC-05")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "5440元")
        self.assertEqual(refined["quote_payload"]["pricing_route"], "bed_mattress_area_fallback")

    def test_build_explicit_catalog_code_quote_payload_uses_contract_product_code(self) -> None:
        refined = PRODUCT_SPLITTER._build_explicit_catalog_code_quote_payload(
            {
                "category": "支腿架式床",
                "material": "北美黑胡桃木",
                "length": "2000mm",
                "width": "1800mm",
                "height": "150mm",
            },
            detail_snippet="主卧支腿架式床，在标准 JSC-03 基础上更改，更改如下：床头板封死；床腿加高50mm。",
            line_total="12545元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "JSC-03")
        self.assertEqual(refined["detail"]["matched_name"], "经典架式床01")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "11800元")
        self.assertEqual(refined["quote_payload"]["pricing_route"], "explicit_catalog_code_fallback")

    def test_retry_generic_cabinet_projection_fallback_accepts_cabinet_route(self) -> None:
        refined = PRODUCT_SPLITTER._retry_generic_cabinet_with_projection_fallback(
            pricing_bridge_payload={
                "precheck_args": {
                    "category": "经典带门书柜",
                    "material": "北美樱桃木",
                    "length": "1240mm",
                    "height": "2000mm",
                    "width": "350mm",
                    "depth": "350mm",
                }
            },
            formal_quote_payload={
                "status": "failed",
                "reason": "formal_quote_total_missing",
                "pricing_route": "cabinet",
            },
            detail_snippet="经典带门书柜，直角圆边，避让踢脚线，玻璃为超白玻璃。",
            line_total="11952元",
        )

        assert refined is not None
        self.assertEqual(refined["fallback_strategy"], "generic_cabinet_projection_profile")
        self.assertEqual(refined["pricing_route"], "cabinet_projection_area_fallback")
        self.assertTrue(str(refined["pricing_total"]).endswith("元"))

    def test_build_generic_cabinet_unit_candidate_quote_payload_prefers_close_tv_console(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_cabinet_unit_candidate_quote_payload(
            {
                "category": "其他电视柜",
                "material": "北美黑胡桃木",
                "length": "3000mm",
                "depth": "420mm",
                "height": "300mm",
            },
            detail_snippet="电视柜直角圆边，左右各两个抽屉，中间为抽拉面；悬浮式底托结构。",
            line_total="10200元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["matched_product_code"], "DSG-11")
        self.assertEqual(refined["detail"]["candidate_quote_total"], "10350元")
        self.assertEqual(refined["quote_payload"]["pricing_route"], "catalog_cabinet_unit_candidate")

    def test_retry_generic_cabinet_with_unit_candidate_prefers_closer_tv_console_than_projection_fallback(self) -> None:
        refined = PRODUCT_SPLITTER._retry_generic_cabinet_with_unit_candidate(
            pricing_bridge_payload={
                "precheck_args": {
                    "category": "其他电视柜",
                    "material": "北美黑胡桃木",
                    "length": "3000mm",
                    "depth": "420mm",
                    "height": "300mm",
                }
            },
            formal_quote_payload={
                "status": "completed",
                "pricing_route": "cabinet_projection_area_fallback",
                "pricing_total": "7182元",
            },
            detail_snippet="电视柜直角圆边，左右各两个抽屉，中间为抽拉面；悬浮式底托结构。",
            line_total="10200元",
        )

        assert refined is not None
        self.assertEqual(refined["pricing_total"], "10350元")
        self.assertEqual(refined["fallback_strategy"], "generic_cabinet_unit_candidate")

    def test_build_generic_desk_candidate_quote_payload_prefers_price_aligned_standard_desk_for_corner_desk_bundle(self) -> None:
        refined = PRODUCT_SPLITTER._build_generic_desk_candidate_quote_payload(
            {
                "category": "其他书桌",
                "material": "北美樱桃木",
                "length": "2580 mm",
                "depth": "900mm",
                "height": "1080 mm",
            },
            detail_snippet="一组两个独立部件：转角高桌 +矮柜。儿童房，左侧有一个下隐藏扣手薄抽屉。",
            line_total="8800元",
        )

        assert refined is not None
        self.assertEqual(refined["detail"]["candidate_category"], "漂流岛")
        self.assertEqual(refined["detail"]["matched_product_code"], "SZ-14")
        self.assertEqual(refined["detail"]["candidate_quote_total"], "8700元")
        self.assertEqual(refined["quote_payload"]["pricing_total"], "8700元")
        self.assertEqual(refined["quote_payload"]["pricing_route"], "catalog_desk_candidate")

    def test_build_multi_product_split_review_can_fallback_combo_chest_and_absorb_zero_amount_layers(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-combo-chest-001",
            batch_id="batch-combo-chest",
            group_key="case-combo-chest",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-combo-chest.pdf",
                    relative_path="raw/case-combo-chest/合同.pdf",
                    file_name="合同.pdf",
                    extension=".pdf",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "附件： 产品名称 产品编号 材质 数量 费用合计（元） "
                        "定制组合斗柜 202604118001001 北美樱桃木 2 9080 "
                        "层板 202604118001002 北美樱桃木 3 0 "
                        "层板 202604118001003 北美樱桃木 1 0 合计 9080 "
                        "第14页 客厅 定制组合斗柜 202604118 001001北美樱桃木 尺寸 长：800mm 宽：450mm 高：1000mm "
                        "注明：共五个简美抽屉，JS-YX圆形金属拉手开启。柜体后方避让踢脚线。 "
                        "第18页 主卧 层板 202604118 001002北美樱桃木 尺寸 长：870mm 宽：548mm 高：20mm 注明： "
                        "第19页 次卧 层板 202604118 001003北美樱桃木 尺寸 长：860mm 宽：548mm 高：20mm 注明： "
                    ),
                    text_extract_method="pdf_text_layer",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = PRODUCT_SPLITTER.build_multi_product_split_review(
                job,
                runtime_root=Path(tmpdir),
            )

        self.assertEqual(payload["item_count"], 3)

        combo_chest_item = payload["items"][0]
        self.assertEqual(combo_chest_item["product_name"], "定制组合斗柜")
        self.assertEqual(combo_chest_item["formal_quote"]["status"], "completed")
        self.assertEqual(
            combo_chest_item["formal_quote"]["fallback_strategy"],
            "generic_cabinet_projection_profile",
        )
        self.assertLessEqual(combo_chest_item["pricing_compare"]["best_match_diff_value"], 600)
        self.assertEqual(combo_chest_item["split_status"], "compared")

        layer_items = payload["items"][1:]
        self.assertTrue(all(item["product_name"] == "层板" for item in layer_items))
        self.assertTrue(all(item["formal_quote"]["status"] == "completed" for item in layer_items))
        self.assertTrue(all(item["formal_quote"]["pricing_total"] == "0元" for item in layer_items))
        self.assertTrue(all(item["split_status"] == "compared" for item in layer_items))

    def test_build_multi_product_split_review_splits_tatami_wardrobe_combo_components(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-tatami-wardrobe-combo",
            batch_id="batch-tatami-wardrobe-combo",
            group_key="case-tatami-wardrobe-combo",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake-tatami-wardrobe-combo.docx",
                    relative_path="raw/case/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称 产品编号 材质 数量 费用合计（元） "
                        "升级经典无腰线衣柜 20260229002001 北美白橡木 1 36936 "
                        "经典榻榻米+衣柜组合 20260229002002 北美白橡木 1 14760 "
                        "合计 51696 折扣 98折 折扣后合计 50660 "
                        "次卧 升级经典无腰线衣柜 20260229002001 北美白橡木 尺寸 长：2090mm 宽：600mm 高：2770mm "
                        "注明：次卧白橡木拼框门衣柜，直角直边，柜内五组抽拉挂衣杆。 "
                        "次卧 经典榻榻米+衣柜组合 20260229002002 北美白橡木 尺寸 长：2000mm 宽：1500mm 高：400mm "
                        "注明：次卧白橡木榻榻米；1.5*2m床垫，榻榻米靠外侧安排抽屉，"
                        "安装注意：当前三件家具不做任何固定，仅安装落地靠在一起。"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = PRODUCT_SPLITTER.build_multi_product_split_review(
                job,
                runtime_root=Path(tmpdir),
            )

        self.assertEqual(payload["item_count"], 3)
        self.assertEqual(payload["status_breakdown"]["compared"], 2)
        self.assertEqual(payload["status_breakdown"]["manual_confirmation_required"], 1)
        names = [item["product_name"] for item in payload["items"]]
        self.assertIn("升级经典无腰线衣柜", names)
        self.assertIn("经典榻榻米+衣柜组合-榻榻米", names)
        self.assertIn("经典榻榻米+衣柜组合-衣柜", names)

        tatami_item = next(item for item in payload["items"] if item["product_name"].endswith("-榻榻米"))
        self.assertEqual(tatami_item["formal_quote"]["status"], "completed")
        self.assertEqual(tatami_item["formal_quote"]["pricing_total"], "13440元")
        self.assertEqual(tatami_item["formal_quote"]["fallback_strategy"], "tatami_wardrobe_combo_tatami_component")
        self.assertEqual(tatami_item["split_status"], "compared")

        wardrobe_item = next(item for item in payload["items"] if item["product_name"].endswith("-衣柜"))
        self.assertEqual(wardrobe_item["split_status"], "manual_confirmation_required")
        self.assertEqual(wardrobe_item["formal_quote"]["status"], "skipped")
        self.assertIn("衣柜部分的独立尺寸", wardrobe_item["pricing_precheck"]["precheck_result"]["next_question"])

    def test_scale_quote_payload_for_quantity_multiplies_completed_total(self) -> None:
        payload = PRODUCT_SPLITTER._scale_quote_payload_for_quantity(
            {
                "status": "completed",
                "pricing_total": "2580元",
                "pricing_total_value": 2580.0,
                "prepared_payload": {
                    "total": "2580元",
                    "items": [
                        {
                            "subtotal": "2580元",
                            "calculation_steps": ["目录标准价：2580 元"],
                        }
                    ],
                },
            },
            quantity="2",
        )

        self.assertEqual(payload["pricing_total"], "5160元")
        self.assertEqual(payload["prepared_payload"]["total"], "5160元")
        self.assertEqual(payload["prepared_payload"]["items"][0]["subtotal"], "5160元")
        self.assertIn("数量：2", payload["prepared_payload"]["items"][0]["calculation_steps"])


if __name__ == "__main__":
    unittest.main()
