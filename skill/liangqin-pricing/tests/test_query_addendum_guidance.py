import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "query_addendum_guidance.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("query_addendum_guidance", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QueryAddendumGuidanceTests(unittest.TestCase):
    def test_query_guidance_returns_opening_method_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-opening"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-opening",
                        "layer_name": "设计师追加规则 Opening",
                        "rules": [
                            {
                                "page": 177,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "其他无把手、无抠手柜门须明确备注开启方式",
                                "detail": "流云门默认为按弹开启，其他无把手、无抠手柜门需备注开启方式",
                                "trigger_terms": ["流云", "无把手", "无抠手", "开启方式"],
                                "required_fields": ["开启方式"],
                                "tags": ["门型"],
                                "relevance_score": 7,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            layer_dir.mkdir()
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "designer-opening",
                        "layer_name": "设计师追加规则 Opening",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.query_guidance(
                "我要做一个北美黑胡桃木流云门衣柜，长1.8米，高2.2米，深600，不做拉手和抠手，开启方向先不说。",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "follow_up")
        self.assertEqual(payload["follow_up_questions"][0]["question"], "请确认开启方式")
        self.assertIn("请确认开启方式", payload["suggested_reply"])

    def test_query_guidance_returns_bed_weight_follow_up_and_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-bed"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-bed",
                        "layer_name": "设计师追加规则 Bed",
                        "rules": [
                            {
                                "page": 369,
                                "domain": "bed",
                                "action_type": "constraint",
                                "title": "床垫重量应≤50kg，设计时需考虑客户家床垫重量，如床垫超重可使用两套750N举升器，下单时需备注。",
                                "detail": "床垫尺寸限制W≤1800、L≤2000，当W＞1800时默认使用两套750N举升器，需要单独收费。",
                                "trigger_terms": ["床垫重量", "举升器", "床垫"],
                                "required_fields": ["床垫重量"],
                                "tags": ["尺寸阈值"],
                                "relevance_score": 6,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            layer_dir.mkdir()
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "designer-bed",
                        "layer_name": "设计师追加规则 Bed",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.query_guidance(
                "我要做一个尾翻箱体床，1.8乘2米，北美黑胡桃木，床垫重量暂时未知，你先按规则告诉我还需要补什么信息，以及举升器怎么判断。",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "follow_up")
        self.assertEqual(payload["follow_up_questions"][0]["question"], "请确认床垫重量")
        self.assertEqual(len(payload["constraints"]), 1)
        self.assertIn("请确认床垫重量", payload["suggested_reply"])
        self.assertIn("750N举升器", payload["suggested_reply"])


if __name__ == "__main__":
    unittest.main()
