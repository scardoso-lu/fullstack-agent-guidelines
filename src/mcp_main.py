from mcp.server.fastmcp import FastMCP

from src.config.constants import C
from src.config.settings import get_config
from src.presentation.view import register_mcp_tools


def create_mcp_server() -> FastMCP:
    """MCP server factory."""
    config = get_config()

    server = FastMCP(
        name=C.TITLE,
        stateless_http=True,
    )

    server.settings.host = config.MCP_HOST
    server.settings.port = config.MCP_PORT

    register_mcp_tools(server)

    return server


mcp = create_mcp_server()

if __name__ == "__main__":
    config = get_config()
    mcp.run(transport=config.MCP_TRANSPORT)
