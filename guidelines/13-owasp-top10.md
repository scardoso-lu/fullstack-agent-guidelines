# OWASP Top 10 — FastAPI Edition

The OWASP Top 10 is the industry-standard list of the most critical web application security risks. Every SaaS backend will be attacked. Building defenses in from day one costs nothing; fixing a breach costs everything.

This guide maps each risk to a concrete FastAPI/Python pattern — both the vulnerable code and the fix.

---

## A01 — Broken Access Control

Users performing actions or reading data they are not allowed to.

**Vulnerable:**
```python
@router.get("/invoices/{invoice_id}", response_model=InvoiceDto)
async def get_invoice(invoice_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> InvoiceDto:
    invoice = await InvoiceRepository(session).get_by_id(invoice_id)
    return InvoiceDto.model_validate(invoice)   # ← any authenticated user can read any invoice
```

**Fixed — scope queries to the authenticated user:**
```python
@router.get("/invoices/{invoice_id}", response_model=InvoiceDto)
async def get_invoice(
    invoice_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InvoiceDto:
    invoice = await GetInvoiceUseCase(InvoiceRepository(session)).execute(invoice_id, owner_id=current_user.id)
    return invoice   # use case raises NotFoundError if owner_id doesn't match
```

The use case enforces ownership — a `NotFoundError` is returned for both "not found" and "not yours" to prevent enumeration.

---

## A02 — Cryptographic Failures

Sensitive data exposed in transit or at rest due to weak or missing encryption.

**Vulnerable:**
```python
user.password = plain_text_password          # stored as plain text
DATABASE_URL = "postgresql://..."            # hardcoded in source code
token = jwt.encode({"sub": user.id}, "")    # empty secret
```

**Fixed:**
```python
# Entity setter always hashes — no way to store plain text
user.password = plain_text_password          # calls bcrypt.hashpw internally

# Secrets come from environment only
DATABASE_URL: str = Field(..., env="DATABASE_URL")   # pydantic-settings, no default
JWT_SECRET: str = Field(..., env="JWT_SECRET")        # must be set — fails at startup if missing

# Strong JWT signing
token = jwt.encode({"sub": str(user.id), "exp": exp}, settings.JWT_SECRET, algorithm="HS256")
```

Never commit `.env` files. Add them to `.gitignore` on day one.

---

## A03 — Injection

Untrusted input executed as code — SQL, shell, LDAP, XML.

**Vulnerable:**
```python
# Raw string interpolation in SQL — classic injection
query = f"SELECT * FROM users WHERE email = '{email}'"
result = await session.execute(text(query))
```

**Fixed — SQLAlchemy parameterized queries (the only way):**
```python
# ORM query — parameters are always bound, never interpolated
result = await session.execute(select(User).where(User.email == email))

# If you must use raw SQL, use bound parameters:
result = await session.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
```

Also applies to shell commands — never `subprocess.run(f"convert {user_filename}")`. Use `shlex.split` and pass a list.

---

## A04 — Insecure Design

Security flaws baked into the architecture — no amount of patching fixes a fundamentally insecure design.

**Examples of insecure design in SaaS:**
- Password reset via predictable tokens (`reset?token=12345`)
- "Security through obscurity" (hiding admin routes instead of protecting them)
- No rate limiting on login endpoints — brute-forceable
- Multi-tenant app with shared DB and no `tenant_id` scoping

**Fixed — design security in from the start:**
```python
# Rate limiting on sensitive endpoints (slowapi)
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("5/minute")          # brute force protection
async def login(request: Request, body: AuthDto, ...) -> AuthSuccessDto: ...

# Multi-tenant scoping — every query includes tenant_id
async def get_all(self, tenant_id: int) -> list[Invoice]:
    result = await self.session.execute(
        select(Invoice).where(Invoice.tenant_id == tenant_id)
    )
    return list(result.scalars().all())
```

---

## A05 — Security Misconfiguration

Default credentials, open S3 buckets, verbose error messages, debug mode in production.

**Vulnerable:**
```python
app = FastAPI(debug=True)                # stack traces exposed to clients
CORS: allow_origins=["*"]               # any domain can call your API
SECRET_KEY = "changeme"                  # default never changed
```

**Fixed:**
```python
# Settings enforce safe defaults
class Settings(BaseSettings):
    DEBUG: bool = False                  # must explicitly set DEBUG=true
    CORS_ORIGINS: list[str] = []         # empty by default — explicitly set in prod
    JWT_SECRET: str = Field(...)         # no default — startup fails if unset

# FastAPI error handler strips stack traces in production
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    if not settings.DEBUG:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    raise exc
```

