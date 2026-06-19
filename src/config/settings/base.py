from typing import List, Literal

EnvType = Literal["PROD", "DEV", "TEST"]


class BaseEnvs:
    ENVIRONMENT: EnvType = "PROD"
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/notes_mcp"
    DATABASE_ECHO: bool = False
    MCP_TRANSPORT: Literal["stdio", "sse"] = "stdio"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 8000
