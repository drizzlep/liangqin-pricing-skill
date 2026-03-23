import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_addendum_runtime_rules.py"
SPEC = importlib.util.spec_from_file_location("build_addendum_runtime_rules", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildAddendumRuntimeRulesTests(unittest.TestCase):
    def test_build_runtime_rules_includes_catalog_option_entries(self) -> None:
        index = {
            "entries": [
                {
                    "page": 279,
                    "domain": "table",
                    "clean_title": "岩板可选色样",
                    "excerpt": "可选色样：圣勃朗鱼肚白、保加利亚浅灰、劳伦特黑金、极光黑、极光白、阿勒山闪电黑。",
                    "tags": ["岩板", "餐桌"],
                    "response_kind": "catalog_option",
                    "runtime_relevant": True,
                    "relevance_score": 6,
                    "pricing_relevant": False,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-option", layer_name="设计师追加规则 Option")

        self.assertEqual(len(payload["rules"]), 1)
        self.assertEqual(payload["rules"][0]["action_type"], "catalog_option")
        self.assertIn("圣勃朗鱼肚白", payload["rules"][0]["detail"])

    def test_build_runtime_rules_generates_structured_entries(self) -> None:
        index = {
            "entries": [
                {
                    "page": 10,
                    "domain": "bed",
                    "clean_title": "床垫重量应≤50kg",
                    "excerpt": "床垫超重需改用两套750N举升器并单独收费",
                    "tags": ["床垫", "举升器"],
                    "relevance_score": 9,
                    "pricing_relevant": True,
                },
                {
                    "page": 11,
                    "domain": "bed",
                    "clean_title": "需先确认床垫重量",
                    "excerpt": "如果客户未提供床垫重量，应先追问床垫重量",
                    "tags": ["床垫", "举升器"],
                    "relevance_score": 8,
                    "pricing_relevant": True,
                },
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-a", layer_name="设计师追加规则 A")

        self.assertEqual(payload["layer_id"], "designer-a")
        self.assertEqual(len(payload["rules"]), 2)
        self.assertEqual(payload["rules"][0]["action_type"], "constraint")
        self.assertIn("床垫重量", payload["rules"][0]["required_fields"])
        self.assertEqual(payload["rules"][1]["action_type"], "follow_up")

    def test_main_writes_json(self) -> None:
        index = {
            "entries": [
                {
                    "page": 8,
                    "domain": "cabinet",
                    "clean_title": "流云门板纹理连续超过0.9m需补差",
                    "excerpt": "流云/飞瀑平板门纹理连续超过0.9m时按平板门差价补差",
                    "tags": ["柜体", "流云", "平板门"],
                    "relevance_score": 9,
                    "pricing_relevant": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "rules-index.json"
            output_path = Path(tmpdir) / "runtime-rules.json"
            input_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

            exit_code = MODULE.main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--layer-id",
                    "designer-b",
                    "--layer-name",
                    "设计师追加规则 B",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["layer_name"], "设计师追加规则 B")
        self.assertEqual(payload["rules"][0]["action_type"], "adjustment")

    def test_build_runtime_rules_cleans_noisy_title_from_detail(self) -> None:
        index = {
            "entries": [
                {
                    "page": 297,
                    "domain": "accessory",
                    "clean_title": "1.打开米家APP，",
                    "excerpt": "1.打开米家APP，点击首页右上角“+”选择添加设备。无线单面板动能开关适用于所有型号的单色温灯带。",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 5,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-c", layer_name="设计师追加规则 C")

        self.assertIn("无线单面板动能开关", payload["rules"][0]["title"])
        self.assertNotIn("打开米家APP", payload["rules"][0]["title"])

    def test_build_runtime_rules_keeps_explicit_rule_title_when_it_is_already_clear(self) -> None:
        index = {
            "entries": [
                {
                    "page": 177,
                    "domain": "door_panel",
                    "clean_title": "3.除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。",
                    "excerpt": "3.除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。 平板门后均有穿带结构，因此以下平板门门型均不可做推拉门。",
                    "tags": ["门型"],
                    "relevance_score": 7,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-d", layer_name="设计师追加规则 D")

        self.assertIn("须明确备注开启方式", payload["rules"][0]["title"])

    def test_build_runtime_rules_strips_numeric_prefix_noise(self) -> None:
        index = {
            "entries": [
                {
                    "page": 21,
                    "domain": "cabinet",
                    "clean_title": "2分别连续。该情况需提前与客户沟通确认。无备注时，默认从分段处断开连纹。",
                    "excerpt": "2分别连续。该情况需提前与客户沟通确认。无备注时，默认从分段处断开连纹。",
                    "tags": ["材质", "尺寸阈值"],
                    "relevance_score": 6,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-e", layer_name="设计师追加规则 E")

        self.assertFalse(payload["rules"][0]["title"].startswith("2"))
        self.assertIn("默认从分段处断开连纹", payload["rules"][0]["title"])

    def test_build_runtime_rules_prefers_clear_bed_limiter_title(self) -> None:
        index = {
            "entries": [
                {
                    "page": 363,
                    "domain": "bed",
                    "clean_title": "床垫限位器床",
                    "excerpt": "50*80*260mm（黑色）；尾翻箱体床限位器安装于床头方向，尾翻床床垫宽度＜1500mm时安装1个，床垫宽度≥1500mm时安装2个；侧翻箱体床限位器安装于侧面，安装2个。",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 8,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-f", layer_name="设计师追加规则 F")

        self.assertIn("尾翻箱体床限位器安装于床头方向", payload["rules"][0]["title"])
        self.assertNotEqual(payload["rules"][0]["title"], "床垫限位器床")

    def test_build_runtime_rules_excludes_introductory_background_entry(self) -> None:
        index = {
            "entries": [
                {
                    "page": 1,
                    "domain": "material",
                    "clean_title": "良禽佳木设计师标准手册",
                    "excerpt": "前言 良禽佳木设计师标准手册 版本20260322 原木定制三大误区 木材小知识",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 5,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-g", layer_name="设计师追加规则 G")

        self.assertEqual(payload["rules"], [])

    def test_build_runtime_rules_excludes_material_grading_knowledge_entry(self) -> None:
        index = {
            "entries": [
                {
                    "page": 11,
                    "domain": "material",
                    "clean_title": "4英寸宽2英尺长。净划面数量根据板材的尺寸而定，",
                    "excerpt": "4英寸宽2英尺长。净划面数量根据板材的尺寸而定， NHLA分等规则 了解NHLA分等规则 以下图片描述了美国硬木的一些特征。",
                    "tags": ["材质", "尺寸阈值"],
                    "relevance_score": 9,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-m", layer_name="设计师追加规则 M")

        self.assertEqual(payload["rules"], [])

    def test_build_runtime_rules_excludes_ocr_gibberish_entry(self) -> None:
        index = {
            "entries": [
                {
                    "page": 20,
                    "domain": "door_panel",
                    "clean_title": "N Ne i 5 —— Se A dare le |",
                    "excerpt": "2s —— — Mb Tr N Ne i 5 —— Se A dare le | Ts eae Sa. Was monies oe |",
                    "tags": ["门型", "尺寸阈值"],
                    "relevance_score": 5,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-h", layer_name="设计师追加规则 H")

        self.assertEqual(payload["rules"], [])

    def test_build_runtime_rules_excludes_fragmented_lookup_table_entry(self) -> None:
        index = {
            "entries": [
                {
                    "page": 203,
                    "domain": "general",
                    "clean_title": "26 60拼框平开门尺寸限制快速检索表-a",
                    "excerpt": "26 60拼框平开门尺寸限制快速检索表-a 单位：mm ≤560",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 5,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-i", layer_name="设计师追加规则 I")

        self.assertEqual(payload["rules"], [])

    def test_build_runtime_rules_keeps_accessory_rule_after_stripping_setup_steps(self) -> None:
        index = {
            "entries": [
                {
                    "page": 297,
                    "domain": "accessory",
                    "clean_title": "1.打开米家APP，",
                    "excerpt": "1.打开米家APP，点击首页右上角“+”选择添加设备。无线单面板动能开关适用于所有型号的单色温灯带，可调节光的亮度，不能调节光的色温。",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 5,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-j", layer_name="设计师追加规则 J")

        self.assertEqual(len(payload["rules"]), 1)
        self.assertEqual(payload["rules"][0]["title"], "无线单面板动能开关")
        self.assertNotIn("打开米家APP", payload["rules"][0]["detail"])

    def test_build_runtime_rules_excludes_code_heavy_fragment_table(self) -> None:
        index = {
            "entries": [
                {
                    "page": 78,
                    "domain": "cabinet",
                    "clean_title": "1-15045 25 150 40DG-02 DG-06 DG-10",
                    "excerpt": "1-15045 25 150 40DG-02 DG-06 DG-10 DSG-03 CTG-01 CTG-03 CBG-04 DSG-08 CBG-07 XSG-04",
                    "tags": ["柜体", "尺寸阈值"],
                    "relevance_score": 8,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-k", layer_name="设计师追加规则 K")

        self.assertEqual(payload["rules"], [])

    def test_build_runtime_rules_prefers_named_accessory_over_control_phrase(self) -> None:
        index = {
            "entries": [
                {
                    "page": 297,
                    "domain": "accessory",
                    "clean_title": "1.打开米家APP，",
                    "excerpt": "1.打开米家APP，点击首页右上角“+”选择添加设备，连接成功后就可以手动控制灯带开关灯/色温/亮度等 无线单面板动能开关 •产品编号：白色：05.637.0011；灰色：05.637.0013 •该开关为无线开关，控制方式为单击灯亮，单击灯灭，长按调节亮度; •适用于所有型号的单色温灯带，可调节光的亮度，不能调节光的色温；",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 5,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-l", layer_name="设计师追加规则 L")

        self.assertEqual(len(payload["rules"]), 1)
        self.assertEqual(payload["rules"][0]["title"], "无线单面板动能开关")
        self.assertNotIn("控制灯带开关", payload["rules"][0]["title"])

    def test_build_runtime_rules_extracts_opening_method_as_required_field(self) -> None:
        index = {
            "entries": [
                {
                    "page": 177,
                    "domain": "door_panel",
                    "clean_title": "3.除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。",
                    "excerpt": "3.除已说明的默认开启方式（如流云门默认为按弹开启），其他无把手、无抠手柜门，除说明开启方向外，须明确备注开启方式。",
                    "tags": ["门型"],
                    "relevance_score": 7,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-n", layer_name="设计师追加规则 N")

        self.assertEqual(len(payload["rules"]), 1)
        self.assertIn("开启方式", payload["rules"][0]["required_fields"])
        self.assertIn("无把手", payload["rules"][0]["trigger_terms"])
        self.assertIn("无抠手", payload["rules"][0]["trigger_terms"])

    def test_build_runtime_rules_does_not_infer_mattress_weight_from_limiter_rule(self) -> None:
        index = {
            "entries": [
                {
                    "page": 363,
                    "domain": "bed",
                    "clean_title": "床垫限位器床",
                    "excerpt": "50*80*260mm（黑色）；尾翻箱体床限位器安装于床头方向，尾翻床床垫宽度＜1500mm时安装1个，床垫宽度≥1500mm时安装2个；侧翻箱体床限位器安装于侧面，安装2个。",
                    "tags": ["尺寸阈值"],
                    "relevance_score": 8,
                    "pricing_relevant": True,
                }
            ]
        }

        payload = MODULE.build_runtime_rules(index, layer_id="designer-o", layer_name="设计师追加规则 O")

        self.assertEqual(len(payload["rules"]), 1)
        self.assertNotIn("床垫重量", payload["rules"][0]["required_fields"])


if __name__ == "__main__":
    unittest.main()
