---
model: sonnet
effort: high
---

# Observability — Structured Logging, Levels, and the Audit/Log Split

Use when adding logging to a use-case, configuring the logger at boot, or reviewing a slice that emits new events. Defines the structured-log facade rule (one app-wide `Logger`, injected via DI — **no module-level `get_logger()`** in business code), the log-level taxonomy (DEBUG / INFO / WARNING / ERROR / CRITICAL), the JSON-to-stdout-only output policy, the redaction rule for cookies/tokens/PII, and the **hard line** between operational logs and the audit trail.

Logging is operational telemetry. The **audit trail** is the system of record. They share **only** the `correlation_id` — never substitute one for the other.

## The rule

> All log output goes through the project's shared structured-log facade.
> No `print()`. No f-string-formatted log messages. No module-level `get_logger("…")` in business code.
> Logs are **JSON to stdout only**; `LOG_LEVEL` is the only env knob.
> The facade is a **single app-wide `Logger` instance** created at API/worker boot and **injected via DI** into use-cases.

## Why one instance, injected

Module-level loggers (`_logger = get_logger("…")` at the top of every file) look ergonomic but cause real problems:

- The logger's configuration is decided at import time, before the config is loaded.
- Tests cannot swap the logger per case — every test sees the global instance.
- Correlation context (`correlation_id`, `actor_id`, `request_id`) has to be smuggled in through global state.
- Discovery is impossible — there's no single place that knows "what does this app log?"

A single app-wide `Logger` class, instantiated at boot from the loaded config and injected into use-cases as a constructor argument (or FastAPI dependency for router-invoked code), fixes all four. Tests pass in a fake. Correlation is part of the logger's context, not global state. The boot config knows every place the logger lands.

## Setup at boot

```python
# src/api_main.py
from src.shared.observability import Logger, configure_root_logger

def create_app(config: Config) -> FastAPI:
    configure_root_logger(level=config.LOG_LEVEL)  # configures the std `logging` root
    app_logger = Logger(service="api", environment=config.ENV)

    app = FastAPI(lifespan=lifespan_factory(app_logger))
    app.dependency_overrides[get_logger] = lambda: app_logger  # FastAPI DI
    return app
```

```python
# src/shared/observability/logger.py
import logging
import structlog
from typing import Any

class Logger:
    def __init__(self, service: str, environment: str) -> None:
        self.inner = structlog.get_logger().bind(service=service, environment=environment)

    def info(self, event: str, **kwargs: Any) -> None:
        self.inner.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self.inner.warning(event, **kwargs)

    def error(self, event: str, exc_info: BaseException | bool | None = None, **kwargs: Any) -> None:
        self.inner.error(event, exc_info=exc_info, **kwargs)

    def critical(self, event: str, exc_info: BaseException | bool | None = None, **kwargs: Any) -> None:
        self.inner.critical(event, exc_info=exc_info, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self.inner.debug(event, **kwargs)

    def bind(self, **kwargs: Any) -> "Logger":
        new = Logger.__new__(Logger)
        new.inner = self.inner.bind(**kwargs)
        return new
```

## Inject into use-cases

```python
# src/application/use_cases/auth/login.py
from src.application.dto.auth_dto import AuthTokenDto, LoginDto
from src.auth.exc import InvalidCredentialsError
from src.infrastructure.repositories.contract import UserRepositoryInterface
from src.shared.observability import Logger


class LoginUseCase:
    def __init__(self, user_repository: UserRepositoryInterface, log: Logger) -> None:
        self.user_repository = user_repository
        self.log = log

    async def execute(self, dto: LoginDto) -> AuthTokenDto:
        user = await self.user_repository.find_by_email(dto.email)
        if not user or not user.verify_password(dto.password):
            self.log.warning("auth.login.invalid_credentials", email_hash=hash_email(dto.email))
            raise InvalidCredentialsError()

        token = issue_token(user)
        self.log.info("auth.login.success", user_id=user.id)
        return AuthTokenDto.model_validate({"token": token})
```

```python
# DI provider — FastAPI (per backend/05, use Annotated[X, Depends(y)])
from typing import Annotated
from fastapi import Depends


def get_login_use_case(
    user_repository: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
    log: Annotated[Logger, Depends(get_logger)],
) -> LoginUseCase:
    return LoginUseCase(user_repository=user_repository, log=log)
```

For worker tasks (Taskiq, Celery, etc.), inject the logger via the task's constructor or the worker's DI container — same principle.

## The log-level taxonomy

