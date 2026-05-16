import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_visual_evidence_layer.py"
SPEC = importlib.util.spec_from_file_location("build_visual_evidence_layer", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class BuildVisualEvidenceLayerTests(unittest.TestCase):
    def test_build_visual_entry_registers_rock_slab_page_image_and_crops(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "岩板__p005.png"
            image_path.write_text("fake image", encoding="utf-8")
            crop_dir = root / "ocr" / "岩板__p005" / "paddleocr" / "page-001" / "imgs"
            crop_dir.mkdir(parents=True)
            crop_path = crop_dir / "img_in_image_box_1.jpg"
            crop_path.write_text("fake crop", encoding="utf-8")
            page = {
                "source_title": "岩板",
                "source_path": "<root>/岩板",
                "source_page": 5,
                "source_node_id": "node-1",
                "source_local_path": str(root / "source.pdf"),
                "image": {"status": "succeeded", "path": str(image_path)},
                "ocr": {
                    "status": "succeeded",
                    "text": "圣勃朗鱼肚 DESCRIPTION SPECIFICATION 1200X2400X12MM",
                    "output_dir": str(root / "ocr" / "岩板__p005"),
                },
            }

            entry = MODULE.build_visual_entry("岩板", page)

        self.assertEqual(entry["topic"], "岩板")
        self.assertEqual(entry["source_title"], "岩板")
        self.assertEqual(entry["source_page"], 5)
        self.assertEqual(entry["page_image"], str(image_path))
        self.assertEqual(entry["crop_images"], [])
        self.assertEqual(entry["debug_crop_images"], [str(crop_path.resolve())])
        self.assertFalse(entry["needs_human_review"])

    def test_build_visual_entry_allows_page_image_without_crop(self) -> None:
        page = {
            "source_title": "岩板",
            "source_page": 6,
            "image": {"status": "succeeded", "path": "/tmp/page.png"},
            "ocr": {"status": "succeeded", "text": "岩板文字" * 20, "output_dir": "/tmp/missing"},
        }

        entry = MODULE.build_visual_entry("岩板", page)

        self.assertFalse(entry["needs_human_review"])
        self.assertEqual(entry["review_reason"], "")

    def test_build_visual_entry_routes_blank_page_image_to_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "blank.png"
            image_path.write_text("fake image", encoding="utf-8")
            original_detector = MODULE.page_image_looks_blank
            try:
                MODULE.page_image_looks_blank = lambda _path: True
                page = {
                    "source_title": "GB 28007-2024 婴幼儿及儿童家具安全技术规范",
                    "source_page": 2,
                    "image": {"status": "succeeded", "path": str(image_path)},
                    "ocr": {"status": "succeeded", "text": "DIzs", "output_dir": "/tmp/missing"},
                }

                entry = MODULE.build_visual_entry("安全规范", page)
            finally:
                MODULE.page_image_looks_blank = original_detector

        self.assertTrue(entry["needs_human_review"])
        self.assertEqual(entry["evidence_status"], "needs_human_review")
        self.assertIn("接近空白", entry["review_reason"])

    def test_build_visual_entry_routes_low_confidence_to_agent_visual_review(self) -> None:
        page = {
            "source_title": "常规推拉门",
            "source_page": 8,
            "image": {"status": "succeeded", "path": "/tmp/page.png"},
            "ocr": {"status": "succeeded", "text": "", "output_dir": "/tmp/missing"},
        }

        entry = MODULE.build_visual_entry("推拉门", page)

        self.assertFalse(entry["needs_human_review"])
        self.assertEqual(entry["evidence_status"], "agent_visual_review")
        self.assertIn("Agent 应直接阅读整页图", entry["agent_guidance"])

    def test_render_html_contains_business_summary_without_sensitive_links(self) -> None:
        model = {
            "topic": "岩板",
            "html_path": "/tmp/visual-evidence/岩板/visual-evidence-board.html",
            "asset_count": 1,
            "page_image_count": 1,
            "crop_image_count": 0,
            "missing_page_image_count": 0,
            "low_confidence_count": 0,
            "needs_human_review_count": 1,
            "agent_ready_count": 0,
            "agent_visual_review_count": 1,
            "recommended_action": "可进入 Agent 视觉阅读：有整页图，OCR 弱的页面由 Agent 直接读图处理。",
            "entries": [
                {
                    "topic": "岩板",
                    "source_title": "岩板",
                    "source_page": 5,
                    "ocr_summary": "圣勃朗鱼肚",
                    "keywords": ["岩板", "圣勃朗鱼肚"],
                    "page_image": "/tmp/岩板__p005.png",
                    "crop_images": [],
                    "debug_crop_images": ["/tmp/crop.jpg"],
                    "needs_human_review": True,
                    "evidence_status": "needs_human_review",
                    "review_reason": "需要人工复核",
                    "agent_guidance": "缺少可展示整页图，需要补资料或人工确认。",
                }
            ],
        }

        html = MODULE.render_html(model)

        self.assertIn("图文证据层", html)
        self.assertIn("可用页图", html)
        self.assertIn("Agent 读图", html)
        self.assertIn("推荐动作", html)
        self.assertIn("不在人工看板默认展示", html)
        self.assertIn("需要人工复核", html)
        self.assertIn("岩板", html)
        self.assertNotIn("Signature=", html)
        self.assertNotIn("https://alidocs2", html)

    def test_topic_hit_uses_aliases_for_safety_manuals(self) -> None:
        page = {
            "source_title": "GB 28007-2024 婴幼儿及儿童家具安全技术规范",
            "source_page": 2,
            "image": {"status": "succeeded", "path": "/tmp/page.png"},
            "ocr": {"status": "succeeded", "text": "边缘及尖端安全要求", "output_dir": "/tmp/missing"},
        }

        self.assertTrue(MODULE.topic_hit(page, "安全规范"))
        self.assertTrue(MODULE.topic_hit(page, "儿童床"))

    def test_write_json_round_trips_visual_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "visual-assets.json"
            MODULE.write_json(path, {"entries": [{"source_title": "岩板", "source_page": 5}]})
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["entries"][0]["source_title"], "岩板")


if __name__ == "__main__":
    unittest.main()
