import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AccessToken,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

_SECRET = os.environ.get("OAUTH_SECRET", "public-mcp-server-no-auth-secret")


def _encode(data: dict[str, Any]) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps(data, default=str).encode()
    ).decode().rstrip("=")
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{payload}.{sig}"


def _decode(token: str) -> dict[str, Any] | None:
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(
            _SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected):
            return None
        padding = "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + padding))
        if "exp" in data and data["exp"] < time.time():
            return None
        return data
    except Exception:
        return None


class PublicOAuthProvider:
    """
    Stateless no-op OAuth provider for a public MCP server.

    All state is encoded into signed tokens so no database or in-memory
    storage is needed between requests — required for Vercel serverless.
    Every authorization request is auto-approved; the server is public.
    """

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        data = _decode(client_id)
        if data is None:
            return None
        return OAuthClientInformationFull(
            client_id=client_id,
            redirect_uris=[AnyUrl(u) for u in data.get("redirect_uris", [])],
            token_endpoint_auth_method=data.get("auth_method", "none"),
            grant_types=data.get("grant_types", ["authorization_code", "refresh_token"]),
            response_types=data.get("response_types", ["code"]),
            scope=data.get("scope"),
            client_name=data.get("client_name"),
        )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        # Encode the client's redirect_uris into the client_id so we can
        # reconstruct the full client in get_client() without any storage.
        encoded_id = _encode({
            "redirect_uris": [str(u) for u in (client_info.redirect_uris or [])],
            "auth_method": client_info.token_endpoint_auth_method,
            "grant_types": client_info.grant_types,
            "response_types": client_info.response_types,
            "scope": client_info.scope,
            "client_name": client_info.client_name,
        })
        client_info.client_id = encoded_id

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        # Auto-approve: encode all authorization data into a signed code and
        # redirect immediately — no user interaction needed for a public server.
        code = _encode({
            "t": "code",
            "cid": client.client_id,
            "cc": params.code_challenge,
            "ru": str(params.redirect_uri),
            "rue": params.redirect_uri_provided_explicitly,
            "sc": params.scopes or [],
            "res": params.resource,
            "exp": time.time() + 300,
            "n": secrets.token_hex(8),
        })
        qs: dict[str, str] = {"code": code}
        if params.state:
            qs["state"] = params.state
        return f"{params.redirect_uri}?{urlencode(qs)}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        data = _decode(authorization_code)
        if data is None or data.get("t") != "code" or data.get("cid") != client.client_id:
            return None
        return AuthorizationCode(
            code=authorization_code,
            client_id=client.client_id,
            scopes=data.get("sc", []),
            expires_at=data["exp"],
            code_challenge=data["cc"],
            redirect_uri=AnyUrl(data["ru"]),
            redirect_uri_provided_explicitly=data.get("rue", False),
            resource=data.get("res"),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        access_token = _encode({
            "t": "at",
            "cid": client.client_id,
            "sc": authorization_code.scopes,
            "exp": time.time() + 86400 * 365,
        })
        refresh_token = _encode({
            "t": "rt",
            "cid": client.client_id,
            "sc": authorization_code.scopes,
        })
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=86400 * 365,
            refresh_token=refresh_token,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        data = _decode(refresh_token)
        if data is None or data.get("t") != "rt" or data.get("cid") != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=data.get("sc", []),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        effective_scopes = scopes or refresh_token.scopes
        access_token = _encode({
            "t": "at",
            "cid": client.client_id,
            "sc": effective_scopes,
            "exp": time.time() + 86400 * 365,
        })
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=86400 * 365,
            refresh_token=refresh_token.token,
            scope=" ".join(effective_scopes) if effective_scopes else None,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        data = _decode(token)
        if data is None or data.get("t") != "at":
            return None
        return AccessToken(
            token=token,
            client_id=data.get("cid", ""),
            scopes=data.get("sc", []),
            expires_at=int(data["exp"]) if "exp" in data else None,
        )

    async def revoke_token(
        self,
        token: AccessToken | RefreshToken,
    ) -> None:
        pass  # Stateless — cannot blacklist tokens without external storage
