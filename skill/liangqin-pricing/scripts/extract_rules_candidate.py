#!/usr/bin/env python3
"""Extract candidate rule sections from a Liangqin docx file."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s*(.+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract candidate rule sections from a docx file.")
    parser.add_argument("--input", required=True, help="Path to the source docx file.")
    parser.add_argument("--output", required=True, help="Path to write candidate JSON.")
    return parser.parse_args()


def extract_lines(path: Path) -> list[str]:
    with ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    lines: list[str] = []
    for para in root.findall(".//w:p", W_NS):
        text = "".join(node.text or "" for node in para.findall(".//w:t", W_NS)).strip()
        if text:
            lines.append(text)
    return lines


def is_heading(line: str) -> bool:
    match = HEADING_RE.match(line)
    if not match:
        return False
    tail = match.group(2).strip()
    if not tail:
        return False
    # Exclude plain numeric table rows such as "4980" or "1.20".
    if re.fullmatch(r"[\d./\-+%＜＞≤≥mM㎡元\s]+", tail):
        return False
    return True


def sectionize(lines: list[str]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        if is_heading(line):
            current = {"heading": line, "content": []}
            sections.append(current)
            continue
        if current is None:
            current = {"heading": "前言", "content": []}
            sections.append(current)
        current["content"].append(line)
    return sections


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = extract_lines(input_path)
    payload = {
        "source_file": str(input_path),
        "line_count": len(lines),
        "sections": sectionize(lines),
    }
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, output_path)

    print(f"Wrote {len(payload['sections'])} candidate sections to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
