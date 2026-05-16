import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_money_rule_regression_pack.py"
SPEC = importlib.util.spec_from_file_location("build_money_rule_regression_pack", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildMoneyRuleRegressionPackTests(unittest.TestCase):
    def write_manifest(self, skill_dir: Path, layer: str, report_dir: Path) -> None:
        manifest_dir = skill_dir / "references" / "addenda" / layer
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "layer_id": layer,
                    "artifacts": {"rules_candidate_file": str(report_dir / "rules-candidate.json")},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_dimensions_without_explicit_amount_do_not_activate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "calculate_modular_child_bed_quote.py").write_text("# stub\n", encoding="utf-8")
            report_dir = skill_dir / "reports" / "addenda" / "new"
            report_dir.mkdir(parents=True)
            self.write_manifest(skill_dir, "new", report_dir)

            money_ledger = report_dir / "money-rule-regression-ledger.json"
            money_ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "landing_id": "landing-rule-test-dimension-only",
                                "source_data_point_id": "data-point-test-dimension-only",
                                "machine_resolution_status": "regression_spec_ready_paused",
                                "suggested_module": "pricing_calculation:modular_child_bed",
                                "risk_level": "P0-影响金额",
                                "required_fields": ["product_or_category"],
                                "source_title": "尺寸-only 测试规则",
                                "source_page": 4,
                                "numeric_signals": ["600mm"],
                                "formula_signals": ["公式"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            landing_pack = report_dir / "agent-rule-landing-pack.json"
            landing_pack.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "landing_id": "landing-rule-test-dimension-only",
                                "source_data_point_id": "data-point-test-dimension-only",
                                "required_fields": ["product_or_category"],
                                "rule_excerpt": "围栏尺寸 600mm，文档称可作为报价公式来源。",
                                "source": {"title": "尺寸-only 测试规则", "page": 4},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            certification = report_dir / "full-document-data-certification.json"
            certification.write_text(
                json.dumps(
                    {
                        "data_points": [
                            {
                                "id": "data-point-test-dimension-only",
                                "topic": "模块化儿童床",
                                "extracted_data": "栏杆间隙应满足 600mm 相关限制，但没有明确金额。",
                                "source": {"title": "尺寸-only 测试规则", "page": 4},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_model(
                skill_dir=skill_dir,
                candidate_layer="new",
                money_ledger_path=money_ledger,
                landing_pack_path=landing_pack,
                certification_path=certification,
                price_index_path=report_dir / "missing-price-index.json",
            )

        self.assertFalse(model["human_rule_by_rule_review_required"])
        self.assertFalse(model["formal_quote_calculation_changed"])
        self.assertEqual(model["counts"]["money_rule_total"], 1)
        self.assertEqual(model["counts"]["activated_count"], 0)
        self.assertEqual(model["counts"]["still_paused_count"], 1)
        rule = model["rules"][0]
        self.assertEqual(rule["runtime_action"], "keep_paused")
        self.assertIn("missing_explicit_amount_or_unit_price", rule["blockers"])
        self.assertIn("missing_golden_expected_amount", rule["blockers"])
        self.assertIn("missing_executable_calculator_mapping", rule["blockers"])
        self.assertEqual(model["golden_amount_cases"][0]["expected_amount"], None)

    def test_conflict_money_rule_remains_blocked_even_with_formula_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir)
            report_dir = skill_dir / "reports" / "addenda" / "new"
            report_dir.mkdir(parents=True)
            money_ledger = report_dir / "money-rule-regression-ledger.json"
            money_ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "landing_id": "landing-rule-0002",
                                "source_data_point_id": "data-point-0002",
                                "machine_resolution_status": "conflict_blocked_until_money_regression",
                                "suggested_module": "pricing_calculation:cabinet_structure_adjustment",
                                "required_fields": ["product_or_category", "height", "width"],
                                "source_title": "天地铰链铝框门",
                                "source_page": 1,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            landing_pack = report_dir / "agent-rule-landing-pack.json"
            landing_pack.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "landing_id": "landing-rule-0002",
                                "rule_excerpt": "门高≤2200mm，宽≤500mm，涉及加价补差公式。",
                                "source": {"title": "天地铰链铝框门", "page": 1},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            certification = report_dir / "full-document-data-certification.json"
            certification.write_text(json.dumps({"data_points": []}, ensure_ascii=False), encoding="utf-8")

            model = MODULE.build_model(
                skill_dir=skill_dir,
                candidate_layer="new",
                money_ledger_path=money_ledger,
                landing_pack_path=landing_pack,
                certification_path=certification,
                price_index_path=report_dir / "missing-price-index.json",
            )

        rule = model["rules"][0]
        self.assertEqual(rule["regression_status"], "blocked_conflict_money_regression")
        self.assertEqual(rule["runtime_action"], "keep_paused")
        self.assertIn("conflict_blocked_until_amount_regression_passes", rule["blockers"])

    def test_amount_extraction_uses_quote_labels_not_dimensions(self) -> None:
        result = {
            "reply_text": "已确认：北美黑胡桃木，长0.6米，深0.12米，高1.8米。这次按目录标准单价计价。正式报价：3680元",
        }

        self.assertEqual(MODULE.extract_regression_amount(result), 3680)

    def test_amount_extraction_prefers_structured_total(self) -> None:
        result = {
            "quote_card_payload": {"total": "3680元"},
            "reply_text": "长0.6米，深0.12米，高1.8米。",
        }

        self.assertEqual(MODULE.extract_regression_amount(result), 3680)

    def test_exact_catalog_unit_price_source_generates_golden_amount(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            money_ledger = report_dir / "money-rule-regression-ledger.json"
            money_ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "landing_id": "landing-rule-0155",
                                "source_data_point_id": "data-point-0155",
                                "machine_resolution_status": "regression_spec_ready_paused",
                                "suggested_module": "pricing_calculation:door_panel_adjustment",
                                "risk_level": "P0-影响金额",
                                "required_fields": ["product_or_category", "material"],
                                "source_title": "穿衣镜",
                                "source_page": 2,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            landing_pack = report_dir / "agent-rule-landing-pack.json"
            landing_pack.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "landing_id": "landing-rule-0155",
                                "source_data_point_id": "data-point-0155",
                                "required_fields": ["product_or_category", "material"],
                                "rule_excerpt": "穿衣镜另收费，按目录标准价。",
                                "source": {"title": "穿衣镜", "page": 2},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            certification = report_dir / "full-document-data-certification.json"
            certification.write_text(json.dumps({"data_points": []}, ensure_ascii=False), encoding="utf-8")

            model = MODULE.build_model(
                skill_dir=skill_dir,
                candidate_layer="new",
                money_ledger_path=money_ledger,
                landing_pack_path=landing_pack,
                certification_path=certification,
                price_index_path=skill_dir / "data" / "current" / "price-index.json",
            )

        self.assertTrue(model["formal_quote_calculation_changed"])
        self.assertEqual(model["counts"]["activated_count"], 1)
        self.assertEqual(model["counts"]["golden_amount_ready_count"], 1)
        rule = model["rules"][0]
        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "price_index_exact_catalog_unit_price")
        self.assertEqual(rule["amount_source"]["expected_amount"], 3680)
        self.assertEqual(rule["regression_result"]["status"], "passed")
        self.assertEqual(model["golden_amount_cases"][0]["expected_amount"], 3680)

    def test_conflict_money_rule_can_activate_after_amount_regression_passes(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            money_ledger = report_dir / "money-rule-regression-ledger.json"
            money_ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "landing_id": "landing-rule-0155",
                                "source_data_point_id": "data-point-0155",
                                "machine_resolution_status": "conflict_blocked_until_money_regression",
                                "suggested_module": "pricing_calculation:door_panel_adjustment",
                                "risk_level": "P0-影响金额",
                                "required_fields": ["product_or_category", "material"],
                                "source_title": "穿衣镜",
                                "source_page": 2,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            landing_pack = report_dir / "agent-rule-landing-pack.json"
            landing_pack.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "landing_id": "landing-rule-0155",
                                "source_data_point_id": "data-point-0155",
                                "required_fields": ["product_or_category", "material"],
                                "rule_excerpt": "穿衣镜另收费，按目录标准价。",
                                "source": {"title": "穿衣镜", "page": 2},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            certification = report_dir / "full-document-data-certification.json"
            certification.write_text(json.dumps({"data_points": []}, ensure_ascii=False), encoding="utf-8")

            model = MODULE.build_model(
                skill_dir=skill_dir,
                candidate_layer="new",
                money_ledger_path=money_ledger,
                landing_pack_path=landing_pack,
                certification_path=certification,
                price_index_path=skill_dir / "data" / "current" / "price-index.json",
            )

        rule = model["rules"][0]
        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["regression_status"], "passed_activate_formal_amount_calculation")
        self.assertNotIn("conflict_blocked_until_amount_regression_passes", rule["blockers"])

    def test_fuzzy_catalog_candidates_are_machine_disambiguation_not_activation(self) -> None:
        price_records = [
            {
                "is_queryable": True,
                "record_kind": "price",
                "is_deprecated": False,
                "sheet": "书柜",
                "group": "海棠书柜",
                "product_code": "SG-22",
                "name": "海棠书柜",
                "door_type": "铝框门",
                "pricing_mode": "projection_area",
                "remark": "铝框门",
                "materials": {"黑胡桃": 6980},
            },
            {
                "is_queryable": True,
                "record_kind": "price",
                "is_deprecated": False,
                "sheet": "书柜",
                "group": "卡座书柜",
                "product_code": "SG-20",
                "name": "卡座书柜",
                "door_type": "铝框门",
                "pricing_mode": "projection_area",
                "remark": "铝框门",
                "materials": {"黑胡桃": 7980},
            },
        ]

        rule = MODULE.classify_rule(
            skill_dir=SCRIPT_PATH.resolve().parents[1],
            entry={
                "landing_id": "landing-rule-test-ambiguous",
                "source_data_point_id": "data-point-test-ambiguous",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:cabinet_structure_adjustment",
                "source_title": "铝框门测试规则",
                "required_fields": ["product_or_category", "door_type"],
            },
            landing={
                "rule_excerpt": "铝框门存在多个整柜价目表候选，不能直接作为局部门板金额。",
                "source": {"title": "铝框门测试规则", "page": 3},
            },
            data_point={},
            price_records=price_records,
        )

        self.assertEqual(rule["runtime_action"], "keep_paused")
        self.assertEqual(rule["machine_resolution_lane"], "machine_price_index_disambiguation_needed")
        self.assertEqual(rule["amount_source"]["candidate_count"], 2)

    def test_direct_projection_remark_candidate_can_activate(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0048",
                "source_data_point_id": "data-point-0048",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:cabinet_structure_adjustment",
                "source_title": "纹理连续说明",
                "required_fields": ["product_or_category", "height", "material"],
            },
            landing={
                "rule_excerpt": "纹理连续不足0.9m时按对应价目表路径。",
                "source": {"title": "纹理连续说明", "page": 1},
            },
            data_point={},
            price_records=MODULE.load_price_records(skill_dir / "data" / "current" / "price-index.json"),
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "price_index_direct_projection_area")
        self.assertEqual(rule["amount_source"]["expected_amount"], 29225)
        self.assertEqual(rule["regression_result"]["status"], "passed")

    def test_quotation_principle_linear_rule_can_activate(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0079",
                "source_data_point_id": "data-point-0079",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:cabinet_structure_adjustment",
                "source_title": "圆弧侧板",
                "required_fields": ["product_or_category", "height", "material"],
            },
            landing={
                "rule_excerpt": "圆弧侧板尺寸限制，报价原则明确圆弧侧板价格按米计算。",
                "source": {"title": "圆弧侧板", "page": 1},
            },
            data_point={},
            price_records=[],
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "quotation_principle_linear_addition")
        self.assertEqual(rule["amount_source"]["expected_amount"], 540)
        self.assertEqual(rule["regression_result"]["status"], "passed")

    def test_quotation_principle_side_panel_rule_can_activate(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0067",
                "source_data_point_id": "data-point-0067",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:cabinet_structure_adjustment",
                "source_title": "无底板柜",
                "required_fields": ["product_or_category", "width", "depth", "length", "wall_or_install_condition"],
            },
            landing={
                "rule_excerpt": "无底板柜下部侧板按照侧板面积计算。",
                "source": {"title": "无底板柜", "page": 2},
            },
            data_point={},
            price_records=[],
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "quotation_principle_side_panel_area")
        self.assertEqual(rule["amount_source"]["expected_amount"], 4329)
        self.assertEqual(rule["regression_result"]["status"], "passed")

    def test_quotation_principle_door_panel_rule_can_activate(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0122",
                "source_data_point_id": "data-point-0122",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:door_panel_adjustment",
                "source_title": "藤编门",
                "required_fields": ["product_or_category", "height", "width", "door_type"],
            },
            landing={
                "rule_excerpt": "藤编门尺寸限制，报价原则门板表提供单独藤编门单价。",
                "source": {"title": "藤编门", "page": 1},
            },
            data_point={},
            price_records=[],
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "quotation_principle_door_panel_area")
        self.assertEqual(rule["amount_source"]["expected_amount"], 4656)
        self.assertEqual(rule["regression_result"]["status"], "passed")

    def test_quotation_principle_frame_door_panel_rule_can_activate(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0027",
                "source_data_point_id": "data-point-0027",
                "machine_resolution_status": "conflict_blocked_until_money_regression",
                "suggested_module": "pricing_calculation:door_panel_adjustment",
                "source_title": "极窄斜边拼框门",
                "required_fields": ["product_or_category", "width", "door_type"],
            },
            landing={
                "rule_excerpt": "极窄斜边拼框门尺寸限制，报价原则门板表提供单独拼框门单价。",
                "source": {"title": "极窄斜边拼框门", "page": 1},
            },
            data_point={},
            price_records=[],
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "quotation_principle_door_panel_area")
        self.assertEqual(rule["amount_source"]["expected_amount"], 3576)
        self.assertEqual(rule["regression_result"]["status"], "passed")

    def test_machine_disambiguated_projection_rule_can_activate(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0010",
                "source_data_point_id": "data-point-0010",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:cabinet_structure_adjustment",
                "source_title": "模块卡座书柜定制设计指引",
                "required_fields": ["product_or_category", "height", "width", "depth", "material", "door_type"],
            },
            landing={
                "rule_excerpt": "模块卡座书柜仅支持模块预设，机器以门型平板门精确消歧。",
                "source": {"title": "模块卡座书柜定制设计指引", "page": 1},
            },
            data_point={},
            price_records=MODULE.load_price_records(skill_dir / "data" / "current" / "price-index.json"),
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "price_index_machine_disambiguated_projection_area")
        self.assertEqual(rule["amount_source"]["expected_amount"], 35112)
        self.assertEqual(rule["regression_result"]["status"], "passed")

    def test_modular_child_bed_rule_uses_calculator_route_not_standard_bed(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0157",
                "source_data_point_id": "data-point-0157",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:modular_child_bed",
                "source_title": "模块化儿童床设计要求",
                "required_fields": ["bed_form", "material", "width", "length", "guardrail_style"],
            },
            landing={
                "rule_excerpt": "模块化儿童床围栏规则，使用现有模块化儿童床计算器生成正式金额。",
                "source": {"title": "模块化儿童床设计要求", "page": 4},
            },
            data_point={},
            price_records=[],
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "modular_child_bed_calculator_golden_total")
        self.assertEqual(rule["amount_source"]["expected_amount"], 8915)
        self.assertEqual(rule["regression_result"]["status"], "passed")
        self.assertEqual(rule["regression_result"]["pricing_route"], "modular_child_bed")
        self.assertEqual(rule["regression_result"]["runtime_status"], "completed")

    def test_soft_package_bed_rule_uses_bed_standard_runtime_after_machine_disambiguation(self) -> None:
        skill_dir = SCRIPT_PATH.resolve().parents[1]
        rule = MODULE.classify_rule(
            skill_dir=skill_dir,
            entry={
                "landing_id": "landing-rule-0009",
                "source_data_point_id": "data-point-0009",
                "machine_resolution_status": "conflict_blocked_until_money_regression",
                "suggested_module": "pricing_calculation:bed_or_soft_package_adjustment",
                "source_title": "软包床头",
                "required_fields": ["product_or_category", "height", "length", "material", "quote_note"],
            },
            landing={
                "rule_excerpt": "华夫格软包床头不可拆卸，软包床头可以搭配任意床体，详见报价原则。",
                "source": {"title": "软包床头", "page": 1},
            },
            data_point={},
            price_records=MODULE.load_price_records(skill_dir / "data" / "current" / "price-index.json"),
        )

        self.assertEqual(rule["runtime_action"], "activate_formal_amount_calculation")
        self.assertEqual(rule["amount_source"]["source_type"], "price_index_machine_disambiguated_soft_package_bed")
        self.assertEqual(rule["amount_source"]["expected_amount"], 8980)
        self.assertEqual(rule["regression_result"]["status"], "passed")
        self.assertEqual(rule["regression_result"]["pricing_route"], "bed_standard")

    def test_plain_unique_projection_candidate_still_requires_disambiguation(self) -> None:
        price_records = [
            {
                "is_queryable": True,
                "record_kind": "price",
                "is_deprecated": False,
                "sheet": "书柜",
                "group": "经典带门书柜",
                "product_code": "SG-17",
                "name": "辛巴书柜",
                "door_type": "拼框门",
                "pricing_mode": "projection_area",
                "remark": "拼框门",
                "materials": {"黑胡桃": 6680},
                "dimensions": {"length": 4.68, "height": 2.2, "depth": 0.35},
            }
        ]

        rule = MODULE.classify_rule(
            skill_dir=SCRIPT_PATH.resolve().parents[1],
            entry={
                "landing_id": "landing-rule-test-plain-projection",
                "source_data_point_id": "data-point-test-plain-projection",
                "machine_resolution_status": "regression_spec_ready_paused",
                "suggested_module": "pricing_calculation:door_panel_adjustment",
                "source_title": "拼框门测试规则",
                "required_fields": ["product_or_category", "door_type"],
            },
            landing={
                "rule_excerpt": "拼框门边宽规则，不等于整柜辛巴书柜价格。",
                "source": {"title": "拼框门测试规则", "page": 1},
            },
            data_point={},
            price_records=price_records,
        )

        self.assertEqual(rule["runtime_action"], "keep_paused")
        self.assertEqual(rule["machine_resolution_lane"], "machine_price_index_disambiguation_needed")


if __name__ == "__main__":
    unittest.main()
