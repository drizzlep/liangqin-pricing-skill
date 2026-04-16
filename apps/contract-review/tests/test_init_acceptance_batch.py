import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CLI_ROOT = APP_ROOT / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

MODULE_PATH = CLI_ROOT / "init_acceptance_batch.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


INIT_ACCEPTANCE_BATCH = load_module("contract_review_init_acceptance_batch_cli", MODULE_PATH)


class InitAcceptanceBatchTests(unittest.TestCase):
    def test_init_acceptance_batch_creates_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            batch_dir = root / "acceptance-batch-2026-04-16"
            payload = INIT_ACCEPTANCE_BATCH.run(
                [
                    "--batch-dir",
                    str(batch_dir),
                    "--output-mode",
                    "json",
                ]
            )

            manifest_path = batch_dir / "manifest.json"
            ground_truth_path = root / "acceptance-ground-truth.csv"
            self.assertTrue(manifest_path.exists())
            self.assertTrue(ground_truth_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["case_keys"], INIT_ACCEPTANCE_BATCH.DEFAULT_CASE_KEYS)
        self.assertEqual(manifest["source_batch_id"], "acceptance-batch-2026-04-16")
        self.assertEqual(manifest["requested_actions"], ["audit", "replay"])


if __name__ == "__main__":
    unittest.main()
