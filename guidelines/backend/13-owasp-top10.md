---
model: opus
effort: high
---

# OWASP Top 10 2025 — FastAPI Edition

Use when implementing or reviewing auth, authorization, input handling, or error responses. Maps all ten OWASP Top 10 2025 risks to FastAPI/Python patterns with vulnerable and fixed code for each entry.

The OWASP Top 10 is the industry-standard list of the most critical web application security risks. This guide uses the **2025 edition** — the ordering and categories changed significantly from 2021. Every SaaS backend will be attacked. Building defenses in from day one costs nothing; fixing a breach costs everything.

Each entry maps the vulnerability to a concrete FastAPI/Python pattern with the vulnerable code and the fix.

---

## A01:2025 — Broken Access Control

Users performing actions or reading data they are not permitted to.

**Vulnerable:**
```python
@router.get("/invoices/{invoice_id}", response_model=InvoiceDto)
async def get_invoice(invoice_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> InvoiceDto:
    invoice = await InvoiceRepository(session).get_by_id(invoice_id)
    return InvoiceDto.model_validate(invoice)   # any authenticated user reads any invoice
```

**Fixed — scope every query to the authenticated user:**
```python
@router.get("/invoices/{invoice_id}", response_model=InvoiceDto)
async def get_invoice(
    invoice_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InvoiceDto:
    # use case enforces ownership — raises NotFoundError for both "not found" and "not yours"
    return await GetInvoiceUseCase(InvoiceRepository(session)).execute(invoice_id, owner_id=current_user.id)
```

Returning `404` instead of `403` prevents resource enumeration — attackers can't tell whether a resource exists or they're just forbidden from it.

---

## A02:2025 — Security Misconfiguration

Default credentials, open CORS, verbose error messages, debug mode in production, unnecessary features enabled.

**Vulnerable:**
```python
app = FastAPI(debug=True)                          # stack traces exposed to clients
app.add_middleware(CORSMiddleware, allow_origins=["*"])  # any domain can call your API
JWT_SECRET = "changeme"                             # default never changed
```

**Fixed — settings enforce safe defaults, fail at startup if secrets are missing:**
```python
class Settings(BaseSettings):
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = []                   # empty — must be explicitly set per environment
    JWT_SECRET: str = Field(...)                   # no default — startup crashes if unset
    DATABASE_URL: str = Field(...)                 # same — never in source code

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    if not settings.DEBUG:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    raise exc   # only full errors in DEBUG mode
```

---

## A03:2025 — Software Supply Chain Failures *(new in 2025)*

Your dependencies, build tools, and CI/CD pipeline are part of your attack surface. Supply chain attacks compromise trusted components to inject malicious code — SolarWinds, Log4Shell, the xz utils backdoor, and hundreds of typosquatted PyPI packages follow this pattern.

**Attack vectors in Python projects:**
- Typosquatting: `pip install reqeusts` (one letter off from `requests`)
- Dependency confusion: attacker uploads a package with your internal package name to PyPI
- Compromised maintainer account: legitimate package hijacked and poisoned
- Unpinned dependencies: `requests>=2.0` installs whatever is latest, including a compromised version
- Unsigned CI artifacts: build pipeline tampered, Docker image poisoned before push

**Prevention — lock, verify, and audit everything:**
```bash
# 1. Pin exact versions with content hashes (poetry.lock contains SHA256 hashes)
poetry install   # installs exactly what's in poetry.lock — no version resolution at deploy time

# 2. Audit for known CVEs in CI
pip install pip-audit
pip-audit --require-hashes -r requirements.txt   # fails build on any known vulnerability

# 3. Check for dependency confusion — use a private registry for internal packages
# pyproject.toml
[[tool.poetry.source]]
name = "internal"
url = "https://your-registry/simple/"
priority = "primary"                # checked before PyPI
```

**`.github/dependabot.yml — automated dependency updates`**
```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 10
```

**`.github/workflows/ci.yml — pin action versions to a commit SHA, not a floating tag`**
```yaml
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5   # v4 pinned to SHA
# NOT: actions/checkout@v4  ← tag can be moved to point at malicious code
```

**Software Bill of Materials (SBOM):** generate a machine-readable inventory of every direct and transitive dependency so you know immediately when a CVE affects you:
```bash
pip install cyclonedx-bom
cyclonedx-py poetry > sbom.json   # generate SBOM from poetry.lock
```

