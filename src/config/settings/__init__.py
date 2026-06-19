import os
from functools import lru_cache

from pydantic_settings import BaseSettings

from src.config.settings.base import BaseEnvs, EnvType


class Settings(BaseSettings, BaseEnvs):
    ENVIRONMENT: EnvType = "PROD"
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/notes_mcp"
    DATABASE_ECHO: bool = False
    MCP_TRANSPORT: str = "stdio"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class TestSettings(Settings):
    ENVIRONMENT: EnvType = "TEST"
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    DATABASE_ECHO: bool = False


_ENV_MAP: dict[str, type[Settings]] = {
    "TEST": TestSettings,
    "DEV": Settings,
    "PROD": Settings,
}


@lru_cache(maxsize=1)
def get_config() -> Settings:
    env = os.getenv("ENVIRONMENT", "PROD")
    config_class = _ENV_MAP.get(env, Settings)
    return config_class()
