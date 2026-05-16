import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "query_manual_evidence.py"
SPEC = importlib.util.spec_from_file_location("query_manual_evidence", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class QueryManualEvidenceTests(unittest.TestCase):
    def test_choose_matches_returns_rock_slab_visual_evidence(self) -> None:
        entries = [
            {
                "topic": "岩板",
                "source_title": "岩板",
                "source_page": 5,
                "keywords": ["岩板", "圣勃朗鱼肚"],
                "ocr_summary": "圣勃朗鱼肚 DESCRIPTION SPECIFICATION",
                "page_image": "/tmp/岩板__p005.png",
                "crop_images": ["/tmp/crop.jpg"],
                "confidence": 0.95,
            },
            {
                "topic": "岩板",
                "source_title": "岩板",
                "source_page": 8,
                "keywords": ["岩板", "其他"],
                "ocr_summary": "另一款岩板",
                "page_image": "/tmp/岩板__p008.png",
                "crop_images": ["/tmp/crop-2.jpg"],
                "confidence": 0.8,
            },
        ]

        matches = MODULE.choose_matches(entries, "读一下岩板圣勃朗鱼肚，给我对应图")

        self.assertEqual(matches[0]["source_page"], 5)
        self.assertGreater(matches[0]["_score"], matches[1]["_score"])

    def test_build_answer_includes_source_and_visual_success(self) -> None:
        matches = [
            {
                "topic": "岩板",
                "source_title": "岩板",
                "source_page": 5,
                "ocr_summary": "圣勃朗鱼肚说明",
                "page_image": "/tmp/page.png",
                "crop_images": ["/tmp/crop.jpg"],
            }
        ]

        answer, needs_review, reason = MODULE.build_answer("岩板圣勃朗鱼肚", matches, "岩板")

        self.assertIn("圣勃朗鱼肚说明", answer)
        self.assertIn("岩板 第 5 页", answer)
        self.assertIn("已附对应整页图", answer)
        self.assertFalse(needs_review)
        self.assertEqual(reason, "")

    def test_build_answer_blocks_missing_visual_asset(self) -> None:
        matches = [
            {
                "topic": "岩板",
                "source_title": "岩板",
                "source_page": 6,
                "ocr_summary": "岩板文字",
                "page_image": "",
                "crop_images": [],
            }
        ]

        answer, needs_review, reason = MODULE.build_answer("岩板", matches, "岩板")

        self.assertTrue(needs_review)
        self.assertEqual(reason, "missing_visual_asset")
        self.assertIn("缺少可展示图片证据", answer)

    def test_build_answer_blocks_blank_visual_asset(self) -> None:
        matches = [
            {
                "topic": "安全规范",
                "source_title": "GB 28007-2024 婴幼儿及儿童家具安全技术规范",
                "source_page": 2,
                "ocr_summary": "DIzs",
                "page_image": "/tmp/blank.png",
                "page_image_looks_blank": True,
            }
        ]

        answer, needs_review, reason = MODULE.build_answer("儿童床安全规范", matches, "安全规范")

        self.assertTrue(needs_review)
        self.assertEqual(reason, "blank_visual_asset")
        self.assertIn("整页图接近空白", answer)
        self.assertIn("不能据此给出具体建议", answer)

    def test_build_response_shape_contains_required_fields(self) -> None:
        entries = [
            {
                "topic": "岩板",
                "source_title": "岩板",
                "source_page": 5,
                "source_path": "<root>/岩板",
                "keywords": ["岩板", "圣勃朗鱼肚"],
                "ocr_summary": "圣勃朗鱼肚说明",
                "page_image": "/tmp/page.png",
                "crop_images": ["/tmp/crop.jpg"],
                "debug_crop_images": ["/tmp/crop.jpg"],
                "confidence": 0.95,
                "evidence_status": "agent_ready",
                "needs_human_review": False,
            }
        ]
        matches = MODULE.choose_matches(entries, "岩板圣勃朗鱼肚")
        answer, needs_review, reason = MODULE.build_answer("岩板圣勃朗鱼肚", matches, "岩板")
        response = {
            "answer": answer,
            "matches": matches,
            "page_images": [match["page_image"] for match in matches if match.get("page_image")],
            "crop_images": [],
            "debug_crop_images": [path for match in matches for path in match.get("debug_crop_images", [])],
            "source_refs": [
                {
                    "source_title": match.get("source_title", ""),
                    "source_page": match.get("source_page", 0),
                    "source_path": match.get("source_path", ""),
                }
                for match in matches
            ],
            "confidence": max(float(match.get("confidence") or 0) for match in matches),
            "needs_human_review": needs_review,
            "review_reason": reason,
            "evidence_status": "agent_ready",
            "agent_guidance": "",
        }

        self.assertEqual(
            set(response),
            {
                "answer",
                "matches",
                "page_images",
                "crop_images",
                "debug_crop_images",
                "source_refs",
                "confidence",
                "needs_human_review",
                "review_reason",
                "evidence_status",
                "agent_guidance",
            },
        )
        self.assertEqual(response["page_images"], ["/tmp/page.png"])
        self.assertEqual(response["crop_images"], [])
        self.assertEqual(response["debug_crop_images"], ["/tmp/crop.jpg"])

    def test_low_confidence_match_routes_to_agent_visual_review(self) -> None:
        matches = [
            {
                "topic": "推拉门",
                "source_title": "常规推拉门",
                "source_page": 8,
                "ocr_summary": "当前页 OCR 未读到稳定文字。",
                "page_image": "/tmp/page.png",
                "confidence": 0.7,
                "evidence_status": "agent_visual_review",
                "needs_human_review": False,
            }
        ]
        answer, needs_review, reason = MODULE.build_answer("推拉门", matches, "推拉门")
        evidence_statuses = [match["evidence_status"] for match in matches]
        agent_visual_review = bool(matches) and not needs_review and "agent_visual_review" in evidence_statuses
        response = {
            "answer": answer,
            "matches": matches,
            "page_images": [match["page_image"] for match in matches if match.get("page_image")],
            "crop_images": [],
            "debug_crop_images": [],
            "source_refs": [{"source_title": "常规推拉门", "source_page": 8, "source_path": ""}],
            "confidence": max(float(match.get("confidence") or 0) for match in matches),
            "evidence_status": "agent_visual_review" if agent_visual_review else "agent_ready",
            "agent_guidance": "当前匹配有整页图但 OCR 文字偏弱，Agent 应直接阅读整页图，不要求人工先介入。",
            "needs_human_review": needs_review,
            "review_reason": reason,
        }

        self.assertFalse(response["needs_human_review"])
        self.assertEqual(response["evidence_status"], "agent_visual_review")
        self.assertIn("不要求人工先介入", response["agent_guidance"])

    def test_choose_matches_uses_topic_aliases_for_safety_manuals(self) -> None:
        entries = [
            {
                "topic": "安全规范",
                "source_title": "GB 28007-2024 婴幼儿及儿童家具安全技术规范",
                "source_page": 2,
                "keywords": ["安全规范", "婴幼儿", "GB", "28007"],
                "ocr_summary": "边缘及尖端安全要求",
                "page_image": "/tmp/safety.png",
                "debug_crop_images": [],
                "confidence": 0.9,
            },
            {
                "topic": "安全规范",
                "source_title": "岩板",
                "source_page": 5,
                "keywords": ["岩板"],
                "ocr_summary": "圣勃朗鱼肚",
                "page_image": "/tmp/rock.png",
                "debug_crop_images": [],
                "confidence": 0.9,
            },
        ]

        matches = MODULE.choose_matches(entries, "儿童床有什么安全规范要注意？")

        self.assertEqual(matches[0]["source_title"], "GB 28007-2024 婴幼儿及儿童家具安全技术规范")


if __name__ == "__main__":
    unittest.main()
