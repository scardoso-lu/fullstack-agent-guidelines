---
model: sonnet
effort: high
---

# Error Handling — Exception Hierarchy, Wrapping, and Boundaries

Use when designing a new module's exceptions, when catching a third-party library's error, or when reviewing a `try/except` block. Defines the **module-rooted exception hierarchy** (every module has one base class; every other exception in the module inherits from it), the rule for **wrapping vs leaking** third-party errors, the **never-swallow-silently** rule, and how exceptions map to HTTP at the edge of the system (in routes, not in use-cases).

Errors are a public contract of the module. A well-designed exception hierarchy lets callers catch a *class* of problem (`AuthError`, `DatasetError`) without listing every concrete subclass. A badly-designed one — strings raised as `Exception`, third-party errors leaking across boundaries, `except Exception: pass` to silence noise — turns the codebase into a guessing game.

## The rule

> Every module has **one base exception class** rooted at the module name (e.g. `AuthError`, `DatasetError`).
> Every other exception in the module inherits from it — directly or transitively.
> Use-cases raise **domain exceptions**, not `HTTPException`.
> Routes (the edge) translate domain exceptions to HTTP via a single exception-handler mapping.
> Never `except Exception` without re-raising, logging with `exc_info`, or wrapping into a domain exception.

## The shape — one `exc.py` per module

```
src/
├── auth/
│   ├── exc.py              ← module exception root + subclasses
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── api.py
├── dataset/
│   ├── exc.py              ← module exception root + subclasses
│   ├── ...
└── shared/
    └── exc.py              ← cross-module shared base (rarely needed)
```

**`src/auth/exc.py`**
```python
class AuthError(Exception):
    """Base class for every error raised by the auth module."""

class InvalidCredentialsError(AuthError):
    """The supplied email/password combination is invalid."""

class TokenExpiredError(AuthError):
    """The supplied token has expired."""

class TokenRevokedError(AuthError):
    """The supplied token was explicitly revoked."""

class PasswordPolicyViolation(AuthError):
    """The supplied password does not meet the policy."""
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
```

A caller that wants "any auth problem" catches `AuthError`. A caller that wants a specific case catches the leaf. Both work without `isinstance` ladders.

## Use-cases raise domain exceptions, not HTTP

```python
# good — use-case knows about its domain, not about HTTP
class LoginUseCase:
    def __init__(self, user_repository: UserRepositoryInterface) -> None:
        self.user_repository = user_repository

    async def execute(self, dto: LoginDto) -> AuthTokenDto:
        user = await self.user_repository.find_by_email(dto.email)
        if not user or not user.verify_password(dto.password):
            raise InvalidCredentialsError()
        return AuthTokenDto.model_validate({"token": issue_token(user)})

# bad — use-case leaks HTTP semantics into business code
class LoginUseCase:
    def __init__(self, user_repository: UserRepositoryInterface) -> None:
        self.user_repository = user_repository

    async def execute(self, dto: LoginDto) -> AuthTokenDto:
        user = await self.user_repository.find_by_email(dto.email)
        if not user or not user.verify_password(dto.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")  # ❌
        return AuthTokenDto.model_validate({"token": issue_token(user)})
```

Why this matters:

- The same use-case may be called from an HTTP route, a CLI, a worker, or a test — only one of those cares about HTTP status codes.
- Tests assert on `InvalidCredentialsError`, not on response codes — the test stays focused on behavior.
- The translation lives in **one place** (the route or a global exception handler), so HTTP semantics change without touching the domain.

## The edge maps domain → HTTP

A single FastAPI exception-handler mapping translates the module exceptions to status codes:

**`src/auth/api.py`**
```python
from fastapi import APIRouter, Depends
from src.auth.exc import (
    AuthError,
    InvalidCredentialsError,
    PasswordPolicyViolation,
    TokenExpiredError,
    TokenRevokedError,
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=AuthTokenDto)
async def login(
    dto: LoginDto,
    use_case: Annotated[LoginUseCase, Depends(get_login_use_case)],
) -> AuthTokenDto:
    return await use_case.execute(dto)
```

