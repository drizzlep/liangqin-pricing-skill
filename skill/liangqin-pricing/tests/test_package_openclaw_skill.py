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
    def test_package_includes_addendum_manifests_and_runtime_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source-skill"
            output_dir = root / "dist"

            (source / "data" / "current").mkdir(parents=True)
            (source / "references" / "current").mkdir(parents=True)
            (source / "references" / "addenda" / "designer-manual-2026-03-22").mkdir(parents=True)
            (source / "reports" / "addenda" / "designer-manual-2026-03-22").mkdir(parents=True)
            (source / "scripts").mkdir(parents=True)
            (source / "sources" / "inbox").mkdir(parents=True)

            (source / "SKILL.md").write_text(
                "---\n"
                "name: liangqin-pricing\n"
                'description: "test skill"\n'
                "---\n\n"
                "# Test\n",
                encoding="utf-8",
            )
            (source / "README.md").write_text("# Test\n", encoding="utf-8")
            (source / "data" / "current" / "price-index.json").write_text("{}", encoding="utf-8")
            (source / "data" / "current" / "release.json").write_text("{}", encoding="utf-8")
            (source / "references" / "current" / "rules.md").write_text("# rules\n", encoding="utf-8")
            (source / "references" / "addenda" / "designer-manual-2026-03-22" / "manifest.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source / "reports" / "addenda" / "designer-manual-2026-03-22" / "runtime-rules.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source / "reports" / "addenda" / "designer-manual-2026-03-22" / "knowledge-layer.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source / "reports" / "addenda" / "designer-manual-2026-03-22" / "coverage-ledger.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source / "reports" / "addenda" / "designer-manual-2026-03-22" / "coverage-ledger-overrides.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            (source / "reports" / "addenda" / "designer-manual-2026-03-22" / "block-images").mkdir()
            (source / "reports" / "addenda" / "designer-manual-2026-03-22" / "block-images" / "tmp.png").write_text(
                "x",
                encoding="utf-8",
            )
            (source / "scripts" / "publish_skill.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (source / "scripts" / "refresh_and_test.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (source / "sources" / "inbox" / "README.md").write_text("# inbox\n", encoding="utf-8")

            env = os.environ.copy()
            env["SOURCE_DIR"] = str(source)

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


if __name__ == "__main__":
    unittest.main()
