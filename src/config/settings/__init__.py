import os
from functools import lru_cache

from pydantic_settings import BaseSettings

from src.config.settings.base import BaseEnvs, EnvType, _REPO_ROOT


class Settings(BaseSettings, BaseEnvs):
    ENVIRONMENT: EnvType = "PROD"
    GUIDELINES_DIR: str = str(_REPO_ROOT / "guidelines")
    EXAMPLES_DIR: str = str(_REPO_ROOT / "examples")
    MCP_TRANSPORT: str = "stdio"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


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
