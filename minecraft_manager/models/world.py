from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .backup import BackupEntry


class WorldInfo(BaseModel):
    name: str
    is_active: bool = False
    size_bytes: int = 0
    size_human: str = "0 B"
    last_modified: datetime | None = None
    has_nether: bool = False
    has_end: bool = False
    snapshots: list[BackupEntry] = []
