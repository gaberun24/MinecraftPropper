from __future__ import annotations

import asyncio
import re
from pathlib import Path

from minecraft_manager.config import Settings
from minecraft_manager.models.server import PlayerInfo, ServerStatus, VersionInfo


def _parse_properties(path: Path) -> dict[str, str]:
    props = {}
    if not path.exists():
        return props
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            props[key.strip()] = value.strip()
    return props


def _parse_version_file(path: Path) -> VersionInfo:
    info = VersionInfo()
    if not path.exists():
        return info
    content = path.read_text().strip()
    # Format: paper-1.21.4-193 or multi-line key=value
    paper_match = re.match(r"paper-(.+?)-(\d+)", content)
    if paper_match:
        info.minecraft = paper_match.group(1)
        info.paper = f"build {paper_match.group(2)}"

    for line in content.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if key == "geyser":
                info.geyser = value
            elif key == "floodgate":
                info.floodgate = value
    return info


def _human_uptime(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        return f"{hours}h {mins}m"
    days = hours // 24
    hrs = hours % 24
    return f"{days}d {hrs}h"


async def _is_server_running(settings: Settings) -> bool:
    if settings.dev_mode:
        return Path(settings.minecraft_dir / ".dev_running").exists()
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "is-active", "--quiet", settings.systemd_unit,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def _get_uptime(settings: Settings) -> str:
    if settings.dev_mode:
        return "dev mode"
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "show", settings.systemd_unit,
            "--property=ActiveEnterTimestamp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        line = stdout.decode().strip()
        if "=" in line:
            timestamp_str = line.split("=", 1)[1].strip()
            if timestamp_str:
                from datetime import datetime

                dt = datetime.strptime(timestamp_str, "%a %Y-%m-%d %H:%M:%S %Z")
                delta = (datetime.now() - dt).total_seconds()
                return _human_uptime(max(0, delta))
    except Exception:
        pass
    return ""


def _parse_players_from_log(log_path: Path) -> list[PlayerInfo]:
    """Parse recent join/leave messages to estimate current players."""
    players: dict[str, PlayerInfo] = {}
    if not log_path.exists():
        return []

    try:
        lines = log_path.read_text().splitlines()[-200:]
    except Exception:
        return []

    join_pattern = re.compile(r"\[.*?INFO\].*?:\s+(\S+)\s+joined the game")
    leave_pattern = re.compile(r"\[.*?INFO\].*?:\s+(\S+)\s+left the game")
    bedrock_prefix = "."  # Floodgate prefixes Bedrock names with "."

    for line in lines:
        join_match = join_pattern.search(line)
        if join_match:
            name = join_match.group(1)
            players[name] = PlayerInfo(
                name=name,
                is_bedrock=name.startswith(bedrock_prefix),
            )
            continue
        leave_match = leave_pattern.search(line)
        if leave_match:
            players.pop(leave_match.group(1), None)

    return list(players.values())


async def get_server_status(settings: Settings) -> ServerStatus:
    running = await _is_server_running(settings)
    props = _parse_properties(settings.server_properties_path)
    versions = _parse_version_file(settings.version_file_path)
    uptime = await _get_uptime(settings) if running else ""
    players = _parse_players_from_log(settings.log_file_path) if running else []

    return ServerStatus(
        running=running,
        uptime=uptime,
        versions=versions,
        players=players,
        player_count=len(players),
        max_players=int(props.get("max-players", "20")),
        motd=props.get("motd", ""),
        level_name=props.get("level-name", "world"),
    )