---

## A06 — Vulnerable and Outdated Components

Using dependencies with known CVEs.

**Prevention:**
```bash
# Audit dependencies for known vulnerabilities
pip install pip-audit
pip-audit

# Pin exact versions in production
poetry add fastapi==0.115.0   # not fastapi="*"

# Enable Dependabot in .github/dependabot.yml
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
```

Check `poetry show --outdated` regularly. A SaaS app with a vulnerable `cryptography` or `pyjwt` dependency is compromised before you write a single line of business logic.

---

## A07 — Identification and Authentication Failures

Broken login, weak passwords, missing token expiry, no logout.

**Vulnerable:**
```python
def create_token(user_id: int) -> str:
    return jwt.encode({"sub": user_id}, SECRET)   # no expiry — token valid forever
```

**Fixed:**
```python
from datetime import datetime, timedelta, timezone

def create_access_token(sub: str, secret: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)   # short-lived
    return jwt.encode({"sub": sub, "exp": exp, "type": "access"}, secret, algorithm="HS256")

def create_refresh_token(sub: str, secret: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=30)
    return jwt.encode({"sub": sub, "exp": exp, "type": "refresh"}, secret, algorithm="HS256")

def decode_token(token: str, secret: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise UnauthorizedAccessError("Wrong token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedAccessError("Token expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedAccessError("Invalid token")
```

Also: enforce minimum password length in the entity, invalidate refresh tokens on logout (store revoked tokens in Redis with TTL).

---

## A08 — Software and Data Integrity Failures

Running code you didn't verify — unsigned packages, auto-update without checksum, deserialization of untrusted data.

**Prevention:**
```bash
# Lock file pins exact hashes — never install without it
poetry install   # uses poetry.lock with content hashes

# Verify Docker base images with digest pinning
FROM python:3.11-slim@sha256:abc123...   # digest, not floating tag
```

```python
# Never deserialize untrusted pickle data
import pickle
data = pickle.loads(user_supplied_bytes)   # ← arbitrary code execution

# Use JSON or Pydantic for external data
body = UserDto.model_validate_json(request_body)   # ← typed, validated
```

---

## A09 — Security Logging and Monitoring Failures

Attacks succeed silently because there are no logs or nobody reads them.

**What must be logged:**
```python
import logging
logger = logging.getLogger(__name__)

# Log authentication events
logger.warning("Failed login attempt", extra={"email": body.email, "ip": request.client.host})
logger.info("User logged in", extra={"user_id": user.id})

# Log authorization failures
logger.warning("Access denied", extra={"user_id": current_user.id, "resource": invoice_id})

# Log data mutations
logger.info("Invoice created", extra={"user_id": current_user.id, "invoice_id": result.id})
```

**What NOT to log:**
```python
logger.info(f"Login: email={email} password={password}")   # ← never log passwords
logger.debug(f"Token: {token}")                             # ← never log tokens
```

Use structured logging (JSON format) in production so logs can be queried by your observability stack.

---

## A10 — Server-Side Request Forgery (SSRF)

Your server fetches a URL supplied by the user — attacker points it at internal services.

**Vulnerable:**
```python
@router.post("/fetch-preview")
async def fetch_preview(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)   # ← attacker can request http://169.254.169.254/
    return {"content": response.text}
```

**Fixed — allowlist external domains:**
```python
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"https"}
ALLOWED_DOMAINS = {"api.stripe.com", "hooks.slack.com"}

def validate_external_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed")
    if parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"Domain '{parsed.hostname}' not in allowlist")
    return url
```

Block requests to private IP ranges (`10.x`, `172.16.x`, `192.168.x`, `169.254.x`) explicitly when a full allowlist is not possible.

---

## Quick Checklist

- [ ] All data queries are scoped to the authenticated user (`owner_id` / `tenant_id`)
- [ ] No secrets in source code — all from environment variables via pydantic-settings with `Field(...)`
- [ ] Passwords use bcrypt, tokens use HS256 with expiry
- [ ] No string interpolation in SQL — all queries use SQLAlchemy ORM or bound parameters
- [ ] `DEBUG=False` in production, error handler strips stack traces
- [ ] `poetry.lock` committed, `pip-audit` runs in CI
- [ ] Login endpoint has rate limiting
- [ ] Authentication, authorization failures, and data mutations are logged (without sensitive values)
- [ ] External URL fetching validates scheme and allowlisted domains
