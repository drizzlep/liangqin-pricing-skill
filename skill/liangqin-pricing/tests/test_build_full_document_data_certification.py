import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_full_document_data_certification.py"
SPEC = importlib.util.spec_from_file_location("build_full_document_data_certification", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildFullDocumentDataCertificationTests(unittest.TestCase):
    def runtime_entry(self) -> dict:
        return {
            "page": 81001,
            "topic": "天地铰链铝框门 尺寸限制 305mm≤高度≤2200mm，180mm≤宽度≤500mm",
            "status": "runtime_hard_rule",
            "domain": "cabinet",
            "summary": "本段主要描述加价、折减或特殊修正条件。 识别标签：柜体, 门型, 尺寸阈值。关键信息：天地铰链铝框门；尺寸限制：305mm≤高度≤2200mm，180mm≤宽度≤500mm；门板厚度：26mm。",
            "source_title": "天地铰链铝框门",
            "source_path": "<root>/7.门板/天地铰链铝框门",
            "source_local_path": "/tmp/manual.pdf",
            "source_page": 1,
            "publish_target": "runtime",
            "rule_layer_status": "runtime",
            "risk_level": "low",
        }

    def test_classifies_runtime_data_as_ready_without_requiring_page_image(self) -> None:
        decision, reason = MODULE.classify_data_point(self.runtime_entry())

        self.assertEqual(decision, MODULE.READY)
        self.assertIn("可用数据", reason)

    def test_build_data_point_keeps_source_page_and_trigger_questions(self) -> None:
        point = MODULE.build_data_point(self.runtime_entry(), 1)

        self.assertTrue(point["agent_ready"])
        self.assertEqual(point["source"]["title"], "天地铰链铝框门")
        self.assertEqual(point["source"]["page"], 1)
        self.assertEqual(point["pricing_system_layer"], MODULE.QUOTE_CALC_RULE)
        self.assertIn("天地铰链铝框门有什么要求？", point["trigger_questions"])
        self.assertIn("关键数据", point["answer_outline"])

    def test_pricing_system_layer_splits_ready_data_points(self) -> None:
        calc = dict(
            self.runtime_entry(),
            topic="流云平板门纹理连续超过0.9m需加价",
            summary="文档说明平板门纹理连续超过0.9m时需加价，详见报价原则。",
        )
        knowledge = dict(
            self.runtime_entry(),
            topic="岩板背板设计注意点",
            summary="文档说明岩板背板的设计注意点和适用场景。",
        )

        self.assertEqual(MODULE.classify_pricing_system_layer(calc, MODULE.READY)[0], MODULE.QUOTE_CALC_RULE)
        self.assertEqual(MODULE.classify_pricing_system_layer(knowledge, MODULE.READY)[0], MODULE.DESIGNER_KNOWLEDGE)

    def test_manual_review_and_background_are_not_forced_into_agent(self) -> None:
        manual = dict(self.runtime_entry(), status="unresolved", publish_target="manual_review", rule_layer_status="manual_review")
        background = dict(self.runtime_entry(), status="excluded_background", publish_target="none", rule_layer_status="excluded")

        self.assertEqual(MODULE.classify_data_point(manual)[0], MODULE.REVIEW)
        self.assertEqual(MODULE.classify_data_point(background)[0], MODULE.NOT_AUTOMATED)

    def test_full_document_closure_statuses_do_not_create_human_limbo(self) -> None:
        knowledge = dict(self.runtime_entry(), status="knowledge_ready", publish_target="knowledge", rule_layer_status="knowledge")
        not_safe = dict(self.runtime_entry(), status="not_safe_for_auto_answer", publish_target="none", rule_layer_status="not_auto")
        recheck = dict(self.runtime_entry(), status="needs_source_recheck", publish_target="none", rule_layer_status="source_recheck")

        self.assertEqual(MODULE.classify_data_point(knowledge)[0], MODULE.READY)
        self.assertEqual(MODULE.classify_data_point(not_safe)[0], MODULE.NOT_AUTOMATED)
        self.assertEqual(MODULE.classify_data_point(recheck)[0], MODULE.NOT_AUTOMATED)

    def test_missing_summary_is_extraction_failed(self) -> None:
        broken = dict(self.runtime_entry(), summary="")

        decision, reason = MODULE.classify_data_point(broken)

        self.assertEqual(decision, MODULE.EXTRACTION_FAILED)
        self.assertIn("缺少", reason)

    def test_query_data_points_matches_question_to_document_data(self) -> None:
        points = [
            MODULE.build_data_point(self.runtime_entry(), 1),
            MODULE.build_data_point(
                dict(
                    self.runtime_entry(),
                    topic="岩板背板 设计注意点",
                    summary="文档说明岩板背板的设计注意点。",
                    source_title="岩板背板",
                ),
                2,
            ),
        ]

        matches = MODULE.query_data_points("天地铰链铝框门高度限制是多少？", points, limit=1)

        self.assertEqual(matches[0]["id"], "data-point-0001")
        self.assertGreater(matches[0]["score"], 0)
        self.assertEqual(matches[0]["source"]["title"], "天地铰链铝框门")

    def test_query_data_points_prefers_specific_combined_terms(self) -> None:
        generic = MODULE.build_data_point(
            dict(
                self.runtime_entry(),
                topic="柜内盖板结构 榻榻米组合柜 加托称",
                summary="文档说明榻榻米组合柜门内使用翻盖结构时，为避让铰链方便开启，需加托称。",
                source_title="柜内盖板结构",
            ),
            1,
        )
        specific = MODULE.build_data_point(
            dict(
                self.runtime_entry(),
                topic="托称 榻榻米组合柜空区 固定上墙",
                summary="文档说明榻榻米组合柜空区适用于托称添加规则，但添加托称的组合柜需配合固定上墙。",
                source_title="托称",
            ),
            2,
        )

        matches = MODULE.query_data_points("榻榻米组合柜空区加托称时，需要固定上墙吗？", [generic, specific], limit=1)

        self.assertEqual(matches[0]["id"], "data-point-0002")
        self.assertEqual(matches[0]["source"]["title"], "托称")

    def test_query_data_points_requires_requested_data_terms(self) -> None:
        generic = MODULE.build_data_point(
            dict(
                self.runtime_entry(),
                topic="常规推拉门 单小块门板厚度12mm",
                summary="文档说明常规推拉门的单小块门板厚度为12mm。",
                source_title="常规推拉门",
            ),
            1,
        )
        specific = MODULE.build_data_point(
            dict(
                self.runtime_entry(),
                topic="常规推拉门 22厚门板 直边圆边内缩60mm",
                summary="文档说明22厚门板：直边、圆边内缩60mm，内斜边内缩65mm。",
                source_title="常规推拉门",
            ),
            2,
        )

        matches = MODULE.query_data_points("推拉门单小块门板内缩多少？", [generic, specific], limit=1)

        self.assertEqual(matches[0]["id"], "data-point-0002")
        self.assertIn("内缩60mm", matches[0]["answer_outline"])

    def test_render_html_is_human_readable_and_hides_internal_terms(self) -> None:
        point = MODULE.build_data_point(self.runtime_entry(), 1)
        model = {
            "title": "良禽佳木设计师手册整本文档数据可用性认证",
            "entry_count": 1,
            "covered_page_count": 1,
            "topic_count": 1,
            "decision_counts": {MODULE.READY: 1},
            "pricing_system_layer_counts": {MODULE.QUOTE_PRECHECK_RULE: 1},
            "recommended_action": "可开放通过数据点。",
            "query_probe_results": MODULE.build_query_probe_results([point], ("天地铰链铝框门高度限制是多少？",)),
            "data_points": [point],
        }

        html = MODULE.render_html(model)

        self.assertIn("整本文档数据认证", html)
        self.assertIn("整页图不是硬门槛", html)
        self.assertIn("天地铰链铝框门", html)
        self.assertIn("可进 Agent", html)
        self.assertIn("报价系统分层", html)
        self.assertIn("追问/拦截", html)
        for term in MODULE.INTERNAL_HTML_TERMS:
            self.assertNotIn(term, html)
        self.assertNotIn("access_token", html)
        self.assertNotIn("Signature=", html)


if __name__ == "__main__":
    unittest.main()
