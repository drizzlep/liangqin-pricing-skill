import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zipfile import ZipFile


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_rules_candidate.py"
SPEC = importlib.util.spec_from_file_location("extract_rules_candidate", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    document_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>',
    ]
    for paragraph in paragraphs:
        document_xml.append(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>")
    document_xml.append("</w:body></w:document>")

    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        archive.writestr("word/document.xml", "".join(document_xml))


def write_minimal_pdf(path: Path, lines: list[str]) -> None:
    stream_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            stream_lines.append("0 -18 Td")
        stream_lines.append(f"({escaped}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream\nendobj\n",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer << /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
    )
    path.write_bytes(pdf)


class ExtractRulesCandidateTests(unittest.TestCase):
    def test_should_ocr_page_when_visual_rule_page_has_many_images(self) -> None:
        should_ocr = MODULE.should_ocr_page(
            text_layer_text="可选色样 圣勃朗鱼肚白 极光白 阿勒山闪电黑",
            image_count=4,
            ocr_min_chars=20,
        )

        self.assertTrue(should_ocr)

    def test_ensure_pdf_renderer_binary_reuses_compiled_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            def fake_run(command: list[str], **kwargs: object) -> object:
                output_flag_index = command.index("-o") + 1
                Path(command[output_flag_index]).write_text("binary", encoding="utf-8")
                return mock.Mock(returncode=0, stderr="", stdout="")

            with mock.patch.object(MODULE.subprocess, "run", side_effect=fake_run) as run_mock:
                first = MODULE.ensure_pdf_renderer_binary(cache_dir=cache_dir)
                second = MODULE.ensure_pdf_renderer_binary(cache_dir=cache_dir)

            self.assertEqual(first, second)
            self.assertEqual(run_mock.call_count, 1)
            self.assertTrue(first.exists())

    def test_build_candidate_payload_supports_docx(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "rules.docx"
            write_minimal_docx(docx_path, ["1.柜体", "600mm＜柜体进深≤700mm，加价15%；"])

            payload = MODULE.build_candidate_payload(docx_path)

        self.assertEqual(payload["source_format"], "docx")
        self.assertEqual(payload["sections"][0]["heading"], "1.柜体")
        self.assertEqual(payload["sections"][1]["heading"], "600mm＜柜体进深≤700mm，加价15%；")

    def test_build_candidate_payload_supports_pdf_and_markdown_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "rules.pdf"
            markdown_path = Path(tmpdir) / "rules-source.md"
            write_minimal_pdf(pdf_path, ["1. Cabinet", "600mm<depth<=700mm add 15%"])

            with mock.patch.object(MODULE, "ocr_pdf_page", side_effect=AssertionError("unexpected OCR")):
                payload = MODULE.build_candidate_payload(pdf_path, markdown_output=markdown_path)

            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(payload["source_format"], "pdf")
        self.assertEqual(payload["page_count"], 1)
        self.assertEqual(payload["pages"][0]["extract_method"], "text_layer")
        self.assertEqual(payload["sections"][0]["page"], 1)
        self.assertIn("normalized_rule", payload["sections"][0])
        self.assertIn("extract_method: text_layer", markdown)
        self.assertIn("1. Cabinet", markdown)

    def test_build_pdf_page_record_marks_hybrid_when_ocr_is_needed(self) -> None:
        record = MODULE.build_pdf_page_record(page_number=7, text_layer_text="Too short", ocr_text="Recovered content", ocr_min_chars=50)

        self.assertEqual(record["page"], 7)
        self.assertEqual(record["extract_method"], "hybrid")
        self.assertIn("Recovered content", record["raw_text"])


if __name__ == "__main__":
    unittest.main()
