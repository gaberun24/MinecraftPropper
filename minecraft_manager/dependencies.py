from functools import lru_cache

from minecraft_manager.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
