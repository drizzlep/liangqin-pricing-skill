import importlib.util
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = APP_ROOT / "core" / "pricing_bridge.py"


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


if __name__ == "__main__":
    unittest.main()