---

## A04:2025 — Cryptographic Failures

Sensitive data exposed in transit or at rest due to weak or missing encryption.

**Vulnerable:**
```python
user.password = plain_text_password           # stored as plain text — catastrophic
token = jwt.encode({"sub": user.id}, "")      # empty secret — any token is valid
DATABASE_URL = "postgresql://user:pass@host"  # hardcoded in source — committed to git
```

**Fixed:**
```python
# Entity setter always hashes — impossible to store plain text accidentally
@password.setter
def password(self, plain: str) -> None:
    self._password_hash = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

# FastAPI does not issue tokens — it validates them.
# Tokens are issued by the IdP (Entra ID) and signed with RS256.
# Validate via JWKS; never generate a shared-secret JWT in application code.
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600)

# Secrets from environment only — pydantic-settings enforces presence at startup
AZURE_AD_TENANT_ID: str = Field(...)  # no default — process refuses to start if missing
AZURE_AD_CLIENT_ID: str = Field(...)  # same
DATABASE_URL: str = Field(...)        # same
```

---

## A05:2025 — Injection

Untrusted input executed as code — SQL, shell commands, LDAP, template strings.

**Vulnerable:**
```python
# Classic SQL injection via string interpolation
query = f"SELECT * FROM users WHERE email = '{email}'"
await session.execute(text(query))

# Shell injection
import subprocess
subprocess.run(f"convert {user_filename} output.jpg", shell=True)  # attacker passes "; rm -rf /"
```

**Fixed:**
```python
# SQLAlchemy ORM — parameters are always bound, never interpolated
result = await session.execute(select(User).where(User.email == email))

# Raw SQL only with bound parameters
result = await session.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}
)

# Shell commands — pass a list, never a string with shell=True
subprocess.run(["convert", user_filename, "output.jpg"])   # no shell injection possible
```

---

## A06:2025 — Insecure Design

Security flaws baked into the architecture — no patching fixes a fundamentally insecure design. Must be addressed at the design phase.

**Examples of insecure design in SaaS:**
- Password reset via predictable tokens (`?token=12345` — sequential, guessable)
- Multi-tenant app with no `tenant_id` scoping — all tenants see each other's data
- No rate limiting on authentication — brute-forceable forever
- Admin functionality on the same domain/port as user functionality — no network isolation

**Fixed — design security in from day one:**
```python
# Cryptographically random reset tokens
import secrets
token = secrets.token_urlsafe(32)   # 256 bits of entropy — not guessable

# Rate limiting on sensitive endpoints
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, body: AuthDto, ...) -> AuthSuccessDto: ...

# Every query is tenant-scoped — enforced in the repository, not the route
async def get_all_invoices(self, tenant_id: int) -> list[Invoice]:
    result = await self.session.execute(
        select(Invoice).where(Invoice.tenant_id == tenant_id)
    )
    return list(result.scalars().all())
```

---

## A07:2025 — Authentication Failures

Broken authentication flows, weak token validation, missing expiry checks, sessions not invalidated on logout.

**Vulnerable:**
```python
# ❌ Trusting a token without verifying the signature
payload = jwt.decode(token, options={"verify_signature": False})   # anyone can forge this

# ❌ Rolling a shared-secret HS256 token in application code
def create_token(user_id: int) -> str:
    return jwt.encode({"sub": user_id}, "my-secret")   # shared secret = single point of failure
```

**Fixed — validate OIDC tokens via JWKS:**
```python
import os
from functools import lru_cache
import jwt
from fastapi import HTTPException, status

TENANT_ID = os.environ["AZURE_AD_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_AD_CLIENT_ID"]
JWKS_URL  = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
ISSUER    = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600)


def validate_token(token: str) -> dict:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,        # rejects tokens from any other tenant
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
```

Token expiry, rotation, and logout are managed by the IdP and the Next.js BFF (Auth.js). FastAPI's responsibility is only validation — if the signature or the `aud`/`iss` claims are wrong, reject the request.

---

## A08:2025 — Software or Data Integrity Failures

Running code you haven't verified — unsigned packages, tampered build artifacts, unsafe deserialization of untrusted data.

