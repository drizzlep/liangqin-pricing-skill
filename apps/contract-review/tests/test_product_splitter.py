import importlib.util
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
        self.assertEqual(payload["items"][0]["split_status"], "formal_quote_failed")
        self.assertEqual(payload["items"][1]["product_name"], "经典床头柜")
        self.assertEqual(payload["items"][1]["pricing_precheck"]["status"], "ready_for_formal_quote")
        self.assertEqual(payload["items"][1]["normalized_fields"]["fields"]["product_category"]["value"], "经典床头柜3")
        self.assertEqual(payload["items"][1]["formal_quote"]["status"], "completed")
        self.assertEqual(payload["items"][1]["split_status"], "compared")
        self.assertEqual(payload["status_breakdown"]["formal_quote_failed"], 1)
        self.assertEqual(payload["status_breakdown"]["compared"], 1)

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

    def test_extract_mattress_dimensions_supports_decimal_meter_notation(self) -> None:
        dims = PRODUCT_SPLITTER._extract_mattress_dimensions("床垫尺寸1.5*2米，床垫厚度建议20cm")

        self.assertEqual(dims, {"length": "2000mm", "width": "1500mm"})

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
