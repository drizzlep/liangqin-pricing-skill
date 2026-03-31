import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_quote_card_reply.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("generate_quote_card_reply", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class GenerateQuoteCardReplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context_json = json.dumps(
            {
                "message_id": "om_x100b53cafe",
                "sender_id": "ou_123456",
                "sender": "ou_123456",
                "timestamp": "Sun 2026-03-29 10:26 GMT+8",
            },
            ensure_ascii=False,
        )
        self.bundle = {
            "prepared_payload": {
                "items": [
                    {
                        "product": "北美黑胡桃木流云衣柜",
                        "confirmed": "长 1.8 米 × 深 0.67 米 × 高 2.2 米，材质北美黑胡桃木，门板纹理连续。",
                        "pricing_method": "按投影面积计价",
                        "calculation_steps": ["投影面积：1.8 × 2.2 = 3.96㎡"],
                        "subtotal": "39,529 元",
                    }
                ],
                "total": "39,529 元",
            },
            "reply_text": "正式报价：39,529 元",
            "quote_kind": "formal",
            "conversation_id": "agent:main:feishu:direct:ou_123456",
            "eligible_for_card": True,
            "created_at": "2026-03-29T10:30:00+08:00",
        }

    def test_returns_clear_message_when_no_cached_bundle_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            reply = MODULE.generate_quote_card_reply(
                context_json=self.context_json,
                channel="feishu",
                bundle_root=Path(tmpdir),
                media_root=Path(tmpdir) / "media",
            )

        self.assertIn("当前会话里还没有可生成图片的完整报价", reply["text"])
        self.assertNotIn("media_url", reply)

    def test_returns_media_reply_when_bundle_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "bundles"
            media_root = Path(tmpdir) / "media"
            bundle_root.mkdir(parents=True, exist_ok=True)
            media_root.mkdir(parents=True, exist_ok=True)

            def fake_renderer(*, view_model, bundle, output_root, hero_image=None):
                export_dir = output_root / "agent_main_feishu_direct_ou_123456" / "20260329T103000"
                export_dir.mkdir(parents=True, exist_ok=True)
                image_path = export_dir / "quote-card.jpg"
                html_path = export_dir / "quote-card.html"
                json_path = export_dir / "quote-card.json"
                bundle_path = export_dir / "quote-result-bundle.json"
                image_path.write_bytes(b"jpg")
                html_path.write_text("<html></html>", encoding="utf-8")
                json_path.write_text(json.dumps(view_model, ensure_ascii=False), encoding="utf-8")
                bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
                return {
                    "image_path": str(image_path),
                    "html_path": str(html_path),
                    "json_path": str(json_path),
                    "bundle_path": str(bundle_path),
                    "width": 1080,
                    "height": 1920,
                }

            MODULE.quote_result_bundle.store_latest_quote_result_bundle(self.bundle, cache_root=bundle_root)
            reply = MODULE.generate_quote_card_reply(
                context_json=self.context_json,
                channel="feishu",
                bundle_root=bundle_root,
                media_root=media_root,
                renderer=fake_renderer,
            )

        self.assertIn("整理成图片发到当前会话", reply["text"])
        self.assertTrue(reply["media_url"].endswith("quote-card.jpg"))
        self.assertTrue(reply["html_path"].endswith("quote-card.html"))


if __name__ == "__main__":
    unittest.main()
