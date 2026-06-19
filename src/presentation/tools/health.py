from mcp.server.fastmcp import FastMCP


def register_health_tools(mcp: FastMCP) -> None:
    @mcp.tool(name="health_check", description="Check server liveness and readiness.")
    async def health_check() -> dict:
        return {"status": "up", "message": "ok"}
