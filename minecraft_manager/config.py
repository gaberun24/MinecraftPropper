from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCM_", env_file=".env")

    # Paths
    minecraft_dir: Path = Path("/opt/minecraft")
    versions_dir: Path = Path("/opt/minecraft-versions")
    backup_dir: Path = Path("/var/backups/minecraft")
    stdin_pipe: Path = Path("/run/minecraft.stdin")

    # Service
    systemd_unit: str = "minecraft"

    # Network
    java_port: int = 25565
    bedrock_port: int = 19132

    # Backups
    daily_retention: int = 7

    # Updates
    auto_update_enabled: bool = False
    builds_to_keep: int = 5
    health_check_timeout: int = 90
    player_notify_seconds: int = 30

    # Dev mode (skip systemd, use mock paths)
    dev_mode: bool = False

    @property
    def server_properties_path(self) -> Path:
        return self.minecraft_dir / "server.properties"

    @property
    def version_file_path(self) -> Path:
        return self.minecraft_dir / "VERSION"

    @property
    def log_file_path(self) -> Path:
        return self.minecraft_dir / "logs" / "latest.log"

    @property
    def plugins_dir(self) -> Path:
        return self.minecraft_dir / "plugins"

    @property
    def worlds_base_dir(self) -> Path:
        return self.minecraft_dir

    @property
    def settings_file_path(self) -> Path:
        return self.minecraft_dir / "manager_settings.json"
