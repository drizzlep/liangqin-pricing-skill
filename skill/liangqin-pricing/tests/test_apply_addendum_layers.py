import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "apply_addendum_layers.py"
SPEC = importlib.util.spec_from_file_location("apply_addendum_layers", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ApplyAddendumLayersTests(unittest.TestCase):
    def make_quote_payload(self) -> dict[str, object]:
        return {
            "items": [
                {
                    "product": "流云衣柜",
                    "confirmed": "北美黑胡桃木，1.8m*2.2m*0.6m，纹理连续",
                    "pricing_method": "投影面积计价",
                    "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                    "subtotal": "34372.8元",
                }
            ],
            "total": "34372.8元",
        }

    def test_apply_active_layer_adds_adjustments_without_changing_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-a"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            index_path = reports_dir / "rules-index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "domain": "cabinet",
                                "pricing_relevant": True,
                                "clean_title": "流云门板纹理连续超过0.9m需补差",
                                "excerpt": "流云/飞瀑平板门纹理连续超过0.9m时按平板门差价补差",
                                "tags": ["柜体", "门型", "流云"],
                                "relevance_score": 9,
                            },
                            {
                                "domain": "cabinet",
                                "pricing_relevant": True,
                                "clean_title": "开放格区域层板内凹",
                                "excerpt": "开放格区域层板内凹时按投影面积结构稳定性规则处理",
                                "tags": ["柜体", "投影面积", "开放格"],
                                "relevance_score": 8,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest_path = layer_dir / "manifest.json"
            layer_dir.mkdir()
            manifest_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-a",
                        "layer_name": "设计师追加规则 A",
                        "status": "ACTIVE",
                        "artifacts": {"rules_index_file": str(index_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            merged = MODULE.apply_addendum_layers(self.make_quote_payload(), addenda_root)

        item = merged["items"][0]
        self.assertEqual(merged["total"], "34372.8元")
        self.assertIn("addendum_adjustments", item)
        self.assertIn("设计师追加规则 A", merged["addendum_notes"][0])
        self.assertIn("纹理连续超过0.9m", item["addendum_adjustments"][0])
        self.assertEqual(len(item["addendum_adjustments"]), 1)
        self.assertEqual(item["addendum_decisions"]["adjustments"][0]["layer_name"], "设计师追加规则 A")
        self.assertEqual(item["addendum_decisions"]["constraints"], [])
        self.assertEqual(item["addendum_decisions"]["follow_up_questions"], [])

    def test_apply_layer_splits_constraint_and_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-b"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            index_path = reports_dir / "rules-index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "domain": "bed",
                                "pricing_relevant": True,
                                "clean_title": "床垫重量应≤50kg",
                                "excerpt": "床垫超重需改用两套750N举升器并单独收费",
                                "tags": ["床垫", "举升器"],
                                "relevance_score": 9,
                            },
                            {
                                "domain": "bed",
                                "pricing_relevant": True,
                                "clean_title": "需先确认床垫重量",
                                "excerpt": "如果客户未提供床垫重量，应先追问床垫重量",
                                "tags": ["床垫", "举升器"],
                                "relevance_score": 8,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            layer_dir.mkdir()
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "designer-b",
                        "layer_name": "设计师追加规则 B",
                        "status": "ACTIVE",
                        "artifacts": {"rules_index_file": str(index_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "箱体床",
                        "confirmed": "北美黑胡桃木，1.8m*2m，床垫重量未知",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 12800"],
                        "subtotal": "12800元",
                    }
                ],
                "total": "12800元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertEqual(decisions["adjustments"], [])
        self.assertEqual(decisions["constraints"][0]["title"], "床垫重量应≤50kg")
        self.assertIn("床垫重量", decisions["follow_up_questions"][0]["question"])

    def test_apply_layer_prefers_runtime_rules_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-runtime"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            index_path = reports_dir / "rules-index.json"
            runtime_rules_path = reports_dir / "runtime-rules.json"
            index_path.write_text(json.dumps({"entries": []}, ensure_ascii=False), encoding="utf-8")
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-runtime",
                        "layer_name": "设计师追加规则 Runtime",
                        "rules": [
                            {
                                "page": 12,
                                "domain": "bed",
                                "action_type": "constraint",
                                "title": "床垫重量应≤50kg",
                                "detail": "床垫超重需改用两套750N举升器并单独收费",
                                "trigger_terms": ["床垫", "举升器"],
                                "required_fields": ["床垫重量"],
                                "tags": ["床垫", "举升器"],
                                "relevance_score": 9,
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
                        "layer_id": "designer-runtime",
                        "layer_name": "设计师追加规则 Runtime",
                        "status": "ACTIVE",
                        "artifacts": {
                            "rules_index_file": str(index_path),
                            "runtime_rules_file": str(runtime_rules_path),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "箱体床",
                        "confirmed": "北美黑胡桃木，1.8m*2m，床垫重量48kg",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 12800"],
                        "subtotal": "12800元",
                    }
                ],
                "total": "12800元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertEqual(decisions["constraints"][0]["title"], "床垫重量应≤50kg")
        self.assertIn("设计师追加规则 Runtime", merged["addendum_notes"][0])

    def test_apply_layer_resolves_relative_runtime_rules_file_from_manifest_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            addenda_root = root / "references" / "addenda"
            layer_dir = addenda_root / "designer-relative"
            reports_dir = root / "reports" / "addenda" / "designer-relative"
            reports_dir.mkdir(parents=True)
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-relative",
                        "layer_name": "设计师追加规则 Relative",
                        "rules": [
                            {
                                "page": 30,
                                "domain": "bed",
                                "action_type": "constraint",
                                "title": "床垫重量应≤50kg",
                                "detail": "床垫超重需改用两套750N举升器并单独收费",
                                "trigger_terms": ["床垫", "举升器"],
                                "required_fields": ["床垫重量"],
                                "tags": ["床垫", "举升器"],
                                "relevance_score": 9,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            layer_dir.mkdir(parents=True)
            relative_runtime_path = os.path.relpath(runtime_rules_path, start=layer_dir)
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "designer-relative",
                        "layer_name": "设计师追加规则 Relative",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": relative_runtime_path},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "箱体床",
                        "confirmed": "北美黑胡桃木，1.8m*2m，床垫重量48kg",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 12800"],
                        "subtotal": "12800元",
                    }
                ],
                "total": "12800元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertEqual(decisions["constraints"][0]["title"], "床垫重量应≤50kg")
        self.assertIn("设计师追加规则 Relative", merged["addendum_notes"][0])

    def test_apply_layer_adds_follow_up_when_required_field_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-follow-up"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-follow-up",
                        "layer_name": "设计师追加规则 FollowUp",
                        "rules": [
                            {
                                "page": 20,
                                "domain": "bed",
                                "action_type": "constraint",
                                "title": "床垫重量应≤50kg",
                                "detail": "床垫超重需改用两套750N举升器并单独收费",
                                "trigger_terms": ["床垫", "举升器", "床垫重量"],
                                "required_fields": ["床垫重量"],
                                "tags": ["床垫", "举升器"],
                                "relevance_score": 9,
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
                        "layer_id": "designer-follow-up",
                        "layer_name": "设计师追加规则 FollowUp",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "箱体床",
                        "confirmed": "北美黑胡桃木，1.8m*2m，床垫重量未知",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 12800"],
                        "subtotal": "12800元",
                    }
                ],
                "total": "12800元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertIn("请确认床垫重量", decisions["follow_up_questions"][0]["question"])

    def test_apply_layer_allows_door_panel_rule_for_cabinet_item_when_signals_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-door-panel"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-door-panel",
                        "layer_name": "设计师追加规则 DoorPanel",
                        "rules": [
                            {
                                "page": 177,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "其他无把手、无抠手柜门须明确备注开启方式",
                                "detail": "流云门默认为按弹开启，其他无把手、无抠手柜门需备注开启方式",
                                "trigger_terms": ["流云", "平板门"],
                                "required_fields": ["门型"],
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
                        "layer_id": "designer-door-panel",
                        "layer_name": "设计师追加规则 DoorPanel",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "流云门衣柜",
                        "confirmed": "北美黑胡桃木，无把手，无抠手，按弹开启",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 2.0 * 2.4 * 8680 = 41664"],
                        "subtotal": "41664元",
                    }
                ],
                "total": "41664元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertEqual(decisions["constraints"][0]["title"], "其他无把手、无抠手柜门须明确备注开启方式")

    def test_apply_layer_deduplicates_follow_up_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-follow-up-dedupe"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-follow-up-dedupe",
                        "layer_name": "设计师追加规则 FollowUp Dedupe",
                        "rules": [
                            {
                                "page": 20,
                                "domain": "bed",
                                "action_type": "constraint",
                                "title": "床垫重量应≤50kg",
                                "detail": "床垫超重需改用两套750N举升器并单独收费",
                                "trigger_terms": ["床垫", "床垫重量"],
                                "required_fields": ["床垫重量"],
                                "tags": ["床垫"],
                                "relevance_score": 9,
                            },
                            {
                                "page": 21,
                                "domain": "bed",
                                "action_type": "constraint",
                                "title": "下单时需备注床垫重量",
                                "detail": "未提供床垫重量时需先确认床垫重量",
                                "trigger_terms": ["床垫", "床垫重量"],
                                "required_fields": ["床垫重量"],
                                "tags": ["床垫"],
                                "relevance_score": 8,
                            },
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
                        "layer_id": "designer-follow-up-dedupe",
                        "layer_name": "设计师追加规则 FollowUp Dedupe",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "箱体床",
                        "confirmed": "北美黑胡桃木，1.8m*2m，床垫重量未知",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 12800"],
                        "subtotal": "12800元",
                    }
                ],
                "total": "12800元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        follow_ups = merged["items"][0]["addendum_decisions"]["follow_up_questions"]
        self.assertEqual(len(follow_ups), 1)
        self.assertEqual(follow_ups[0]["question"], "请确认床垫重量")

    def test_apply_layer_turns_opening_method_rule_into_follow_up_when_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-opening-follow-up"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-opening-follow-up",
                        "layer_name": "设计师追加规则 Opening",
                        "rules": [
                            {
                                "page": 177,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "其他无把手、无抠手柜门须明确备注开启方式",
                                "detail": "流云门默认为按弹开启，其他无把手、无抠手柜门需备注开启方式",
                                "trigger_terms": ["流云", "平板门", "无把手", "无抠手", "开启方式"],
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
                        "layer_id": "designer-opening-follow-up",
                        "layer_name": "设计师追加规则 Opening",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "流云门衣柜",
                        "confirmed": "北美黑胡桃木，长1.8m，高2.2m，深600mm，无把手，无抠手，开启方向先不说",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 1.8 * 2.2 * 8680 = 34372.8"],
                        "subtotal": "34372.8元",
                    }
                ],
                "total": "34372.8元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertEqual(decisions["adjustments"], [])
        self.assertEqual(decisions["constraints"], [])
        self.assertEqual(decisions["follow_up_questions"][0]["question"], "请确认开启方式")

    def test_apply_layer_avoids_false_positive_when_only_generic_terms_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-precision"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-precision",
                        "layer_name": "设计师追加规则 Precision",
                        "rules": [
                            {
                                "page": 195,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "使用天地铰链的柜体，顶板不可做检修口等的避让开口",
                                "detail": "平板门纹理连续超过0.9m时需加价；使用天地铰链的柜体，顶板不可做检修口等的避让开口",
                                "trigger_terms": ["纹理连续", "平板门", "抽屉", "天地铰链"],
                                "required_fields": ["门型", "长度"],
                                "tags": ["柜体", "门型"],
                                "relevance_score": 10,
                            },
                            {
                                "page": 159,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "使用明装拉手时抽面长度＞600mm建议双孔长拉手或2个单孔拉手",
                                "detail": "抽面长度＞600mm建议使用双孔长拉手或2个单孔拉手",
                                "trigger_terms": ["抽面", "拉手"],
                                "required_fields": ["长度"],
                                "tags": ["抽屉"],
                                "relevance_score": 8,
                            },
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
                        "layer_id": "designer-precision",
                        "layer_name": "设计师追加规则 Precision",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = {
                "items": [
                    {
                        "product": "餐边柜抽屉",
                        "confirmed": "抽面长度700mm，明装拉手",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 3200"],
                        "subtotal": "3200元",
                    }
                ],
                "total": "3200元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(len(constraints), 1)
        self.assertEqual(constraints[0]["title"], "使用明装拉手时抽面长度＞600mm建议双孔长拉手或2个单孔拉手")

    def test_paused_layer_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-paused"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            index_path = reports_dir / "rules-index.json"
            index_path.write_text(json.dumps({"entries": []}, ensure_ascii=False), encoding="utf-8")
            layer_dir.mkdir()
            (layer_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "layer_id": "designer-paused",
                        "layer_name": "暂停规则",
                        "status": "PAUSED",
                        "artifacts": {"rules_index_file": str(index_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            merged = MODULE.apply_addendum_layers(self.make_quote_payload(), addenda_root)

        self.assertNotIn("addendum_notes", merged)
        self.assertNotIn("addendum_adjustments", merged["items"][0])


if __name__ == "__main__":
    unittest.main()
