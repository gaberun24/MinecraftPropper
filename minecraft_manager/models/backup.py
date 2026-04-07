from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BackupEntry(BaseModel):
    filename: str
    path: str
    backup_type: str  # daily, monthly, update, world
    size_bytes: int
    size_human: str
    created: datetime
    world_name: str | None = None
