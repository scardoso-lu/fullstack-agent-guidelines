import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure repo root is on sys.path when running from the api/ subdirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starlette.applications import Starlette  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402

from src.config.settings import get_config  # noqa: E402
from src.mcp_main import mcp  # noqa: E402

_config = get_config()
_base_url = _config.MCP_BASE_URL.rstrip("/")


async def oauth_protected_resource(request: Request) -> JSONResponse:
    """
    RFC 9728 OAuth 2.0 Protected Resource Metadata.
    Declaring authorization_servers as empty tells MCP clients this is a
    public resource — no tokens required.
    """
    return JSONResponse(
        {
            "resource": f"{_base_url}/mcp",
            "authorization_servers": [],
            "bearer_methods_supported": [],
            "resource_documentation": _base_url,
        },
        headers={"Cache-Control": "no-store"},
    )


@asynccontextmanager
async def _lifespan(app):
    async with mcp.session_manager.run():
        yield


_starlette = Starlette(
    lifespan=_lifespan,
    routes=[
        Route("/.well-known/oauth-protected-resource", oauth_protected_resource),
        Route("/.well-known/oauth-protected-resource/mcp", oauth_protected_resource),
        Mount("/", app=mcp.streamable_http_app()),
    ]
)

# Vercel detects and serves this ASGI app.
# MCP streamable-HTTP endpoint: POST /mcp  (and GET /mcp for SSE stream)
app = CORSMiddleware(
    app=_starlette,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
