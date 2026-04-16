#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI_ROOT = PROJECT_ROOT / "apps" / "contract-review" / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

import review_chat  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return review_chat.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
