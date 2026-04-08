import importlib.util
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "refresh_and_test.py"
SPEC = importlib.util.spec_from_file_location("refresh_and_test", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RefreshAndTestTests(unittest.TestCase):
    def test_has_ready_sources_accepts_pdf_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox = Path(tmpdir)
            (inbox / "catalog.xlsx").write_text("xlsx", encoding="utf-8")
            (inbox / "rules.pdf").write_text("pdf", encoding="utf-8")

            self.assertTrue(MODULE.has_ready_sources(inbox))

    def test_resolve_test_message_prefers_explicit_message(self) -> None:
        message = MODULE.resolve_test_message("自定义测试", "modular-child-bed")
        self.assertEqual(message, "自定义测试")

    def test_resolve_test_message_supports_modular_child_bed_preset(self) -> None:
        message = MODULE.resolve_test_message(None, "modular-child-bed")
        self.assertIn("定制上下床", message)
        self.assertIn("梯柜款", message)

    def test_resolve_test_message_supports_hardware_boundary_preset(self) -> None:
        message = MODULE.resolve_test_message(None, "hardware-boundary")
        self.assertIn("BLUM", message)
        self.assertIn("五金", message)

    def test_resolve_test_message_supports_loft_double_row_wardrobe_preset(self) -> None:
        message = MODULE.resolve_test_message(None, "loft-double-row-wardrobe")
        self.assertIn("半高梯柜上铺床", message)
        self.assertIn("前后双排衣柜", message)

    def test_resolve_test_message_supports_child_bed_rosewood_special_preset(self) -> None:
        message = MODULE.resolve_test_message(None, "child-bed-rosewood-special")
        self.assertIn("乌拉圭玫瑰木", message)
        self.assertIn("错层床", message)

    def test_resolve_test_message_supports_child_bed_width_limit_preset(self) -> None:
        message = MODULE.resolve_test_message(None, "child-bed-width-limit")
        self.assertIn("高架床", message)
        self.assertIn("1.35", message)

    def test_build_reset_command_supports_feishu(self) -> None:
        command = MODULE.build_reset_command(Path("/tmp/skill/scripts"), include_feishu=True)
        self.assertEqual(command[-2:], ["--apply", "--include-feishu"])

    def test_build_reset_command_defaults_to_dingtalk_and_main_only(self) -> None:
        command = MODULE.build_reset_command(Path("/tmp/skill/scripts"), include_feishu=False)
        self.assertEqual(command[-1], "--apply")
        self.assertNotIn("--include-feishu", command)

    def test_build_runtime_health_command_targets_check_script(self) -> None:
        command = MODULE.build_runtime_health_command(Path("/tmp/skill/scripts"), Path("/tmp/skill"))
        self.assertIn("check_runtime_health.py", command[1])
        self.assertEqual(command[-2:], ["--skill-dir", "/tmp/skill"])

    def test_main_runs_runtime_health_check_before_agent(self) -> None:
        calls: list[list[str]] = []

        def fake_run_step(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[1].endswith("publish_skill.py"):
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[1].endswith("check_runtime_health.py"):
                return subprocess.CompletedProcess(command, 0, "运行环境诊断：ok\n", "")
            if command[0] == "openclaw":
                return subprocess.CompletedProcess(command, 0, '{"result":{"payloads":[{"text":"测试通过"}]}}', "")
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "skill"
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "sources" / "inbox").mkdir(parents=True)
            stdout = io.StringIO()
            with mock.patch.object(MODULE, "run_step", side_effect=fake_run_step):
                with redirect_stdout(stdout):
                    exit_code = MODULE.main(["--skill-dir", str(skill_dir), "--timeout", "5"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(any(command[1].endswith("check_runtime_health.py") for command in calls if len(command) > 1))
        self.assertTrue(any(command[0] == "openclaw" for command in calls))
        self.assertIn("运行环境诊断：ok", stdout.getvalue())

    def test_main_stops_when_runtime_health_check_fails(self) -> None:
        calls: list[list[str]] = []

        def fake_run_step(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[1].endswith("publish_skill.py"):
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[1].endswith("check_runtime_health.py"):
                return subprocess.CompletedProcess(command, 1, "运行环境诊断：error\n", "")
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "skill"
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "sources" / "inbox").mkdir(parents=True)
            stdout = io.StringIO()
            with mock.patch.object(MODULE, "run_step", side_effect=fake_run_step):
                with redirect_stdout(stdout):
                    exit_code = MODULE.main(["--skill-dir", str(skill_dir), "--timeout", "5"])

        self.assertEqual(exit_code, 1)
        self.assertTrue(any(command[1].endswith("check_runtime_health.py") for command in calls if len(command) > 1))
        self.assertFalse(any(command[0] == "openclaw" for command in calls))
        self.assertIn("运行环境诊断：error", stdout.getvalue())

    def test_main_can_skip_runtime_health_check(self) -> None:
        calls: list[list[str]] = []

        def fake_run_step(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[1].endswith("publish_skill.py"):
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[0] == "openclaw":
                return subprocess.CompletedProcess(command, 0, '{"result":{"payloads":[{"text":"测试通过"}]}}', "")
            raise AssertionError(f"unexpected command: {command}")

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "skill"
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "sources" / "inbox").mkdir(parents=True)
            stdout = io.StringIO()
            with mock.patch.object(MODULE, "run_step", side_effect=fake_run_step):
                with redirect_stdout(stdout):
                    exit_code = MODULE.main(
                        ["--skill-dir", str(skill_dir), "--timeout", "5", "--skip-runtime-health-check"]
                    )

        self.assertEqual(exit_code, 0)
        self.assertFalse(any(command[1].endswith("check_runtime_health.py") for command in calls if len(command) > 1))
        self.assertTrue(any(command[0] == "openclaw" for command in calls))


if __name__ == "__main__":
    unittest.main()
