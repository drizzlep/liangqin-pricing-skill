import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
BRIDGE_PATH = APP_ROOT / "core" / "pricing_bridge.py"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


BRIDGE = load_module("contract_review_pricing_bridge", BRIDGE_PATH)


class PricingBridgeTests(unittest.TestCase):
    def test_bridge_runs_pricing_precheck_for_high_confidence_bookcase_fields(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "书柜", "confidence": 0.98},
                "length": {"value": "2400mm", "confidence": 0.96},
                "depth": {"value": "350mm", "confidence": 0.96},
                "height": {"value": "2100mm", "confidence": 0.96},
                "wood_material": {"value": "北美黑胡桃木", "confidence": 0.95},
            }
        )

        self.assertEqual(result["status"], "ready_for_formal_quote")
        self.assertEqual(result["precheck_args"]["category"], "书柜")
        self.assertEqual(result["precheck_args"]["material"], "北美黑胡桃木")
        self.assertEqual(result["precheck_result"]["normalized_category_type"], "cabinet")
        self.assertTrue(result["precheck_result"]["ready_for_formal_quote"])

    def test_bridge_blocks_low_confidence_sensitive_fields_before_pricing(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "书柜", "confidence": 0.98},
                "length": {"value": "2400mm", "confidence": 0.96},
                "depth": {"value": "350mm", "confidence": 0.96},
                "height": {"value": "2100mm", "confidence": 0.96},
                "wood_material": {"value": "北美黑胡桃木", "confidence": 0.62},
            }
        )

        self.assertEqual(result["status"], "manual_confirmation_required")
        self.assertEqual(result["precheck_args"]["category"], "书柜")
        self.assertIn("material", result["blocked_fields"])
        self.assertIn("wood_material", result["withheld_source_fields"])
        self.assertIsNone(result["precheck_result"])

    def test_bridge_returns_needs_input_when_pricing_precheck_still_lacks_required_fields(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "床", "confidence": 0.98},
                "quote_kind": {"value": "standard", "confidence": 0.95},
                "bed_length": {"value": "2000mm", "confidence": 0.95},
                "wood_material": {"value": "北美白蜡木", "confidence": 0.94},
            }
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["precheck_args"]["category"], "床")
        self.assertEqual(result["precheck_result"]["next_required_field"], "width")
        self.assertFalse(result["precheck_result"]["ready_for_formal_quote"])

    def test_bridge_uses_width_as_depth_fallback_for_table_quotes(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "升降桌", "confidence": 0.98},
                "length": {"value": "1200mm", "confidence": 0.96},
                "width": {"value": "750mm", "confidence": 0.96},
                "height": {"value": "780mm", "confidence": 0.96},
                "wood_material": {"value": "北美樱桃木", "confidence": 0.95},
            }
        )

        self.assertEqual(result["precheck_args"]["depth"], "750mm")
        self.assertNotEqual(result["precheck_result"]["next_required_field"], "depth")

    def test_bridge_uses_width_as_depth_fallback_for_cabinet_quotes(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {"value": "组合餐边柜", "confidence": 0.98},
                "length": {"value": "4070mm", "confidence": 0.96},
                "width": {"value": "2338mm", "confidence": 0.96},
                "height": {"value": "2295mm", "confidence": 0.96},
                "wood_material": {"value": "北美白橡木", "confidence": 0.95},
                "quote_kind": {"value": "custom", "confidence": 0.9},
            }
        )

        self.assertEqual(result["precheck_args"]["depth"], "2338mm")
        self.assertNotEqual(result["precheck_result"]["next_required_field"], "depth")

    def test_bridge_blocks_ocr_only_child_bed_fields_for_manual_confirmation(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "product_category": {
                    "value": "高架床",
                    "confidence": 0.98,
                    "evidence_refs": [{"source_kind": "native_preview"}],
                },
                "quote_kind": {
                    "value": "custom",
                    "confidence": 0.96,
                    "evidence_refs": [{"source_kind": "native_preview"}],
                },
                "bed_form": {
                    "value": "高架床",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "access_style": {
                    "value": "梯柜",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "guardrail_style": {
                    "value": "胶囊围栏",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "guardrail_length": {
                    "value": "1800mm",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "guardrail_height": {
                    "value": "320mm",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "stair_width": {
                    "value": "500mm",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "stair_depth": {
                    "value": "900mm",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "width": {
                    "value": "1080mm",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "length": {
                    "value": "3045mm",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
                "wood_material": {
                    "value": "北美白橡木",
                    "confidence": 0.95,
                    "evidence_refs": [{"source_kind": "ocr_markdown"}],
                },
            }
        )

        self.assertEqual(result["status"], "manual_confirmation_required")
        self.assertIn("bed_form", result["blocked_fields"])
        self.assertIn("guardrail_style", result["strict_ocr_blocked_fields"])
        self.assertIn("stair_depth", result["strict_ocr_blocked_fields"])
        override_fields = {item["target_field"] for item in result["confidence_overrides"]}
        self.assertIn("bed_form", override_fields)
        self.assertIn("width", override_fields)
        self.assertIsNone(result["precheck_result"])

    def test_bridge_blocks_child_bed_when_primary_drawing_review_is_required(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "fields": {
                    "product_category": {"value": "高架床", "confidence": 0.98},
                    "quote_kind": {"value": "custom", "confidence": 0.96},
                    "bed_form": {"value": "高架床", "confidence": 0.96},
                    "access_style": {"value": "梯柜", "confidence": 0.96},
                    "guardrail_style": {"value": "胶囊围栏", "confidence": 0.96},
                    "width": {"value": "1080mm", "confidence": 0.96},
                    "length": {"value": "2096mm", "confidence": 0.96},
                    "wood_material": {"value": "北美白橡木", "confidence": 0.95},
                },
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "primary_drawing_asset_id": "asset-main-drawing",
                    "primary_drawing_file_name": "大尺寸图.png",
                    "requires_primary_drawing_review": True,
                    "review_reason": "child_bed_primary_drawing_fields_incomplete",
                    "review_block_fields": ["bed_form", "width", "length"],
                },
            }
        )

        self.assertEqual(result["status"], "manual_confirmation_required")
        self.assertEqual(result["reason"], "child_bed_primary_drawing_review_required")
        self.assertIn("bed_form", result["blocked_fields"])
        self.assertIn("width", result["strict_ocr_blocked_fields"])
        self.assertEqual(result["child_bed_analysis"]["primary_drawing_file_name"], "大尺寸图.png")
        self.assertIsNone(result["precheck_result"])

    def test_bridge_does_not_block_explicit_adult_bed_with_child_bed_only_field_name_overlap(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "fields": {
                    "product_category": {
                        "value": "经典箱体床",
                        "confidence": 0.9,
                        "evidence_refs": [{"source_kind": "ocr_unknown"}],
                    },
                    "lower_bed_type": {
                        "value": "箱体床",
                        "confidence": 0.9,
                        "evidence_refs": [{"source_kind": "ocr_unknown"}],
                    },
                    "wood_material": {"value": "北美樱桃木", "confidence": 0.99},
                    "quote_kind": {"value": "custom", "confidence": 0.87},
                    "length": {"value": "2520 mm", "confidence": 0.95},
                    "width": {"value": "1360 mm", "confidence": 0.95},
                    "height": {"value": "1050 mm", "confidence": 0.95},
                }
            }
        )

        self.assertEqual(result["status"], "ready_for_formal_quote")
        self.assertEqual(result["precheck_args"]["category"], "经典箱体床")
        self.assertEqual(result["precheck_result"]["pricing_route"], "bed_standard")
        self.assertNotIn("lower_bed_type", result["blocked_fields"])
        self.assertEqual(result["strict_ocr_blocked_fields"], [])

    def test_bridge_accepts_high_confidence_primary_child_bed_drawing_fields(self) -> None:
        result = BRIDGE.bridge_contract_to_pricing_precheck(
            {
                "fields": {
                    "product_category": {
                        "value": "高架床",
                        "confidence": 0.98,
                        "evidence_refs": [{"asset_id": "asset-contract", "source_kind": "native_preview"}],
                    },
                    "quote_kind": {
                        "value": "custom",
                        "confidence": 0.96,
                        "evidence_refs": [{"asset_id": "asset-contract", "source_kind": "native_preview"}],
                    },
                    "bed_form": {
                        "value": "高架床",
                        "confidence": 0.96,
                        "evidence_refs": [{"asset_id": "asset-main-drawing", "source_kind": "ocr_markdown"}],
                    },
                    "access_style": {
                        "value": "梯柜",
                        "confidence": 0.96,
                        "evidence_refs": [{"asset_id": "asset-main-drawing", "source_kind": "ocr_markdown"}],
                    },
                    "guardrail_style": {
                        "value": "胶囊围栏",
                        "confidence": 0.96,
                        "evidence_refs": [{"asset_id": "asset-main-drawing", "source_kind": "ocr_markdown"}],
                    },
                    "width": {
                        "value": "1080mm",
                        "confidence": 0.96,
                        "evidence_refs": [{"asset_id": "asset-main-drawing", "source_kind": "ocr_markdown"}],
                    },
                    "length": {
                        "value": "2096mm",
                        "confidence": 0.96,
                        "evidence_refs": [{"asset_id": "asset-main-drawing", "source_kind": "ocr_markdown"}],
                    },
                    "wood_material": {
                        "value": "北美白橡木",
                        "confidence": 0.95,
                        "evidence_refs": [{"asset_id": "asset-contract", "source_kind": "native_preview"}],
                    },
                },
                "child_bed_analysis": {
                    "is_child_bed": True,
                    "primary_drawing_asset_id": "asset-main-drawing",
                    "primary_drawing_file_name": "大尺寸图.png",
                    "primary_drawing_confidence": "high",
                    "requires_primary_drawing_review": False,
                    "main_drawing_field_hits": ["bed_form", "access_style", "guardrail_style", "width", "length"],
                    "review_block_fields": [],
                },
            }
        )

        self.assertEqual(result["status"], "needs_input")
        self.assertNotIn("bed_form", result["blocked_fields"])
        self.assertNotIn("width", result["strict_ocr_blocked_fields"])
        self.assertEqual(result["precheck_args"]["width"], "1080mm")
        self.assertEqual(result["precheck_result"]["next_required_field"], "guardrail_length")

    def test_lightweight_amount_check_can_use_cabinet_route_evidence_from_visual_caption(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "柜体", "confidence": 0.96},
                "length": {"value": "2000mm", "confidence": 0.95},
                "height": {"value": "2400mm", "confidence": 0.95},
                "wood_material": {"value": "北美樱桃木", "confidence": 0.95},
            },
            "route_evidence": {
                "recommended_route": "cabinet",
                "candidates": [
                    {
                        "route": "cabinet",
                        "score": 9,
                        "signals": ["开放书柜"],
                        "evidence_snippets": ["图下注：开放书柜，层板可调"],
                        "source_asset_ids": ["asset-visual"],
                        "inferred_overrides": {
                            "category": "书柜",
                            "has_door": "no",
                        },
                    }
                ],
            },
        }

        result = BRIDGE.build_lightweight_amount_check_quote_payload(
            normalized_fields,
            pricing_bridge_payload={
                "status": "manual_confirmation_required",
                "reason": "category_missing_or_untrusted",
                "precheck_args": {
                    "category": "柜体",
                    "length": "2000mm",
                    "height": "2400mm",
                    "material": "北美樱桃木",
                },
                "precheck_result": None,
            },
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["reason"], "approximate_quote_completed")
        self.assertEqual(result["pricing_route"], "cabinet_projection_area")
        self.assertTrue(str(result["pricing_total"]).endswith("元"))
        assumed_fields = {item["field"] for item in result["assumed_defaults"]}
        self.assertIn("category", assumed_fields)
        self.assertIn("has_door", assumed_fields)

    def test_lightweight_amount_check_prefers_best_cabinet_candidate_by_contract_amount(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "柜体", "confidence": 0.96},
                "length": {"value": "2000mm", "confidence": 0.95},
                "height": {"value": "2400mm", "confidence": 0.95},
                "wood_material": {"value": "北美樱桃木", "confidence": 0.95},
            },
            "route_evidence": {
                "recommended_route": "cabinet",
                "candidates": [
                    {
                        "route": "cabinet",
                        "score": 9,
                        "signals": ["开放书柜"],
                        "evidence_snippets": ["图下注：开放书柜，层板可调"],
                        "source_asset_ids": ["asset-visual"],
                        "inferred_overrides": {
                            "category": "书柜",
                            "has_door": "no",
                        },
                    }
                ],
            },
        }

        def fake_run_precheck(precheck_args: dict[str, str]) -> dict[str, object]:
            self.assertEqual(precheck_args["category"], "书柜")
            return {
                "ready_for_formal_quote": True,
                "quote_decision": "reference_quote",
                "assumed_defaults": [],
                "pricing_route": "cabinet",
            }

        def fake_build_quote_payload_from_precheck(*, precheck_args: dict[str, str], precheck_result: dict[str, object]) -> dict[str, object]:
            del precheck_result
            total = "21200元" if precheck_args.get("has_door") == "yes" else "20500元"
            return {
                "items": [],
                "total": total,
                "pricing_route": "cabinet_projection_area",
                "reference": True,
            }

        fake_module = type(
            "FakeQuoteModule",
            (),
            {"_build_quote_payload_from_precheck": staticmethod(fake_build_quote_payload_from_precheck)},
        )

        with mock.patch.object(BRIDGE, "run_liangqin_pricing_precheck", side_effect=fake_run_precheck), mock.patch.object(
            BRIDGE,
            "_load_handle_quote_message_module",
            return_value=fake_module,
        ):
            result = BRIDGE.build_lightweight_amount_check_quote_payload(
                normalized_fields,
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "reason": "category_missing_or_untrusted",
                    "precheck_args": {
                        "category": "柜体",
                        "length": "2000mm",
                        "height": "2400mm",
                        "material": "北美樱桃木",
                    },
                    "precheck_result": None,
                },
                contract_total="21200元",
            )

        assert result is not None
        self.assertEqual(result["pricing_total"], "21200元")
        self.assertEqual(result["selected_route_candidate"]["inferred_overrides"]["has_door"], "yes")
        self.assertEqual(result["selected_route_candidate"]["match_diff_value"], 0.0)
        self.assertEqual(len(result["route_candidates"]), 2)
        self.assertFalse(result["route_uncertainty"])

    def test_lightweight_amount_check_marks_route_uncertainty_when_runner_up_is_close(self) -> None:
        normalized_fields = {
            "fields": {
                "product_category": {"value": "柜体", "confidence": 0.96},
                "length": {"value": "2000mm", "confidence": 0.95},
                "height": {"value": "2400mm", "confidence": 0.95},
                "wood_material": {"value": "北美樱桃木", "confidence": 0.95},
            },
            "route_evidence": {
                "recommended_route": "cabinet",
                "candidates": [
                    {
                        "route": "cabinet",
                        "score": 9,
                        "signals": ["开放书柜"],
                        "evidence_snippets": ["图下注：开放书柜，层板可调"],
                        "source_asset_ids": ["asset-visual"],
                        "inferred_overrides": {
                            "category": "书柜",
                            "has_door": "no",
                        },
                    }
                ],
            },
        }

        def fake_run_precheck(precheck_args: dict[str, str]) -> dict[str, object]:
            self.assertEqual(precheck_args["category"], "书柜")
            return {
                "ready_for_formal_quote": True,
                "quote_decision": "reference_quote",
                "assumed_defaults": [],
                "pricing_route": "cabinet",
            }

        def fake_build_quote_payload_from_precheck(*, precheck_args: dict[str, str], precheck_result: dict[str, object]) -> dict[str, object]:
            del precheck_result
            total = "21020元" if precheck_args.get("has_door") == "no" else "21060元"
            return {
                "items": [],
                "total": total,
                "pricing_route": "cabinet_projection_area",
                "reference": True,
            }

        fake_module = type(
            "FakeQuoteModule",
            (),
            {"_build_quote_payload_from_precheck": staticmethod(fake_build_quote_payload_from_precheck)},
        )

        with mock.patch.object(BRIDGE, "run_liangqin_pricing_precheck", side_effect=fake_run_precheck), mock.patch.object(
            BRIDGE,
            "_load_handle_quote_message_module",
            return_value=fake_module,
        ):
            result = BRIDGE.build_lightweight_amount_check_quote_payload(
                normalized_fields,
                pricing_bridge_payload={
                    "status": "manual_confirmation_required",
                    "reason": "category_missing_or_untrusted",
                    "precheck_args": {
                        "category": "柜体",
                        "length": "2000mm",
                        "height": "2400mm",
                        "material": "北美樱桃木",
                    },
                    "precheck_result": None,
                },
                contract_total="21000元",
            )

        assert result is not None
        self.assertEqual(result["selected_route_candidate"]["inferred_overrides"]["has_door"], "no")
        self.assertTrue(result["route_uncertainty"])
        self.assertEqual(result["selected_vs_runner_up_diff_value"], 40.0)
        self.assertEqual(result["runner_up_route_candidate"]["inferred_overrides"]["has_door"], "yes")


if __name__ == "__main__":
    unittest.main()
