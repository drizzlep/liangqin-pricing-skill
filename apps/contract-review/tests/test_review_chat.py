import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
CLI_ROOT = APP_ROOT / "cli"
for root in (CORE_ROOT, CLI_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

MODULE_PATH = CLI_ROOT / "review_chat.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


REVIEW_CHAT = load_module("contract_review_review_chat_cli", MODULE_PATH)


def write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    document_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>',
    ]
    for paragraph in paragraphs:
        document_xml.append(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>")
    document_xml.append("</w:body></w:document>")
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "".join(document_xml))


class ReviewChatTests(unittest.TestCase):
    def test_parse_child_bed_confirmation_fields_supports_guardrail_style(self) -> None:
        fields = REVIEW_CHAT._parse_child_bed_confirmation_fields("这单做篱笆围栏")

        self.assertEqual(fields["guardrail_style"], "篱笆围栏")

    def test_parse_child_bed_confirmation_fields_supports_guardrail_length(self) -> None:
        fields = REVIEW_CHAT._parse_child_bed_confirmation_fields("围栏总长 1200mm")

        self.assertEqual(fields["guardrail_length"], "1200mm")

    def test_parse_child_bed_confirmation_fields_supports_guardrail_height_from_prompt_context(self) -> None:
        fields = REVIEW_CHAT._parse_child_bed_confirmation_fields(
            "350mm",
            prompt_question="这个围栏我还需要确认高度，请问围栏高度大概多少？",
        )

        self.assertEqual(fields["guardrail_height"], "350mm")

    def test_parse_child_bed_confirmation_fields_supports_stair_width_band_from_prompt_context(self) -> None:
        fields = REVIEW_CHAT._parse_child_bed_confirmation_fields(
            "500-600mm",
            prompt_question="这个梯柜我还需要确认踏步宽度，请问大概是 450-500mm，还是 500-600mm 这一档？",
        )

        self.assertEqual(fields["stair_width"], "520mm")

    def test_parse_child_bed_confirmation_fields_supports_stair_depth_from_prompt_context(self) -> None:
        fields = REVIEW_CHAT._parse_child_bed_confirmation_fields(
            "500mm",
            prompt_question="这个梯柜我还需要确认进深，请问大概做多深？",
        )

        self.assertEqual(fields["stair_depth"], "500mm")

    def test_parse_child_bed_confirmation_fields_supports_access_height_from_prompt_context(self) -> None:
        fields = REVIEW_CHAT._parse_child_bed_confirmation_fields(
            "1180mm",
            prompt_question="这个梯子我还需要确认垂直高度，请问上下床间距或实际垂直高度大概多少？",
        )

        self.assertEqual(fields["access_height"], "1180mm")

    def test_render_review_reply_uses_review_hint_label_for_release_with_advice(self) -> None:
        reply_text, next_question = REVIEW_CHAT._render_review_reply(
            {
                "review_card": {
                    "verdict": "recommended_release",
                    "priority": "normal",
                    "contract_total": "34523元",
                    "pricing_total": "34524元",
                    "best_match_target": "contract_total",
                    "next_actions": ["本单更像床体+床下组合柜路线，请优先复核床下柜体配置。"],
                },
                "issues": [],
                "review_analysis": {},
            }
        )

        self.assertEqual(next_question, "")
        self.assertIn("复核提示：", reply_text)
        self.assertNotIn("请人工核对：", reply_text)

    def test_render_review_reply_prefers_pricing_compare_diff_over_issue_delta(self) -> None:
        reply_text, next_question = REVIEW_CHAT._render_review_reply(
            {
                "review_card": {
                    "verdict": "manual_review_required",
                    "priority": "p0",
                    "contract_total": "49700元",
                    "pricing_total": "54109元",
                    "best_match_target": "list_price_total",
                    "next_actions": ["请优先核对柜类路线。"],
                },
                "pricing_compare": {
                    "best_match_diff": "1790元",
                },
                "issues": [
                    {
                        "delta_value": "3.05元",
                        "suspected_causes": ["合同折扣计算不自洽。"],
                    }
                ],
                "review_analysis": {},
            }
        )

        self.assertEqual(next_question, "")
        self.assertIn("差额：1790元", reply_text)
        self.assertNotIn("差额：3.05元", reply_text)

    def test_render_review_reply_lists_multi_product_breakdown(self) -> None:
        reply_text, next_question = REVIEW_CHAT._render_review_reply(
            {
                "review_card": {
                    "verdict": "manual_review_required",
                    "priority": "p0",
                    "contract_total": "49700元",
                    "pricing_total": "54109元",
                    "best_match_target": "list_price_total",
                    "next_actions": ["请优先核对 其他衣柜 是否应改走更具体柜型或组合拆分。"],
                },
                "pricing_compare": {
                    "best_match_diff": "1790元",
                    "aggregation_scope": "multi_product_split_sum",
                    "included_items": [
                        {
                            "product_name": "经典箱体床",
                            "product_code": "20260333003002",
                            "line_total": "8800元",
                            "pricing_total": "8528元",
                            "pricing_route": "bed_standard",
                        },
                        {
                            "product_name": "其他衣柜",
                            "product_code": "20260333003003",
                            "line_total": "36140元",
                            "pricing_total": "37812元",
                            "pricing_route": "cabinet_projection_area_fallback",
                            "fallback_strategy": "generic_cabinet_projection_profile",
                            "fallback_detail": {
                                "profile_key": "衣柜",
                                "candidate_quote_diff": "1672元",
                            },
                        },
                    ],
                },
                "issues": [],
                "review_analysis": {},
            }
        )

        self.assertEqual(next_question, "")
        self.assertIn("单项对比：", reply_text)
        self.assertIn("1. 经典箱体床（20260333003002）：合同 8800元 -> 报价 8528元，差额 272元", reply_text)
        self.assertIn("2. 其他衣柜（20260333003003）：合同 36140元 -> 报价 37812元，差额 1672元", reply_text)
        self.assertIn("路线：通用衣柜投影面积估算", reply_text)

    def test_render_review_reply_lists_unpriced_multi_product_items(self) -> None:
        reply_text, next_question = REVIEW_CHAT._render_review_reply(
            {
                "review_card": {
                    "verdict": "manual_review_required",
                    "priority": "p1",
                    "contract_total": "34142元",
                    "pricing_total": "未回放",
                    "next_actions": ["请先人工确认 其他衣柜 的详情首页和连续图纸页是否切对。"],
                },
                "pricing_compare": {
                    "aggregation_scope": "multi_product_split_sum",
                    "excluded_items": [
                        {
                            "product_name": "其他衣柜",
                            "product_code": "20260391004005",
                            "line_total": "34142元",
                            "reason": "pricing_total_missing",
                            "follow_up_question": "请先人工确认 其他衣柜 的详情首页和连续图纸页是否切对，再继续金额核对。",
                        }
                    ],
                },
                "issues": [],
                "review_analysis": {},
            }
        )

        self.assertEqual(next_question, "")
        self.assertIn("待确认品项：", reply_text)
        self.assertIn("1. 其他衣柜（20260391004005）：合同 34142元，当前未形成报价金额", reply_text)
        self.assertIn("详情首页和连续图纸页是否切对", reply_text)

    def test_render_review_reply_prefers_reviewer_card(self) -> None:
        reply_text, next_question = REVIEW_CHAT._render_review_reply(
            {
                "reviewer_card": {
                    "decision_label": "必须人工确认",
                    "primary_reason": "存在1个品项未入账，不能判断整单金额是否正确。",
                    "amounts": {
                        "contract_amount": "50660元",
                        "pricing_amount": "36940元",
                        "difference": "13720元",
                        "comparison_basis_label": "折后合计",
                    },
                    "line_items": [
                        {
                            "product_name": "衣柜组合",
                            "contract_amount": "14760元",
                            "pricing_amount": "",
                            "difference": "",
                            "review_status_label": "必须人工确认",
                            "manual_hint": "该品项未形成报价，请人工确认。",
                        }
                    ],
                    "next_actions": ["优先确认衣柜组合应走哪个报价路线。"],
                },
                "review_card": {
                    "verdict": "manual_review_required",
                    "priority": "p0",
                    "contract_total": "",
                    "pricing_total": "36940元",
                    "next_actions": ["旧技术提示"],
                },
                "issues": [],
                "review_analysis": {},
            }
        )

        self.assertEqual(next_question, "")
        self.assertIn("审核结论：必须人工确认", reply_text)
        self.assertIn("主要原因：存在1个品项未入账", reply_text)
        self.assertIn("衣柜组合", reply_text)
        self.assertNotIn("是否建议放行", reply_text)
        self.assertNotIn("旧技术提示", reply_text)

    def test_chat_returns_single_follow_up_question_when_required_field_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：床",
                    "本单按成品执行",
                    "长度：2000mm",
                    "材质：北美白蜡木",
                    "费用合计：8200元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )

        self.assertEqual(payload["handled_by"], "contract_review_chat")
        self.assertEqual(payload["review_card"]["priority"], "p1")
        self.assertIn("宽度", payload["reply_text"])
        self.assertEqual(payload["next_question"], "请先核对这份合同的宽度（width）。")

    def test_chat_can_mark_last_job_as_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )
            payload = REVIEW_CHAT.run(
                [
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--text",
                    "标记已核对",
                    "--output-mode",
                    "json",
                ]
            )

            feedback_path = root / "runtime" / "jobs" / "batch-chat-001" / "output" / "review-feedback.json"
            self.assertTrue(feedback_path.exists())
            saved = json.loads(feedback_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["action"], "marked_reviewed")
        self.assertEqual(saved["human_decision"], "reviewed")

    def test_chat_mark_reviewed_can_capture_root_cause_and_corrected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )
            payload = REVIEW_CHAT.run(
                [
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--text",
                    "标记已核对 结论=确认问题 原因=template_alias_missing 字段=product_category:书柜,width:1500mm",
                    "--output-mode",
                    "json",
                ]
            )

            feedback_path = root / "runtime" / "jobs" / "batch-chat-001" / "output" / "review-feedback.json"
            self.assertTrue(feedback_path.exists())
            saved = json.loads(feedback_path.read_text(encoding="utf-8"))
            template_files = list((root / "runtime" / "templates").glob("*.json"))
            self.assertEqual(len(template_files), 1)
            template_profile = json.loads(template_files[0].read_text(encoding="utf-8"))

        self.assertEqual(payload["action"], "marked_reviewed")
        self.assertEqual(saved["human_decision"], "confirmed")
        self.assertEqual(saved["confirmed_root_cause"], "template_alias_missing")
        self.assertEqual(saved["corrected_fields"]["product_category"], "书柜")
        self.assertEqual(saved["corrected_fields"]["width"], "1500mm")
        self.assertEqual(saved["template_profile_update"]["learned_field_names"], ["product_category", "width"])
        self.assertIn("template_alias_missing", payload["reply_text"])
        self.assertEqual(template_profile["human_decision_breakdown"]["confirmed"], 1)
        self.assertIn("1500mm", template_profile["field_aliases"]["width"]["confirmed_values"])

    def test_chat_can_execute_template_quick_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "batch-chat"
            raw_dir = batch_dir / "raw" / "case-001"
            raw_dir.mkdir(parents=True)
            write_minimal_docx(
                raw_dir / "合同.docx",
                [
                    "产品名称：书柜",
                    "长度：2400mm",
                    "进深：350mm",
                    "高度：2100mm",
                    "材质：北美黑胡桃木",
                    "费用合计：19800元",
                ],
            )
            (batch_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "source_batch_id": "batch-chat",
                        "requested_actions": ["audit", "replay"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            REVIEW_CHAT.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--ocr-backend",
                    "disabled",
                    "--text",
                    "审这份合同",
                    "--output-mode",
                    "json",
                ]
            )
            dashboard = json.loads(
                (root / "runtime" / "batches" / "batch-chat" / "batch-dashboard.json").read_text(encoding="utf-8")
            )
            action_id = dashboard["template_learning_top_templates"][0]["quick_actions"][0]["action_id"]
            payload = REVIEW_CHAT.run(
                [
                    "--runtime-root",
                    str(root / "runtime"),
                    "--state-root",
                    str(root / "state"),
                    "--text",
                    f"执行模板快捷动作 {action_id}",
                    "--output-mode",
                    "json",
                ]
            )
            feedback_path = root / "runtime" / "jobs" / "batch-chat-001" / "output" / "review-feedback.json"
            saved = json.loads(feedback_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["action"], "executed_template_quick_action")
        self.assertEqual(payload["quick_action"]["action_id"], action_id)
        self.assertEqual(saved["job_id"], "batch-chat-001")
        self.assertIn("已执行模板快捷动作", payload["reply_text"])

    def test_chat_can_apply_child_bed_confirmation_and_rerun_last_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_root = root / "runtime"
            state_root = root / "state"
            job_id = "batch-chat-001"
            batch_id = "batch-chat"
            contract_path = root / "合同.docx"
            write_minimal_docx(contract_path, ["甲方：客户A", "费用合计：138825元"])

            (state_root / "contract-review-chat-state.json").parent.mkdir(parents=True, exist_ok=True)
            (state_root / "contract-review-chat-state.json").write_text(
                json.dumps(
                    {
                        "queue_job_ids": [job_id],
                        "cursor": 0,
                        "last_job_id": job_id,
                        "last_batch_id": batch_id,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            job_dir = runtime_root / "jobs" / job_id
            (job_dir / "output").mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "group_key": "20260391004",
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "requested_actions": ["audit", "replay"],
                        "assets": [
                            {
                                "asset_id": "asset-001",
                                "source_path": str(contract_path),
                                "relative_path": "raw/case-001/合同.docx",
                                "file_name": "合同.docx",
                                "extension": ".docx",
                                "media_kind": "document",
                                "role_hint": "primary_contract",
                                "text_preview": "合同内容",
                                "text_extract_method": "docx_text_layer",
                                "metadata": {},
                            }
                        ],
                        "metadata": {},
                        "created_at": "2026-04-18T08:00:00+08:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (job_dir / "output" / "review.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "review_card": {
                            "verdict": "manual_review_required",
                            "priority": "p0",
                            "contract_total": "138825元",
                            "pricing_total": "125582元",
                            "best_match_target": "contract_total",
                            "next_actions": [
                                "请人工确认：这是不是梯柜上下床儿童床，下层结构是否为箱体床？若是，再补充围栏样式、梯柜参数和上下床尺寸。"
                            ],
                        },
                        "review_analysis": {
                            "issue_codes": ["quote_conflict", "ocr_low_confidence"],
                            "next_question": "请人工确认：这是不是梯柜上下床儿童床，下层结构是否为箱体床？若是，再补充围栏样式、梯柜参数和上下床尺寸。",
                        },
                        "pricing_compare": {
                            "excluded_items": [
                                {
                                    "product_name": "其他儿童床",
                                    "product_code": "20260391004004",
                                    "follow_up_question": "请人工确认：这是不是梯柜上下床儿童床，下层结构是否为箱体床？若是，再补充围栏样式、梯柜参数和上下床尺寸。",
                                }
                            ]
                        },
                        "product_split": {
                            "items": [
                                {
                                    "product_name": "其他儿童床",
                                    "product_code": "20260391004004",
                                    "normalized_fields": {
                                        "fields": {
                                            "length": {"value": "1380mm"},
                                            "width": {"value": "2568mm"},
                                            "height": {"value": "1885mm"},
                                        }
                                    },
                                }
                            ]
                        },
                        "issues": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            batch_output_dir = runtime_root / "batches" / batch_id
            batch_output_dir.mkdir(parents=True, exist_ok=True)
            (batch_output_dir / "batch-summary.json").write_text(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "requested_actions": ["audit", "replay"],
                        "job_count": 1,
                        "warnings": [],
                        "jobs": [
                            {
                                "job_id": job_id,
                                "group_key": "20260391004",
                                "status": "manual_review_required",
                                "finding_count": 0,
                                "blocking_finding_count": 0,
                                "primary_contract_count": 1,
                                "review_priority": "p0",
                                "review_priority_score": 0,
                                "review_priority_reason": "",
                                "automation_state": "ingest_scaffold_ready",
                                "actionable_priority": "need_user_input",
                                "actionable_priority_score": 1,
                                "risk_flags": [],
                                "product_split_item_count": 6,
                                "conflict_count": 0,
                                "conflict_fields": [],
                                "manual_review_reasons": [],
                                "issue_codes": ["quote_conflict", "ocr_low_confidence"],
                                "issue_count": 2,
                                "contract_total": "138825元",
                                "list_price_total": "146132元",
                                "discounted_total": "138825元",
                                "discount_rate": "95折",
                                "pricing_total": "125582元",
                                "pricing_compare_status": "mismatch_contract_total",
                                "pricing_compare_match_band": "mismatch",
                                "pricing_compare_best_match_target": "contract_total",
                                "pricing_compare_best_match_diff": "13243元",
                                "pricing_route": "multi_product_aggregate",
                                "template_id": "tpl-test",
                                "template_fingerprint": "fp-test",
                                "review_path": str(job_dir / "output" / "review.md"),
                                "job_dir": str(job_dir),
                            }
                        ],
                        "manifest": {
                            "source_type": "manual_batch",
                            "source_channel": "manual",
                            "requested_actions": ["audit", "replay"],
                        },
                        "created_at": "2026-04-18T08:00:00+08:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            captured: dict[str, object] = {}
            original_run_review_job = REVIEW_CHAT.run_review_job

            def fake_run_review_job(job, *, job_dir, extraction_config=None, ocr_extractor=None):
                captured["metadata"] = json.loads(json.dumps(job.metadata, ensure_ascii=False))
                (job_dir / "output").mkdir(parents=True, exist_ok=True)
                (job_dir / "output" / "review.json").write_text(
                    json.dumps(
                        {
                            "job_id": job.job_id,
                            "batch_id": job.batch_id,
                            "review_card": {
                                "verdict": "manual_review_required",
                                "priority": "p1",
                                "contract_total": "138825元",
                                "pricing_total": "132900元",
                                "best_match_target": "contract_total",
                                "next_actions": ["已按人工确认回填儿童床路线，并完成重新核价。"],
                            },
                            "review_analysis": {"issue_codes": ["quote_conflict"], "next_question": ""},
                            "issues": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                return {
                    "job_id": job.job_id,
                    "group_key": "20260391004",
                    "status": "manual_review_required",
                    "finding_count": 0,
                    "blocking_finding_count": 0,
                    "primary_contract_count": 1,
                    "review_priority": "p1",
                    "review_priority_score": 1,
                    "review_priority_reason": "",
                    "automation_state": "ingest_scaffold_ready",
                    "actionable_priority": "ready_now",
                    "actionable_priority_score": 0,
                    "risk_flags": [],
                    "product_split_item_count": 6,
                    "conflict_count": 0,
                    "conflict_fields": [],
                    "manual_review_reasons": [],
                    "issue_codes": ["quote_conflict"],
                    "issue_count": 1,
                    "contract_total": "138825元",
                    "list_price_total": "146132元",
                    "discounted_total": "138825元",
                    "discount_rate": "95折",
                    "pricing_total": "132900元",
                    "pricing_compare_status": "mismatch_contract_total",
                    "pricing_compare_match_band": "mismatch",
                    "pricing_compare_best_match_target": "contract_total",
                    "pricing_compare_best_match_diff": "5925元",
                    "pricing_route": "multi_product_aggregate",
                    "template_id": "tpl-test",
                    "template_fingerprint": "fp-test",
                    "review_path": str(job_dir / "output" / "review.md"),
                    "job_dir": str(job_dir),
                }

            REVIEW_CHAT.run_review_job = fake_run_review_job
            try:
                payload = REVIEW_CHAT.run(
                    [
                        "--runtime-root",
                        str(runtime_root),
                        "--state-root",
                        str(state_root),
                        "--ocr-backend",
                        "disabled",
                        "--text",
                        "04004 是梯柜上下床，箱体床",
                        "--output-mode",
                        "json",
                    ]
                )
            finally:
                REVIEW_CHAT.run_review_job = original_run_review_job

        self.assertEqual(payload["action"], "applied_human_confirmation")
        self.assertEqual(payload["confirmed_fields"]["access_style"], "梯柜")
        self.assertEqual(payload["confirmed_fields"]["bed_form"], "上下床")
        self.assertEqual(payload["confirmed_fields"]["lower_bed_type"], "箱体床")
        self.assertEqual(payload["confirmed_fields"]["length"], "1380mm")
        self.assertEqual(payload["confirmed_fields"]["width"], "2568mm")
        override_payload = next(iter((captured["metadata"]["manual_split_field_overrides"]).values()))
        self.assertEqual(override_payload["confirmed_route"], "modular_child_bed")
        self.assertEqual(override_payload["field_values"]["access_style"], "梯柜")
        self.assertIn("已按人工确认回填", payload["reply_text"])

    def test_chat_can_apply_guardrail_length_confirmation_after_route_is_already_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_root = root / "runtime"
            state_root = root / "state"
            job_id = "batch-chat-001"
            batch_id = "batch-chat"
            contract_path = root / "合同.docx"
            write_minimal_docx(contract_path, ["甲方：客户A", "费用合计：138825元"])

            (state_root / "contract-review-chat-state.json").parent.mkdir(parents=True, exist_ok=True)
            (state_root / "contract-review-chat-state.json").write_text(
                json.dumps(
                    {
                        "queue_job_ids": [job_id],
                        "cursor": 0,
                        "last_job_id": job_id,
                        "last_batch_id": batch_id,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            job_dir = runtime_root / "jobs" / job_id
            (job_dir / "output").mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "group_key": "20260391004",
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "requested_actions": ["audit", "replay"],
                        "assets": [
                            {
                                "asset_id": "asset-001",
                                "source_path": str(contract_path),
                                "relative_path": "raw/case-001/合同.docx",
                                "file_name": "合同.docx",
                                "extension": ".docx",
                                "media_kind": "document",
                                "role_hint": "primary_contract",
                                "text_preview": "合同内容",
                                "text_extract_method": "docx_text_layer",
                                "metadata": {},
                            }
                        ],
                        "metadata": {
                            "manual_split_field_overrides": {
                                "20260391004004": {
                                    "confirmed": True,
                                    "confirmed_route": "modular_child_bed",
                                    "field_values": {
                                        "length": "1380mm",
                                        "width": "2568mm",
                                        "height": "1885mm",
                                        "access_style": "梯柜",
                                        "bed_form": "上下床",
                                        "lower_bed_type": "箱体床",
                                        "guardrail_style": "篱笆围栏",
                                    },
                                }
                            }
                        },
                        "created_at": "2026-04-18T08:00:00+08:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (job_dir / "output" / "review.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "review_card": {
                            "verdict": "manual_review_required",
                            "priority": "p0",
                            "contract_total": "138825元",
                            "pricing_total": "125582元",
                            "best_match_target": "contract_total",
                            "next_actions": ["这个围栏我还需要确认长度，请问围栏总长度大概多少？"],
                        },
                        "review_analysis": {
                            "issue_codes": ["quote_conflict", "missing_required_field"],
                            "next_question": "这个围栏我还需要确认长度，请问围栏总长度大概多少？",
                        },
                        "pricing_compare": {
                            "excluded_items": [
                                {
                                    "product_name": "其他儿童床",
                                    "product_code": "20260391004004",
                                    "follow_up_question": "这个围栏我还需要确认长度，请问围栏总长度大概多少？",
                                }
                            ]
                        },
                        "product_split": {
                            "items": [
                                {
                                    "product_name": "其他儿童床",
                                    "product_code": "20260391004004",
                                    "normalized_fields": {
                                        "route_evidence": {
                                            "recommended_route": "modular_child_bed",
                                            "candidates": [{"route": "modular_child_bed"}],
                                        },
                                        "fields": {
                                            "length": {"value": "1380mm"},
                                            "width": {"value": "2568mm"},
                                            "height": {"value": "1885mm"},
                                        },
                                    },
                                }
                            ]
                        },
                        "issues": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            batch_output_dir = runtime_root / "batches" / batch_id
            batch_output_dir.mkdir(parents=True, exist_ok=True)
            (batch_output_dir / "batch-summary.json").write_text(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "requested_actions": ["audit", "replay"],
                        "job_count": 1,
                        "warnings": [],
                        "jobs": [
                            {
                                "job_id": job_id,
                                "group_key": "20260391004",
                                "status": "manual_review_required",
                                "finding_count": 0,
                                "blocking_finding_count": 0,
                                "primary_contract_count": 1,
                                "review_priority": "p0",
                                "review_priority_score": 0,
                                "review_priority_reason": "",
                                "automation_state": "ingest_scaffold_ready",
                                "actionable_priority": "need_user_input",
                                "actionable_priority_score": 1,
                                "risk_flags": [],
                                "product_split_item_count": 6,
                                "conflict_count": 0,
                                "conflict_fields": [],
                                "manual_review_reasons": [],
                                "issue_codes": ["quote_conflict", "missing_required_field"],
                                "issue_count": 2,
                                "contract_total": "138825元",
                                "list_price_total": "146132元",
                                "discounted_total": "138825元",
                                "discount_rate": "95折",
                                "pricing_total": "125582元",
                                "pricing_compare_status": "mismatch_contract_total",
                                "pricing_compare_match_band": "mismatch",
                                "pricing_compare_best_match_target": "contract_total",
                                "pricing_compare_best_match_diff": "13243元",
                                "pricing_route": "multi_product_aggregate",
                                "template_id": "tpl-test",
                                "template_fingerprint": "fp-test",
                                "review_path": str(job_dir / "output" / "review.md"),
                                "job_dir": str(job_dir),
                            }
                        ],
                        "manifest": {
                            "source_type": "manual_batch",
                            "source_channel": "manual",
                            "requested_actions": ["audit", "replay"],
                        },
                        "created_at": "2026-04-18T08:00:00+08:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            captured: dict[str, object] = {}
            original_run_review_job = REVIEW_CHAT.run_review_job

            def fake_run_review_job(job, *, job_dir, extraction_config=None, ocr_extractor=None):
                captured["metadata"] = json.loads(json.dumps(job.metadata, ensure_ascii=False))
                (job_dir / "output").mkdir(parents=True, exist_ok=True)
                (job_dir / "output" / "review.json").write_text(
                    json.dumps(
                        {
                            "job_id": job.job_id,
                            "batch_id": job.batch_id,
                            "review_card": {
                                "verdict": "manual_review_required",
                                "priority": "p1",
                                "contract_total": "138825元",
                                "pricing_total": "134100元",
                                "best_match_target": "contract_total",
                                "next_actions": ["已按人工确认回填围栏长度，并完成重新核价。"],
                            },
                            "review_analysis": {"issue_codes": ["quote_conflict"], "next_question": ""},
                            "issues": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                return {
                    "job_id": job.job_id,
                    "group_key": "20260391004",
                    "status": "manual_review_required",
                    "finding_count": 0,
                    "blocking_finding_count": 0,
                    "primary_contract_count": 1,
                    "review_priority": "p1",
                    "review_priority_score": 1,
                    "review_priority_reason": "",
                    "automation_state": "ingest_scaffold_ready",
                    "actionable_priority": "ready_now",
                    "actionable_priority_score": 0,
                    "risk_flags": [],
                    "product_split_item_count": 6,
                    "conflict_count": 0,
                    "conflict_fields": [],
                    "manual_review_reasons": [],
                    "issue_codes": ["quote_conflict"],
                    "issue_count": 1,
                    "contract_total": "138825元",
                    "list_price_total": "146132元",
                    "discounted_total": "138825元",
                    "discount_rate": "95折",
                    "pricing_total": "134100元",
                    "pricing_compare_status": "mismatch_contract_total",
                    "pricing_compare_match_band": "mismatch",
                    "pricing_compare_best_match_target": "contract_total",
                    "pricing_compare_best_match_diff": "4725元",
                    "pricing_route": "multi_product_aggregate",
                    "template_id": "tpl-test",
                    "template_fingerprint": "fp-test",
                    "review_path": str(job_dir / "output" / "review.md"),
                    "job_dir": str(job_dir),
                }

            REVIEW_CHAT.run_review_job = fake_run_review_job
            try:
                payload = REVIEW_CHAT.run(
                    [
                        "--runtime-root",
                        str(runtime_root),
                        "--state-root",
                        str(state_root),
                        "--ocr-backend",
                        "disabled",
                        "--text",
                        "围栏总长 1200mm",
                        "--output-mode",
                        "json",
                    ]
                )
            finally:
                REVIEW_CHAT.run_review_job = original_run_review_job

        self.assertEqual(payload["action"], "applied_human_confirmation")
        self.assertEqual(payload["confirmed_fields"]["guardrail_length"], "1200mm")
        override_payload = next(iter((captured["metadata"]["manual_split_field_overrides"]).values()))
        self.assertEqual(override_payload["field_values"]["guardrail_length"], "1200mm")
        self.assertIn("已按人工确认回填", payload["reply_text"])

    def test_chat_can_apply_stair_width_band_confirmation_after_route_is_already_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_root = root / "runtime"
            state_root = root / "state"
            job_id = "batch-chat-001"
            batch_id = "batch-chat"
            contract_path = root / "合同.docx"
            write_minimal_docx(contract_path, ["甲方：客户A", "费用合计：138825元"])

            (state_root / "contract-review-chat-state.json").parent.mkdir(parents=True, exist_ok=True)
            (state_root / "contract-review-chat-state.json").write_text(
                json.dumps(
                    {
                        "queue_job_ids": [job_id],
                        "cursor": 0,
                        "last_job_id": job_id,
                        "last_batch_id": batch_id,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            job_dir = runtime_root / "jobs" / job_id
            (job_dir / "output").mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "group_key": "20260391004",
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "requested_actions": ["audit", "replay"],
                        "assets": [
                            {
                                "asset_id": "asset-001",
                                "source_path": str(contract_path),
                                "relative_path": "raw/case-001/合同.docx",
                                "file_name": "合同.docx",
                                "extension": ".docx",
                                "media_kind": "document",
                                "role_hint": "primary_contract",
                                "text_preview": "合同内容",
                                "text_extract_method": "docx_text_layer",
                                "metadata": {},
                            }
                        ],
                        "metadata": {
                            "manual_split_field_overrides": {
                                "20260391004004": {
                                    "confirmed": True,
                                    "confirmed_route": "modular_child_bed",
                                    "field_values": {
                                        "length": "1380mm",
                                        "width": "2568mm",
                                        "height": "1885mm",
                                        "access_style": "梯柜",
                                        "bed_form": "上下床",
                                        "lower_bed_type": "箱体床",
                                        "guardrail_style": "篱笆围栏",
                                        "guardrail_length": "1200mm",
                                        "guardrail_height": "350mm",
                                    },
                                }
                            }
                        },
                        "created_at": "2026-04-18T08:00:00+08:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (job_dir / "output" / "review.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "batch_id": batch_id,
                        "review_card": {
                            "verdict": "manual_review_required",
                            "priority": "p0",
                            "contract_total": "138825元",
                            "pricing_total": "125582元",
                            "best_match_target": "contract_total",
                            "next_actions": ["这个梯柜我还需要确认踏步宽度，请问大概是 450-500mm，还是 500-600mm 这一档？"],
                        },
                        "review_analysis": {
                            "issue_codes": ["quote_conflict", "missing_required_field"],
                            "next_question": "这个梯柜我还需要确认踏步宽度，请问大概是 450-500mm，还是 500-600mm 这一档？",
                        },
                        "pricing_compare": {
                            "excluded_items": [
                                {
                                    "product_name": "其他儿童床",
                                    "product_code": "20260391004004",
                                    "follow_up_question": "这个梯柜我还需要确认踏步宽度，请问大概是 450-500mm，还是 500-600mm 这一档？",
                                }
                            ]
                        },
                        "product_split": {
                            "items": [
                                {
                                    "product_name": "其他儿童床",
                                    "product_code": "20260391004004",
                                    "normalized_fields": {
                                        "route_evidence": {
                                            "recommended_route": "modular_child_bed",
                                            "candidates": [{"route": "modular_child_bed"}],
                                        },
                                        "fields": {
                                            "length": {"value": "1380mm"},
                                            "width": {"value": "2568mm"},
                                            "height": {"value": "1885mm"},
                                        },
                                    },
                                }
                            ]
                        },
                        "issues": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            batch_output_dir = runtime_root / "batches" / batch_id
            batch_output_dir.mkdir(parents=True, exist_ok=True)
            (batch_output_dir / "batch-summary.json").write_text(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "source_type": "manual_batch",
                        "source_channel": "manual",
                        "requested_actions": ["audit", "replay"],
                        "job_count": 1,
                        "warnings": [],
                        "jobs": [
                            {
                                "job_id": job_id,
                                "group_key": "20260391004",
                                "status": "manual_review_required",
                                "finding_count": 0,
                                "blocking_finding_count": 0,
                                "primary_contract_count": 1,
                                "review_priority": "p0",
                                "review_priority_score": 0,
                                "review_priority_reason": "",
                                "automation_state": "ingest_scaffold_ready",
                                "actionable_priority": "need_user_input",
                                "actionable_priority_score": 1,
                                "risk_flags": [],
                                "product_split_item_count": 6,
                                "conflict_count": 0,
                                "conflict_fields": [],
                                "manual_review_reasons": [],
                                "issue_codes": ["quote_conflict", "missing_required_field"],
                                "issue_count": 2,
                                "contract_total": "138825元",
                                "list_price_total": "146132元",
                                "discounted_total": "138825元",
                                "discount_rate": "95折",
                                "pricing_total": "125582元",
                                "pricing_compare_status": "mismatch_contract_total",
                                "pricing_compare_match_band": "mismatch",
                                "pricing_compare_best_match_target": "contract_total",
                                "pricing_compare_best_match_diff": "13243元",
                                "pricing_route": "multi_product_aggregate",
                                "template_id": "tpl-test",
                                "template_fingerprint": "fp-test",
                                "review_path": str(job_dir / "output" / "review.md"),
                                "job_dir": str(job_dir),
                            }
                        ],
                        "manifest": {
                            "source_type": "manual_batch",
                            "source_channel": "manual",
                            "requested_actions": ["audit", "replay"],
                        },
                        "created_at": "2026-04-18T08:00:00+08:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            captured: dict[str, object] = {}
            original_run_review_job = REVIEW_CHAT.run_review_job

            def fake_run_review_job(job, *, job_dir, extraction_config=None, ocr_extractor=None):
                captured["metadata"] = json.loads(json.dumps(job.metadata, ensure_ascii=False))
                (job_dir / "output").mkdir(parents=True, exist_ok=True)
                (job_dir / "output" / "review.json").write_text(
                    json.dumps(
                        {
                            "job_id": job.job_id,
                            "batch_id": job.batch_id,
                            "review_card": {
                                "verdict": "manual_review_required",
                                "priority": "p1",
                                "contract_total": "138825元",
                                "pricing_total": "130800元",
                                "best_match_target": "contract_total",
                                "next_actions": ["已按人工确认回填梯柜踏步宽度，并完成重新核价。"],
                            },
                            "review_analysis": {"issue_codes": ["quote_conflict"], "next_question": ""},
                            "issues": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                return {
                    "job_id": job.job_id,
                    "group_key": "20260391004",
                    "status": "manual_review_required",
                    "finding_count": 0,
                    "blocking_finding_count": 0,
                    "primary_contract_count": 1,
                    "review_priority": "p1",
                    "review_priority_score": 1,
                    "review_priority_reason": "",
                    "automation_state": "ingest_scaffold_ready",
                    "actionable_priority": "ready_now",
                    "actionable_priority_score": 0,
                    "risk_flags": [],
                    "product_split_item_count": 6,
                    "conflict_count": 0,
                    "conflict_fields": [],
                    "manual_review_reasons": [],
                    "issue_codes": ["quote_conflict"],
                    "issue_count": 1,
                    "contract_total": "138825元",
                    "list_price_total": "146132元",
                    "discounted_total": "138825元",
                    "discount_rate": "95折",
                    "pricing_total": "130800元",
                    "pricing_compare_status": "mismatch_contract_total",
                    "pricing_compare_match_band": "mismatch",
                    "pricing_compare_best_match_target": "contract_total",
                    "pricing_compare_best_match_diff": "8025元",
                    "pricing_route": "multi_product_aggregate",
                    "template_id": "tpl-test",
                    "template_fingerprint": "fp-test",
                    "review_path": str(job_dir / "output" / "review.md"),
                    "job_dir": str(job_dir),
                }

            REVIEW_CHAT.run_review_job = fake_run_review_job
            try:
                payload = REVIEW_CHAT.run(
                    [
                        "--runtime-root",
                        str(runtime_root),
                        "--state-root",
                        str(state_root),
                        "--ocr-backend",
                        "disabled",
                        "--text",
                        "500-600mm",
                        "--output-mode",
                        "json",
                    ]
                )
            finally:
                REVIEW_CHAT.run_review_job = original_run_review_job

        self.assertEqual(payload["action"], "applied_human_confirmation")
        self.assertEqual(payload["confirmed_fields"]["stair_width"], "520mm")
        override_payload = next(iter((captured["metadata"]["manual_split_field_overrides"]).values()))
        self.assertEqual(override_payload["field_values"]["stair_width"], "520mm")
        self.assertIn("已按人工确认回填", payload["reply_text"])


if __name__ == "__main__":
    unittest.main()