Pick the level by **intent**, not habit. Levels are an interface — operations decides their alert thresholds against them, so consistency matters more than your preference.

| Level | When to use | Example event |
|---|---|---|
| **DEBUG** | Per-item / fine-grained processing. High cardinality. Off in production. | `import.row.parsed` per row of a 100k-row import. |
| **INFO** | Domain state changes & lifecycle boundaries. **One event per use-case boundary.** | `auth.login.success`, `import.completed`, `dataset.archived`. |
| **WARNING** | Expected-bad / recoverable. Validation rejects, permission denied, not-found, row errors, retries. | `auth.login.invalid_credentials`, `import.row.invalid`, `dataset.access_denied`. |
| **ERROR** | Unexpected-but-handled exception caught at a boundary. **Always with `exc_info`.** | `import.task.failed` with the exception. |
| **CRITICAL** | System-threatening / unrecoverable. DB/broker unavailable, startup failure, data-integrity violation. | `db.connection.unreachable`, `app.boot.failed`. |

**WARNING** is the one most often misused. A 401 from a login attempt is **WARNING**, not ERROR — it's expected and recoverable; the user just retries. ERROR is reserved for *unexpected* exceptions.

## Event names are dotted, kebabable, and stable

```
auth.login.success
auth.login.invalid_credentials
import.completed
import.row.invalid
dataset.archived
```

- **Dotted hierarchy** — `domain.aggregate.action`.
- **Stable** — once shipped, an event name is **part of the contract** with operations and dashboards. Renaming silently breaks alerts. Add a new event and deprecate the old one; don't rename in place.
- **Snake / kebab inside segments** — pick one (snake matches Python convention; kebab matches Node/pino). Don't mix.
- **No prose** — the event name is the *what*; the structured fields are the *details*. "user logged in successfully via the password flow" is a sentence, not an event name.

## Structured fields, not f-strings

```python
# bad — f-string formatting in the message
self.log.info(f"user {user.id} logged in from {request.client.host}")

# good — event name + structured fields
self.log.info("auth.login.success", user_id=user.id, ip=request.client.host)
```

The bad form is unparseable by any log aggregator, requires regex to search, and inevitably leaks PII into the message body.

## Correlation IDs are automatic

A `correlation_id` (and optionally `request_id`, `actor_id`, `tenant_id`) is set by the **middleware** at the edge of the request — FastAPI ASGI middleware for the API, the equivalent on the task worker — and propagates through `contextvars`. Every log line in that request inherits it without the use-case knowing.

Same `correlation_id` spans **proxy → API → worker** when the proxy stamps it on the inbound request and the worker preserves it across the queue boundary.

## Redaction

The middleware redacts known-sensitive headers and fields before they reach the structured fields:

- `Cookie`, `Set-Cookie`, `Authorization` → `[redacted]`.
- Request bodies are not logged by default. If you must log a body field for debugging, allow-list specific safe fields — never the whole body.
- PII fields (`email`, `phone`, full name) — either hash (e.g. `email_hash`) or omit. The audit trail captures the actor by ID; the log doesn't need the email.

## Logs are operational. The audit trail is the system of record.

| Concern | Logs | Audit trail |
|---|---|---|
| **Purpose** | Operate the system (alert, debug, trace). | Prove what happened. |
| **Volume** | High (every event). | Low (every write). |
| **Retention** | Days to weeks. | Months to years, often by policy/regulation. |
| **Storage** | Log aggregator (Loki, ELK, CloudWatch). | Database table or append-only store, queryable. |
| **Mutability** | Best-effort; some loss is acceptable. | Strict; no loss, written in the same DB transaction as the action. |
| **Bridge** | `correlation_id` only. | `correlation_id` only. |

**The audit trail is not a log.** Do not write business writes to the logger and call it "audit". The audit trail lives in the database, is written in the same transaction as the action, and is queryable. See `backend/19-audit-on-write`.

The only thing they share is `correlation_id` — so given an audit entry, you can find the operational logs from that request, and vice versa.

## Spot-check at review time

The DoD's audit-on-write check is a hard gate. The observability rules above are a **soft spot-check**:

- No `print()` in business code.
- No module-level `get_logger("…")` in business code.
- No f-string-formatted log messages.
- Log levels picked per the taxonomy (no DEBUG-as-INFO, no ERROR-as-WARNING).
- Structured fields, not prose.
- Sensitive fields redacted.

Flag findings; route them to the owning engineer. A repeat offense across multiple slices warrants an ADR or a lint rule, not a per-PR conversation.
