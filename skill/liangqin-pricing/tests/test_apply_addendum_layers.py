import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "apply_addendum_layers.py"
RUNTIME_RULES_PATH = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "addenda"
    / "designer-manual-2026-03-22"
    / "runtime-rules.json"
)
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

    def test_apply_layer_promotes_rock_slab_countertop_to_follow_up_when_length_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-rock-slab"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-rock-slab",
                        "layer_name": "设计师追加规则 Rock Slab",
                        "rules": [
                            {
                                "page": 38,
                                "domain": "cabinet",
                                "action_type": "adjustment",
                                "title": "岩板台面按长度加价",
                                "detail": "岩板台面：1460*岩板长度+柜体正常计算",
                                "trigger_terms": ["岩板台面", "岩板", "台面"],
                                "required_fields": ["岩板长度"],
                                "tags": ["柜体", "岩板"],
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
                        "layer_id": "designer-rock-slab",
                        "layer_name": "设计师追加规则 Rock Slab",
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
                        "product": "玄关柜",
                        "confirmed": "北美白橡木，带岩板台面",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 1.6 * 2.2 * 6380 = 22457.6"],
                        "subtotal": "22457.6元",
                    }
                ],
                "total": "22457.6元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        follow_ups = merged["items"][0]["addendum_decisions"]["follow_up_questions"]
        self.assertEqual(follow_ups[0]["question"], "请确认岩板长度")

    def test_apply_layer_does_not_match_plain_rock_slab_dining_table_runtime_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-rock-slab"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-rock-slab",
                        "layer_name": "设计师追加规则 Rock Slab",
                        "rules": [
                            {
                                "page": 38,
                                "domain": "cabinet",
                                "action_type": "adjustment",
                                "title": "岩板台面按长度加价",
                                "detail": "岩板台面：1460*岩板长度+柜体正常计算",
                                "trigger_terms": ["岩板台面", "岩板", "台面"],
                                "required_fields": ["岩板长度"],
                                "tags": ["柜体", "岩板"],
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
                        "layer_id": "designer-rock-slab",
                        "layer_name": "设计师追加规则 Rock Slab",
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
                        "product": "岩板餐桌",
                        "confirmed": "北美黑胡桃木，1.6m*0.8m",
                        "pricing_method": "单件计价",
                        "calculation_steps": ["基础价格 = 6380"],
                        "subtotal": "6380元",
                    }
                ],
                "total": "6380元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        self.assertNotIn("addendum_decisions", merged["items"][0])

    def test_apply_layer_asks_side_panel_area_after_backboard_height_reaches_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-rock-slab"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-rock-slab",
                        "layer_name": "设计师追加规则 Rock Slab",
                        "rules": [
                            {
                                "page": 38,
                                "domain": "cabinet",
                                "action_type": "adjustment",
                                "title": "岩板背板按长度加价",
                                "detail": "岩板背板：1460*岩板长度。空区高度＜55cm不计算侧板；空区高度≥55cm时，按照超出侧板面积*单价计算。",
                                "trigger_terms": ["岩板背板", "背板"],
                                "required_fields": ["空区高度"],
                                "tags": ["柜体", "岩板", "背板"],
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
                        "layer_id": "designer-rock-slab",
                        "layer_name": "设计师追加规则 Rock Slab",
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
                        "product": "玄关柜",
                        "confirmed": "北美白橡木，岩板背板，空区高度0.55米",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 1.6 * 2.2 * 6380 = 22457.6"],
                        "subtotal": "22457.6元",
                    }
                ],
                "total": "22457.6元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        follow_ups = merged["items"][0]["addendum_decisions"]["follow_up_questions"]
        self.assertEqual(follow_ups[0]["question"], "请确认超出侧板面积")

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

    def test_apply_layer_matches_specific_door_panel_rule_but_not_generic_aluminum_frame_door(self) -> None:
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
                                "page": 196,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "针式铰链铝框门尺寸限制",
                                "detail": "针式铰链铝框门：305mm≤高度≤3000mm，180mm≤宽度≤500mm；只适用针式铰链。",
                                "trigger_terms": ["针式铰链铝框门"],
                                "required_fields": [],
                                "tags": ["门型", "尺寸阈值", "铝框"],
                                "relevance_score": 10,
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

            specific_payload = {
                "items": [
                    {
                        "product": "针式铰链铝框门衣柜",
                        "confirmed": "针式铰链铝框门，高2400mm，宽450mm",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 2.0 * 2.4 * 8680 = 41664"],
                        "subtotal": "41664元",
                    }
                ],
                "total": "41664元",
            }
            generic_payload = {
                "items": [
                    {
                        "product": "普通铝框门衣柜",
                        "confirmed": "普通铝框门，高2400mm，宽450mm",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 2.0 * 2.4 * 8680 = 41664"],
                        "subtotal": "41664元",
                    }
                ],
                "total": "41664元",
            }

            specific_merged = MODULE.apply_addendum_layers(specific_payload, addenda_root)
            generic_merged = MODULE.apply_addendum_layers(generic_payload, addenda_root)

        self.assertEqual(
            specific_merged["items"][0]["addendum_decisions"]["constraints"][0]["title"],
            "针式铰链铝框门尺寸限制",
        )
        self.assertNotIn("addendum_decisions", generic_merged["items"][0])

    def test_apply_layer_does_not_misclassify_generic_structured_frame_door_as_specific_subtype(self) -> None:
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
                                "page": 221,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "藤编门尺寸限制",
                                "detail": "藤编门：单扇门宽≤560mm，门高≤2300mm；藤面高度每700mm需加一根暗称。",
                                "trigger_terms": ["藤编门"],
                                "required_fields": [],
                                "tags": ["门型", "尺寸阈值"],
                                "relevance_score": 10,
                            },
                            {
                                "page": 224,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "美式玻璃门尺寸限制",
                                "detail": "美式玻璃门：300mm＜单扇门宽≤560mm；无中横门高≤2200mm；带中横门高≤2300mm。",
                                "trigger_terms": ["美式玻璃门"],
                                "required_fields": [],
                                "tags": ["门型", "尺寸阈值", "玻璃门"],
                                "relevance_score": 10,
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
                        "product": "拼框门衣柜",
                        "confirmed": "普通拼框门，高2200mm，宽500mm",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 2.0 * 2.2 * 8680 = 38192"],
                        "subtotal": "38192元",
                    }
                ],
                "total": "38192元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        self.assertNotIn("addendum_decisions", merged["items"][0])

    def test_apply_layer_matches_narrow_edge_disassembly_clearance_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 50,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "窄边风格拆装时门盖牙称与顶挡条最少留出15mm",
                                "detail": "窄边风格拆装柜体中，门盖牙称与顶挡条时，最少需要留出15mm。",
                                "trigger_terms": ["窄边风格", "牙称", "顶挡条"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "窄边"],
                                "relevance_score": 10,
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "窄边风格拆装斗柜",
                        "confirmed": "窄边风格，门盖牙称，带顶挡条",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "窄边风格拆装时门盖牙称与顶挡条最少留出15mm")

    def test_apply_layer_does_not_misclassify_generic_cabinet_as_narrow_edge_clearance_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 50,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "窄边风格拆装时门盖牙称与顶挡条最少留出15mm",
                                "detail": "窄边风格拆装柜体中，门盖牙称与顶挡条时，最少需要留出15mm。",
                                "trigger_terms": ["窄边风格", "牙称", "顶挡条"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "窄边"],
                                "relevance_score": 10,
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "普通斗柜",
                        "confirmed": "常规斗柜，平板门",
                        "pricing_method": "投影面积计价",
                        "calculation_steps": ["基础价格 = 5600"],
                        "subtotal": "5600元",
                    }
                ],
                "total": "5600元",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        self.assertNotIn("addendum_decisions", merged["items"][0])

    def test_apply_layer_matches_new_modern_edge_structure_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 34,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "新现代边角风格柜体默认顶盖侧结构，侧盖顶需特殊备注",
                                "detail": "新现代边角风格柜体默认为顶盖侧结构；如需侧盖顶结构，必须特殊备注。",
                                "trigger_terms": ["新现代边角", "顶盖侧", "侧盖顶"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "边角"],
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "新现代边角电视柜",
                        "confirmed": "新现代边角风格，柜体结构待确认",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "新现代边角风格柜体默认顶盖侧结构，侧盖顶需特殊备注")

    def test_apply_layer_matches_cable_grommet_clearance_constraint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 128,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "走线圆口规格与距边要求",
                                "detail": "走线圆口可用于书桌、书柜等家具穿线；直径规格为50/60/80mm，无标注默认50mm；柜体中的走线口和检修口需距边≥50mm；到顶柜体顶板如有可拆卸式检修口盖板，封边条尺寸需≥30mm。",
                                "trigger_terms": ["走线圆口", "检修口", "距边", "封边条"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "走线"],
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "书柜",
                        "confirmed": "书柜带走线圆口，检修口待定",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "走线圆口规格与距边要求")

    def test_apply_layer_matches_glass_drawer_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 159,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "玻璃抽屉尺寸与开启方式限制",
                                "detail": "玻璃抽屉为玻璃+木质平板组合抽面抽屉，长虹玻璃不可使用；有扣手时抽面厚26mm，无扣手时厚22mm；抽面长度≤1040mm，长度＞600mm时中间需加底称；150mm≤抽面高度≤350mm，木抽面高度需≥80mm；可使用扣手、明装拉手、按弹开启；使用明装拉手且抽面长度＞600mm时，建议使用双孔长拉手或2个单孔拉手。",
                                "trigger_terms": ["玻璃抽屉", "扣手", "明装拉手", "按弹开启"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "抽屉"],
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "玻璃抽屉餐边柜",
                        "confirmed": "玻璃抽屉，明装拉手",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "玻璃抽屉尺寸与开启方式限制")

    def test_apply_layer_matches_book_ladder_bookcase_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 97,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "书梯书柜尺寸与滑轨安装要求",
                                "detail": "带有书梯的书柜高度建议≥2800mm；爬梯宽度500mm，爬梯总长≤2600mm；爬梯滑轨安装板净高度要求≥80mm，超高柜体如分段在上，分缝处应在滑轨安装板下方；梯子底部内侧距离书柜前侧450-500mm，默认450mm；滑轨安装板默认平板无造型，如做造型需备注并附尺寸图；轨道支架处需留白不做造型；书梯分为可回收和不可回收两种，下单需明确备注。",
                                "trigger_terms": ["书梯", "滑轨", "滑轨安装板", "可回收书梯"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "书梯"],
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "书梯书柜",
                        "confirmed": "带书梯，滑轨安装板待确认",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "书梯书柜尺寸与滑轨安装要求")

    def test_apply_layer_matches_tray_drawer_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "rules": [
                            {
                                "page": 170,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "托盘抽尺寸与开启方式限制",
                                "detail": "托盘抽主要用于书桌键盘抽、储物柜或餐边柜拉出平台；抽面厚度22mm；66mm≤抽面高度≤128mm；抽面上沿至托盘上沿高差20mm≤C≤60mm；抽面长度≤1050mm；承重30kg；可使用扣手、明装拉手；使用明装拉手且抽面长度＞600mm时，建议使用双孔长拉手或2个单孔拉手；适用海蒂诗全拉出阻尼托底轨，规格250-500mm。",
                                "trigger_terms": ["托盘抽", "键盘抽", "拉出平台", "明装拉手"],
                                "required_fields": [],
                                "tags": ["柜体", "尺寸阈值", "抽屉"],
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
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
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
                        "product": "餐边柜托盘抽",
                        "confirmed": "托盘抽，明装拉手",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "托盘抽尺寸与开启方式限制")

    def test_apply_layer_matches_radar_switch_material_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-accessory"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-accessory",
                        "layer_name": "设计师追加规则 Accessory",
                        "rules": [
                            {
                                "page": 289,
                                "domain": "accessory",
                                "action_type": "constraint",
                                "title": "可隔门板手扫雷达开关适用材质与灯带范围",
                                "detail": "24V驱动款可隔门板手扫雷达开关可隐藏于柜内，支持暗装手扫或明装触摸；适用约25mm以内的木材、玻璃、石材、亚克力，不适用金属材质板材及金属包覆板；适用于所有型号的单色温灯带，不可调节色温和亮度。",
                                "trigger_terms": ["手扫雷达开关", "门板", "石材板", "单色温灯带"],
                                "required_fields": ["材质"],
                                "tags": ["配件", "灯带", "开关", "材质"],
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
                        "layer_id": "designer-accessory",
                        "layer_name": "设计师追加规则 Accessory",
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
                        "product": "手扫雷达开关",
                        "confirmed": "可隔门板手扫雷达开关，用于石材板",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        constraints = merged["items"][0]["addendum_decisions"]["constraints"]
        self.assertEqual(constraints[0]["title"], "可隔门板手扫雷达开关适用材质与灯带范围")

    def test_actual_runtime_rules_include_new_specific_door_panel_constraints_and_exclude_noise_pages(self) -> None:
        runtime_payload = json.loads(RUNTIME_RULES_PATH.read_text(encoding="utf-8"))
        rules = runtime_payload["rules"]
        titles = {str(rule.get("title", "")) for rule in rules}
        pages = {int(rule.get("page", -1)) for rule in rules}
        details = [str(rule.get("detail", "")) for rule in rules]
        titles_by_page: dict[int, set[str]] = {}
        for rule in rules:
            page = int(rule.get("page", -1))
            titles_by_page.setdefault(page, set()).add(str(rule.get("title", "")))

        self.assertIn("针式铰链铝框门尺寸限制", titles)
        self.assertIn("铝框岩板门尺寸限制", titles)
        self.assertIn("超高拼框木门尺寸限制", titles)
        self.assertIn("拱形玻璃门尺寸限制", titles)
        self.assertIn("胶囊玻璃门尺寸限制", titles)
        self.assertIn("超高拼框玻璃门尺寸限制", titles)
        self.assertIn("藤编门尺寸限制", titles)
        self.assertIn("拱形藤编门尺寸限制", titles)
        self.assertIn("美式木门尺寸限制", titles)
        self.assertIn("美式玻璃门尺寸限制", titles)
        self.assertIn("窄边风格拆装时门盖牙称与顶挡条最少留出15mm", titles)
        self.assertIn("新现代边角风格柜体默认顶盖侧结构，侧盖顶需特殊备注", titles)
        self.assertIn("走线圆口规格与距边要求", titles)
        self.assertIn("榻榻米组合柜空区加托称时需固定上墙", titles)
        self.assertIn("柜侧前开口尺寸限制", titles)
        self.assertIn("柜侧前缺口尺寸限制", titles)
        self.assertIn("柜侧闭合缺口尺寸限制", titles)
        self.assertIn("超高带门柜体开放格分段缝优先对齐层板上方", titles)
        self.assertIn("遇见书柜下柜高度超过1700mm时不建议做侧包顶底", titles)
        self.assertIn("常规拆装柜体高度≤1700mm默认顶盖侧，＞1700mm默认侧盖顶", titles)
        self.assertIn("常规拆装柜体牙称常用50/80mm，允许范围50-250mm", titles)
        self.assertIn("玻璃抽屉尺寸与开启方式限制", titles)
        self.assertIn("书梯书柜尺寸与滑轨安装要求", titles)
        self.assertIn("托盘抽尺寸与开启方式限制", titles)
        self.assertIn("可隔门板手扫雷达开关适用材质与灯带范围", titles)
        self.assertNotIn("榻榻米组合柜空区适用于该托称添加规则，但添加托称的组合柜需配合 固定上墙", titles)
        self.assertNotIn("参考铰链", titles)
        self.assertNotIn("方剩余板件宽度不小于侧板宽度的1", titles)
        self.assertNotIn("情况开放格区域层板内凹，层板外沿与门板不齐平。为提高家具结构稳定性及保", titles)
        self.assertNotIn("遇见书柜-上柜顶底包侧", titles)
        self.assertNotIn("其他特殊情况可调整牙称高度", titles)
        self.assertNotIn("铝框门、天地铰链铝框门和、针式铰链", titles)
        self.assertNotIn("可使用扣手、明装拉手", titles_by_page.get(159, set()))
        self.assertNotIn("注意轨道", titles_by_page.get(97, set()))
        self.assertNotIn("可使用扣手、明装拉手", titles_by_page.get(170, set()))
        self.assertNotIn("适用于所有型号的单色温灯带", titles_by_page.get(289, set()))
        self.assertNotIn(
            "新现代边角-侧边平齐 本 工 + IMS Tw ol PATER CEE QP ds 3k 抽屉间空隙为18mm新现代边角 -侧边平齐 MIST ey RE 由二",
            titles,
        )
        self.assertNotIn("为方便查看尺寸，尺寸图中边角为直边，实物为圆边，可参考下页实物图与渲染图", titles)
        self.assertNotIn("层板 层板 层板 层板前 托 称后 托 称 前 托 称后 托 称前托称 后托称 前托称 后托称 走线圆口", titles)
        self.assertTrue(all("经典木门/拱形木门/胶囊木门" not in detail for detail in details))
        self.assertNotIn(1, pages)
        self.assertNotIn(20, pages)
        self.assertNotIn(78, pages)
        self.assertNotIn(284, pages)

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

    def test_apply_layer_requires_specific_match_before_generic_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-generic"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-generic",
                        "layer_name": "设计师追加规则 Generic",
                        "rules": [
                            {
                                "page": 188,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "美式木门尺寸限制",
                                "detail": "单扇门宽≤560mm，无中横门高≤1700mm。",
                                "trigger_terms": ["门型", "高度", "宽度"],
                                "match_terms_specific": ["美式木门"],
                                "match_terms_generic": ["门型", "高度", "宽度"],
                                "required_fields": ["高度", "宽度", "门型"],
                                "tags": ["门型"],
                                "relevance_score": 9,
                                "user_summary": "美式木门这条要按专门尺寸限制判断。",
                                "question_template": "这组门板还需要确认具体门型。",
                                "evidence_level": "hard_rule",
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
                        "layer_id": "designer-generic",
                        "layer_name": "设计师追加规则 Generic",
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
                        "product": "柜门",
                        "confirmed": "高2.2米，宽500，不做拉手",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        self.assertNotIn("addendum_decisions", merged["items"][0])

    def test_apply_layer_uses_question_template_and_keeps_single_core_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-question"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-question",
                        "layer_name": "设计师追加规则 Question",
                        "rules": [
                            {
                                "page": 177,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "其他无把手、无抠手柜门须明确备注开启方式",
                                "detail": "其他无把手、无抠手柜门都要明确备注开启方式。",
                                "trigger_terms": ["无把手", "无抠手", "开启方式"],
                                "match_terms_specific": ["无把手", "无抠手"],
                                "match_terms_generic": ["开启方式"],
                                "required_fields": ["开启方式", "开启方向"],
                                "tags": ["门型"],
                                "relevance_score": 9,
                                "user_summary": "这组无把手柜门不能直接继续判断，需要先确认开启方式。",
                                "question_template": "这组柜门还需要确认开启方式。",
                                "evidence_level": "hard_rule",
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
                        "layer_id": "designer-question",
                        "layer_name": "设计师追加规则 Question",
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
                        "confirmed": "无把手，开启方向未知",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        follow_ups = merged["items"][0]["addendum_decisions"]["follow_up_questions"]
        self.assertEqual(len(follow_ups), 1)
        self.assertEqual(follow_ups[0]["question"], "这组柜门还需要确认开启方式。")

    def test_apply_layer_drops_adjustments_when_hard_constraint_already_matched(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-priority"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-priority",
                        "layer_name": "设计师追加规则 Priority",
                        "rules": [
                            {
                                "page": 125,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "玻璃抽屉尺寸与开启方式限制",
                                "detail": "玻璃抽屉长度≤1040mm，长度＞600mm时中间需加底称。",
                                "trigger_terms": ["玻璃抽屉", "抽屉"],
                                "match_terms_specific": ["玻璃抽屉"],
                                "match_terms_generic": ["抽屉"],
                                "required_fields": [],
                                "tags": ["抽屉"],
                                "relevance_score": 9,
                                "user_summary": "这组玻璃抽屉要先按专项尺寸限制判断。",
                                "question_template": "",
                                "evidence_level": "hard_rule",
                            },
                            {
                                "page": 126,
                                "domain": "cabinet",
                                "action_type": "adjustment",
                                "title": "抽屉长度超过600mm建议双孔长拉手",
                                "detail": "使用明装拉手且抽面长度＞600mm时，建议双孔长拉手或2个单孔拉手。",
                                "trigger_terms": ["抽屉", "拉手"],
                                "match_terms_specific": ["玻璃抽屉"],
                                "match_terms_generic": ["抽屉", "拉手"],
                                "required_fields": [],
                                "tags": ["抽屉", "拉手"],
                                "relevance_score": 7,
                                "user_summary": "如果后面做明装拉手，再补充看拉手建议。",
                                "question_template": "",
                                "evidence_level": "hard_rule",
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
                        "layer_id": "designer-priority",
                        "layer_name": "设计师追加规则 Priority",
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
                        "product": "玻璃抽屉书柜",
                        "confirmed": "玻璃抽屉，长度800，明装拉手",
                        "pricing_method": "规则咨询",
                        "calculation_steps": [],
                        "subtotal": "待确认",
                    }
                ],
                "total": "待确认",
            }

            merged = MODULE.apply_addendum_layers(payload, addenda_root)

        decisions = merged["items"][0]["addendum_decisions"]
        self.assertEqual(len(decisions["constraints"]), 1)
        self.assertEqual(decisions["constraints"][0]["title"], "玻璃抽屉尺寸与开启方式限制")
        self.assertEqual(decisions["adjustments"], [])


if __name__ == "__main__":
    unittest.main()
