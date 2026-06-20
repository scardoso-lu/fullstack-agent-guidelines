from pathlib import Path
from typing import Literal

EnvType = Literal["PROD", "DEV", "TEST"]

# Resolves to the repo root regardless of CWD:
# base.py lives at src/config/settings/base.py → parents[3] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]


class BaseEnvs:
    ENVIRONMENT: EnvType = "PROD"
    GUIDELINES_DIR: str = str(_REPO_ROOT / "guidelines")
    EXAMPLES_DIR: str = str(_REPO_ROOT / "examples")
    MCP_TRANSPORT: Literal["stdio", "sse"] = "stdio"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000
