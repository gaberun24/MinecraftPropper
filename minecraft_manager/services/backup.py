from __future__ import annotations

import asyncio
import shutil
import tarfile
from datetime import datetime
from pathlib import Path

from minecraft_manager.config import Settings
from minecraft_manager.models.backup import BackupEntry
from minecraft_manager.services.console import send_command, wait_for_log_message


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _backup_dir_for_type(settings: Settings, backup_type: str, world_name: str | None = None) -> Path:
    if backup_type == "world" and world_name:
        return settings.backup_dir / "worlds" / world_name / "snapshots"
    return settings.backup_dir / backup_type


async def safe_save_off(settings: Settings) -> bool:
    """Disable auto-save and flush all data to disk. Returns True if successful."""
    ok, _ = await send_command("save-off", settings)
    if not ok:
        return False
    ok, _ = await send_command("save-all flush", settings)
    if not ok:
        return False
    return await wait_for_log_message(settings, "Saved the game", timeout=30)


async def safe_save_on(settings: Settings) -> None:
    """Re-enable auto-save."""
    await send_command("save-on", settings)


async def create_backup(
    settings: Settings,
    backup_type: str = "daily",
    world_name: str | None = None,
    is_server_running: bool = False,
) -> BackupEntry | None:
    """Create a backup. For world type, only backs up the world dirs."""
    dest_dir = _backup_dir_for_type(settings, backup_type, world_name)
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{backup_type}_{timestamp}.tar.gz"
    backup_path = dest_dir / filename

    # Safe save flow if server is running
    save_was_off = False
    if is_server_running:
        save_was_off = await safe_save_off(settings)

    try:
        mc_dir = settings.minecraft_dir

        def _do_backup():
            with tarfile.open(backup_path, "w:gz") as tar:
                if backup_type == "world" and world_name:
                    # Only backup the 3 world dimension dirs
                    for suffix in ("", "_nether", "_the_end"):
                        world_dir = mc_dir / f"{world_name}{suffix}"
                        if world_dir.exists():
                            tar.add(world_dir, arcname=f"{world_name}{suffix}")
                else:
                    # Full server backup (exclude logs, cache)
                    for item in mc_dir.iterdir():
                        if item.name in ("logs", "cache", ".dev_running", "commands.log", "stdin.pipe"):
                            continue
                        tar.add(item, arcname=item.name)

        await asyncio.get_event_loop().run_in_executor(None, _do_backup)
    finally:
        if save_was_off:
            await safe_save_on(settings)

    if not backup_path.exists():
        return None

    stat = backup_path.stat()
    return BackupEntry(
        filename=filename,
        path=str(backup_path),
        backup_type=backup_type,
        size_bytes=stat.st_size,
        size_human=_human_size(stat.st_size),
        created=datetime.fromtimestamp(stat.st_mtime),
        world_name=world_name,
    )


def list_backups(settings: Settings, backup_type: str | None = None) -> list[BackupEntry]:
    """List all backups, optionally filtered by type."""
    entries: list[BackupEntry] = []
    base = settings.backup_dir

    if not base.exists():
        return entries

    # Walk through all backup subdirectories
    dirs_to_scan: list[tuple[str, Path]] = []

    if backup_type:
        if backup_type == "world":
            worlds_dir = base / "worlds"
            if worlds_dir.exists():
                for world_dir in worlds_dir.iterdir():
                    snap_dir = world_dir / "snapshots"
                    if snap_dir.exists():
                        dirs_to_scan.append(("world", snap_dir))
        else:
            type_dir = base / backup_type
            if type_dir.exists():
                dirs_to_scan.append((backup_type, type_dir))
    else:
        for btype in ("daily", "monthly", "update"):
            type_dir = base / btype
            if type_dir.exists():
                dirs_to_scan.append((btype, type_dir))
        worlds_dir = base / "worlds"
        if worlds_dir.exists():
            for world_dir in worlds_dir.iterdir():
                snap_dir = world_dir / "snapshots"
                if snap_dir.exists():
                    dirs_to_scan.append(("world", snap_dir))

    for btype, scan_dir in dirs_to_scan:
        for f in scan_dir.glob("*.tar.gz"):
            stat = f.stat()
            # Extract world name from path if world type
            wname = None
            if btype == "world":
                wname = f.parent.parent.name

            entries.append(BackupEntry(
                filename=f.name,
                path=str(f),
                backup_type=btype,
                size_bytes=stat.st_size,
                size_human=_human_size(stat.st_size),
                created=datetime.fromtimestamp(stat.st_mtime),
                world_name=wname,
            ))

    entries.sort(key=lambda e: e.created, reverse=True)
    return entries


async def restore_backup(
    settings: Settings,
    backup_path: str,
    is_world: bool = False,
) -> tuple[bool, str]:
    """Restore from a backup file."""
    path = Path(backup_path)
    if not path.exists():
        return False, f"Backup file not found: {backup_path}"

    mc_dir = settings.minecraft_dir

    def _do_restore():
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(path=mc_dir)

    await asyncio.get_event_loop().run_in_executor(None, _do_restore)
    return True, "Backup restored successfully"


def apply_retention(settings: Settings) -> int:
    """Apply retention policy to daily backups. Returns number of deleted files."""
    daily_dir = settings.backup_dir / "daily"
    if not daily_dir.exists():
        return 0

    backups = sorted(daily_dir.glob("*.tar.gz"), key=lambda f: f.stat().st_mtime, reverse=True)
    deleted = 0
    for old_backup in backups[settings.daily_retention:]:
        old_backup.unlink()
        deleted += 1
    return deleted


def delete_backup(backup_path: str) -> tuple[bool, str]:
    """Delete a specific backup file."""
    path = Path(backup_path)
    if not path.exists():
        return False, "Backup not found"
    path.unlink()
    return True, f"Deleted {path.name}"
