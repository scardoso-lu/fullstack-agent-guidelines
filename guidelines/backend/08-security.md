---
model: opus
effort: high
---

# Security Patterns: OIDC Token Validation and Secrets

Use when handling authentication, OIDC tokens, or environment secrets in FastAPI. Covers JWKS-based JWT validation, pydantic-settings with no-default secrets, and the dependency injection pattern for the current user.

With OIDC as the identity layer, FastAPI does **not** issue tokens — it only validates them. Tokens arrive as signed Bearer JWTs issued by Entra ID (or another OIDC IdP). FastAPI verifies the signature, the issuer, and the audience on every request using the IdP's published public keys.

---

## Rule 1 — Never Commit Secrets

```python
# ❌ WRONG — secret in source code
class Settings(BaseSettings):
    AZURE_AD_CLIENT_ID: str = "12345678-..."   # hardcoded — leaked to anyone with repo access
    DATABASE_URL: str = "postgresql://admin:password@prod-db/app"
```

```python
# ✅ CORRECT — required from environment, crash at startup if missing
class Settings(BaseSettings):
    AZURE_AD_TENANT_ID: str        # no default → crashes immediately if not set in prod
    AZURE_AD_CLIENT_ID: str        # same
    DATABASE_URL: str              # same

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",            # silently ignore unknown env vars (don't leak)
    )
```

`.env` is in `.gitignore`. Commit `.env.example` with placeholder values so teammates know what's needed:

**`.env.example`**
```bash
AZURE_AD_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_AD_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   # fastapi-api app registration
DATABASE_URL=postgresql+asyncpg://user:password@localhost/appdb
```

---

## JWT Validation via JWKS

FastAPI receives Bearer tokens issued by the IdP. It validates the signature against the IdP's published JWKS endpoint, and checks that the `aud` and `iss` claims match the expected values.

```python
# src/infrastructure/services/auth_dependency.py
import os
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

TENANT_ID = os.environ["AZURE_AD_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_AD_CLIENT_ID"]   # the fastapi-api app registration
JWKS_URL  = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
ISSUER    = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

bearer_scheme = HTTPBearer()


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict[str, Any]:
    token = credentials.credentials
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
        )
        return payload
    except jwt.exceptions.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
```

**Key claims available after validation:**

| Claim | Meaning |
|---|---|
| `oid` | Object ID — stable, unique user identifier across all tokens |
| `preferred_username` | UPN / email |
| `groups` | Group membership (requires explicit configuration in Entra) |
| `scp` | Delegated scopes granted to the caller |

**Using the dependency in routes:**

```python
from typing import Annotated, Any
from fastapi import Depends

@router.get("/me", response_model=UserDto)
async def get_me(
    user_claims: Annotated[dict[str, Any], Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDto:
    user = await UserRepository(session).get_by_oid(user_claims["oid"])
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDto.model_validate(user)
```

---

## Password Hashing with bcrypt

Only relevant when the application manages local credentials (e.g. service accounts or a hybrid identity setup where not all users authenticate via OIDC). If all users authenticate through the IdP, this section does not apply.

```python
import bcrypt

@password.setter
def password(self, raw_password: str) -> None:
    password_bytes = raw_password.encode("utf-8")
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    self._password = password_hash.decode("utf-8")

def verify_password(self, raw_password: str) -> bool:
    return bcrypt.checkpw(
        raw_password.encode("utf-8"),
        self.password.encode("utf-8"),
    )
```

Never compare passwords with `==`. `checkpw()` uses a constant-time comparison immune to timing attacks.

---

## Pydantic-Settings Configuration

```python
# src/config/settings/__init__.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # OIDC — required; no defaults; process refuses to start if unset
    AZURE_AD_TENANT_ID: str = Field(...)
    AZURE_AD_CLIENT_ID: str = Field(...)

    # Database
    DATABASE_URL: str = Field(...)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # never expose unknown env var names in error output
    )
```

`extra = "ignore"` prevents accidentally surfacing config key names through validation errors.

---

## Security Anti-Patterns

| Anti-pattern | Why it's dangerous | Fix |
|---|---|---|
| Hardcoded client IDs or tenant IDs in source | Anyone with repo access has your IdP config | Read from env, crash if missing |
| Trusting `sub` or `oid` from an **unverified** JWT | Forged identity | Always verify signature via JWKS before reading any claim |
| Skipping `aud` validation | Token issued for another app is accepted | Always check `audience=CLIENT_ID` |
| Rolling your own HS256 tokens | Shared secret is a single point of failure; doesn't integrate with IdP | Use OIDC — let the IdP issue and sign tokens |
| Returning stack traces to the client | Leaks internal architecture | Return generic error messages; log the detail server-side |
| `pass` on `jwt.PyJWTError` | Fails open — unauthenticated request proceeds | Always fail closed with `HTTPException(401)` |

---

## Quick Checklist

- [ ] `.env` is in `.gitignore`; `.env.example` exists with placeholder values
- [ ] `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID`, and `DATABASE_URL` use `Field(...)` with no default — startup crashes if unset
- [ ] `get_current_user` validates against JWKS — not a shared secret; `aud` and `iss` are both checked
- [ ] `@lru_cache` on the `PyJWKClient` — JWKS keys are not fetched on every request
- [ ] `jwt.PyJWTError` is caught and re-raised as `HTTPException(401)` — never `pass`
- [ ] Error responses return safe messages, not Python stack traces or JWT details
- [ ] If local credentials exist: passwords hashed with bcrypt in the entity setter, never stored raw
