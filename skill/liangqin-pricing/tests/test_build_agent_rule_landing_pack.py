import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_agent_rule_landing_pack.py"
SPEC = importlib.util.spec_from_file_location("build_agent_rule_landing_pack", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildAgentRuleLandingPackTests(unittest.TestCase):
    def data_point(
        self,
        *,
        point_id: str,
        layer: str,
        topic: str,
        summary: str,
        domain: str = "cabinet",
        domain_label: str = "柜体",
        source_title: str = "测试来源",
        page: int = 1,
    ) -> dict:
        return {
            "id": point_id,
            "pricing_system_layer": layer,
            "domain": domain,
            "domain_label": domain_label,
            "topic": topic,
            "extracted_data": summary,
            "answer_outline": summary,
            "source": {
                "title": source_title,
                "page": page,
                "path": "<root>/测试来源",
                "local_path": "/tmp/source.pdf",
                "node_id": "node-1",
            },
            "trigger_questions": [f"{topic}怎么处理？"],
        }

    def test_build_pack_filters_to_pricing_landing_layers(self) -> None:
        certification_path = Path(tempfile.mkdtemp()) / "certification.json"
        certification_path.write_text(
            json.dumps(
                {
                    "data_points": [
                        self.data_point(
                            point_id="data-point-0001",
                            layer=MODULE.QUOTE_CALC_RULE,
                            topic="天地铰链铝框门加价",
                            summary="文档说明天地铰链铝框门需要按加价规则处理。",
                        ),
                        self.data_point(
                            point_id="data-point-0002",
                            layer=MODULE.QUOTE_PRECHECK_RULE,
                            topic="儿童床安全规范",
                            summary="文档说明儿童床需要符合 GB 28007 安全规范，缺少条件时必须确认。",
                            domain="bed",
                            domain_label="床榻",
                        ),
                        self.data_point(
                            point_id="data-point-0003",
                            layer="设计师咨询知识",
                            topic="岩板设计说明",
                            summary="文档说明岩板设计注意事项。",
                        ),
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        model = MODULE.build_pack_model(certification_path=certification_path, candidate_layer="candidate", first_batch_size=10)

        self.assertEqual(model["landing_rule_count"], 2)
        self.assertEqual(model["pricing_system_layer_counts"][MODULE.QUOTE_CALC_RULE], 1)
        self.assertEqual(model["pricing_system_layer_counts"][MODULE.QUOTE_PRECHECK_RULE], 1)
        self.assertEqual({rule["source_data_point_id"] for rule in model["rules"]}, {"data-point-0001", "data-point-0002"})

    def test_priority_puts_p0_money_and_safety_rules_first(self) -> None:
        certification_path = Path(tempfile.mkdtemp()) / "certification.json"
        certification_path.write_text(
            json.dumps(
                {
                    "data_points": [
                        self.data_point(
                            point_id="data-point-0001",
                            layer=MODULE.QUOTE_PRECHECK_RULE,
                            topic="普通备注",
                            summary="文档说明下单需要备注颜色。",
                        ),
                        self.data_point(
                            point_id="data-point-0002",
                            layer=MODULE.QUOTE_CALC_RULE,
                            topic="门板补差",
                            summary="文档说明该门板需要补差并进入报价公式。",
                            domain="door_panel",
                            domain_label="门板",
                        ),
                        self.data_point(
                            point_id="data-point-0003",
                            layer=MODULE.QUOTE_PRECHECK_RULE,
                            topic="儿童床安全规范",
                            summary="文档说明儿童床需要符合 GB 28007 安全规范。",
                            domain="bed",
                            domain_label="床榻",
                        ),
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        model = MODULE.build_pack_model(certification_path=certification_path, candidate_layer="candidate", first_batch_size=2)
        first_ids = [rule["source_data_point_id"] for rule in model["first_batch"]]

        self.assertEqual(first_ids, ["data-point-0002", "data-point-0003"])
        self.assertTrue(all(rule["risk_level"].startswith("P0") for rule in model["first_batch"]))

    def test_landing_rule_contains_agent_execution_contract(self) -> None:
        point = self.data_point(
            point_id="data-point-0001",
            layer=MODULE.QUOTE_PRECHECK_RULE,
            topic="悬空电视柜固定上墙",
            summary="文档说明悬空支架需要固定在承重墙上，设计阶段必须确认安装条件。",
        )

        rule = MODULE.build_landing_rule(point, 1)

        assert rule is not None
        self.assertEqual(rule["landing_action"], MODULE.ACTION_PRECHECK)
        self.assertEqual(rule["suggested_module"], "precheck_quote:safety_or_install_gate")
        self.assertIn("wall_or_install_condition", rule["required_fields"])
        self.assertIn("不进入正式报价", rule["expected_behavior"])
        self.assertIn("precheck", rule["test_suggestion"])

    def test_build_and_write_pack_outputs_json_csv_and_markdown_without_blocked_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            certification_path = tmp / "full-document-data-certification.json"
            certification_path.write_text(
                json.dumps(
                    {
                        "data_points": [
                            self.data_point(
                                point_id="data-point-0001",
                                layer=MODULE.QUOTE_CALC_RULE,
                                topic="软包床头报价",
                                summary="文档说明软包床头定制价格计算方法详见报价原则。",
                                domain="bed",
                                domain_label="床榻",
                                source_title="软包床头",
                            )
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            model = MODULE.build_and_write_pack(
                skill_dir=tmp,
                candidate_layer="candidate",
                input_json=str(certification_path),
                output_dir=tmp,
                first_batch_size=1,
            )

            output_json = Path(model["outputs"]["json"])
            output_csv = Path(model["outputs"]["csv"])
            output_protocol = Path(model["outputs"]["protocol"])
            output_summary = Path(model["outputs"]["summary"])
            self.assertTrue(output_json.exists())
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_protocol.exists())
            self.assertTrue(output_summary.exists())

            protocol = output_protocol.read_text(encoding="utf-8")
            summary = output_summary.read_text(encoding="utf-8")
            self.assertIn("AI Agent 落地协议", protocol)
            self.assertIn("不做人类逐条规则看板", summary)
            for text in [output_json.read_text(encoding="utf-8"), output_csv.read_text(encoding="utf-8"), protocol, summary]:
                for term in MODULE.BLOCKED_TERMS:
                    self.assertNotIn(term, text)

            with output_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["first_batch_recommended"], "yes")
            self.assertEqual(rows[0]["source_title"], "软包床头")


if __name__ == "__main__":
    unittest.main()
