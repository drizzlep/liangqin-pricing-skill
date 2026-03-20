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


if __name__ == "__main__":
    unittest.main()
