import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "package_openclaw_skill.sh"
if not SCRIPT_PATH.exists():
    raise unittest.SkipTest("repo-level package_openclaw_skill.sh is unavailable in this environment")


class PackageOpenClawSkillTests(unittest.TestCase):
    def test_package_includes_dual_skill_bundle_and_runtime_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pricing_source = root / "pricing-skill"
            contract_review_source = root / "contract-review-skill"
            contract_review_app_root = root / "apps" / "contract-review"
            publish_script = root / "scripts" / "publish_openclaw_skills.py"
            output_dir = root / "dist"

            (pricing_source / "data" / "current").mkdir(parents=True)
            (pricing_source / "references" / "current").mkdir(parents=True)
            (pricing_source / "references" / "addenda" / "designer-manual-2026-03-22").mkdir(parents=True)
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22").mkdir(parents=True)
            (pricing_source / "scripts").mkdir(parents=True)
            (pricing_source / "sources" / "inbox").mkdir(parents=True)
            (contract_review_source / "scripts").mkdir(parents=True)
            (contract_review_app_root / "cli").mkdir(parents=True)
            (contract_review_app_root / "core").mkdir(parents=True)
            publish_script.parent.mkdir(parents=True, exist_ok=True)

            (pricing_source / "SKILL.md").write_text(
                "---\n"
                "name: liangqin-pricing\n"
                'description: "test skill"\n'
                "---\n\n"
                "# Test\n",
                encoding="utf-8",
            )
            (pricing_source / "README.md").write_text("# Test\n", encoding="utf-8")
            (pricing_source / "data" / "current" / "price-index.json").write_text("{}", encoding="utf-8")
            (pricing_source / "data" / "current" / "release.json").write_text("{}", encoding="utf-8")
            (pricing_source / "references" / "current" / "rules.md").write_text("# rules\n", encoding="utf-8")
            (pricing_source / "references" / "addenda" / "designer-manual-2026-03-22" / "manifest.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22" / "runtime-rules.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22" / "knowledge-layer.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22" / "coverage-ledger.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22" / "coverage-ledger-overrides.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22" / "block-images").mkdir()
            (pricing_source / "reports" / "addenda" / "designer-manual-2026-03-22" / "block-images" / "tmp.png").write_text(
                "x",
                encoding="utf-8",
            )
            (pricing_source / "scripts" / "publish_skill.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (pricing_source / "scripts" / "refresh_and_test.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (pricing_source / "sources" / "inbox" / "README.md").write_text("# inbox\n", encoding="utf-8")
            (contract_review_source / "SKILL.md").write_text(
                "---\n"
                "name: liangqin-contract-review\n"
                'description: "test review skill"\n'
                "---\n\n"
                "# Review\n",
                encoding="utf-8",
            )
            (contract_review_source / "README.md").write_text("# Review\n", encoding="utf-8")
            (contract_review_source / "scripts" / "handle_review_message.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (contract_review_app_root / "cli" / "review_chat.py").write_text("# review chat\n", encoding="utf-8")
            (contract_review_app_root / "core" / "liangqin_paths.py").write_text("# paths\n", encoding="utf-8")
            (contract_review_app_root / "tests").mkdir(parents=True)
            (contract_review_app_root / "tests" / "test_review_chat.py").write_text("# ignore\n", encoding="utf-8")
            publish_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            env = os.environ.copy()
            env["PRICING_SOURCE_DIR"] = str(pricing_source)
            env["CONTRACT_REVIEW_SOURCE_DIR"] = str(contract_review_source)
            env["CONTRACT_REVIEW_APP_ROOT"] = str(contract_review_app_root)
            env["PUBLISH_OPENCLAW_SKILLS_SCRIPT"] = str(publish_script)

            subprocess.run(
                ["bash", str(SCRIPT_PATH), str(output_dir)],
                check=True,
                env=env,
                cwd=REPO_ROOT,
            )

            packages = sorted(output_dir.glob("liangqin-pricing-openclaw-*.zip"))
            self.assertTrue(packages, "expected package_openclaw_skill.sh to create a zip archive")

            with zipfile.ZipFile(packages[-1]) as archive:
                names = set(archive.namelist())

            self.assertIn(
                "liangqin-pricing/references/addenda/designer-manual-2026-03-22/manifest.json",
                names,
            )
            self.assertIn("liangqin-contract-review/SKILL.md", names)
            self.assertIn("liangqin-contract-review/scripts/handle_review_message.py", names)
            self.assertIn(
                "liangqin-contract-review/apps/contract-review/cli/review_chat.py",
                names,
            )
            self.assertIn("scripts/publish_openclaw_skills.py", names)
            self.assertIn(
                "liangqin-pricing/reports/addenda/designer-manual-2026-03-22/runtime-rules.json",
                names,
            )
            self.assertIn(
                "liangqin-pricing/reports/addenda/designer-manual-2026-03-22/knowledge-layer.json",
                names,
            )
            self.assertIn(
                "liangqin-pricing/reports/addenda/designer-manual-2026-03-22/coverage-ledger.json",
                names,
            )
            self.assertIn(
                "liangqin-pricing/reports/addenda/designer-manual-2026-03-22/coverage-ledger-overrides.json",
                names,
            )
            self.assertNotIn(
                "liangqin-pricing/reports/addenda/designer-manual-2026-03-22/block-images/tmp.png",
                names,
            )
            self.assertNotIn(
                "liangqin-contract-review/apps/contract-review/tests/test_review_chat.py",
                names,
            )


if __name__ == "__main__":
    unittest.main()
