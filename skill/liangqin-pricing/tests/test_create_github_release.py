import importlib.util
import unittest
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "create_github_release.py"
if not SCRIPT_PATH.exists():
    raise unittest.SkipTest("repo-level create_github_release.py is unavailable in this environment")
SPEC = importlib.util.spec_from_file_location("create_github_release", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CreateGithubReleaseTests(unittest.TestCase):
    def test_parse_github_repo_supports_https_and_ssh(self) -> None:
        self.assertEqual(
            MODULE.parse_github_repo("https://github.com/drizzlep/liangqin-pricing-skill.git"),
            "drizzlep/liangqin-pricing-skill",
        )
        self.assertEqual(
            MODULE.parse_github_repo("git@github.com:drizzlep/liangqin-pricing-skill.git"),
            "drizzlep/liangqin-pricing-skill",
        )

    def test_choose_next_tag_uses_date_and_increments_suffix(self) -> None:
        today = date(2026, 3, 30)
        self.assertEqual(MODULE.choose_next_tag([], today=today), "v2026.03.30")
        self.assertEqual(
            MODULE.choose_next_tag(["v2026.03.30"], today=today),
            "v2026.03.30.1",
        )
        self.assertEqual(
            MODULE.choose_next_tag(["v2026.03.30", "v2026.03.30.1", "v2026.03.29"], today=today),
            "v2026.03.30.2",
        )

    def test_release_stamp_for_tag_supports_suffix(self) -> None:
        self.assertEqual(MODULE.release_stamp_for_tag("v2026.03.30"), "20260330")
        self.assertEqual(MODULE.release_stamp_for_tag("v2026.03.30.1"), "20260330-1")

    def test_build_release_notes_lists_commits_assets_and_verification(self) -> None:
        notes = MODULE.build_release_notes(
            tag="v2026.03.30",
            target_commit="48be677",
            previous_tag="v2026.03.26",
            verify_command="python3 -m unittest discover -s skill/liangqin-pricing/tests",
            assets=[
                "liangqin-pricing-installer-20260330.sh",
                "liangqin-pricing-openclaw-20260330.zip",
            ],
            commit_lines=[
                "48be677 feat: tighten addendum runtime publish loop",
                "3d64d6d test: stabilize child bed prompt suite coverage",
            ],
        )

        self.assertIn("`v2026.03.30`", notes)
        self.assertIn("`48be677`", notes)
        self.assertIn("`v2026.03.26`", notes)
        self.assertIn("`python3 -m unittest discover -s skill/liangqin-pricing/tests`", notes)
        self.assertIn("`48be677 feat: tighten addendum runtime publish loop`", notes)
        self.assertIn("`liangqin-pricing-openclaw-20260330.zip`", notes)


if __name__ == "__main__":
    unittest.main()
