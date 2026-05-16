import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_agent_validation_pack.py"
SPEC = importlib.util.spec_from_file_location("build_agent_validation_pack", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildAgentValidationPackTests(unittest.TestCase):
    def test_current_standard_usage_detects_archived_layer(self) -> None:
        guidance = {
            "matched": True,
            "constraints": [{"layer_name": "设计师追加规则 2026-03-22"}],
            "follow_up_questions": [],
            "adjustments": [],
            "addendum_notes": [],
        }
        statuses = {"设计师追加规则 2026-03-22": "ARCHIVED"}

        usage = MODULE.current_standard_usage(guidance, statuses)

        self.assertTrue(usage["used"])
        self.assertEqual(usage["status"], "命中非当前标准，需排除")
        self.assertEqual(usage["layers"], ["设计师追加规则 2026-03-22"])

    def test_build_case_result_marks_page_first_visual_case_ready(self) -> None:
        case = {
            "id": "rock",
            "category": "岩板材料图文查询",
            "question": "读一下岩板圣勃朗鱼肚，给我对应整页图。",
            "topic": "岩板",
            "expected": "整页图可用。",
        }
        guidance = {
            "matched": True,
            "recommended_reply_mode": "rule_explanation",
            "evidence_level": "hard_rule",
            "suggested_reply": "岩板台面有明确注意事项。",
            "constraints": [{"layer_name": "设计师追加规则 线上版 2026-05-13"}],
        }
        evidence = {
            "answer": "已附对应整页图。",
            "page_images": ["/tmp/page.png"],
            "crop_images": [],
            "debug_crop_images": ["/tmp/debug-crop.jpg"],
            "needs_human_review": False,
            "evidence_status": "agent_ready",
            "source_refs": [{"source_title": "岩板", "source_page": 5}],
        }
        statuses = {"设计师追加规则 线上版 2026-05-13": "ACTIVE"}

        result = MODULE.build_case_result(case, guidance=guidance, evidence=evidence, layer_statuses=statuses)

        self.assertEqual(result["decision"], MODULE.READY)
        self.assertTrue(result["agent_sample_ready"])
        self.assertEqual(result["visual_evidence"]["page_images"], ["/tmp/page.png"])
        self.assertEqual(result["visual_evidence"]["crop_images"], [])
        self.assertEqual(result["visual_evidence"]["debug_crop_image_count"], 1)

    def test_build_case_result_routes_follow_up_to_review(self) -> None:
        case = {
            "id": "open-shelf",
            "category": "开放格/分段缝/柜体结构",
            "question": "超高带门柜体有开放格时，分段缝应该怎么对齐？",
            "topic": "",
            "expected": "缺高度时应追问。",
        }
        guidance = {
            "matched": True,
            "recommended_reply_mode": "follow_up",
            "evidence_level": "needs_confirmation",
            "suggested_reply": "这组柜门还需要确认高度。",
            "missing_fields": ["高度"],
            "follow_up_questions": [{"layer_name": "设计师追加规则 2026-03-22"}],
        }

        result = MODULE.build_case_result(case, guidance=guidance, evidence={}, layer_statuses={"设计师追加规则 2026-03-22": "ARCHIVED"})

        self.assertEqual(result["decision"], MODULE.REVIEW)
        self.assertFalse(result["agent_sample_ready"])
        self.assertEqual(result["current_standard_usage"]["status"], "命中非当前标准，需排除")
        self.assertIn("还缺必要信息", "".join(result["decision_reasons"]))
        self.assertEqual(result["suggested_reply"], "还差一个信息：高度。补上后才能判断。")

    def test_build_case_result_blocks_visual_case_without_page_image(self) -> None:
        case = {
            "id": "sliding-door",
            "category": "推拉门相关规则",
            "question": "推拉门要注意什么？",
            "topic": "推拉门",
            "expected": "必须有整页图。",
        }
        guidance = {"matched": True, "recommended_reply_mode": "rule_explanation", "suggested_reply": "推拉门规则。"}
        evidence = {"page_images": [], "crop_images": [], "needs_human_review": False}

        result = MODULE.build_case_result(case, guidance=guidance, evidence=evidence, layer_statuses={})

        self.assertEqual(result["decision"], MODULE.BLOCKED)
        self.assertIn("没有对应整页图证据", result["decision_reasons"][0])

    def test_build_case_result_uses_conservative_visual_reply_for_blank_page(self) -> None:
        case = {
            "id": "children-bed-safety",
            "category": "儿童床/安全规范",
            "question": "儿童床有什么安全规范要注意？给我对应整页图。",
            "topic": "安全规范",
            "expected": "空白页不能给具体建议。",
        }
        guidance = {
            "matched": True,
            "recommended_reply_mode": "rule_explanation",
            "suggested_reply": "这块有明确的补充规则。儿童床围栏样式多样可选。",
            "constraints": [{"layer_name": "设计师追加规则 线上版 2026-05-13"}],
        }
        evidence = {
            "answer": "检索到安全规范相关资料来源：GB 28007 第 2 页。但对应整页图接近空白，OCR 也没有读出可用内容；当前不能据此给出具体建议，需要重新导出来源页或人工补证据。",
            "page_images": ["/tmp/blank.png"],
            "crop_images": [],
            "debug_crop_images": [],
            "needs_human_review": True,
            "review_reason": "blank_visual_asset",
            "matches": [{"page_image_looks_blank": True}],
            "evidence_status": "needs_human_review",
        }

        result = MODULE.build_case_result(case, guidance=guidance, evidence=evidence, layer_statuses={})

        self.assertEqual(result["decision"], MODULE.REVIEW)
        self.assertIn("图片几乎是空白", result["suggested_reply"])
        self.assertNotIn("围栏样式多样可选", result["suggested_reply"])
        self.assertNotIn("OCR", result["suggested_reply"])

    def test_human_reply_shortens_rock_slab_visual_answer(self) -> None:
        case = {
            "id": "rock-slab-pricing",
            "category": "报价注意点",
            "question": "岩板台面和岩板背板报价或设计有什么注意点？",
            "topic": "岩板",
            "expected": "不贴大段 OCR。",
        }
        guidance = {"matched": True, "recommended_reply_mode": "rule_explanation", "suggested_reply": "这个场景有明确要求。岩板台面。"}
        evidence = {
            "answer": "检索到岩板相关资料：## 圣勃朗鱼肚 ## DESCRIPTION 踏上瓦特纳冰原，凝视着冰川划过的痕迹，纵横交错，犹如不同的人生轨迹。SPECIFICATION DA2M78BR-Y 来源：岩板 第 5 页。已附对应整页图。",
            "page_images": ["/tmp/page.png"],
            "crop_images": [],
            "debug_crop_images": [],
            "needs_human_review": False,
            "evidence_status": "agent_ready",
            "source_refs": [{"source_title": "岩板", "source_page": 5}],
        }

        result = MODULE.build_case_result(case, guidance=guidance, evidence=evidence, layer_statuses={})

        self.assertEqual(result["decision"], MODULE.READY)
        self.assertIn("找到了对应页", result["suggested_reply"])
        self.assertIn("圣勃朗鱼肚", result["suggested_reply"])
        self.assertNotIn("DESCRIPTION", result["suggested_reply"])
        self.assertNotIn("踏上瓦特纳冰原", result["suggested_reply"])

    def test_human_reply_removes_internal_terms_from_rule_reply(self) -> None:
        raw = "如果是问推拉门这组结构尺寸，目前能稳定确认到一组常用口径。现有复盘里能稳定读到：22 厚门板做推拉门时，直边和圆边通常按内缩 60mm 理解。这块目前还是高置信复盘口径，术语口径还没完全锁定。后续仍要结合 runtime 规则一起看。"

        reply = MODULE.humanize_rule_reply(raw)

        self.assertIn("推拉门", reply)
        self.assertIn("60mm", reply)
        self.assertNotIn("高置信复盘口径", reply)
        self.assertNotIn("runtime", reply)

    def test_source_boundary_reply_is_plain_language(self) -> None:
        reply = MODULE.humanize_source_boundary_reply(
            {
                "answer_summary": "现有良禽资料对良禽是否支持国产五金或进口五金、以及 BLUM 这类品牌配置都未明确。这里我不能替你按行业常识往下确认；如果你要准确口径，建议直接和设计师或门店确认。"
            }
        )

        self.assertEqual(reply, "文档里没写清楚这件事，所以不能替你确认。要得到准确口径，需要问设计师或门店。")

    def test_render_html_is_human_readable_and_page_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "agent-validation-pack.html"
            model = {
                "title": "良禽设计师手册企业 Agent 验证包",
                "case_count": 1,
                "decision_counts": {MODULE.READY: 1},
                "recommended_action": "可进入企业 Agent 样例封装。",
                "cases": [
                    {
                        "category": "岩板材料图文查询",
                        "question": "读一下岩板圣勃朗鱼肚，给我对应整页图。",
                        "expected": "整页图可用。",
                        "decision": MODULE.READY,
                        "decision_reasons": ["回答和证据满足本阶段样例要求。"],
                        "agent_sample_ready": True,
                        "suggested_reply": "已附对应整页图。",
                        "guidance": {"matched": True, "reply_mode": "rule_explanation", "evidence_level": "hard_rule"},
                        "visual_evidence": {
                            "evidence_status": "agent_ready",
                            "needs_human_review": False,
                            "page_images": [str(Path(tmpdir) / "page.png")],
                            "crop_images": [],
                            "debug_crop_image_count": 2,
                            "source_refs": [{"source_title": "岩板", "source_page": 5}],
                        },
                        "rule_sources": ["设计师追加规则 线上版 2026-05-13"],
                        "current_standard_usage": {"status": "仅使用新版"},
                    }
                ],
            }

            html = MODULE.render_html(model, html_path=html_path)

        self.assertIn("企业 Agent 验证包", html)
        self.assertIn("page-first", html)
        self.assertIn("对应整页图", html)
        self.assertIn("调试裁剪图", html)
        self.assertIn("仅 JSON 保留", html)
        self.assertIn("回答状态", html)
        self.assertIn("当前标准", html)
        self.assertNotIn("证据等级", html)
        self.assertNotIn("回复模式", html)
        self.assertNotIn("旧版兜底", html)
        self.assertNotIn("PREVIOUS_ACTIVE", html)
        self.assertNotIn("规则咨询入口", html)
        self.assertNotIn("Signature=", html)
        self.assertNotIn("access_token", html)


if __name__ == "__main__":
    unittest.main()
