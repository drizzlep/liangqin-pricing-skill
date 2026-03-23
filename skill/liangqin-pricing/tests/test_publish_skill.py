import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "publish_skill.py"
SPEC = importlib.util.spec_from_file_location("publish_skill", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PublishSkillTests(unittest.TestCase):
    def test_main_publishes_to_active_and_workspace_skill_stores(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source-skill"
            source.mkdir()
            (source / "SKILL.md").write_text(
                "---\n"
                "name: liangqin-pricing\n"
                'description: "test skill"\n'
                "---\n\n"
                "# Test\n",
                encoding="utf-8",
            )
            (source / "README.md").write_text("hello", encoding="utf-8")

            active_dest = root / "openclaw" / "skills" / "liangqin-pricing"
            workspace_dest = root / "openclaw" / "workspace" / "skills" / "liangqin-pricing"

            argv = [
                "publish_skill.py",
                "--source",
                str(source),
                "--dest",
                str(active_dest),
                "--workspace-dest",
                str(workspace_dest),
            ]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(MODULE.main(), 0)

            self.assertTrue((active_dest / "SKILL.md").exists())
            self.assertTrue((workspace_dest / "SKILL.md").exists())
            self.assertEqual(
                (active_dest / "README.md").read_text(encoding="utf-8"),
                "hello",
            )
            self.assertEqual(
                (workspace_dest / "README.md").read_text(encoding="utf-8"),
                "hello",
            )


if __name__ == "__main__":
    unittest.main()
