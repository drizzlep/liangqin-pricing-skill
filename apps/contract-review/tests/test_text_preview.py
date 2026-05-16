import importlib.util
import sys
import tempfile
import unittest
import zipfile
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
    def test_extract_docx_preview_keeps_later_product_detail_by_default(self) -> None:
        paragraphs = [
            "产品名称 产品编号 材质 数量 费用合计（元）",
            "升级经典无腰线衣柜 20260229002001 北美白橡木 1 36936",
            "经典榻榻米+衣柜组合 20260229002002 北美白橡木 1 14760",
        ]
        paragraphs.extend(f"合同条款占位文本{i:03d}" for i in range(80))
        paragraphs.append(
            "次卧 经典榻榻米+衣柜组合 20260229002002 北美白橡木 "
            "尺寸 长：2000mm 宽：1500mm 高：400mm"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "combo.docx"
            _write_minimal_docx(path, paragraphs)

            text, method = TEXT_PREVIEW.extract_text_preview(path)

        self.assertEqual(method, "docx_text")
        self.assertIn("经典榻榻米+衣柜组合", text)
        self.assertIn("长：2000mm", text)
        self.assertIn("宽：1500mm", text)
        self.assertIn("高：400mm", text)

    def test_compose_pdf_text_keeps_later_pages(self) -> None:
        text = TEXT_PREVIEW._compose_pdf_text(
            [
                "第13页 附件 产品名称 产品编号 材质 数量 费用合计（元）",
                "",
                "第21页 儿童房 经典带门书柜 20260350004003 尺寸 长：1240mm 宽：350mm 高：2000mm",
                "第26页 儿童房 经典双屉书桌 20260350004004 尺寸 长：1300mm 宽：600mm 高：780mm",
            ]
        )

        self.assertIn("经典带门书柜", text)
        self.assertIn("经典双屉书桌", text)
        self.assertIn("长：1240mm", text)
        self.assertIn("长：1300mm", text)


def _write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    xml_paragraphs = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{xml_paragraphs}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


if __name__ == "__main__":
    unittest.main()
