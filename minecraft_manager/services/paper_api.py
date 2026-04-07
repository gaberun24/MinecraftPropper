from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from minecraft_manager.models.update import BuildInfo

PAPER_API = "https://api.papermc.io/v2/projects/paper"
GEYSER_API = "https://download.geysermc.org/v2/projects/geyser"
FLOODGATE_API = "https://download.geysermc.org/v2/projects/floodgate"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def get_paper_versions() -> list[str]:
    """Get list of available Minecraft versions for Paper."""
    client = _get_client()
    resp = await client.get(PAPER_API)
    resp.raise_for_status()
    return resp.json().get("versions", [])


async def get_latest_paper_build(mc_version: str | None = None) -> BuildInfo | None:
    """Get the latest Paper build for a given MC version (or latest MC version)."""
    client = _get_client()

    if not mc_version:
        versions = await get_paper_versions()
        if not versions:
            return None
        mc_version = versions[-1]

    resp = await client.get(f"{PAPER_API}/versions/{mc_version}/builds")
    resp.raise_for_status()
    data = resp.json()

    builds = data.get("builds", [])
    if not builds:
        return None

    latest = builds[-1]
    build_num = latest["build"]
    download = latest.get("downloads", {}).get("application", {})
    filename = download.get("name", f"paper-{mc_version}-{build_num}.jar")
    sha256 = download.get("sha256", "")

    return BuildInfo(
        project="paper",
        version=mc_version,
        build=build_num,
        download_url=f"{PAPER_API}/versions/{mc_version}/builds/{build_num}/downloads/{filename}",
        sha256=sha256,
    )


async def get_latest_geyser_build() -> BuildInfo | None:
    """Get the latest Geyser build."""
    client = _get_client()
    try:
        resp = await client.get(f"{GEYSER_API}/versions/latest/builds/latest")
        resp.raise_for_status()
        data = resp.json()

        build_num = data.get("build", 0)
        version = data.get("version", "latest")
        downloads = data.get("downloads", {})
        spigot = downloads.get("spigot", {})
        sha256 = spigot.get("sha256", "")

        return BuildInfo(
            project="geyser",
            version=version,
            build=build_num,
            download_url=f"{GEYSER_API}/versions/{version}/builds/{build_num}/downloads/spigot",
            sha256=sha256,
        )
    except httpx.HTTPError:
        return None


async def get_latest_floodgate_build() -> BuildInfo | None:
    """Get the latest Floodgate build."""
    client = _get_client()
    try:
        resp = await client.get(f"{FLOODGATE_API}/versions/latest/builds/latest")
        resp.raise_for_status()
        data = resp.json()

        build_num = data.get("build", 0)
        version = data.get("version", "latest")
        downloads = data.get("downloads", {})
        spigot = downloads.get("spigot", {})
        sha256 = spigot.get("sha256", "")

        return BuildInfo(
            project="floodgate",
            version=version,
            build=build_num,
            download_url=f"{FLOODGATE_API}/versions/{version}/builds/{build_num}/downloads/spigot",
            sha256=sha256,
        )
    except httpx.HTTPError:
        return None


async def download_jar(url: str, dest: Path, expected_sha256: str = "") -> tuple[bool, str]:
    """Download a JAR file and optionally verify its SHA256 checksum."""
    client = _get_client()
    try:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            hasher = hashlib.sha256()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(8192):
                    f.write(chunk)
                    hasher.update(chunk)

        if expected_sha256:
            actual = hasher.hexdigest()
            if actual != expected_sha256:
                dest.unlink(missing_ok=True)
                return False, f"SHA256 mismatch: expected {expected_sha256[:16]}... got {actual[:16]}..."

        return True, str(dest)
    except httpx.HTTPError as e:
        dest.unlink(missing_ok=True)
        return False, f"Download failed: {e}"


async def check_geyser_supports_mc_version(mc_version: str) -> bool:
    """Check if the latest Geyser build supports a given MC version.

    This is a heuristic - Geyser typically supports the latest MC version
    within a few days of release.
    """
    build = await get_latest_geyser_build()
    if not build:
        return False
    # Geyser version string often contains the supported MC version range
    # For now, assume compatible if Geyser is available
    # A more robust check would query Geyser's supported versions
    return True
