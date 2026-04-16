from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def resolve_pricing_skill_dir() -> Path:
    env_path = str(os.environ.get("LIANGQIN_PRICING_SKILL_DIR") or "").strip()
    candidates = [
        Path(env_path).expanduser() if env_path else None,
        _repo_root() / "skill" / "liangqin-pricing",
        _repo_root().parent / "liangqin-pricing",
        Path.home() / ".openclaw" / "workspace" / "skills" / "liangqin-pricing",
        Path.home() / ".openclaw" / "skills" / "liangqin-pricing",
    ]
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Unable to locate liangqin-pricing. Set LIANGQIN_PRICING_SKILL_DIR to the installed skill directory."
    )


@lru_cache(maxsize=1)
def resolve_pricing_scripts_dir() -> Path:
    scripts_dir = resolve_pricing_skill_dir() / "scripts"
    if not scripts_dir.is_dir():
        raise FileNotFoundError(f"Pricing scripts directory not found: {scripts_dir}")
    return scripts_dir


@lru_cache(maxsize=1)
def resolve_paddleocr_python() -> Path | None:
    env_path = str(os.environ.get("LIANGQIN_CONTRACT_AUDIT_PADDLE_PYTHON") or "").strip()
    candidates = [
        Path(env_path).expanduser() if env_path else None,
        _repo_root() / ".venv-paddleocr310-arm64" / "bin" / "python",
        _repo_root() / ".venv-paddleocr310-arm64" / "bin" / "python3",
        _repo_root() / ".venv" / "bin" / "python",
        _repo_root() / ".venv" / "bin" / "python3",
        Path(sys.executable) if sys.executable else None,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None
