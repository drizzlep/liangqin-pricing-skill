import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reset_quote_sessions.py"
SPEC = importlib.util.spec_from_file_location("reset_quote_sessions", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ResetQuoteSessionsTests(unittest.TestCase):
    def test_targets_main_and_dingtalk_quote_sessions(self) -> None:
        self.assertTrue(MODULE.should_reset_session_key("agent:main:main"))
        self.assertTrue(MODULE.should_reset_session_key("agent:main:dingtalk:direct:03676533111017629"))
        self.assertTrue(
            MODULE.should_reset_session_key(
                'agent:main:openai-user:{"channel":"dingtalk-connector","accountid":"__default__","peerid":"03676533111017629"}'
            )
        )

    def test_keeps_unrelated_sessions(self) -> None:
        self.assertFalse(MODULE.should_reset_session_key("agent:main:cron:b4fa8059-cb08-475f-8db4-7aecc25619e4"))
        self.assertFalse(MODULE.should_reset_session_key("agent:main:feishu:direct:ou_1f712bb904913367faaef7565a1963d4"))

    def test_group_filter_only_targets_dingtalk_group_sessions(self) -> None:
        self.assertTrue(
            MODULE.should_reset_session_key(
                'agent:main:openai-user:{"channel":"dingtalk-connector","accountid":"__default__","chattype":"group","peerid":"03676533111017629"}',
                dingtalk_chat_type="group",
            )
        )
        self.assertTrue(
            MODULE.should_reset_session_key(
                "agent:main:dingtalk-connector:group:-1002381931352",
                dingtalk_chat_type="group",
            )
        )
        self.assertFalse(
            MODULE.should_reset_session_key(
                'agent:main:openai-user:{"channel":"dingtalk-connector","accountid":"__default__","chattype":"direct","peerid":"03676533111017629"}',
                dingtalk_chat_type="group",
            )
        )
        self.assertFalse(MODULE.should_reset_session_key("agent:main:main", dingtalk_chat_type="group"))

    def test_direct_filter_only_targets_dingtalk_direct_sessions(self) -> None:
        self.assertTrue(
            MODULE.should_reset_session_key(
                'agent:main:openai-user:{"channel":"dingtalk-connector","accountid":"__default__","chattype":"direct","peerid":"03676533111017629"}',
                dingtalk_chat_type="direct",
            )
        )
        self.assertFalse(
            MODULE.should_reset_session_key(
                'agent:main:openai-user:{"channel":"dingtalk-connector","accountid":"__default__","chattype":"group","peerid":"03676533111017629"}',
                dingtalk_chat_type="direct",
            )
        )


if __name__ == "__main__":
    unittest.main()