**Vulnerable:**
```python
import pickle
user_data = pickle.loads(request.body)   # arbitrary code execution — never do this

# Unpinned CI action — tag can be silently redirected to malicious code
- uses: actions/checkout@v4   # "v4" is a tag, not a content hash
```

**Fixed:**
```python
# Never deserialize untrusted pickle — use JSON + Pydantic instead
body = UserDto.model_validate_json(raw_bytes)   # typed, validated, safe

# Pin Docker base images to digest — immutable content address
FROM python:3.11-slim@sha256:a1b2c3d4...   # this exact image layer, forever

# Pin CI actions to SHA
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
```

Use `poetry.lock` with content hashes at every deployment — never `pip install requests` without a hash.

---

## A09:2025 — Security Logging and Alerting Failures

Attacks succeed silently — nobody notices the breach until the damage is done.

**What must be logged:**
```python
import logging
import structlog   # structured JSON logging for production

logger = structlog.get_logger()

# Authentication events
logger.warning("login_failed", email=body.email, ip=request.client.host)
logger.info("login_success", user_id=user.id)

# Authorization failures
logger.warning("access_denied", user_id=current_user.id, resource="invoice", resource_id=invoice_id)

# Data mutations — who changed what, when
logger.info("invoice_created", user_id=current_user.id, invoice_id=result.id, tenant_id=current_user.tenant_id)
logger.info("user_deleted", actor_id=admin.id, target_user_id=user_id)
```

**What NEVER to log:**
```python
logger.info(f"login attempt: email={email} password={password}")  # never log passwords
logger.debug(f"token issued: {token}")                             # never log tokens
logger.info(f"card: {card_number}")                               # never log PAN/PII
```

Set up alerts on: repeated login failures from one IP, access denied spikes, unusual off-hours admin actions.

---

## A10:2025 — Mishandling of Exceptional Conditions *(new in 2025)*

Applications that don't properly catch, respond to, and recover from error conditions expose internal state, fail open (grant access on error), or crash in ways that attackers can exploit.

**Vulnerable — fail open:**
```python
async def get_current_user(token: str) -> User:
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = await repo.get_by_id(payload["sub"])
        return user
    except Exception:
        pass   # any error silently returns None — caller may treat None as "anonymous admin"
```

**Vulnerable — exception leaks internals:**
```python
@router.get("/users/{user_id}")
async def get_user(user_id: int, session=Depends(get_session)):
    user = await session.get(User, user_id)
    return user   # raises UnmappedInstanceError if user is None — full stack trace to client
```

**Fixed — fail closed, handle specifically, centralize handling:**
```python
# Always fail closed — on any auth error, deny access
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session=Depends(get_session)) -> User:
    try:
        payload = jwt.decode(token, get_config().JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await UserRepository(session).get_by_id(int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")   # still 401, not 404
    return user

# Global handler — strip internals in production, never let unhandled exceptions reach clients
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Handle None explicitly — never let it propagate as an ORM error
@router.get("/users/{user_id}", response_model=UserDto)
async def get_user(user_id: int, session=Depends(get_session)) -> UserDto:
    try:
        return await GetUserByIdUseCase(UserRepository(session)).execute(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

---

## Quick Checklist

- [ ] All data queries are scoped to `owner_id` / `tenant_id` — checked in use cases, not routes
- [ ] `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID`, `DATABASE_URL`, and all secrets use `Field(...)` with no default — crash at startup if missing
- [ ] `poetry.lock` committed, `pip-audit` runs in CI — breaks build on any CVE
- [ ] CI actions pinned to SHA, not floating tags
- [ ] SBOM generated and stored with each release
- [ ] No string interpolation in SQL — SQLAlchemy ORM or bound `:param` placeholders only
- [ ] Rate limiting on any sensitive unauthenticated endpoints
- [ ] OIDC token validated via JWKS — `aud` and `iss` both checked; no shared-secret HS256 tokens issued by the app
- [ ] `PyJWKClient` instantiated with `@lru_cache` — JWKS keys not fetched on every request
- [ ] No `pickle.loads()` on untrusted data — Pydantic `model_validate_json()` instead
- [ ] Auth functions never `pass` on exceptions — always fail closed with `HTTPException(401)`
- [ ] Global unhandled exception handler strips stack traces in production
- [ ] Login failures, access denials, and data mutations are logged with structured JSON (no passwords, tokens, or PAN)
