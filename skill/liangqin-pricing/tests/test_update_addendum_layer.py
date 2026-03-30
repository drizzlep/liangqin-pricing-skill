import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_addendum_layer.py"
SPEC = importlib.util.spec_from_file_location("update_addendum_layer", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class UpdateAddendumLayerTests(unittest.TestCase):
    def test_designer_manual_runtime_overrides_drop_round1_noise_rules(self) -> None:
        reports_dir = (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "addenda"
            / "designer-manual-2026-03-22"
        )
        runtime_overrides = json.loads((reports_dir / "runtime-rules-overrides.json").read_text(encoding="utf-8"))
        knowledge_overrides = json.loads((reports_dir / "knowledge-layer-overrides.json").read_text(encoding="utf-8"))

        runtime_titles = {rule.get("title") for rule in runtime_overrides.get("replace_rules", []) if isinstance(rule, dict)}
        knowledge_topics = {
            entry.get("topic")
            for entry in knowledge_overrides.get("replace_entries", [])
            if isinstance(entry, dict)
        }

        self.assertNotIn("可推弹开启、扣手开启、拉手", runtime_titles)
        self.assertNotIn(
            "尾翻箱体床限位器安装于床头方向， 尾翻床床垫宽度＜1500mm时安装1个，床垫宽度≥1500mm时 安装2个",
            runtime_titles,
        )
        self.assertIn("箱体床床垫限位器规格与安装方向提示", knowledge_topics)

    def test_designer_manual_runtime_overrides_drop_round2_ocr_noise_rules(self) -> None:
        reports_dir = (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "addenda"
            / "designer-manual-2026-03-22"
        )
        runtime_overrides = json.loads((reports_dir / "runtime-rules-overrides.json").read_text(encoding="utf-8"))
        runtime_titles = {rule.get("title") for rule in runtime_overrides.get("replace_rules", []) if isinstance(rule, dict)}

        self.assertNotIn(
            "165°铰链开启 默认铰链开启柜体离床铺很近，柜门单开一侧衣服拿取不太方便",
            runtime_titles,
        )
        self.assertNotIn(
            "7 OE NT AE BX TORI IS NIRS, Mls ELON TSE. DEAS CCT LC CEES I RS LS PSS SE NEVO NOT SRN",
            runtime_titles,
        )

    def test_apply_coverage_ledger_overrides_updates_entries_and_appends_entries(self) -> None:
        payload = {
            "entries": [
                {"page": 10, "topic": "A", "status": "unresolved"},
                {"page": 11, "topic": "B 安装说明", "status": "unresolved"},
            ]
        }
        overrides = {
            "overrides": [
                {"page": 10, "status": "excluded_background", "note": "背景页"},
                {"page": 11, "topic_contains": "安装说明", "status": "knowledge_ready", "note": "知识层"},
            ],
            "append_entries": [
                {"page": 12, "topic": "C", "status": "covered_existing", "note": "已覆盖"}
            ],
        }

        merged = MODULE.apply_coverage_ledger_overrides(payload, overrides)

        self.assertEqual(merged["entry_count"], 3)
        self.assertEqual(merged["entries"][0]["status"], "excluded_background")
        self.assertEqual(merged["entries"][0]["note"], "背景页")
        self.assertEqual(merged["entries"][1]["status"], "knowledge_ready")
        self.assertEqual(merged["entries"][1]["note"], "知识层")
        self.assertEqual(merged["entries"][2]["status"], "covered_existing")
        self.assertEqual(merged["status_counts"]["covered_existing"], 1)
        self.assertEqual(merged["status_counts"]["excluded_background"], 1)
        self.assertEqual(merged["status_counts"]["knowledge_ready"], 1)

    def test_apply_coverage_ledger_overrides_can_match_same_topic_by_summary_contains(self) -> None:
        payload = {
            "entries": [
                {"page": 20, "topic": "订制款：", "summary": "1400*1400*780；桌面直径≤1400mm", "status": "unresolved"},
                {"page": 20, "topic": "订制款：", "summary": "1600*700*780；桌长≥1400mm时", "status": "unresolved"},
            ]
        }
        overrides = {
            "overrides": [
                {
                    "page": 20,
                    "topic": "订制款：",
                    "summary_contains": "1400*1400*780",
                    "status": "knowledge_ready",
                    "note": "圆桌上限",
                }
            ]
        }

        merged = MODULE.apply_coverage_ledger_overrides(payload, overrides)

        self.assertEqual(merged["entries"][0]["status"], "knowledge_ready")
        self.assertEqual(merged["entries"][0]["note"], "圆桌上限")
        self.assertEqual(merged["entries"][1]["status"], "unresolved")

    def test_build_seed_coverage_ledger_includes_entry_count_and_status_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            index.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "page": 1,
                                "clean_title": "已入 runtime 的规则",
                                "heading": "已入 runtime 的规则",
                                "pricing_relevant": True,
                                "domain": "cabinet",
                                "normalized_rule": "规则一",
                            },
                            {
                                "page": 2,
                                "clean_title": "待人工复核的规则",
                                "heading": "待人工复核的规则",
                                "pricing_relevant": True,
                                "domain": "cabinet",
                                "normalized_rule": "规则二",
                            },
                            {
                                "page": 3,
                                "clean_title": "背景说明",
                                "heading": "背景说明",
                                "pricing_relevant": False,
                                "domain": "general",
                                "normalized_rule": "规则三",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            runtime_rules.write_text(
                json.dumps({"rules": [{"title": "已入 runtime 的规则"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            payload = MODULE.build_seed_coverage_ledger(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                index_path=index,
                runtime_rules_path=runtime_rules,
            )

        self.assertEqual(payload["entry_count"], 3)
        self.assertEqual(payload["status_counts"]["runtime_hard_rule"], 1)
        self.assertEqual(payload["status_counts"]["unresolved"], 1)
        self.assertEqual(payload["status_counts"]["excluded_background"], 1)

    def test_build_seed_coverage_ledger_prefers_audit_csv_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audit_csv = root / "pdf-coverage-audit.csv"
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            audit_csv.write_text(
                "\n".join(
                    [
                        "status,page,domain,rule_type,relevance_score,pricing_relevant,clean_title,heading,tags,excerpt,normalized_rule,runtime_title,runtime_action,reason",
                        "included_runtime,11,material,formula,9,True,规则A,规则A,尺寸阈值,excerpt-a,summary-a,标题A,constraint,已进入运行时追加规则，action_type=constraint",
                        "excluded_non_pricing,12,general,narrative_rule,2,False,规则B,规则B,待分类,excerpt-b,summary-b,,,背景说明",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            index.write_text('{"entries": []}', encoding="utf-8")
            runtime_rules.write_text('{"rules": []}', encoding="utf-8")

            payload = MODULE.build_seed_coverage_ledger(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                index_path=index,
                runtime_rules_path=runtime_rules,
                audit_csv_path=audit_csv,
            )

        self.assertEqual(payload["entry_count"], 2)
        self.assertEqual(payload["entries"][0]["status"], "runtime_hard_rule")
        self.assertEqual(payload["entries"][0]["note"], "已进入运行时追加规则，action_type=constraint")
        self.assertEqual(payload["entries"][1]["status"], "excluded_background")
        self.assertEqual(payload["entries"][1]["source"], "pdf_coverage_audit")

    def test_finalize_coverage_ledger_assigns_unique_publish_targets(self) -> None:
        payload = {
            "entries": [
                {"page": 10, "topic": "A", "status": "runtime_hard_rule"},
                {"page": 11, "topic": "B", "status": "knowledge_ready"},
                {"page": 12, "topic": "C", "status": "covered_existing"},
                {"page": 13, "topic": "D", "status": "unresolved"},
                {"page": 14, "topic": "E", "status": "manual_review"},
                {"page": 15, "topic": "F", "status": "unknown_status"},
            ]
        }

        finalized = MODULE.finalize_coverage_ledger(payload)

        self.assertEqual(finalized["entries"][0]["publish_target"], "runtime")
        self.assertEqual(finalized["entries"][1]["publish_target"], "knowledge")
        self.assertEqual(finalized["entries"][2]["publish_target"], "none")
        self.assertEqual(finalized["entries"][3]["publish_target"], "manual_review")
        self.assertEqual(finalized["entries"][4]["publish_target"], "manual_review")
        self.assertEqual(finalized["entries"][5]["publish_target"], "manual_review")
        self.assertEqual(finalized["publish_target_counts"]["runtime"], 1)
        self.assertEqual(finalized["publish_target_counts"]["knowledge"], 1)
        self.assertEqual(finalized["publish_target_counts"]["none"], 1)
        self.assertEqual(finalized["publish_target_counts"]["manual_review"], 3)

    def test_build_published_runtime_rules_filters_by_finalized_ledger(self) -> None:
        runtime_payload = {
            "layer_id": "designer-a",
            "layer_name": "设计师追加规则 A",
            "source_file": "rules-index.json",
            "page_count": 2,
            "rule_count": 2,
            "rules": [
                {
                    "page": 10,
                    "title": "飞瀑门高度限制",
                    "detail": "飞瀑门高度应≤2400mm",
                    "normalized_rule": "飞瀑门高度应≤2400mm",
                },
                {
                    "page": 11,
                    "title": "灯带开关安装提醒",
                    "detail": "优先考虑安装位置",
                    "normalized_rule": "灯带开关安装提醒",
                },
            ],
        }
        coverage_ledger = MODULE.finalize_coverage_ledger(
            {
                "entries": [
                    {
                        "page": 10,
                        "topic": "飞瀑门高度限制",
                        "summary": "飞瀑门高度应≤2400mm",
                        "status": "runtime_hard_rule",
                    },
                    {
                        "page": 11,
                        "topic": "灯带开关总览页",
                        "summary": "优先选用有线开关",
                        "status": "knowledge_ready",
                    },
                ]
            }
        )

        published = MODULE.build_published_runtime_rules(runtime_payload, coverage_ledger)

        self.assertEqual(published["rule_count"], 1)
        self.assertEqual(len(published["rules"]), 1)
        self.assertEqual(published["rules"][0]["title"], "飞瀑门高度限制")

    def test_apply_runtime_rules_overrides_can_replace_all_rules(self) -> None:
        payload = {
            "layer_id": "designer-a",
            "layer_name": "设计师追加规则 A",
            "rule_count": 1,
            "rules": [
                {"page": 1, "title": "原始规则", "detail": "原始内容", "trigger_terms": ["原始"]},
            ],
        }
        overrides = {
            "replace_rules": [
                {"page": 2, "title": "人工整理规则", "detail": "只保留这一条", "trigger_terms": ["人工整理"]},
            ]
        }

        merged = MODULE.apply_runtime_rules_overrides(payload, overrides)

        self.assertEqual(merged["rule_count"], 1)
        self.assertEqual(len(merged["rules"]), 1)
        self.assertEqual(merged["rules"][0]["title"], "人工整理规则")

    def test_apply_runtime_rules_overrides_backfills_runtime_rule_fields_for_legacy_rules(self) -> None:
        payload = {
            "layer_id": "designer-a",
            "layer_name": "设计师追加规则 A",
            "rule_count": 0,
            "rules": [],
        }
        overrides = {
            "replace_rules": [
                {
                    "page": 249,
                    "domain": "cabinet",
                    "action_type": "constraint",
                    "title": "60mm以下不能做居中圆扣手。",
                    "detail": "60mm以下不能做居中圆扣手。 上翻回收展板门 平板上翻门 拼框上翻门 上翻回收展板门；简美上翻回收展板门可见参考模型。",
                    "trigger_terms": [],
                    "required_fields": [],
                    "tags": ["柜体", "尺寸阈值"],
                    "confidence": 0.95,
                    "relevance_score": 7,
                    "source_heading": "60mm以下不能做居中圆扣手。",
                    "normalized_rule": "本段主要定义尺寸阈值、适用区间或边界条件。",
                }
            ]
        }

        merged = MODULE.apply_runtime_rules_overrides(payload, overrides)
        merged_rule = merged["rules"][0]

        self.assertEqual(merged["rule_count"], 1)
        self.assertTrue(merged_rule["trigger_terms"])
        self.assertIn("上翻回收展板门", merged_rule["match_terms_specific"])
        self.assertEqual(merged_rule["evidence_level"], "hard_rule")
        self.assertTrue(merged_rule["user_summary"])
        self.assertIn("match_terms_generic", merged_rule)
        self.assertIn("question_template", merged_rule)

    def test_build_published_knowledge_layer_uses_knowledge_ready_entries(self) -> None:
        coverage_ledger = MODULE.finalize_coverage_ledger(
            {
                "entries": [
                    {
                        "page": 48,
                        "topic": "直角圆边-窄边高柜",
                        "summary": "本段主要是业务说明。识别标签：节点尺寸, 凹槽内退。关键信息：直角圆边-窄边高柜；上下节点尺寸；凹槽内退尺寸",
                        "note": "已转入知识层回答，当前作为高置信结构复盘提示，不直接入 runtime。",
                        "status": "knowledge_ready",
                    },
                    {
                        "page": 49,
                        "topic": "已覆盖规则",
                        "summary": "这一条不应进入知识层",
                        "status": "covered_existing",
                    },
                ]
            }
        )

        payload = MODULE.build_published_knowledge_layer(
            layer_id="designer-a",
            layer_name="设计师追加规则 A",
            coverage_ledger=coverage_ledger,
        )

        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["topic"], "直角圆边-窄边高柜")
        self.assertEqual(payload["entries"][0]["source_pages"], [48])
        self.assertEqual(payload["entries"][0]["evidence_level"], "high_confidence_review")
        self.assertIn("上下节点尺寸", payload["entries"][0]["answerable_summary"])
        self.assertIn("节点尺寸", payload["entries"][0]["trigger_terms"])
        self.assertIn("不直接入 runtime", payload["entries"][0]["do_not_overclaim"])

    def test_build_published_knowledge_layer_adds_default_templates_when_note_missing(self) -> None:
        coverage_ledger = MODULE.finalize_coverage_ledger(
            {
                "entries": [
                    {
                        "page": 288,
                        "topic": "灯带开关总览页",
                        "summary": "本页可稳定提炼为下单与图纸备注提示：优先选用有线开关、需考虑走线位置、开关默认外露式、需备注开关名称与安装位置、分区控制或单区域多个开关需额外收费。",
                        "status": "knowledge_ready",
                    }
                ]
            }
        )

        payload = MODULE.build_published_knowledge_layer(
            layer_id="designer-a",
            layer_name="设计师追加规则 A",
            coverage_ledger=coverage_ledger,
        )

        self.assertEqual(len(payload["entries"]), 1)
        self.assertIn("图纸备注提示", payload["entries"][0]["answer_lead"])
        self.assertIn("有线开关", payload["entries"][0]["answerable_summary"])
        self.assertIn("没有明确证据的部分就直接说不知道", payload["entries"][0]["do_not_overclaim"])

    def test_apply_knowledge_layer_overrides_updates_generated_entries(self) -> None:
        payload = {
            "entries": [
                {
                    "topic": "灯带开关总览页",
                    "answer_lead": "原始 lead",
                    "answerable_summary": "原始 summary",
                    "evidence_level": "high_confidence_review",
                    "source_pages": [288],
                    "trigger_terms": ["灯带开关"],
                    "do_not_overclaim": "原始边界",
                }
            ]
        }
        overrides = {
            "overrides": [
                {
                    "page": 288,
                    "topic_contains": "灯带开关",
                    "answer_lead": "这页目前更适合作为下单和图纸备注提示来用。",
                    "answerable_summary": "优先选用有线开关，并提前备注安装位置。",
                    "trigger_terms": ["灯带开关", "有线开关", "安装位置"],
                    "do_not_overclaim": "不要把具体型号直接说成统一死规则。",
                }
            ],
            "append_entries": [
                {
                    "topic": "新增人工补充条目",
                    "answerable_summary": "这是一条人工追加的知识提示。",
                    "evidence_level": "high_confidence_review",
                    "source_pages": [999],
                    "trigger_terms": ["人工补充"],
                    "do_not_overclaim": "仅作提示。",
                }
            ],
        }

        merged = MODULE.apply_knowledge_layer_overrides(payload, overrides)

        self.assertEqual(len(merged["entries"]), 2)
        self.assertEqual(merged["entries"][0]["answer_lead"], "这页目前更适合作为下单和图纸备注提示来用。")
        self.assertIn("有线开关", merged["entries"][0]["answerable_summary"])
        self.assertEqual(merged["entries"][0]["trigger_terms"], ["灯带开关", "有线开关", "安装位置"])
        self.assertEqual(merged["entries"][1]["topic"], "新增人工补充条目")

    def test_apply_knowledge_layer_overrides_can_replace_all_entries(self) -> None:
        payload = {
            "entries": [
                {
                    "topic": "原始条目",
                    "answerable_summary": "原始内容",
                    "evidence_level": "high_confidence_review",
                    "source_pages": [1],
                    "trigger_terms": ["原始"],
                    "do_not_overclaim": "原始边界",
                }
            ]
        }
        overrides = {
            "replace_entries": [
                {
                    "topic": "人工整理条目",
                    "answer_lead": "这条来自人工整理。",
                    "answerable_summary": "只保留这一条作为最终知识层输出。",
                    "evidence_level": "high_confidence_review",
                    "source_pages": [288],
                    "trigger_terms": ["人工整理"],
                    "do_not_overclaim": "目前只能作为提示。",
                }
            ]
        }

        merged = MODULE.apply_knowledge_layer_overrides(payload, overrides)

        self.assertEqual(len(merged["entries"]), 1)
        self.assertEqual(merged["entries"][0]["topic"], "人工整理条目")
        self.assertEqual(merged["entries"][0]["source_pages"], [288])
        self.assertEqual(merged["entries"][0]["trigger_terms"], ["人工整理"])

    def test_build_layer_manifest_keeps_layer_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            layer_dir = root / "references" / "addenda" / "designer-a"
            layer_dir.mkdir(parents=True)
            candidate = root / "rules-candidate.json"
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            runtime_rules_overrides = root / "runtime-rules-overrides.json"
            knowledge_layer = root / "knowledge-layer.json"
            knowledge_layer_overrides = root / "knowledge-layer-overrides.json"
            coverage_ledger = root / "coverage-ledger.json"
            coverage_ledger_overrides = root / "coverage-ledger-overrides.json"
            drafts_dir = root / "drafts"
            source_md = root / "rules-source.md"
            candidate.write_text("{}", encoding="utf-8")
            index.write_text("{}", encoding="utf-8")
            runtime_rules.write_text("{}", encoding="utf-8")
            runtime_rules_overrides.write_text("{}", encoding="utf-8")
            knowledge_layer.write_text("{}", encoding="utf-8")
            knowledge_layer_overrides.write_text("{}", encoding="utf-8")
            coverage_ledger.write_text("{}", encoding="utf-8")
            coverage_ledger_overrides.write_text("{}", encoding="utf-8")
            drafts_dir.mkdir()
            (drafts_dir / "manifest.json").write_text('{"domain_count": 2}', encoding="utf-8")
            source_md.write_text("# draft", encoding="utf-8")

            manifest = MODULE.build_layer_manifest(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                source_file=Path("/tmp/source.pdf"),
                candidate_path=candidate,
                index_path=index,
                runtime_rules_path=runtime_rules,
                runtime_rules_overrides_path=runtime_rules_overrides,
                knowledge_layer_path=knowledge_layer,
                knowledge_layer_overrides_path=knowledge_layer_overrides,
                coverage_ledger_path=coverage_ledger,
                coverage_ledger_overrides_path=coverage_ledger_overrides,
                source_markdown_path=source_md,
                drafts_dir=drafts_dir,
                manifest_dir=layer_dir,
            )

        self.assertEqual(manifest["layer_id"], "designer-a")
        self.assertEqual(manifest["layer_name"], "设计师追加规则 A")
        self.assertEqual(manifest["status"], "ACTIVE")
        self.assertFalse(manifest["mutates_base_rules"])
        self.assertIn("rules_index_file", manifest["artifacts"])
        self.assertIn("runtime_rules_file", manifest["artifacts"])
        self.assertIn("runtime_rules_overrides_file", manifest["artifacts"])
        self.assertIn("knowledge_layer_file", manifest["artifacts"])
        self.assertIn("knowledge_layer_overrides_file", manifest["artifacts"])
        self.assertIn("coverage_ledger_file", manifest["artifacts"])
        self.assertIn("coverage_ledger_overrides_file", manifest["artifacts"])
        self.assertFalse(str(manifest["source_file"]).startswith("/"))
        self.assertFalse(str(manifest["artifacts"]["runtime_rules_file"]).startswith("/"))

    def test_write_manifest_creates_layer_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "layer"
            manifest = {"layer_id": "designer-b", "status": "ACTIVE"}

            MODULE.write_manifest(output_dir, manifest)

            written = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(written["layer_id"], "designer-b")

    def test_designer_manual_runtime_artifact_has_no_empty_triggers_or_known_ocr_noise(self) -> None:
        reports_dir = (
            Path(__file__).resolve().parents[1]
            / "reports"
            / "addenda"
            / "designer-manual-2026-03-22"
        )
        runtime_payload = json.loads((reports_dir / "runtime-rules.json").read_text(encoding="utf-8"))
        known_ocr_markers = ("QNEKRE", "Wuoww", "PA: j", "1e2. RUE", "POP Ra Pe", "NT AE BX")

        for rule in runtime_payload.get("rules", []):
            self.assertTrue(rule.get("trigger_terms"), msg=f"empty trigger_terms: {rule.get('page')} {rule.get('title')}")
            self.assertTrue(rule.get("user_summary"), msg=f"empty user_summary: {rule.get('page')} {rule.get('title')}")
            self.assertIn("match_terms_specific", rule)
            self.assertIn("match_terms_generic", rule)
            self.assertEqual(rule.get("evidence_level"), "hard_rule")
            combined = f"{rule.get('title', '')} {rule.get('detail', '')}"
            self.assertFalse(
                any(marker in combined for marker in known_ocr_markers),
                msg=f"known OCR noise leaked: {rule.get('page')} {rule.get('title')}",
            )


if __name__ == "__main__":
    unittest.main()
