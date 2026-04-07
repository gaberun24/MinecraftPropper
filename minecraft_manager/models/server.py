from __future__ import annotations

from pydantic import BaseModel


class VersionInfo(BaseModel):
    paper: str = "unknown"
    minecraft: str = "unknown"
    geyser: str = "unknown"
    floodgate: str = "unknown"


class PlayerInfo(BaseModel):
    name: str
    is_bedrock: bool = False


class ServerStatus(BaseModel):
    running: bool = False
    uptime: str = ""
    versions: VersionInfo = VersionInfo()
    players: list[PlayerInfo] = []
    player_count: int = 0
    max_players: int = 0
    motd: str = ""
    level_name: str = ""
