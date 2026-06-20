import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure repo root is on sys.path when running from the api/ subdirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.types import ASGIApp, Receive, Scope, Send  # noqa: E402

from src.config.settings import get_config  # noqa: E402
from src.mcp_main import mcp  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

# Disable FastMCP's DNS-rebinding Host validation for Vercel: the check only
# allows loopback Host headers and cannot be configured per-hostname at runtime.
# Vercel's edge layer is the actual origin-security boundary; standalone and
# Docker runs (which don't go through this module) keep the protection on.
mcp.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

_logger = get_logger("api")
_config = get_config()
_base_url = _config.MCP_BASE_URL.rstrip("/")


def _mask_auth(header: str) -> str:
    if not header:
        return "<absent>"
    parts = header.split(" ", 1)
    if len(parts) == 2:
        scheme, token = parts
        masked = token[:8] + "…" if len(token) > 8 else token
        return f"{scheme} {masked}"
    return header[:16] + "…"


class RequestLoggingMiddleware:
    """Pure ASGI logging middleware — never buffers, safe for SSE/streaming."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        start = time.monotonic()
        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        raw_headers: list[tuple[bytes, bytes]] = list(scope.get("headers", []))
        raw_headers_map = {k: v for k, v in raw_headers}
        auth_log = _mask_auth(raw_headers_map.get(b"authorization", b"").decode())
        original_host = raw_headers_map.get(b"host", b"").decode()

        _logger.info("request  method=%s path=%s client=%s host=%s auth=%s", method, path, client_ip, original_host, auth_log)
        _logger.debug("request  headers=%s", {k.decode(): v.decode() for k, v in raw_headers})

        status_code: int | None = None

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            _logger.error("response method=%s path=%s status=500 duration_ms=%.1f error=%r", method, path, elapsed, exc)
            raise

        elapsed = (time.monotonic() - start) * 1000
        if status_code is not None:
            log_fn = _logger.warning if status_code in (401, 403) else _logger.info
            log_fn("response method=%s path=%s status=%d duration_ms=%.1f auth=%s", method, path, status_code, elapsed, auth_log)


async def oauth_authorization_server(request: Request) -> JSONResponse:
    """
    RFC 8414 OAuth 2.0 Authorization Server Metadata.
    Points clients at this server as the auth server; token_endpoint is
    omitted and grant_types_supported is empty to signal no auth is required.
    """
    return JSONResponse(
        {
            "issuer": _base_url,
            # authorization_endpoint and token_endpoint are required by RFC 8414
            # and validated by MCP SDK clients even when grant_types_supported is
            # empty (meaning no actual OAuth flow is performed).
            "authorization_endpoint": f"{_base_url}/oauth/authorize",
            "token_endpoint": f"{_base_url}/oauth/token",
            "registration_endpoint": f"{_base_url}/register",
            "response_types_supported": [],
            "grant_types_supported": [],
            "token_endpoint_auth_methods_supported": ["none"],
        },
        headers={"Cache-Control": "no-store"},
    )


async def oauth_register(request: Request) -> JSONResponse:
    """
    RFC 7591 Dynamic Client Registration stub.
    Returns a public client registration so MCP clients that attempt
    dynamic registration don't stall on a 404 and fall back to sending
    bad tokens (which would produce 401s on subsequent requests).
    """
    return JSONResponse(
        {
            "client_id": "public",
            "client_id_issued_at": int(time.time()),
            "token_endpoint_auth_method": "none",
        },
        status_code=201,
        headers={"Cache-Control": "no-store"},
    )


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
        Route("/.well-known/oauth-authorization-server", oauth_authorization_server),
        Route("/.well-known/oauth-protected-resource", oauth_protected_resource),
        Route("/.well-known/oauth-protected-resource/mcp", oauth_protected_resource),
        Route("/register", oauth_register, methods=["POST"]),
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
