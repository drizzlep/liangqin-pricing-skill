import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "material_names.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("material_names", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class MaterialNamesTests(unittest.TestCase):
    def test_normalize_material_for_query_supports_common_aliases(self) -> None:
        self.assertEqual(MODULE.normalize_material_for_query("北美黑胡桃"), "黑胡桃")
        self.assertEqual(MODULE.normalize_material_for_query("白橡"), "白橡木")
        self.assertEqual(MODULE.normalize_material_for_query("北美白蜡"), "白蜡木")
        self.assertEqual(MODULE.normalize_material_for_query("玫瑰木"), "玫瑰木")

    def test_formalize_material_name_promotes_aliases_to_formal_names(self) -> None:
        self.assertEqual(MODULE.formalize_material_name("黑胡桃"), "北美黑胡桃木")
        self.assertEqual(MODULE.formalize_material_name("北美樱桃"), "北美樱桃木")
        self.assertEqual(MODULE.formalize_material_name("白橡"), "北美白橡木")
        self.assertEqual(MODULE.formalize_material_name("乌拉圭玫瑰木"), "乌拉圭玫瑰木")

    def test_formalize_text_rewrites_common_material_aliases(self) -> None:
        text = "黑胡桃衣柜配白橡门板，里面用玫瑰木。"
        result = MODULE.formalize_text(text)

        self.assertIn("北美黑胡桃木衣柜", result)
        self.assertIn("北美白橡木门板", result)
        self.assertIn("乌拉圭玫瑰木", result)


if __name__ == "__main__":
    unittest.main()
