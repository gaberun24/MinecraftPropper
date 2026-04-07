from __future__ import annotations

import asyncio
import re
import shutil
import tarfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from minecraft_manager.config import Settings
from minecraft_manager.models.backup import BackupEntry
from minecraft_manager.models.world import WorldInfo
from minecraft_manager.services.backup import (
    _human_size,
    _dir_size,
    create_backup,
    list_backups,
)
from minecraft_manager.services.console import send_command
from minecraft_manager.services.server_control import start_server, stop_server
from minecraft_manager.services.server_status import _is_server_running, _parse_properties

# Lock for world operations
_world_lock = asyncio.Lock()

# Characters allowed in world names
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_\- ]+$")


def _world_dirs(base: Path, name: str) -> list[Path]:
    """Return the 3 dimension directories for a world."""
    return [
        base / name,
        base / f"{name}_nether",
        base / f"{name}_the_end",
    ]


def _is_world_dir(path: Path) -> bool:
    """Check if a directory is a Minecraft world (has level.dat)."""
    return (path / "level.dat").exists()


def _get_active_world(settings: Settings) -> str:
    """Read the active world name from server.properties."""
    props = _parse_properties(settings.server_properties_path)
    return props.get("level-name", "world")


def _set_active_world(settings: Settings, name: str) -> None:
    """Update level-name in server.properties."""
    props_path = settings.server_properties_path
    if not props_path.exists():
        return

    content = props_path.read_text()
    new_content = re.sub(
        r"^level-name=.*$",
        f"level-name={name}",
        content,
        flags=re.MULTILINE,
    )
    props_path.write_text(new_content)


def list_worlds(settings: Settings) -> list[WorldInfo]:
    """List all worlds in the minecraft directory."""
    mc_dir = settings.minecraft_dir
    active_name = _get_active_world(settings)
    worlds: dict[str, WorldInfo] = {}

    if not mc_dir.exists():
        return []

    # Find all directories that contain level.dat (overworld dirs)
    for item in sorted(mc_dir.iterdir()):
        if not item.is_dir():
            continue
        # Skip non-world directories
        if item.name in ("plugins", "logs", "cache", "libraries", "config", "versions"):
            continue
        # Skip nether/end dirs (they'll be associated with their overworld)
        if item.name.endswith("_nether") or item.name.endswith("_the_end"):
            continue

        if _is_world_dir(item):
            name = item.name
            nether_dir = mc_dir / f"{name}_nether"
            end_dir = mc_dir / f"{name}_the_end"

            total_size = _dir_size(item)
            has_nether = nether_dir.exists()
            has_end = end_dir.exists()
            if has_nether:
                total_size += _dir_size(nether_dir)
            if has_end:
                total_size += _dir_size(end_dir)

            # Get last modified from level.dat
            level_dat = item / "level.dat"
            last_mod = datetime.fromtimestamp(level_dat.stat().st_mtime) if level_dat.exists() else None

            # Get snapshots for this world
            snapshots = list_backups(settings, backup_type="world")
            world_snaps = [s for s in snapshots if s.world_name == name]

            worlds[name] = WorldInfo(
                name=name,
                is_active=(name == active_name),
                size_bytes=total_size,
                size_human=_human_size(total_size),
                last_modified=last_mod,
                has_nether=has_nether,
                has_end=has_end,
                snapshots=world_snaps,
            )

    return sorted(worlds.values(), key=lambda w: (not w.is_active, w.name))


async def activate_world(settings: Settings, name: str) -> tuple[bool, str]:
    """Switch the active world. Requires server stop/start."""
    if _world_lock.locked():
        return False, "Another world operation is in progress"

    async with _world_lock:
        mc_dir = settings.minecraft_dir
        overworld = mc_dir / name

        if not _is_world_dir(overworld):
            return False, f"World '{name}' not found or invalid"

        active = _get_active_world(settings)
        if active == name:
            return True, f"World '{name}' is already active"

        # Stop server if running
        was_running = await _is_server_running(settings)
        if was_running:
            await send_command("say Switching worlds, server restarting...", settings)
            await asyncio.sleep(2)
            await stop_server(settings)
            await asyncio.sleep(3)

        # Update server.properties
        _set_active_world(settings, name)

        # Start server if it was running
        if was_running:
            await start_server(settings)

        return True, f"Switched to world '{name}'"


async def snapshot_world(settings: Settings, name: str) -> tuple[bool, str]:
    """Create a snapshot of a world (safe save if server running)."""
    mc_dir = settings.minecraft_dir
    if not _is_world_dir(mc_dir / name):
        return False, f"World '{name}' not found"

    running = await _is_server_running(settings)
    entry = await create_backup(
        settings,
        backup_type="world",
        world_name=name,
        is_server_running=running,
    )

    if entry:
        return True, f"Snapshot created: {entry.filename}"
    return False, "Failed to create snapshot"


