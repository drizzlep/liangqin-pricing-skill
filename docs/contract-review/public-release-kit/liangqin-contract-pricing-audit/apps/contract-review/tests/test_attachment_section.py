import importlib.util
import sys
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = APP_ROOT / "core"
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

MODULE_PATH = CORE_ROOT / "attachment_section.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ATTACHMENT_SECTION = load_module("contract_review_attachment_section", MODULE_PATH)


class AttachmentSectionTests(unittest.TestCase):
    def test_resolve_attachment_anchor_page_prefers_real_attachment_page(self) -> None:
        text = (
            "第1页 合同首页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》）。"
            "第13页 附件：《定制清单及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
            "经典床头柜 20990010004001 北美樱桃木 1 1780 "
            "第14页 主卧 经典床头柜 20990010004001 尺寸 长：450mm 宽：400mm 高：500mm"
        )

        page_no = ATTACHMENT_SECTION.resolve_attachment_anchor_page(text)

        self.assertEqual(page_no, 13)

    def test_extract_attachment_pricing_section_prefers_explicit_attachment_anchor(self) -> None:
        text = (
            "第1页 合同首页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》）。"
            "第13页 附件：《定制清单及设计图纸》 产品名称 产品编号 材质 数量 费用合计（元） "
            "经典床头柜 20990010004001 北美樱桃木 1 1780 "
            "第14页 主卧 经典床头柜 209900100 04001 尺寸 长：450mm 宽：400mm 高：500mm"
        )

        section = ATTACHMENT_SECTION.extract_attachment_pricing_section(text)

        self.assertTrue(section.startswith("附件：《定制清单及设计图纸》"))
        self.assertNotIn("1.1甲方委托乙方定制家具", section)
        self.assertIn("长：450mm", section)

    def test_extract_attachment_pricing_section_trims_repeated_contract_pages_after_attachment(self) -> None:
        text = (
            "第13页 附件： 产品名称 产品编号 材质 数量 费用合计（元） "
            "经典床头柜 20990010004001 北美樱桃木 1 1780 "
            "第14页 主卧 经典床头柜 209900100 04001 尺寸 长：450mm 宽：400mm 高：500mm "
            "第1页 1.1甲方委托乙方定制家具（详见附件《定制清单及设计图纸》），合同总金额1780元。"
        )

        section = ATTACHMENT_SECTION.extract_attachment_pricing_section(text)

        self.assertIn("经典床头柜 20990010004001", section)
        self.assertNotIn("合同总金额1780元", section)
        self.assertNotIn("1.1甲方委托乙方定制家具", section)

    def test_extract_attachment_pricing_section_falls_back_to_original_text_without_anchor(self) -> None:
        text = "产品名称：儿童上下床 材质：乌拉圭玫瑰木 床垫宽度：900mm 床垫长度：2000mm"

        section = ATTACHMENT_SECTION.extract_attachment_pricing_section(text)

        self.assertEqual(section, text)


if __name__ == "__main__":
    unittest.main()
