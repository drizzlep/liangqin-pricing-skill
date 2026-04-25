from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def _candidate_parent(path: Path, index: int) -> Path | None:
    parents = path.parents
    if index >= len(parents):
        return None
    return parents[index]


@lru_cache(maxsize=None)
def resolve_pricing_scripts_dir(anchor_path: str | Path | None = None) -> Path:
    anchor = Path(anchor_path).expanduser().resolve() if anchor_path else Path(__file__).resolve()
    candidates: list[Path] = []

    repo_root = _candidate_parent(anchor, 3)
    if repo_root is not None:
        candidates.append(repo_root / "skill" / "liangqin-pricing" / "scripts")

    skills_root = _candidate_parent(anchor, 4)
    if skills_root is not None:
        candidates.append(skills_root / "liangqin-pricing" / "scripts")

    seen: set[Path] = set()
    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen:
            continue
        seen.add(resolved_candidate)
        if resolved_candidate.exists():
            return resolved_candidate

    raise FileNotFoundError(
        "未找到 liangqin-pricing scripts 目录，已检查："
        + ", ".join(str(path) for path in candidates)
    )
