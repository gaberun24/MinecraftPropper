from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from minecraft_manager.config import Settings
from minecraft_manager.models.update import BuildInfo, UpdateCheck
from minecraft_manager.services import paper_api
from minecraft_manager.services.backup import create_backup
from minecraft_manager.services.console import send_command
from minecraft_manager.services.server_control import start_server, stop_server
from minecraft_manager.services.server_status import get_server_status

# Global lock to prevent concurrent updates
_update_lock = asyncio.Lock()


def read_installed_versions(settings: Settings) -> dict[str, BuildInfo]:
    """Read currently installed versions from VERSION file."""
    versions: dict[str, BuildInfo] = {}
    version_file = settings.version_file_path

    if not version_file.exists():
        return versions

    content = version_file.read_text().strip()

    # Parse paper version from first line: paper-1.21.4-193
    paper_match = re.match(r"paper-(.+?)-(\d+)", content)
    if paper_match:
        versions["paper"] = BuildInfo(
            project="paper",
            version=paper_match.group(1),
            build=int(paper_match.group(2)),
        )

    # Parse additional lines: geyser=2.4.0-build123, floodgate=2.2.0-build45
    for line in content.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip().lower()
            build_match = re.search(r"(\d+)", value.split("-build")[-1] if "-build" in value else "0")
            build_num = int(build_match.group(1)) if build_match else 0
            version_str = value.split("-build")[0] if "-build" in value else value

            if key in ("geyser", "floodgate"):
                versions[key] = BuildInfo(
                    project=key,
                    version=version_str.strip(),
                    build=build_num,
                )

    return versions


def write_versions(settings: Settings, versions: dict[str, BuildInfo]) -> None:
    """Write version info to VERSION file."""
    lines = []
    if "paper" in versions:
        v = versions["paper"]
        lines.append(f"paper-{v.version}-{v.build}")
    if "geyser" in versions:
        v = versions["geyser"]
        lines.append(f"geyser={v.version}-build{v.build}")
    if "floodgate" in versions:
        v = versions["floodgate"]
        lines.append(f"floodgate={v.version}-build{v.build}")

    settings.version_file_path.write_text("\n".join(lines) + "\n")


async def check_updates(settings: Settings) -> UpdateCheck:
    """Check for available updates for all components."""
    installed = read_installed_versions(settings)
    result = UpdateCheck()

    try:
        # Check all three in parallel
        paper_task = paper_api.get_latest_paper_build()
        geyser_task = paper_api.get_latest_geyser_build()
        floodgate_task = paper_api.get_latest_floodgate_build()

        paper_latest, geyser_latest, floodgate_latest = await asyncio.gather(
            paper_task, geyser_task, floodgate_task, return_exceptions=True
        )

        if isinstance(paper_latest, BuildInfo):
            result.paper = paper_latest
            current = installed.get("paper")
            if current and (paper_latest.version != current.version or paper_latest.build > current.build):
                result.paper_update_available = True

        if isinstance(geyser_latest, BuildInfo):
            result.geyser = geyser_latest
            current = installed.get("geyser")
            if current and geyser_latest.build > current.build:
                result.geyser_update_available = True

        if isinstance(floodgate_latest, BuildInfo):
            result.floodgate = floodgate_latest
            current = installed.get("floodgate")
            if current and floodgate_latest.build > current.build:
                result.floodgate_update_available = True

        # Geyser compatibility check
        if result.paper_update_available and result.paper:
            current_paper = installed.get("paper")
            if current_paper and result.paper.version != current_paper.version:
                compatible = await paper_api.check_geyser_supports_mc_version(result.paper.version)
                result.geyser_compatible = compatible
                if not compatible:
                    result.message = (
                        f"Paper has a new MC version ({result.paper.version}) but Geyser "
                        "may not support it yet. Bedrock players won't be able to connect. "
                        "Consider waiting."
                    )

    except Exception as e:
        result.message = f"Error checking updates: {e}"

    return result


