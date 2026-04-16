import importlib.util
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

MODULE_PATH = CORE_ROOT / "text_preview.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TEXT_PREVIEW = load_module("contract_review_text_preview", MODULE_PATH)


class TextPreviewTests(unittest.TestCase):
    def test_compose_pdf_text_keeps_later_pages(self) -> None:
        text = TEXT_PREVIEW._compose_pdf_text(
            [
                "第13页 附件 产品名称 产品编号 材质 数量 费用合计（元）",
                "",
                "第21页 儿童房 经典带门书柜 20990010004003 尺寸 长：1240mm 宽：350mm 高：2000mm",
                "第26页 儿童房 经典双屉书桌 20990010004004 尺寸 长：1300mm 宽：600mm 高：780mm",
            ]
        )

        self.assertIn("经典带门书柜", text)
        self.assertIn("经典双屉书桌", text)
        self.assertIn("长：1240mm", text)
        self.assertIn("长：1300mm", text)


if __name__ == "__main__":
    unittest.main()
