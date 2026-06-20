import os

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from src.auth.oauth import PublicOAuthProvider
from src.config.constants import C
from src.config.settings import get_config
from src.presentation.view import register_mcp_tools


def create_mcp_server() -> FastMCP:
    """MCP server factory."""
    config = get_config()

    # Propagate OAUTH_SECRET to the provider module before it reads os.environ.
    os.environ.setdefault("OAUTH_SECRET", config.OAUTH_SECRET)

    server = FastMCP(
        name=C.TITLE,
        stateless_http=True,
        auth_server_provider=PublicOAuthProvider(),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(config.MCP_BASE_URL),
            resource_server_url=AnyHttpUrl(config.MCP_BASE_URL),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
            ),
        ),
    )

    server.settings.host = config.MCP_HOST
    server.settings.port = config.MCP_PORT

    register_mcp_tools(server)

    return server


mcp = create_mcp_server()

if __name__ == "__main__":
    config = get_config()
    mcp.run(transport=config.MCP_TRANSPORT)
