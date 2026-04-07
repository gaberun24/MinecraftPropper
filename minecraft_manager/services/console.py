from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from minecraft_manager.config import Settings


async def tail_log(settings: Settings) -> AsyncGenerator[str, None]:
    """Async generator that yields new lines from the server log file."""
    log_path = settings.log_file_path

    if not log_path.exists():
        yield "[Log file not found - waiting...]"

    # Wait for file to exist
    while not log_path.exists():
        await asyncio.sleep(1)

    # Seek to end and stream new lines
    inode = os.stat(log_path).st_ino
    with open(log_path) as f:
        # Start from end of file
        f.seek(0, 2)

        while True:
            line = f.readline()
            if line:
                yield line.rstrip("\n")
            else:
                await asyncio.sleep(0.3)

                # Check for log rotation (inode changed)
                try:
                    new_inode = os.stat(log_path).st_ino
                    if new_inode != inode:
                        inode = new_inode
                        f.close()
                        f_new = open(log_path)
                        f = f_new  # noqa: F841 - reassigning loop variable intentionally
                        yield "[Log rotated]"
                except FileNotFoundError:
                    yield "[Log file removed - waiting...]"
                    while not log_path.exists():
                        await asyncio.sleep(1)
                    inode = os.stat(log_path).st_ino
                    f.close()
                    f = open(log_path)


async def send_command(command: str, settings: Settings) -> tuple[bool, str]:
    """Send a command to the Minecraft server via the named pipe."""
    pipe_path = settings.stdin_pipe

    if settings.dev_mode:
        # In dev mode, append to a command log file
        cmd_log = settings.minecraft_dir / "commands.log"
        with open(cmd_log, "a") as f:
            f.write(command + "\n")

        # Also append to the log file so it shows up in the console
        log_path = settings.log_file_path
        if log_path.exists():
            with open(log_path, "a") as f:
                f.write(f"[DEV] Command sent: {command}\n")

        return True, f"Command sent: {command}"

    if not pipe_path.exists():
        return False, "Server stdin pipe not found - is the server running?"

    try:
        # Open pipe in non-blocking write mode
        fd = os.open(str(pipe_path), os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (command + "\n").encode())
        finally:
            os.close(fd)
        return True, f"Command sent: {command}"
    except OSError as e:
        return False, f"Failed to send command: {e}"


async def wait_for_log_message(
    settings: Settings, message: str, timeout: int = 30
) -> bool:
    """Wait for a specific message to appear in the log file."""
    log_path = settings.log_file_path
    if not log_path.exists():
        return False

    # Record current position
    with open(log_path) as f:
        f.seek(0, 2)
        start_pos = f.tell()

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with open(log_path) as f:
            f.seek(start_pos)
            content = f.read()
            if message in content:
                return True
        await asyncio.sleep(0.5)

    return False
