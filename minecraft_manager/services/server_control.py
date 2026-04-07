import asyncio
from pathlib import Path

from minecraft_manager.config import Settings


async def _run_systemctl(action: str, settings: Settings) -> tuple[bool, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", action, settings.systemd_unit,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True, f"Server {action} successful"
        return False, stderr.decode().strip() or f"Failed to {action} server"
    except FileNotFoundError:
        return False, "systemctl not found"


async def start_server(settings: Settings) -> tuple[bool, str]:
    if settings.dev_mode:
        marker = Path(settings.minecraft_dir / ".dev_running")
        marker.touch()
        return True, "Server started (dev mode)"
    return await _run_systemctl("start", settings)


async def stop_server(settings: Settings) -> tuple[bool, str]:
    if settings.dev_mode:
        marker = Path(settings.minecraft_dir / ".dev_running")
        marker.unlink(missing_ok=True)
        return True, "Server stopped (dev mode)"
    return await _run_systemctl("stop", settings)


async def restart_server(settings: Settings) -> tuple[bool, str]:
    if settings.dev_mode:
        marker = Path(settings.minecraft_dir / ".dev_running")
        marker.touch()
        return True, "Server restarted (dev mode)"
    return await _run_systemctl("restart", settings)
