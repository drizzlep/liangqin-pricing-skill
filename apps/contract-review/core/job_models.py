from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class SourceAsset:
    asset_id: str
    source_path: str
    relative_path: str
    file_name: str
    extension: str
    media_kind: str
    role_hint: str
    text_preview: str = ""
    text_extract_method: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "relative_path": self.relative_path,
            "file_name": self.file_name,
            "extension": self.extension,
            "media_kind": self.media_kind,
            "role_hint": self.role_hint,
            "text_preview": self.text_preview,
            "text_extract_method": self.text_extract_method,
            "metadata": dict(self.metadata),
        }


@dataclass
class ReviewJob:
    job_id: str
    batch_id: str
    group_key: str
    source_type: str
    source_channel: str
    requested_actions: list[str]
    assets: list[SourceAsset]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)

    def primary_contract_assets(self) -> list[SourceAsset]:
        return [asset for asset in self.assets if asset.role_hint == "primary_contract"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "batch_id": self.batch_id,
            "group_key": self.group_key,
            "source_type": self.source_type,
            "source_channel": self.source_channel,
            "requested_actions": list(self.requested_actions),
            "assets": [asset.to_dict() for asset in self.assets],
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


@dataclass
class BatchPlan:
    batch_id: str
    batch_dir: Path
    source_type: str
    source_channel: str
    requested_actions: list[str]
    jobs: list[ReviewJob]
    manifest: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "batch_dir": str(self.batch_dir),
            "source_type": self.source_type,
            "source_channel": self.source_channel,
            "requested_actions": list(self.requested_actions),
            "jobs": [job.to_dict() for job in self.jobs],
            "manifest": dict(self.manifest),
            "warnings": list(self.warnings),
            "created_at": self.created_at,
        }
