from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from src.config.constants import C
from src.config.settings import get_config
from src.presentation.view import register_mcp_tools
from src.utils.logger import get_logger

_logger = get_logger("mcp_server")


def create_mcp_server() -> FastMCP:
    """MCP server factory."""
    config = get_config()

    _logger.info(
        "creating MCP server name=%r host=%s port=%d transport=%s",
        C.TITLE,
        config.MCP_HOST,
        config.MCP_PORT,
        config.MCP_TRANSPORT,
    )

    # Disable FastMCP's DNS-rebinding protection: it only allows loopback Host
    # headers, which breaks Vercel deployments. Vercel's edge layer is the
    # actual security boundary for origin validation.
    server = FastMCP(
        name=C.TITLE,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    server.settings.host = config.MCP_HOST
    server.settings.port = config.MCP_PORT

    register_mcp_tools(server)

    _logger.info("MCP server ready — tools registered")
    return server


mcp = create_mcp_server()

if __name__ == "__main__":
    config = get_config()
    _logger.info("starting MCP server transport=%s", config.MCP_TRANSPORT)
    mcp.run(transport=config.MCP_TRANSPORT)
