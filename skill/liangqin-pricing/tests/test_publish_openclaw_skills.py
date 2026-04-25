import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "publish_openclaw_skills.py"
SPEC = importlib.util.spec_from_file_location("publish_openclaw_skills", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_stub_publish_engine(engine_path: Path) -> None:
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    engine_path.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import argparse
            import sys
            import shutil
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument("--source", required=True)
            parser.add_argument("--dest", required=True)
            parser.add_argument("--workspace-dest", required=True)
            args = parser.parse_args()

            if Path(args.source).resolve() == Path(args.dest).resolve():
                print("Source and destination must be different.", file=sys.stderr)
                raise SystemExit(1)

            for raw_target in (args.dest, args.workspace_dest):
                target = Path(raw_target)
                if target.exists():
                    shutil.rmtree(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(args.source, target)
                print(f"Published skill to {target}")
            """
        ),
        encoding="utf-8",
    )


def write_skill_dir(skill_root: Path, skill_name: str) -> None:
    skill_root.mkdir(parents=True, exist_ok=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        f"name: {skill_name}\n"
        'description: "test skill"\n'
        "---\n\n"
        "# Test\n",
        encoding="utf-8",
    )
    (skill_root / "README.md").write_text(f"# {skill_name}\n", encoding="utf-8")


def write_contract_review_app(app_root: Path) -> None:
    (app_root / "cli").mkdir(parents=True, exist_ok=True)
    (app_root / "core").mkdir(parents=True, exist_ok=True)
    (app_root / "cli" / "review_chat.py").write_text("# review chat\n", encoding="utf-8")
    (app_root / "core" / "batch_runtime.py").write_text("# batch runtime\n", encoding="utf-8")


class PublishOpenClawSkillsTests(unittest.TestCase):
    def test_main_publishes_supported_skills_to_active_and_workspace_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "skill"
            skills_root = root / "openclaw" / "skills"
            workspace_root = root / "openclaw" / "workspace" / "skills"
            engine_path = source_root / "liangqin-pricing" / "scripts" / "publish_skill.py"
            contract_review_app_root = root / "apps" / "contract-review"

            write_skill_dir(source_root / "liangqin-pricing", "liangqin-pricing")
            write_skill_dir(source_root / "liangqin-contract-review", "liangqin-contract-review")
            write_stub_publish_engine(engine_path)
            write_contract_review_app(contract_review_app_root)

            exit_code = MODULE.main(
                [
                    "--source-root",
                    str(source_root),
                    "--skills-root",
                    str(skills_root),
                    "--workspace-root",
                    str(workspace_root),
                    "--publish-engine",
                    str(engine_path),
                    "--contract-review-app-root",
                    str(contract_review_app_root),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((skills_root / "liangqin-pricing" / "SKILL.md").exists())
            self.assertTrue((skills_root / "liangqin-contract-review" / "SKILL.md").exists())
            self.assertTrue((workspace_root / "liangqin-pricing" / "SKILL.md").exists())
            self.assertTrue((workspace_root / "liangqin-contract-review" / "SKILL.md").exists())
            self.assertTrue(
                (workspace_root / "liangqin-contract-review" / "apps" / "contract-review" / "cli" / "review_chat.py").exists()
            )

    def test_main_can_publish_from_installed_skills_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            skills_root = root / "openclaw" / "skills"
            workspace_root = root / "openclaw" / "workspace" / "skills"
            engine_path = skills_root / "liangqin-pricing" / "scripts" / "publish_skill.py"

            write_skill_dir(skills_root / "liangqin-pricing", "liangqin-pricing")
            write_skill_dir(skills_root / "liangqin-contract-review", "liangqin-contract-review")
            write_contract_review_app(skills_root / "liangqin-contract-review" / "apps" / "contract-review")
            write_stub_publish_engine(engine_path)

            exit_code = MODULE.main(
                [
                    "--source-root",
                    str(skills_root),
                    "--skills-root",
                    str(skills_root),
                    "--workspace-root",
                    str(workspace_root),
                    "--publish-engine",
                    str(engine_path),
                    "--contract-review-app-root",
                    str(root / "missing-app-root"),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((workspace_root / "liangqin-pricing" / "SKILL.md").exists())
            self.assertTrue((workspace_root / "liangqin-contract-review" / "SKILL.md").exists())

    def test_main_can_publish_only_contract_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "skill"
            skills_root = root / "openclaw" / "skills"
            workspace_root = root / "openclaw" / "workspace" / "skills"
            engine_path = source_root / "liangqin-pricing" / "scripts" / "publish_skill.py"
            contract_review_app_root = root / "apps" / "contract-review"

            write_skill_dir(source_root / "liangqin-pricing", "liangqin-pricing")
            write_skill_dir(source_root / "liangqin-contract-review", "liangqin-contract-review")
            write_stub_publish_engine(engine_path)
            write_contract_review_app(contract_review_app_root)

            exit_code = MODULE.main(
                [
                    "--skill",
                    "liangqin-contract-review",
                    "--source-root",
                    str(source_root),
                    "--skills-root",
                    str(skills_root),
                    "--workspace-root",
                    str(workspace_root),
                    "--publish-engine",
                    str(engine_path),
                    "--contract-review-app-root",
                    str(contract_review_app_root),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse((skills_root / "liangqin-pricing").exists())
            self.assertTrue((skills_root / "liangqin-contract-review" / "SKILL.md").exists())
            self.assertFalse((workspace_root / "liangqin-pricing").exists())
            self.assertTrue((workspace_root / "liangqin-contract-review" / "SKILL.md").exists())
            self.assertTrue(
                (workspace_root / "liangqin-contract-review" / "apps" / "contract-review" / "core" / "batch_runtime.py").exists()
            )

    def test_main_can_publish_prebundled_contract_review_without_external_app_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "skill"
            skills_root = root / "openclaw" / "skills"
            workspace_root = root / "openclaw" / "workspace" / "skills"
            engine_path = source_root / "liangqin-pricing" / "scripts" / "publish_skill.py"

            write_skill_dir(source_root / "liangqin-pricing", "liangqin-pricing")
            write_skill_dir(source_root / "liangqin-contract-review", "liangqin-contract-review")
            write_contract_review_app(source_root / "liangqin-contract-review" / "apps" / "contract-review")
            write_stub_publish_engine(engine_path)

            exit_code = MODULE.main(
                [
                    "--skill",
                    "liangqin-contract-review",
                    "--source-root",
                    str(source_root),
                    "--skills-root",
                    str(skills_root),
                    "--workspace-root",
                    str(workspace_root),
                    "--publish-engine",
                    str(engine_path),
                    "--contract-review-app-root",
                    str(root / "missing-app-root"),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(
                (workspace_root / "liangqin-contract-review" / "apps" / "contract-review" / "cli" / "review_chat.py").exists()
            )


if __name__ == "__main__":
    unittest.main()