async def apply_update(
    settings: Settings,
    component: str,
    build: BuildInfo,
) -> AsyncGenerator[str, None]:
    """Apply an update for a component. Yields progress messages."""
    if _update_lock.locked():
        yield "ERROR: Another update is already in progress"
        return

    async with _update_lock:
        status = await get_server_status(settings)
        installed = read_installed_versions(settings)

        # Step 1: Notify players
        if status.running and status.player_count > 0:
            yield "Notifying players..."
            await send_command(
                f"say Server updating {component} in {settings.player_notify_seconds} seconds...",
                settings,
            )
            await asyncio.sleep(min(settings.player_notify_seconds, 5))  # Cap wait in practice

        # Step 2: Create pre-update backup
        yield "Creating pre-update backup..."
        backup = await create_backup(
            settings,
            backup_type="update",
            is_server_running=status.running,
        )
        if backup:
            yield f"Backup created: {backup.filename}"
        else:
            yield "WARNING: Backup creation failed, continuing anyway..."

        # Step 3: Stop server
        was_running = status.running
        if was_running:
            yield "Stopping server..."
            await send_command("say Server stopping for update...", settings)
            await stop_server(settings)
            await asyncio.sleep(2)

        # Step 4: Download new build
        yield f"Downloading {component} build {build.build}..."

        if settings.dev_mode:
            # Dev mode: simulate download
            yield f"[DEV] Simulated download of {component}"
        else:
            if component == "paper":
                dest = settings.versions_dir / f"paper-{build.version}-{build.build}.jar"
                ok, msg = await paper_api.download_jar(build.download_url, dest, build.sha256)
                if not ok:
                    yield f"ERROR: Download failed: {msg}"
                    if was_running:
                        await start_server(settings)
                    return

                # Update symlink
                jar_link = settings.minecraft_dir / "paper.jar"
                jar_link.unlink(missing_ok=True)
                jar_link.symlink_to(dest)
                yield f"Paper JAR updated: {dest.name}"

            elif component in ("geyser", "floodgate"):
                filename = "Geyser-Spigot.jar" if component == "geyser" else "floodgate-spigot.jar"
                dest = settings.plugins_dir / filename
                ok, msg = await paper_api.download_jar(build.download_url, dest, build.sha256)
                if not ok:
                    yield f"ERROR: Download failed: {msg}"
                    if was_running:
                        await start_server(settings)
                    return
                yield f"{component} plugin updated: {filename}"

        # Step 5: Update version file
        installed[component] = build
        write_versions(settings, installed)
        yield "Version file updated"

        # Step 6: Start server
        if was_running:
            yield "Starting server..."
            await start_server(settings)

            # Step 7: Health check
            yield f"Health check (waiting up to {settings.health_check_timeout}s)..."
            if not settings.dev_mode:
                import socket
                for i in range(settings.health_check_timeout):
                    try:
                        with socket.create_connection(("localhost", settings.java_port), timeout=2):
                            yield f"Server is responding on port {settings.java_port} after {i+1}s"
                            break
                    except (ConnectionRefusedError, OSError, socket.timeout):
                        await asyncio.sleep(1)
                else:
                    yield f"WARNING: Server not responding after {settings.health_check_timeout}s"
            else:
                yield "[DEV] Health check skipped"

        # Step 8: Clean old versions
        if component == "paper":
            _clean_old_versions(settings)
            yield "Old versions cleaned up"

        yield f"UPDATE COMPLETE: {component} updated to build {build.build}"


def _clean_old_versions(settings: Settings) -> None:
    """Keep only the newest N Paper builds."""
    if not settings.versions_dir.exists():
        return
    jars = sorted(
        settings.versions_dir.glob("paper-*.jar"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old in jars[settings.builds_to_keep:]:
        old.unlink(missing_ok=True)