**`src/api_main.py — global exception handlers`**
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.auth.exc import (
    AuthError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenRevokedError,
    PasswordPolicyViolation,
)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidCredentialsError)
    async def _invalid_credentials(_: Request, exc: InvalidCredentialsError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    @app.exception_handler(TokenExpiredError)
    async def _token_expired(_: Request, __: TokenExpiredError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Token expired"})

    @app.exception_handler(TokenRevokedError)
    async def _token_revoked(_: Request, __: TokenRevokedError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Token revoked"})

    @app.exception_handler(PasswordPolicyViolation)
    async def _policy(_: Request, exc: PasswordPolicyViolation) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.reason})

    @app.exception_handler(AuthError)              # fallback for unmapped AuthError subclasses
    async def _auth(_: Request, __: AuthError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Auth error"})
```

The route is **thin**. The use-case raises the domain exception. The global handler maps to HTTP. New leaf exceptions cost one handler entry — and if you forget, the module base handler catches it as a sane default.

## Wrap third-party exceptions at the boundary

```python
# good — infrastructure wraps the library error into a domain exception
import httpx
from src.payments.exc import PaymentGatewayError, PaymentTimeoutError


class PaymentGatewayClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def charge(self, amount_cents: int, card_token: str) -> ChargeResult:
        try:
            response = await self.http.post("/v1/charges", json={...}, timeout=10)
            response.raise_for_status()
            return ChargeResult(...)
        except httpx.TimeoutException as exc:
            raise PaymentTimeoutError("gateway did not respond in time") from exc
        except httpx.HTTPStatusError as exc:
            raise PaymentGatewayError(f"gateway returned {exc.response.status_code}") from exc

# bad — httpx exception escapes the infrastructure layer
class PaymentGatewayClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def charge(self, amount_cents: int, card_token: str) -> ChargeResult:
        response = await self.http.post("/v1/charges", json={...})    # may raise anything
        return ChargeResult(...)
```

Why wrap:

- The use-case shouldn't import `httpx`. It owns business logic, not HTTP client internals.
- Swapping `httpx` for another client doesn't ripple through the codebase.
- Tests stub the boundary with a domain-error fake, not a library-specific mock.
- The exception type names what *the business* sees (a payment-gateway error), not what the library did.

The `raise ... from exc` chains the original — debugging keeps the traceback intact.

## When to swallow — almost never

These are the only legitimate `except Exception: ...` patterns:

```python
# 1. Log + re-raise (preserve the exception, capture context)
try:
    result = await risky_call()
except Exception:
    self.log.error("risky_call.failed", exc_info=True)
    raise

# 2. Convert to a typed domain exception (boundary wrap)
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    raise InvalidPayloadError("not valid JSON") from exc

# 3. Best-effort cleanup that must not crash the surrounding flow
try:
    await self.cache.invalidate(key)
except Exception:
    self.log.warning("cache.invalidate.failed", exc_info=True, key=key)
    # don't re-raise; the user's request succeeded — cache is best-effort
```

Anti-patterns:

```python
# silent swallow — the bug ships
try:
    await save(thing)
except Exception:
    pass

# log-and-continue without context — useless
try:
    result = something()
except Exception as e:
    print(f"oops: {e}")
    return None
```

The `pass` version is the single worst pattern an AI generates — it makes the bug invisible. Code review should reject every `except: pass` that isn't case (3) with an explicit comment naming the reason.

## Custom payloads on exceptions

Pass structured detail through the exception, not through string formatting:

```python
# good
class ValidationError(DatasetError):
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason

# handler can return a structured 422
@app.exception_handler(ValidationError)
async def _validation(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "validation_failed", "field": exc.field, "reason": exc.reason},
    )
```

The handler reads structured fields off the exception; the response is parseable by the client. The string in `super().__init__` is for the traceback / logs, not the API contract.

## Logging exceptions correctly

When an exception is caught (Mode 2 above — log and re-raise), log with `exc_info=True` (or pass the exception explicitly to structlog) so the traceback lands in the log aggregator:

```python
# good — traceback in the log line
try:
    await charge(amount, token)
except PaymentGatewayError:
    self.log.error("payment.gateway.failed", exc_info=True, amount=amount)
    raise

# bad — stringified exception, no traceback
try:
    await charge(amount, token)
except PaymentGatewayError as e:
    self.log.error(f"payment failed: {e}")
    raise
```

The `exc_info=True` argument ships the stack trace through structlog as a structured field — searchable, alertable, and visible in tracing tools.

See `backend/18-observability-logging` for the level taxonomy. Caught-and-handled exceptions are **ERROR**. Expected-bad (validation reject, permission denied) is **WARNING**.

## What about `assert`?

`assert` is **not** an exception-handling tool — it's a development sanity check, and it's stripped by `python -O`. Don't use `assert` to validate input at runtime:

```python
# bad — disabled in production builds
def transfer(amount: int) -> None:
    assert amount > 0, "amount must be positive"

# good
def transfer(amount: int) -> None:
    if amount <= 0:
        raise InvalidAmountError("amount must be positive")
```

Reserve `assert` for type narrowing or post-condition checks that should genuinely never fire in production — and even then, prefer a real exception with a clear name.

## Quick checklist

- [ ] Module has exactly one base exception class named `<Module>Error`.
- [ ] Every other exception in the module inherits from that base.
- [ ] Use-cases raise domain exceptions, **never** `HTTPException`.
- [ ] A global exception-handler maps domain → HTTP, with a base-class fallback.
- [ ] Third-party exceptions are wrapped at the infrastructure boundary (`raise … from exc`).
- [ ] No bare `except:` or `except Exception: pass` outside the three legitimate cases.
- [ ] Caught-and-re-raised exceptions log with `exc_info=True`.
- [ ] No `assert` for input validation.
- [ ] Exception names describe the *business* problem, not the technical cause.
