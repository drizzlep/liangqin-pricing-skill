import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "query_addendum_guidance.py"
ACTUAL_ADDENDA_ROOT = Path(__file__).resolve().parents[1] / "references" / "addenda"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("query_addendum_guidance", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QueryAddendumGuidanceTests(unittest.TestCase):
    def test_query_guidance_returns_boundary_reply_for_hardware_brand_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = MODULE.query_guidance(
                "良禽佳木可以选国产五金和进口五金吗？良禽有BLUM的五金，是什么啊？",
                Path(tmpdir),
            )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["answer_style"], "natural_rule_explanation")
        self.assertIn("现有良禽资料", payload["suggested_reply"])
        self.assertIn("未明确", payload["suggested_reply"])
        self.assertIn("设计师或门店确认", payload["suggested_reply"])
        self.assertNotIn("BLUMOTION", payload["suggested_reply"])
        self.assertNotIn("CLIP top", payload["suggested_reply"])

    def test_query_guidance_returns_boundary_reply_for_source_attribution_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = MODULE.query_guidance(
                "你刚才说的五金配置，这条到底是良禽资料，还是行业常识？资料来源是哪里？",
                Path(tmpdir),
            )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertIn("不能算良禽资料结论", payload["suggested_reply"])
        self.assertIn("现有良禽资料", payload["suggested_reply"])

    def test_query_guidance_adds_natural_answer_for_runtime_constraint(self) -> None:
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

            payload = MODULE.query_guidance(
                "窄边风格柜体门板要盖到顶挡条，现场安装怕打架，需要提前留多少？",
                addenda_root,
            )

        self.assertEqual(payload["answer_style"], "natural_rule_explanation")
        self.assertEqual(payload["evidence_level"], "hard_rule")
        self.assertIn("至少预留15mm", payload["answer_summary"])
        self.assertIn("明确要求", payload["answer_summary"])
        self.assertEqual(payload["confidence_note"], "")

    def test_query_guidance_falls_back_to_knowledge_entry_for_narrow_edge_slot_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-cabinet"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {"layer_id": "designer-cabinet", "layer_name": "设计师追加规则 Cabinet", "rules": []},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            knowledge_path = reports_dir / "knowledge-layer.json"
            knowledge_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-cabinet",
                        "layer_name": "设计师追加规则 Cabinet",
                        "entries": [
                            {
                                "topic": "直角圆边窄边高柜凹槽内退尺寸提示",
                                "answerable_summary": "直角圆边窄边高柜这组节点，当前能确认存在凹槽内退尺寸约束。现有复盘里能稳定读到的尺寸包括上节点20/8/12、下节点12/6/8；其中20mm更倾向于顶挡条可见高度或宽度相关尺寸，但术语口径还没完全锁定。",
                                "evidence_level": "high_confidence_review",
                                "source_pages": [48, 49],
                                "trigger_terms": ["直角圆边", "窄边高柜", "凹槽内退尺寸", "节点尺寸"],
                                "do_not_overclaim": "不要把20mm直接说成已经锁定名称的工艺死规则。",
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
                        "artifacts": {
                            "runtime_rules_file": str(runtime_rules_path),
                            "knowledge_layer_file": str(knowledge_path),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.query_guidance(
                "直角圆边的窄边高柜，凹槽内退尺寸有没有什么要注意的？",
                addenda_root,
            )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["answer_style"], "natural_rule_explanation")
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("凹槽内退尺寸约束", payload["answer_summary"])
        self.assertIn("20/8/12", payload["answer_summary"])
        self.assertIn("术语口径还没完全锁定", payload["confidence_note"])
        self.assertEqual(payload["constraints"], [])

    def test_query_guidance_answers_node_dimensions_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "窄边高柜做直角圆边的时候，上下节点尺寸有没有固定要求？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertIn("12/12/8", payload["answer_summary"])
        self.assertIn("20/8/12", payload["answer_summary"])
        self.assertIn("12/6/8", payload["answer_summary"])
        self.assertIn("20mm", payload["confidence_note"])

    def test_query_guidance_answers_lighting_switch_guidance_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "灯带开关下单时怎么备注安装位置？如果客户还没定位置，是不是可以写现场确定？另外做分区控制是不是要额外收费？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("优先选用有线开关", payload["answer_summary"])
        self.assertIn("现场确定开关位置", payload["answer_summary"])
        self.assertIn("分区控制", payload["answer_summary"])
        self.assertIn("额外收费", payload["answer_summary"])

    def test_query_guidance_answers_hand_sweep_switch_installation_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "可隔门板手扫雷达开关一般怎么安装？能不能底装在岩板下面，或者侧装在侧板里？正面明装是不是就按触摸开关用？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("底装", payload["answer_summary"])
        self.assertIn("侧装", payload["answer_summary"])
        self.assertIn("触摸开关", payload["answer_summary"])

    def test_query_guidance_answers_integrated_switch_series_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "12mm集控感应开关这组一共有几款？人体红外和手扫、触摸这几种有什么区别？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("三种常见类型", payload["answer_summary"])
        self.assertIn("人体红外", payload["answer_summary"])
        self.assertIn("手扫", payload["answer_summary"])
        self.assertIn("触摸", payload["answer_summary"])

    def test_query_guidance_answers_lift_inner_space_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "箱体床做小蜻蜓举升器时，内空高度和内空长度有没有最低要求？中间那段长度能不能做可开启床屉板？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("196mm", payload["answer_summary"])
        self.assertIn("950mm", payload["answer_summary"])
        self.assertIn("不能做可开启床屉板", payload["answer_summary"])

    def test_query_guidance_answers_slat_frame_quantity_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "所有床的排骨架如果床宽超过1450，是不是默认双块？排骨条宽度是不是统一80mm？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("1450mm", payload["answer_summary"])
        self.assertIn("双块排骨架", payload["answer_summary"])
        self.assertIn("80mm", payload["answer_summary"])

    def test_query_guidance_answers_drawer_face_pairing_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "抽屉如果上下左右四边都内嵌，抽面一般做多厚？如果是26厚门板配22mm抽屉，抽面怎么处理？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("22 厚", payload["answer_summary"])
        self.assertIn("全盖层板", payload["answer_summary"])
        self.assertIn("26 厚", payload["answer_summary"])

    def test_query_guidance_answers_sliding_door_inset_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "推拉门如果是22厚门板，直边圆边和内斜边分别要内缩多少？单小块门板宽度有没有上限？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("60mm", payload["answer_summary"])
        self.assertIn("65mm", payload["answer_summary"])
        self.assertIn("600mm", payload["answer_summary"])

    def test_query_guidance_answers_single_small_panel_seam_limits_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "单小块门板如果外观做中缝，宽度一般能放到多大？如果不做中缝是不是就要控制得更窄？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("450mm", payload["answer_summary"])
        self.assertIn("600mm", payload["answer_summary"])
        self.assertIn("无中缝", payload["answer_summary"])

    def test_query_guidance_answers_odd_door_opening_direction_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "柜门数量是单数的时候，图纸是不是一定要标开启方向？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("单数", payload["answer_summary"])
        self.assertIn("开启方向", payload["answer_summary"])
        self.assertIn("图纸", payload["answer_summary"])

    def test_query_guidance_answers_drawer_desk_clearance_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "带抽屉书桌如果桌长做到1400以上，桌下抽屉内部空间是不是会变小？要提前注意多少？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("1400mm", payload["answer_summary"])
        self.assertIn("钢管", payload["answer_summary"])
        self.assertIn("25mm", payload["answer_summary"])

    def test_query_guidance_answers_parallel_desk_segment_guidance_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "定制并立书桌如果桌长做得比较长，要不要分段或者做拆装？入户搬运这块怎么提醒客户？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("2000mm", payload["answer_summary"])
        self.assertIn("2400mm", payload["answer_summary"])
        self.assertIn("拆装结构", payload["answer_summary"])
        self.assertIn("分段", payload["answer_summary"])

    def test_query_guidance_answers_lift_desk_power_guidance_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "升降桌设计时电源怎么预留？如果客户家插座离得远，现场能不能直接改线或者剪插头？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertEqual(payload["constraints"], [])
        self.assertIn("3.3m", payload["answer_summary"])
        self.assertIn("预留插座", payload["answer_summary"])
        self.assertIn("插线板", payload["answer_summary"])
        self.assertIn("现场接线", payload["answer_summary"])

    def test_query_guidance_answers_mattress_limiter_installation_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "尾翻箱体床和侧翻箱体床的床垫限位器一般装几个、装在哪边？规格大概是多少？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("50*80*260", payload["answer_summary"])
        self.assertIn("床头方向", payload["answer_summary"])
        self.assertIn("锁扣相反方向", payload["answer_summary"])
        self.assertIn("1500mm", payload["answer_summary"])

    def test_query_guidance_answers_luopang_dimension_marking_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "罗胖系列桌子下单出图时尺寸应该标桌面还是支腿？支腿和桌面默认差多少？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("桌面或凳面尺寸", payload["answer_summary"])
        self.assertIn("不要标注支腿尺寸", payload["answer_summary"])
        self.assertIn("10mm", payload["answer_summary"])

    def test_query_guidance_answers_wall_mounted_desk_guidance_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "挂墙书桌是不是必须固定在承重墙上？订制的话桌面边角能不能改，容腿空间一般怎么留？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("固定在承重墙上", payload["answer_summary"])
        self.assertIn("桌面边角", payload["answer_summary"])
        self.assertIn("580mm", payload["answer_summary"])
        self.assertIn("隐藏支架", payload["answer_summary"])

    def test_query_guidance_answers_luopang_drawer_table_dimensions_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "罗胖带屉餐桌或者罗胖书桌，屉柜一般多宽多深多高？跟桌面长宽怎么对应？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("屉柜总长", payload["answer_summary"])
        self.assertIn("L-160", payload["answer_summary"])
        self.assertIn("400", payload["answer_summary"])
        self.assertIn("600", payload["answer_summary"])
        self.assertIn("300mm", payload["answer_summary"])

    def test_query_guidance_answers_luopang_table_custom_limits_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "罗胖餐桌或者罗胖书桌如果做订制，长度和宽度上限一般按多少理解？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("2000mm", payload["answer_summary"])
        self.assertIn("900mm", payload["answer_summary"])

    def test_query_guidance_answers_round_table_and_jianmei_max_sizes_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "经典圆餐桌和简美大桌如果做订制，尺寸上限一般到哪里？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("桌面直径通常不超过 1400mm", payload["answer_summary"])
        self.assertIn("长度不超过 2100mm", payload["answer_summary"])
        self.assertIn("宽度不超过 900mm", payload["answer_summary"])

    def test_query_guidance_answers_parallel_desk_no_drawer_limits_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "定制并立书桌如果做无屉款，最长能做到多少，宽度有没有上限？横称高度一般怎么跟桌长对应？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("2200mm", payload["answer_summary"])
        self.assertIn("600mm", payload["answer_summary"])
        self.assertIn("横称高度", payload["answer_summary"])
        self.assertIn("50", payload["answer_summary"])
        self.assertIn("100", payload["answer_summary"])

    def test_query_guidance_answers_legless_desk_fixing_and_limits_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "定制无腿书桌要怎么固定？能不能做抽屉？桌长、进深和高度大概有什么限制？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("承重墙", payload["answer_summary"])
        self.assertIn("左右固定到柜子", payload["answer_summary"])
        self.assertIn("1800mm", payload["answer_summary"])
        self.assertIn("600mm", payload["answer_summary"])
        self.assertIn("150mm", payload["answer_summary"])

    def test_query_guidance_answers_child_furniture_safety_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "儿童家具如果做拉手、翻门和玻璃，有没有什么限制？藤编网布这些能不能用在孩子能碰到的位置？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("优先使用扣手", payload["answer_summary"])
        self.assertIn("儿童拉手", payload["answer_summary"])
        self.assertIn("藤编、网布", payload["answer_summary"])
        self.assertIn("玻璃部件", payload["answer_summary"])
        self.assertIn("1600mm", payload["answer_summary"])

    def test_query_guidance_answers_child_corner_radius_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "儿童家具外露边角一般怎么做？危险外角的圆半径和圆弧长度有没有最低要求？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("圆边圆角", payload["answer_summary"])
        self.assertIn("10mm", payload["answer_summary"])
        self.assertIn("15mm", payload["answer_summary"])

    def test_query_guidance_answers_child_bed_access_safety_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "儿童高架床的进出通道和围栏附近间隙一般怎么控？梯子最高踏步离入口大概有什么限制？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("进出通道", payload["answer_summary"])
        self.assertIn("500mm", payload["answer_summary"])
        self.assertIn("小于 7mm", payload["answer_summary"])
        self.assertIn("不大于 400mm", payload["answer_summary"])

    def test_query_guidance_answers_hinge_angle_and_note_requirements_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "海蒂诗铝框门铰链默认开多大？如果我想改成165度，是不是要另外上传图纸和备注具体门扇？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("95°", payload["answer_summary"])
        self.assertIn("165°", payload["answer_summary"])
        self.assertIn("上传", payload["answer_summary"])
        self.assertIn("哪一扇门", payload["answer_summary"])

    def test_query_guidance_answers_child_handle_styles_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "儿童房家具如果不用扣手，儿童拉手都有哪些常见款式？有没有甜甜圈、云朵、小熊这类？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("甜甜圈", payload["answer_summary"])
        self.assertIn("云朵", payload["answer_summary"])
        self.assertIn("小熊", payload["answer_summary"])
        self.assertIn("小鱼", payload["answer_summary"])

    def test_query_guidance_answers_empty_space_brace_rules_from_actual_knowledge_layer(self) -> None:
        payload = MODULE.query_guidance(
            "空区加托称时，前后托称怎么配？不同长度和高度有没有常用规则？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("前托称", payload["answer_summary"])
        self.assertIn("后托称", payload["answer_summary"])
        self.assertIn("60*26", payload["answer_summary"])
        self.assertIn("70*26", payload["answer_summary"])
        self.assertIn("80*26", payload["answer_summary"])

    def test_query_guidance_returns_rock_slab_dining_table_color_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-rock-slab-options"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-rock-slab-options",
                        "layer_name": "设计师追加规则 Rock Slab Options",
                        "rules": [
                            {
                                "page": 279,
                                "domain": "table",
                                "action_type": "catalog_option",
                                "title": "岩板餐桌可选色样",
                                "detail": "岩板餐桌当前参考 12mm 岩板可选色样：圣勃朗鱼肚白（天鹅绒面）、保加利亚浅灰（细哑面）、劳伦特黑金（粗哑面）、极光黑（粗哑面 / 模具面）、极光白（天鹅绒面 / 模具面）、阿勒山闪电黑（粗哑面+数码纹理通体）。",
                                "trigger_terms": ["岩板餐桌", "花色", "色样", "岩板"],
                                "required_fields": [],
                                "tags": ["岩板", "餐桌", "花色"],
                                "relevance_score": 8,
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
                        "layer_id": "designer-rock-slab-options",
                        "layer_name": "设计师追加规则 Rock Slab Options",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = MODULE.query_guidance(
                "岩板餐桌都有什么花色可选？",
                addenda_root,
            )

        self.assertTrue(payload["matched"])
        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "岩板餐桌可选色样")
        self.assertIn("圣勃朗鱼肚白", payload["suggested_reply"])
        self.assertIn("劳伦特黑金", payload["suggested_reply"])
        self.assertIn("极光白", payload["suggested_reply"])

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

    def test_query_guidance_returns_rock_slab_length_follow_up(self) -> None:
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

            payload = MODULE.query_guidance(
                "我要做一个北美白橡木玄关柜，加岩板台面，先按规则告诉我还缺什么。",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "follow_up")
        self.assertEqual(payload["follow_up_questions"][0]["question"], "请确认岩板长度")
        self.assertIn("1460", payload["suggested_reply"])

    def test_query_guidance_does_not_misclassify_plain_rock_slab_dining_table_as_addendum(self) -> None:
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

            payload = MODULE.query_guidance(
                "我要做一个岩板餐桌，长1.6米，宽0.8米，多少钱？",
                addenda_root,
            )

        self.assertFalse(payload["matched"])
        self.assertEqual(payload["recommended_reply_mode"], "none")

    def test_query_guidance_asks_side_panel_area_after_backboard_height_reaches_threshold(self) -> None:
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

            payload = MODULE.query_guidance(
                "玄关柜背板做岩板，空区高度0.55米，先按规则告诉我还缺什么。",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "follow_up")
        self.assertEqual(payload["follow_up_questions"][0]["question"], "请确认超出侧板面积")

    def test_query_guidance_prefers_rock_slab_backboard_rule_over_generic_backboard_noise(self) -> None:
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
                            },
                            {
                                "page": 135,
                                "domain": "cabinet",
                                "action_type": "constraint",
                                "title": "背板和层板需要自攻螺丝固定",
                                "detail": "平板背板可通顶或者分段使用，背板和层板需要自攻螺丝固定。",
                                "trigger_terms": ["背板", "层板"],
                                "required_fields": [],
                                "tags": ["柜体", "背板"],
                                "relevance_score": 8,
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

            payload = MODULE.query_guidance(
                "玄关柜背板做岩板，空区高度0.55米，先按规则告诉我还缺什么。",
                addenda_root,
            )

        self.assertIn("岩板背板按长度加价", payload["suggested_reply"])
        self.assertNotIn("自攻螺丝", payload["suggested_reply"])

    def test_query_guidance_matches_specific_aluminum_frame_door_size_constraints(self) -> None:
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
                                "detail": "针式铰链铝框门：305mm≤高度≤3000mm，180mm≤宽度≤500mm；扣手及铰链处厚36mm，其余厚22mm；上下门框宽31mm，左右门框宽29mm；开启方式为扣手开启；只适用针式铰链。",
                                "trigger_terms": ["针式铰链铝框门"],
                                "required_fields": [],
                                "tags": ["门型", "尺寸阈值", "铝框"],
                                "relevance_score": 10,
                            },
                            {
                                "page": 197,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "铝框岩板门尺寸限制",
                                "detail": "铝框岩板门：300mm≤高度≤2700mm，300mm≤宽度≤500mm；门厚22mm；门边框宽55mm；岩板厚6mm；开启方式为按弹开启。",
                                "trigger_terms": ["铝框岩板门"],
                                "required_fields": [],
                                "tags": ["门型", "尺寸阈值", "铝框", "岩板"],
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

            pin_payload = MODULE.query_guidance(
                "针式铰链铝框门最高能做到多少，宽度有什么限制？",
                addenda_root,
            )
            rock_payload = MODULE.query_guidance(
                "铝框岩板门的高度和宽度限制是什么？",
                addenda_root,
            )

        self.assertEqual(pin_payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(pin_payload["constraints"][0]["title"], "针式铰链铝框门尺寸限制")
        self.assertIn("305mm≤高度≤3000mm", pin_payload["suggested_reply"])
        self.assertEqual(rock_payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(rock_payload["constraints"][0]["title"], "铝框岩板门尺寸限制")
        self.assertIn("300mm≤高度≤2700mm", rock_payload["suggested_reply"])

    def test_query_guidance_matches_specific_structured_frame_door_size_constraints(self) -> None:
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
                                "page": 217,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "拱形玻璃门尺寸限制",
                                "detail": "拱形玻璃门：单扇门宽≤560mm；无中横门高≤2200mm；带中横及带格栅条门高≤2300mm；带格栅条时门厚26mm，否则门高≤1500mm时门厚22mm、门高＞1500mm时门厚26mm；门边框宽60mm（含斜切边）。",
                                "trigger_terms": ["拱形玻璃门"],
                                "required_fields": [],
                                "tags": ["门型", "尺寸阈值", "玻璃门"],
                                "relevance_score": 10,
                            },
                            {
                                "page": 221,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "藤编门尺寸限制",
                                "detail": "藤编门：单扇门宽≤560mm，门高≤2300mm；藤面高度每700mm需加一根暗称；门厚22mm；门边框宽60mm（外露30mm）；可推弹开启、拉手开启。",
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
                                "detail": "美式玻璃门：300mm＜单扇门宽≤560mm；无中横门高≤2200mm；带中横门高≤2300mm；门厚26mm；门边框宽60mm。",
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

            arch_payload = MODULE.query_guidance("拱形玻璃门的尺寸限制是什么？", addenda_root)
            rattan_payload = MODULE.query_guidance("藤编门最大能做多宽多高？", addenda_root)
            american_payload = MODULE.query_guidance("美式玻璃门的尺寸限制怎么规定？", addenda_root)

        self.assertEqual(arch_payload["constraints"][0]["title"], "拱形玻璃门尺寸限制")
        self.assertIn("单扇门宽≤560mm", arch_payload["suggested_reply"])
        self.assertEqual(rattan_payload["constraints"][0]["title"], "藤编门尺寸限制")
        self.assertIn("每700mm需加一根暗称", rattan_payload["suggested_reply"])
        self.assertEqual(american_payload["constraints"][0]["title"], "美式玻璃门尺寸限制")
        self.assertIn("300mm＜单扇门宽≤560mm", american_payload["suggested_reply"])

    def test_query_guidance_matches_narrow_edge_disassembly_clearance_constraint(self) -> None:
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

            payload = MODULE.query_guidance(
                "窄边风格拆装斗柜，门盖牙称并且要做顶挡条，按规则需要留多少？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "窄边风格拆装时门盖牙称与顶挡条最少留出15mm")
        self.assertIn("至少预留15mm", payload["suggested_reply"])

    def test_query_guidance_matches_new_modern_edge_structure_constraint(self) -> None:
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

            payload = MODULE.query_guidance(
                "新现代边角风格柜体默认做顶盖侧还是侧盖顶？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "新现代边角风格柜体默认顶盖侧结构，侧盖顶需特殊备注")
        self.assertIn("默认为顶盖侧结构", payload["suggested_reply"])

    def test_query_guidance_matches_cable_grommet_clearance_constraint(self) -> None:
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

            payload = MODULE.query_guidance(
                "书柜做走线圆口，如果没标尺寸默认多少，离边最少要留多少？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "走线圆口规格与距边要求")
        self.assertIn("默认50mm", payload["suggested_reply"])

    def test_query_guidance_matches_glass_drawer_constraints(self) -> None:
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

            payload = MODULE.query_guidance(
                "玻璃抽屉能不能做明装拉手，长度超过600的时候有什么要求？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "玻璃抽屉尺寸与开启方式限制")
        self.assertIn("长度＞600mm时", payload["suggested_reply"])

    def test_query_guidance_matches_book_ladder_bookcase_constraints(self) -> None:
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

            payload = MODULE.query_guidance(
                "书梯书柜的滑轨安装板要留多高，梯子离柜前侧默认多远？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "书梯书柜尺寸与滑轨安装要求")
        self.assertIn("净高度要求≥80mm", payload["suggested_reply"])

    def test_query_guidance_matches_tray_drawer_constraints(self) -> None:
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

            payload = MODULE.query_guidance(
                "餐边柜做托盘抽，明装拉手时如果长度超过600有什么要求？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "托盘抽尺寸与开启方式限制")
        self.assertIn("抽面长度＞600mm", payload["suggested_reply"])

    def test_query_guidance_matches_radar_switch_material_constraints(self) -> None:
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

            payload = MODULE.query_guidance(
                "可隔门板手扫雷达开关能不能隔石材板用，支持什么灯带？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "可隔门板手扫雷达开关适用材质与灯带范围")
        self.assertIn("单色温灯带", payload["suggested_reply"])

    def test_actual_query_guidance_matches_tatami_support_wall_constraint(self) -> None:
        payload = MODULE.query_guidance(
            "榻榻米组合柜中间空区要按托称规则做，还需要固定上墙吗？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "榻榻米组合柜空区加托称时需固定上墙")
        self.assertIn("固定上墙", payload["suggested_reply"])

    def test_actual_query_guidance_matches_specific_cabinet_side_opening_constraints(self) -> None:
        closed_payload = MODULE.query_guidance(
            "柜侧闭合缺口的高度和距后要求是什么？",
            ACTUAL_ADDENDA_ROOT,
        )
        front_cut_payload = MODULE.query_guidance(
            "柜侧前缺口两侧开口时，上柜有什么要求？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(closed_payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(closed_payload["constraints"][0]["title"], "柜侧闭合缺口尺寸限制")
        self.assertIn("开口距后方≥50mm", closed_payload["suggested_reply"])

        self.assertEqual(front_cut_payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(front_cut_payload["constraints"][0]["title"], "柜侧前缺口尺寸限制")
        self.assertIn("两侧开口时，上柜需固定上墙", front_cut_payload["suggested_reply"])

    def test_actual_query_guidance_matches_open_shelf_segmentation_preference(self) -> None:
        payload = MODULE.query_guidance(
            "超高带门柜体有一部分开放格，分段缝应该对齐层板上方还是下方？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "超高带门柜体开放格分段缝优先对齐层板上方")
        self.assertIn("优先采用分段缝对齐层板上方", payload["suggested_reply"])

    def test_actual_query_guidance_matches_yujian_bookcase_structure_preference(self) -> None:
        payload = MODULE.query_guidance(
            "遇见书柜如果单独下柜高度超过1700mm，结构怎么做？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "遇见书柜下柜高度超过1700mm时不建议做侧包顶底")
        self.assertIn("下柜高度＞1700mm时", payload["suggested_reply"])

    def test_actual_query_guidance_matches_knock_down_cabinet_structure_threshold(self) -> None:
        payload = MODULE.query_guidance(
            "常规拆装柜体高度1700以内默认做顶盖侧还是侧盖顶？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "常规拆装柜体高度≤1700mm默认顶盖侧，＞1700mm默认侧盖顶")
        self.assertIn("高度≤1700mm默认顶盖侧", payload["suggested_reply"])

    def test_actual_query_guidance_matches_knock_down_tooth_support_height_range(self) -> None:
        payload = MODULE.query_guidance(
            "衣柜牙称高度一般多少，允许范围多大？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "常规拆装柜体牙称常用50/80mm，允许范围50-250mm")
        self.assertIn("衣柜常用80mm", payload["suggested_reply"])

    def test_actual_query_guidance_matches_rock_slab_dining_table_color_options(self) -> None:
        payload = MODULE.query_guidance(
            "岩板餐桌都有什么花色可选？",
            ACTUAL_ADDENDA_ROOT,
        )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["constraints"][0]["title"], "岩板餐桌可选色样")
        self.assertIn("圣勃朗鱼肚白", payload["suggested_reply"])
        self.assertIn("劳伦特黑金", payload["suggested_reply"])

    def test_query_guidance_uses_question_template_instead_of_raw_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-template"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-template",
                        "layer_name": "设计师追加规则 Template",
                        "rules": [
                            {
                                "page": 177,
                                "domain": "door_panel",
                                "action_type": "constraint",
                                "title": "其他无把手、无抠手柜门须明确备注开启方式",
                                "detail": "其他无把手、无抠手柜门都要明确备注开启方式，且原始图纸里还混着很多无关说明。",
                                "trigger_terms": ["无把手", "无抠手", "开启方式"],
                                "match_terms_specific": ["无把手", "无抠手"],
                                "match_terms_generic": ["开启方式"],
                                "required_fields": ["开启方式"],
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
                        "layer_id": "designer-template",
                        "layer_name": "设计师追加规则 Template",
                        "status": "ACTIVE",
                        "artifacts": {"runtime_rules_file": str(runtime_rules_path)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.query_guidance(
                "这组流云门衣柜不做拉手和抠手，先按规则告诉我还缺什么。",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "follow_up")
        self.assertEqual(payload["follow_up_questions"][0]["question"], "这组柜门还需要确认开启方式。")
        self.assertEqual(payload["suggested_reply"], "这组柜门还需要确认开启方式。")

    def test_query_guidance_prefers_knowledge_for_explanatory_installation_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-switch"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            knowledge_layer_path = reports_dir / "knowledge-layer.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-switch",
                        "layer_name": "设计师追加规则 Switch",
                        "rules": [
                            {
                                "page": 290,
                                "domain": "accessory",
                                "action_type": "constraint",
                                "title": "手扫雷达开关适用灯带范围",
                                "detail": "可隔门板手扫雷达开关适用于单色温灯带。",
                                "trigger_terms": ["手扫雷达开关", "灯带"],
                                "match_terms_specific": ["手扫雷达开关"],
                                "match_terms_generic": ["灯带"],
                                "required_fields": [],
                                "tags": ["开关", "灯带"],
                                "relevance_score": 8,
                                "user_summary": "这款开关要先确认是不是单色温灯带。",
                                "question_template": "",
                                "evidence_level": "hard_rule",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            knowledge_layer_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-switch",
                        "layer_name": "设计师追加规则 Switch",
                        "entries": [
                            {
                                "topic": "可隔门板手扫雷达开关安装方式提示",
                                "answerable_summary": "常见做法有底装在岩板或台面下方、侧装在侧板内侧；如果正面明装，可以按触摸开关理解。",
                                "evidence_level": "high_confidence_review",
                                "trigger_terms": ["手扫雷达开关", "安装", "底装", "侧装", "触摸开关"],
                                "do_not_overclaim": "目前更适合作为安装提示，不要当成所有现场都必须照搬的硬规则。",
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
                        "layer_id": "designer-switch",
                        "layer_name": "设计师追加规则 Switch",
                        "status": "ACTIVE",
                        "artifacts": {
                            "runtime_rules_file": str(runtime_rules_path),
                            "knowledge_layer_file": str(knowledge_layer_path),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.query_guidance(
                "可隔门板手扫雷达开关一般怎么安装，能不能底装或者侧装？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "rule_explanation")
        self.assertEqual(payload["evidence_level"], "high_confidence_review")
        self.assertIn("底装", payload["suggested_reply"])
        self.assertIn("侧装", payload["suggested_reply"])

    def test_query_guidance_prefers_runtime_for_pricing_gap_question_even_when_knowledge_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            addenda_root = Path(tmpdir)
            layer_dir = addenda_root / "designer-switch"
            reports_dir = addenda_root / "reports"
            reports_dir.mkdir()
            runtime_rules_path = reports_dir / "runtime-rules.json"
            knowledge_layer_path = reports_dir / "knowledge-layer.json"
            runtime_rules_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-switch",
                        "layer_name": "设计师追加规则 Switch",
                        "rules": [
                            {
                                "page": 290,
                                "domain": "accessory",
                                "action_type": "adjustment",
                                "title": "手扫雷达开关适用灯带范围",
                                "detail": "可隔门板手扫雷达开关适用于单色温灯带。",
                                "trigger_terms": ["手扫雷达开关", "灯带"],
                                "match_terms_specific": ["手扫雷达开关"],
                                "match_terms_generic": ["灯带"],
                                "required_fields": ["灯带类型"],
                                "tags": ["开关", "灯带"],
                                "relevance_score": 8,
                                "user_summary": "这条规则要先确认灯带类型，确定后才能继续判断。",
                                "question_template": "这边还需要先确认灯带类型。",
                                "evidence_level": "hard_rule",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            knowledge_layer_path.write_text(
                json.dumps(
                    {
                        "layer_id": "designer-switch",
                        "layer_name": "设计师追加规则 Switch",
                        "entries": [
                            {
                                "topic": "可隔门板手扫雷达开关安装方式提示",
                                "answerable_summary": "常见做法有底装和侧装。",
                                "evidence_level": "high_confidence_review",
                                "trigger_terms": ["手扫雷达开关", "安装", "底装", "侧装"],
                                "do_not_overclaim": "目前更适合作为安装提示。",
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
                        "layer_id": "designer-switch",
                        "layer_name": "设计师追加规则 Switch",
                        "status": "ACTIVE",
                        "artifacts": {
                            "runtime_rules_file": str(runtime_rules_path),
                            "knowledge_layer_file": str(knowledge_layer_path),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = MODULE.query_guidance(
                "我这个柜体要配手扫雷达开关，先按规则告诉我还缺什么，能不能继续往下报？",
                addenda_root,
            )

        self.assertEqual(payload["recommended_reply_mode"], "follow_up")
        self.assertEqual(payload["follow_up_questions"][0]["question"], "这边还需要先确认灯带类型。")
        self.assertEqual(payload["suggested_reply"], "这边还需要先确认灯带类型。")


if __name__ == "__main__":
    unittest.main()
