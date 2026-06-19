# Security Patterns: JWT, Passwords, and Secrets

Security mistakes are the most expensive technical debt. This guide covers the patterns used in mdip-backend for authentication, authorization, and secret management.

## Rule 1 — Never Commit Secrets

```python
# ❌ WRONG — secret in source code
class Settings(BaseSettings):
    JWT_SECRET: str = "my-super-secret-key"
    DATABASE_URL: str = "postgresql://admin:password@prod-db/app"
```

```python
# ✅ CORRECT — required from environment
class Settings(BaseSettings):
    JWT_SECRET: str          # no default → crashes immediately if not set in prod
    DATABASE_URL: str        # same

    class Config:
        env_file = ".env"    # reads .env in development
```

`.env` is in `.gitignore`. Commit `.env.example` with placeholder values so teammates know what's needed:

```bash
# .env.example
JWT_SECRET=replace-with-64-char-random-string
DATABASE_URL=postgresql+asyncpg://user:password@localhost/appdb
```

## Password Hashing with bcrypt

Always hash passwords before storing. Use bcrypt, not SHA-256 or MD5.

```python
# src/domain/entities/user.py (from mdip-backend)
import bcrypt

@password.setter
def password(self, raw_password: str) -> None:
    password_bytes = raw_password.encode("utf-8")
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    self._password = password_hash.decode("utf-8")

def verify_password(self, raw_password: str) -> bool:
    return bcrypt.checkpw(
        raw_password.encode("utf-8"),
        self.password.encode("utf-8")
    )
```

Why bcrypt:
- **Adaptive cost** — automatically slows down as hardware improves
- **Built-in salt** — `bcrypt.gensalt()` ensures every hash is unique
- **Constant-time comparison** — `checkpw()` is immune to timing attacks

Never do: `if user.password == sha256(input)`. SHA-256 is fast — brute force is cheap.

## JWT Access Tokens

```python
# src/infrastructure/services/token_service.py (from mdip-backend)
import jwt
from datetime import datetime, timedelta, timezone

ALGORITHM = "HS256"

class IAccessTokenService:
    def __init__(self, secret_key: str, expiration: float = 3600):
        self._secret_key = secret_key
        self._expiration = expiration

    def generate_token(self, sub: int, scopes: list[str], extra: dict = None) -> str:
        expiration = datetime.now(timezone.utc) + timedelta(seconds=self._expiration)
        payload = {"sub": sub, "scopes": scopes, "exp": expiration}
        if extra:
            payload["extra"] = extra
        return jwt.encode(payload, self._secret_key, algorithm=ALGORITHM)

    def get_token_payload(self, token: str) -> TokenPayload:
        payload = jwt.decode(token, self._secret_key, algorithms=[ALGORITHM])
        return TokenPayload(sub=payload["sub"], scopes=payload.get("scopes", []))
```

Token design:
- **Short-lived access tokens** — expire in 15–60 minutes (`JWT_ACCESS_EXPIRATION = 900`)
- **Longer-lived refresh tokens** — expire in 30–60 minutes, used only to get a new access token
- **`exp` claim** — `jwt.decode()` validates expiry automatically; expired tokens raise `jwt.ExpiredSignatureError`

## Refresh Token Pattern

```python
# src/application/use_cases/auth/user_token_refresh.py (mdip-backend pattern)
class UserTokenRefreshUseCase:
    def __init__(self, user_repo, access_service, refresh_service): ...

    async def execute(self, refresh_token: str) -> AuthSuccessDto:
        payload = self.refresh_service.get_token_payload(refresh_token)
        user = await self.user_repo.get_by_sub(payload.sub)
        if user is None:
            raise UnauthorizedAccessError("User not found")
        new_access = self.access_service.generate_token(user.sub, scopes=["user"])
        new_refresh = self.refresh_service.generate_token(user.sub)
        return AuthSuccessDto(access_token=new_access, refresh_token=new_refresh)
```

The refresh token is sent in a custom header (`x-refresh-token`) not the body — it doesn't appear in server logs.

## OAuth2 Bearer Pattern (FastAPI)

```python
# src/domain/services/auth_service.py (from mdip-backend)
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{C.URL_PREFIX}/docs/jwt")

async def manager(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    user_repository = IUserRepository(session)
    access_token_service = IAccessTokenService(get_config().JWT_SECRET)
    api_auth = ApiAuthorizationUseCase(user_repository, access_token_service)
    return await api_auth.execute(token, security_scopes)
```

Routes that require authentication declare `Depends(manager)`:
```python
@user_router.get("/me", response_model=UserDto)
async def get_me(user: Annotated[User, Depends(manager)]):
    return UserDto.model_validate(user)
```

## Pydantic-Settings Security Configuration

```python
# src/config/settings/__init__.py
class Settings(BaseSettings):
    JWT_SECRET: str              # required — no default
    JWT_ACCESS_EXPIRATION: int = 900   # 15 minutes
    JWT_REFRESH_EXPIRATION: int = 1800 # 30 minutes

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"   # silently ignore unknown env vars (don't leak)
```

`extra = "ignore"` prevents accidentally exposing configuration values through unknown variables.

## Security Anti-Patterns

| Anti-pattern | Why it's dangerous | Fix |
|---|---|---|
| `JWT_SECRET = "thisissecret"` in code | Anyone with repo access owns all tokens | Read from env, crash if missing |
| MD5/SHA-256 for passwords | Brute-forceable in seconds with a GPU | Use bcrypt |
| Storing raw passwords | Data breach exposes all passwords | Hash in setter, never store raw |
| JWT without expiry (`exp`) | Stolen tokens work forever | Always set `exp` |
| Returning stack traces to client | Leaks internal architecture | Return generic error messages |
| Trusting `sub` from unverified JWT | Forged identity | Always verify signature |

## Quick Checklist

- [ ] `.env` is in `.gitignore`; `.env.example` exists with placeholder values
- [ ] `JWT_SECRET` and database credentials have no default values in `Settings`
- [ ] Passwords are hashed with bcrypt in the entity setter, never in services or routes
- [ ] Access tokens expire in ≤ 60 minutes
- [ ] `jwt.decode()` is used (not manual payload parsing) — it verifies signature and expiry
- [ ] Error responses return domain messages, not Python stack traces
