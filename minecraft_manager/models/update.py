from __future__ import annotations

from pydantic import BaseModel


class BuildInfo(BaseModel):
    project: str  # paper, geyser, floodgate
    version: str
    build: int
    download_url: str = ""
    sha256: str = ""


class UpdateCheck(BaseModel):
    paper: BuildInfo | None = None
    geyser: BuildInfo | None = None
    floodgate: BuildInfo | None = None
    paper_update_available: bool = False
    geyser_update_available: bool = False
    floodgate_update_available: bool = False
    geyser_compatible: bool = True
    message: str = ""
