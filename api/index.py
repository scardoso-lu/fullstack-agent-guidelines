import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure repo root is on sys.path when running from the api/ subdirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starlette.applications import Starlette  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.types import ASGIApp  # noqa: E402

from src.config.settings import get_config  # noqa: E402
from src.mcp_main import mcp  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

_logger = get_logger("api")
_config = get_config()
_base_url = _config.MCP_BASE_URL.rstrip("/")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request and response to aid 401 debugging."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()

        auth_header = request.headers.get("authorization", "")
        if auth_header:
            # Show scheme + first 8 chars of token to identify the credential
            # without leaking it fully in logs.
            parts = auth_header.split(" ", 1)
            if len(parts) == 2:
                scheme, token = parts
                masked = token[:8] + "…" if len(token) > 8 else token
                auth_log = f"{scheme} {masked}"
            else:
                auth_log = auth_header[:16] + "…"
        else:
            auth_log = "<absent>"

        _logger.info(
            "request  method=%s path=%s client=%s auth=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            auth_log,
        )
        _logger.debug("request  headers=%s", dict(request.headers))

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            _logger.error(
                "response method=%s path=%s status=500 duration_ms=%.1f error=%r",
                request.method,
                request.url.path,
                elapsed,
                exc,
            )
            raise

        elapsed = (time.monotonic() - start) * 1000
        log_fn = _logger.warning if response.status_code in (401, 403) else _logger.info
        log_fn(
            "response method=%s path=%s status=%d duration_ms=%.1f auth=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            auth_log,
        )

        return response


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
    _logger.info("startup  base_url=%s", _base_url)
    async with mcp.session_manager.run():
        yield
    _logger.info("shutdown complete")


_starlette = Starlette(
    lifespan=_lifespan,
    routes=[
        Route("/.well-known/oauth-protected-resource", oauth_protected_resource),
        Route("/.well-known/oauth-protected-resource/mcp", oauth_protected_resource),
        Mount("/", app=mcp.streamable_http_app()),
    ],
)

# Vercel detects and serves this ASGI app.
# MCP streamable-HTTP endpoint: POST /mcp  (and GET /mcp for SSE stream)
app = CORSMiddleware(
    app=RequestLoggingMiddleware(_starlette),
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