async def restore_snapshot(settings: Settings, name: str, snapshot_path: str) -> tuple[bool, str]:
    """Restore a world from a snapshot."""
    if _world_lock.locked():
        return False, "Another world operation is in progress"

    async with _world_lock:
        path = Path(snapshot_path)
        if not path.exists():
            return False, "Snapshot not found"

        mc_dir = settings.minecraft_dir

        # Stop server if running
        was_running = await _is_server_running(settings)
        if was_running:
            await stop_server(settings)
            await asyncio.sleep(3)

        # Remove existing world dirs
        for d in _world_dirs(mc_dir, name):
            if d.exists():
                shutil.rmtree(d)

        # Extract snapshot
        def _extract():
            with tarfile.open(path, "r:gz") as tar:
                tar.extractall(path=mc_dir)

        await asyncio.get_event_loop().run_in_executor(None, _extract)

        if was_running:
            await start_server(settings)

        return True, f"World '{name}' restored from snapshot"


async def upload_world(settings: Settings, name: str, file_content: bytes) -> tuple[bool, str]:
    """Upload a world from a zip file."""
    if not _SAFE_NAME.match(name):
        return False, "Invalid world name. Use only letters, numbers, underscore, hyphen, space."

    mc_dir = settings.minecraft_dir
    if _is_world_dir(mc_dir / name):
        return False, f"World '{name}' already exists"

    # Extract zip to temp directory first, then validate
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            with zipfile.ZipFile(BytesIO(file_content)) as zf:
                zf.extractall(tmp_path)
        except zipfile.BadZipFile:
            return False, "Invalid zip file"

        # Find the level.dat - it might be in a subdirectory
        level_dats = list(tmp_path.rglob("level.dat"))
        if not level_dats:
            return False, "No level.dat found in zip - not a valid Minecraft world"

        # Use the directory containing the first level.dat as overworld
        world_source = level_dats[0].parent

        # Copy to minecraft dir
        dest = mc_dir / name
        shutil.copytree(world_source, dest)

        # Check for nether/end in the extracted content
        parent = world_source.parent
        for suffix in ("_nether", "_the_end"):
            candidate = parent / f"{world_source.name}{suffix}"
            if candidate.exists():
                shutil.copytree(candidate, mc_dir / f"{name}{suffix}")

    return True, f"World '{name}' uploaded successfully"


async def download_world(settings: Settings, name: str) -> Path | None:
    """Create a tar.gz of a world for download. Returns the temp file path."""
    mc_dir = settings.minecraft_dir
    if not _is_world_dir(mc_dir / name):
        return None

    # Safe save if running
    running = await _is_server_running(settings)
    from minecraft_manager.services.backup import safe_save_off, safe_save_on

    save_was_off = False
    if running:
        save_was_off = await safe_save_off(settings)

    try:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        def _create_archive():
            with tarfile.open(tmp_path, "w:gz") as tar:
                for suffix in ("", "_nether", "_the_end"):
                    d = mc_dir / f"{name}{suffix}"
                    if d.exists():
                        tar.add(d, arcname=f"{name}{suffix}")

        await asyncio.get_event_loop().run_in_executor(None, _create_archive)
        return tmp_path
    finally:
        if save_was_off:
            await safe_save_on(settings)


async def duplicate_world(settings: Settings, source: str, new_name: str) -> tuple[bool, str]:
    """Duplicate a world with a new name."""
    if not _SAFE_NAME.match(new_name):
        return False, "Invalid world name"

    mc_dir = settings.minecraft_dir
    if not _is_world_dir(mc_dir / source):
        return False, f"Source world '{source}' not found"
    if (mc_dir / new_name).exists():
        return False, f"World '{new_name}' already exists"

    def _copy():
        for suffix in ("", "_nether", "_the_end"):
            src = mc_dir / f"{source}{suffix}"
            dst = mc_dir / f"{new_name}{suffix}"
            if src.exists():
                shutil.copytree(src, dst)

    await asyncio.get_event_loop().run_in_executor(None, _copy)
    return True, f"World '{source}' duplicated as '{new_name}'"


async def rename_world(settings: Settings, old_name: str, new_name: str) -> tuple[bool, str]:
    """Rename a world."""
    if not _SAFE_NAME.match(new_name):
        return False, "Invalid world name"

    mc_dir = settings.minecraft_dir
    if not _is_world_dir(mc_dir / old_name):
        return False, f"World '{old_name}' not found"
    if (mc_dir / new_name).exists():
        return False, f"World '{new_name}' already exists"

    active = _get_active_world(settings)
    if active == old_name:
        running = await _is_server_running(settings)
        if running:
            return False, "Cannot rename the active world while server is running. Stop the server first."
        _set_active_world(settings, new_name)

    for suffix in ("", "_nether", "_the_end"):
        src = mc_dir / f"{old_name}{suffix}"
        dst = mc_dir / f"{new_name}{suffix}"
        if src.exists():
            src.rename(dst)

    return True, f"World renamed from '{old_name}' to '{new_name}'"


async def delete_world(settings: Settings, name: str) -> tuple[bool, str]:
    """Delete a world. Creates an auto-snapshot first."""
    mc_dir = settings.minecraft_dir
    if not _is_world_dir(mc_dir / name):
        return False, f"World '{name}' not found"

    active = _get_active_world(settings)
    if active == name:
        return False, "Cannot delete the active world. Switch to another world first."

    # Auto-snapshot before delete
    ok, msg = await snapshot_world(settings, name)
    if not ok:
        return False, f"Failed to create safety snapshot before delete: {msg}"

    # Delete the directories
    for d in _world_dirs(mc_dir, name):
        if d.exists():
            shutil.rmtree(d)

    return True, f"World '{name}' deleted (snapshot saved)"
