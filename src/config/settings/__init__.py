import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.settings.base import EnvType, _REPO_ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: EnvType = "PROD"
    GUIDELINES_DIR: str = str(_REPO_ROOT / "guidelines")
    EXAMPLES_DIR: str = str(_REPO_ROOT / "examples")
    MCP_TRANSPORT: Literal["stdio", "sse"] = "stdio"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000
    MCP_BASE_URL: str = "https://fullstack-agent-guidelines.vercel.app"


class TestSettings(Settings):
    ENVIRONMENT: EnvType = "TEST"
    GUIDELINES_DIR: str = str(_REPO_ROOT / "test" / "fixtures" / "guidelines")
    EXAMPLES_DIR: str = str(_REPO_ROOT / "test" / "fixtures" / "examples")


_ENV_MAP: dict[str, type[Settings]] = {
    "TEST": TestSettings,
    "DEV": Settings,
    "PROD": Settings,
}


@lru_cache(maxsize=1)
def get_config() -> Settings:
    env = os.getenv("ENVIRONMENT", "PROD")
    return _ENV_MAP.get(env, Settings)()
