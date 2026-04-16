from __future__ import annotations

import re


DIGIT_RUN_PATTERN = re.compile(r"\d{11,}")
MIN_PRODUCT_CODE_LENGTH = 14
MAX_PRODUCT_CODE_LENGTH = 15


def extract_unique_product_codes(text: str) -> list[str]:
    compact_text = re.sub(r"\s+", "", str(text or ""))
    if not compact_text:
        return []

    product_codes: set[str] = set()
    for match in DIGIT_RUN_PATTERN.finditer(compact_text):
        token = match.group(0)
        for index in range(len(token) - 1):
            if token[index : index + 2] != "20":
                continue
            candidate = token[index:]
            if MIN_PRODUCT_CODE_LENGTH <= len(candidate) <= MAX_PRODUCT_CODE_LENGTH:
                product_codes.add(candidate)

    return sorted(product_codes)


def count_unique_product_codes(text: str) -> int:
    return len(extract_unique_product_codes(text))
