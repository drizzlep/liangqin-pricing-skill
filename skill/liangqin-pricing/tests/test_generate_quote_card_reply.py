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
            self.bundle["quote_card_payload"] = {
                "items": [
                    {
                        "product": "客户版衣柜",
                        "confirmed": "白橡木，1.8×2.2×0.6",
                        "pricing_method": "按投影面积计价",
                        "calculation_steps": ["按当前尺寸和材质计算"],
                        "subtotal": "39,529 元",
                    }
                ],
                "total": "39,529 元",
            }

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
        self.assertTrue(reply["json_path"].endswith("quote-card.json"))

    def test_consultant_bundle_merges_conversion_fields_into_quote_card_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir) / "bundles"
            media_root = Path(tmpdir) / "media"
            bundle_root.mkdir(parents=True, exist_ok=True)
            media_root.mkdir(parents=True, exist_ok=True)
            self.bundle["audience_role"] = "consultant"
            self.bundle["output_profile"] = "consultant_dual"
            self.bundle["prepared_payload"]["quote_version_actions"] = {
                "current_send_action": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                "next_version_offer_action": "如果客户继续压预算，再发 V2 预算收一档对比版。",
                "customer_transition_line": "如果你想把预算再往下收，我可以先让主体结构先不动，再补你一版预算收一档对比版。",
            }
            self.bundle["prepared_payload"]["objection_playbook"] = {
                "recommended_first_code": "cheaper_option",
                "cheaper_option": {
                    "label": "客户问能不能便宜点",
                    "customer_reply": "如果你更想先控预算，我可以基于这版再补一版预算收一档对比版。",
                    "transition_line": "如果你想先控预算，我可以先按同样结构补一版预算收一档对比给你。",
                    "followthrough_line": "如果这版区间接受，下一步优先约到店或沟通，把预算边界一次收清。",
                },
            }
            self.bundle["prepared_payload"]["consultant_action_queue"] = [
                {
                    "code": "send_current_quote",
                    "title": "先发当前版",
                    "text": "先发 V1 当前正式版，先把当前锁价结果发给客户。",
                    "group": "current_main",
                    "priority": "p1",
                    "rank": 1,
                    "recommended": True,
                    "source": "quote_version_actions.current_send_action",
                    "trigger_hint": "适合正式报价刚发出这一轮先用。",
                }
            ]
            self.bundle["prepared_payload"]["consultant_quick_actions"] = [
                {
                    "code": "copy_ready_offer",
                    "label": "当前发送句",
                    "text": "这版我先发你当前正式报价；如果你想继续压预算，我可以再补一版预算收一档对比给你参考。",
                    "group": "quote_send",
                    "priority": "primary",
                    "source": "quote_version_actions.copy_ready_offer",
                }
            ]
            self.bundle["quote_card_payload"] = {
                "items": [
                    {
                        "product": "客户版衣柜",
                        "confirmed": "白橡木，1.8×2.2×0.6",
                        "pricing_method": "按投影面积计价",
                        "calculation_steps": ["按当前尺寸和材质计算"],
                        "subtotal": "39,529 元",
                    }
                ],
                "total": "39,529 元",
            }
            captured: dict[str, object] = {}

            def fake_renderer(*, view_model, bundle, output_root, hero_image=None):
                captured["view_model"] = view_model
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
            MODULE.generate_quote_card_reply(
                context_json=self.context_json,
                channel="feishu",
                bundle_root=bundle_root,
                media_root=media_root,
                renderer=fake_renderer,
            )

        view_model = captured["view_model"]
        assert isinstance(view_model, dict)
        self.assertEqual(view_model["action_queue_cards"][0]["title"], "建议先做 1 | 先发当前版")
        self.assertIn("动作：先发 V1 当前正式版", view_model["action_queue_cards"][0]["lines"][0])
        self.assertEqual(view_model["quick_action_cards"][0]["title"], "当前发送句")
        self.assertIn("预算收一档对比版", view_model["version_action_cards"][1]["detail"])
        self.assertIn("客户问能不能便宜点", view_model["objection_action_cards"][0]["title"])


if __name__ == "__main__":
    unittest.main()
