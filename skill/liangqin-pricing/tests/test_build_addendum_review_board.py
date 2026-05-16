import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_addendum_review_board.py"
SPEC = importlib.util.spec_from_file_location("build_addendum_review_board", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildAddendumReviewBoardTests(unittest.TestCase):
    def write_layer(
        self,
        root: Path,
        layer_id: str,
        *,
        status: str,
        titles: list[str],
        runtime_titles: list[str],
        manual_review_titles: list[str] | None = None,
    ) -> None:
        layer_dir = root / "references" / "addenda" / layer_id
        reports_dir = root / "reports" / "addenda" / layer_id
        layer_dir.mkdir(parents=True)
        reports_dir.mkdir(parents=True)
        (reports_dir / "rules-index.json").write_text(
            json.dumps(
                {
                    "entry_count": len(titles),
                    "page_count": len(titles),
                    "entries": [
                        {
                            "page": index + 1,
                            "clean_title": title,
                            "domain": "cabinet",
                            "excerpt": f"{title} 摘要",
                            "source_title": "线上手册",
                            "source_path": "<root>/柜体",
                            "source_page": index + 1,
                        }
                        for index, title in enumerate(titles)
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (reports_dir / "runtime-rules.json").write_text(
            json.dumps(
                {
                    "rule_count": len(runtime_titles),
                    "rules": [
                        {
                            "page": index + 1,
                            "title": title,
                            "domain": "cabinet",
                            "user_summary": f"{title} 会影响报价",
                            "source_title": "线上手册",
                            "source_page": index + 1,
                        }
                        for index, title in enumerate(runtime_titles)
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (reports_dir / "knowledge-layer.json").write_text(
            json.dumps({"entries": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        manual_review_titles = manual_review_titles or []
        coverage_entries = [
            {
                "page": index + 1,
                "topic": title,
                "domain": "cabinet",
                "summary": f"{title} 待人工确认",
                "status": "unresolved",
                "publish_target": "manual_review",
                "risk_level": "high",
                "source_title": "线上手册",
                "source_page": index + 1,
            }
            for index, title in enumerate(manual_review_titles)
        ]
        (reports_dir / "coverage-ledger.json").write_text(
            json.dumps(
                {
                    "entry_count": len(coverage_entries),
                    "status_counts": {"unresolved": len(coverage_entries)},
                    "publish_target_counts": {"manual_review": len(coverage_entries)},
                    "entries": coverage_entries,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (reports_dir / "rules-candidate.json").write_text(
            json.dumps(
                {
                    "artifact_count": 2,
                    "processed_artifact_count": 2,
                    "skipped_artifact_count": 0,
                    "page_count": 3,
                    "pages": [
                        {"page": 1, "extract_method": "text_layer"},
                        {"page": 2, "extract_method": "unknown"},
                    ],
                    "sections": [
                        {"page": 1, "extract_method": "dingtalk_markdown"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (layer_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "layer_id": layer_id,
                    "layer_name": layer_id,
                    "status": status,
                    "source_file": f"../../../sources/inbox/{layer_id}",
                    "artifacts": {
                        "rules_candidate_file": f"../../../reports/addenda/{layer_id}/rules-candidate.json",
                        "rules_index_file": f"../../../reports/addenda/{layer_id}/rules-index.json",
                        "runtime_rules_file": f"../../../reports/addenda/{layer_id}/runtime-rules.json",
                        "knowledge_layer_file": f"../../../reports/addenda/{layer_id}/knowledge-layer.json",
                        "coverage_ledger_file": f"../../../reports/addenda/{layer_id}/coverage-ledger.json",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_review_model_groups_human_action_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_layer(root, "old", status="ACTIVE", titles=["旧柜体规则"], runtime_titles=["旧硬规则"])
            self.write_layer(
                root,
                "online",
                status="PAUSED",
                titles=["旧柜体规则", "新柜体规则", "待确认柜体"],
                runtime_titles=["新硬规则"],
                manual_review_titles=["待确认柜体"],
            )

            model = MODULE.build_review_model(root, "old", "online")

        buckets = {card["bucket"] for card in model["cards"]}
        self.assertEqual(model["candidate_layer"]["status"], "PAUSED")
        self.assertIn("added_runtime", buckets)
        self.assertIn("manual_review", buckets)
        self.assertIn("removed_runtime", buckets)
        self.assertEqual(model["candidate_rules"]["processed_artifact_count"], 2)
        self.assertEqual(model["quality"]["ocr_page_count"], 0)
        self.assertEqual(model["quality"]["unknown_page_count"], 1)

    def test_render_html_includes_decision_summary_and_filters(self) -> None:
        model = {
            "base_layer": {"layer_id": "old", "status": "ACTIVE"},
            "candidate_layer": {"layer_id": "online", "status": "PAUSED"},
            "candidate_rules": {"artifact_count": 2, "processed_artifact_count": 2, "skipped_artifact_count": 0, "page_count": 3},
            "coverage": {"publish_target_counts": {"manual_review": 1, "runtime": 1, "none": 0}},
            "quality": {
                "ocr_page_count": 0,
                "page_method_counts": {"text_layer": 2},
                "index_method_counts": {"text_layer": 1},
                "average_confidence": 0.95,
                "text_layer_page_ratio": 1.0,
                "unknown_page_count": 0,
            },
            "counts": {"rules_added": 1, "rules_removed": 0, "runtime_added": 1, "runtime_removed": 0},
            "cards": [
                {
                    "bucket": "added_runtime",
                    "bucket_label": "可能影响报价",
                    "title": "新柜体规则",
                    "domain": "cabinet",
                    "domain_label": "柜体",
                    "page": 1,
                    "action": "先请懂报价的人看一眼",
                    "reason": "会影响报价",
                    "risk": "high",
                    "risk_label": "优先看",
                    "choices": ("采用", "暂缓", "找设计师确认"),
                    "summary": "摘要",
                    "source": "线上手册 / 源页 1",
                }
            ],
        }

        html = MODULE.render_html(model)

        self.assertIn("设计师手册线上版审核台", html)
        self.assertIn("这份线上手册还没有接进正式报价", html)
        self.assertIn("可能影响报价", html)
        self.assertIn("这条怎么处理", html)
        self.assertIn("可选判断", html)
        self.assertIn("这次文字从哪里来", html)
        self.assertIn("本次没有跑 OCR", html)
        self.assertIn("触发 OCR 页", html)
        self.assertIn("data-filter-bucket", html)
        self.assertIn("优先确认", html)
        self.assertIn("let activeBucket = 'priority'", html)


if __name__ == "__main__":
    unittest.main()
