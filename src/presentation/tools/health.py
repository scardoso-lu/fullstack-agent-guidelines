from mcp.server.fastmcp import FastMCP

from src.utils.logger import get_logger

_logger = get_logger("tools.health")


def register_health_tools(mcp: FastMCP) -> None:
    @mcp.tool(name="health_check", description="Check server liveness and readiness.")
    async def health_check() -> dict:
        _logger.info("tool=health_check")
        return {"status": "up", "message": "ok"}
