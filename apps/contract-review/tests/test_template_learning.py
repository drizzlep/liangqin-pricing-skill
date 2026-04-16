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
MODULE_PATH = CORE_ROOT / "template_learning.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


JOB_MODELS = load_module("contract_review_job_models_for_template_learning", JOB_MODELS_PATH)
TEMPLATE_LEARNING = load_module("contract_review_template_learning", MODULE_PATH)


class TemplateLearningTests(unittest.TestCase):
    def test_build_template_profile_persists_template_metadata(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-template-001",
            batch_id="batch-template",
            group_key="case-template",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.docx",
                    relative_path="raw/case-template/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview=(
                        "产品名称：书柜\n"
                        "长度：2400mm\n"
                        "进深：350mm\n"
                        "高度：2100mm\n"
                        "材质：北美黑胡桃木\n"
                    ),
                    text_extract_method="docx_text",
                )
            ],
        )
        normalized_fields = {
            "fields": {
                "product_category": {
                    "value": "书柜",
                    "confidence": 0.98,
                    "evidence_refs": [{"snippet": "产品名称：书柜", "source_kind": "native_preview"}],
                },
                "length": {
                    "value": "2400mm",
                    "confidence": 0.96,
                    "evidence_refs": [{"snippet": "长度：2400mm", "source_kind": "native_preview"}],
                },
            }
        }
        review_analysis = {
            "issues": [
                {"issue_code": "missing_required_field", "severity": "medium"},
                {"issue_code": "field_conflict", "severity": "high"},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            profile = TEMPLATE_LEARNING.build_template_profile(
                job=job,
                normalized_fields_payload=normalized_fields,
                review_analysis=review_analysis,
                runtime_root=runtime_root,
            )

            profile_path = runtime_root / "templates" / f"{profile['template_id']}.json"
            self.assertTrue(profile_path.exists())
            saved = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(profile["learning_version"], 1)
        self.assertEqual(saved["template_fingerprint"], profile["template_fingerprint"])
        self.assertIn("product_category", profile["field_aliases"])
        self.assertGreaterEqual(profile["trust_score"], 0.0)
        self.assertEqual(profile["observed_job_count"], 1)

    def test_apply_review_feedback_updates_template_profile(self) -> None:
        job = JOB_MODELS.ReviewJob(
            job_id="job-template-002",
            batch_id="batch-template",
            group_key="case-template",
            source_type="manual_batch",
            source_channel="manual",
            requested_actions=["audit", "replay"],
            assets=[
                JOB_MODELS.SourceAsset(
                    asset_id="asset-001",
                    source_path="/tmp/fake.docx",
                    relative_path="raw/case-template/合同.docx",
                    file_name="合同.docx",
                    extension=".docx",
                    media_kind="document",
                    role_hint="primary_contract",
                    text_preview="产品名称：书柜\n长度：2400mm\n",
                    text_extract_method="docx_text",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            profile = TEMPLATE_LEARNING.build_template_profile(
                job=job,
                normalized_fields_payload={"fields": {}},
                review_analysis={"issues": [{"issue_code": "field_conflict", "severity": "high"}]},
                runtime_root=runtime_root,
            )
            updated = TEMPLATE_LEARNING.apply_review_feedback(
                {
                    "job_id": job.job_id,
                    "template_id": profile["template_id"],
                    "issue_code": "field_conflict",
                    "human_decision": "confirmed",
                    "corrected_fields": {"product_category": "书柜"},
                    "confirmed_root_cause": "template_alias_missing",
                },
                runtime_root=runtime_root,
            )

        self.assertEqual(updated["feedback_count"], 1)
        self.assertEqual(updated["human_decision_breakdown"]["confirmed"], 1)
        self.assertEqual(updated["observed_issue_breakdown"]["field_conflict"], 1)
        self.assertEqual(updated["feedback_issue_breakdown"]["field_conflict"]["confirmed_count"], 1)
        self.assertEqual(updated["field_aliases"]["product_category"]["confirmed_values"][0], "书柜")
        self.assertEqual(updated["common_conflict_rules"][0]["root_cause"], "template_alias_missing")
        self.assertGreaterEqual(updated["trust_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
