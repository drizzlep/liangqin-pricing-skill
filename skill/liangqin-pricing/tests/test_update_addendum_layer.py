import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_addendum_layer.py"
SPEC = importlib.util.spec_from_file_location("update_addendum_layer", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class UpdateAddendumLayerTests(unittest.TestCase):
    def test_build_layer_manifest_keeps_layer_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            layer_dir = root / "references" / "addenda" / "designer-a"
            layer_dir.mkdir(parents=True)
            candidate = root / "rules-candidate.json"
            index = root / "rules-index.json"
            runtime_rules = root / "runtime-rules.json"
            drafts_dir = root / "drafts"
            source_md = root / "rules-source.md"
            candidate.write_text("{}", encoding="utf-8")
            index.write_text("{}", encoding="utf-8")
            runtime_rules.write_text("{}", encoding="utf-8")
            drafts_dir.mkdir()
            (drafts_dir / "manifest.json").write_text('{"domain_count": 2}', encoding="utf-8")
            source_md.write_text("# draft", encoding="utf-8")

            manifest = MODULE.build_layer_manifest(
                layer_id="designer-a",
                layer_name="设计师追加规则 A",
                source_file=Path("/tmp/source.pdf"),
                candidate_path=candidate,
                index_path=index,
                runtime_rules_path=runtime_rules,
                source_markdown_path=source_md,
                drafts_dir=drafts_dir,
                manifest_dir=layer_dir,
            )

        self.assertEqual(manifest["layer_id"], "designer-a")
        self.assertEqual(manifest["layer_name"], "设计师追加规则 A")
        self.assertEqual(manifest["status"], "ACTIVE")
        self.assertFalse(manifest["mutates_base_rules"])
        self.assertIn("rules_index_file", manifest["artifacts"])
        self.assertIn("runtime_rules_file", manifest["artifacts"])
        self.assertFalse(str(manifest["source_file"]).startswith("/"))
        self.assertFalse(str(manifest["artifacts"]["runtime_rules_file"]).startswith("/"))

    def test_write_manifest_creates_layer_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "layer"
            manifest = {"layer_id": "designer-b", "status": "ACTIVE"}

            MODULE.write_manifest(output_dir, manifest)

            written = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(written["layer_id"], "designer-b")


if __name__ == "__main__":
    unittest.main()
