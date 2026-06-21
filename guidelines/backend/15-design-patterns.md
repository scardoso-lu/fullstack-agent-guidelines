---
model: opus
effort: high
---

# Design Patterns for SaaS Backends

Use when designing a service, adapter, or cross-cutting infrastructure component. Covers Singleton (lru_cache), Factory Method, Repository, Strategy, Observer, and Command patterns with FastAPI/SQLAlchemy examples.

Design patterns are proven solutions to recurring problems. Instead of inventing logic from scratch every time, you apply a named, tested structure. The result is code that other developers (and AI agents) can recognize, extend, and debug without reading every line.

This guide covers the patterns most relevant to Python SaaS backends, with concrete FastAPI/SQLAlchemy examples.

---

## Creational Patterns

### Singleton — One Instance Per Process

Use `lru_cache(maxsize=1)` as the Python idiom for a singleton. It creates the object once and returns the same instance on every call.

```python
# ✅ Singleton via lru_cache — thread-safe, lazy, simple
from functools import lru_cache

@lru_cache(maxsize=1)
def get_db_engine() -> AsyncEngine:
    return create_async_engine(get_config().DATABASE_URL, echo=get_config().DEBUG)

@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(get_db_engine(), expire_on_commit=False)
```

**When to use:** anything expensive to create that should be shared — DB engine, HTTP client, settings object, ML model.

**When NOT to use:** objects with mutable state that varies per request — use `Depends()` instead.

### Factory Method — Delegate Object Creation

A function or method that creates objects without the caller needing to know the concrete class.

```python
# Notification factory — caller asks for a sender by channel name
class NotificationSender(Protocol):
    async def send(self, recipient: str, message: str) -> None: ...

class EmailSender:
    async def send(self, recipient: str, message: str) -> None:
        # send via SMTP / SendGrid
        ...

class SmsSender:
    async def send(self, recipient: str, message: str) -> None:
        # send via Twilio
        ...

def get_notification_sender(channel: str) -> NotificationSender:
    senders = {"email": EmailSender, "sms": SmsSender}
    cls = senders.get(channel)
    if cls is None:
        raise ValueError(f"Unknown notification channel: {channel!r}")
    return cls()
```

The use case calls `get_notification_sender("email")` — it never imports `EmailSender` directly. Adding a new channel is one new class plus one dict entry, with zero changes to callers (Open/Closed Principle).

---

## Structural Patterns

### Repository — Abstract Data Access

Already covered in guideline 04, but worth naming explicitly: **Repository is a structural pattern** that wraps data access behind an interface. The rest of the application never knows if data comes from PostgreSQL, Redis, a filesystem, or an in-memory dict.

```python
# The interface is the contract — use cases depend on this
class UserRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...
    @abstractmethod
    async def create(self, user: User) -> User: ...

# Concrete implementation is infrastructure detail
class UserRepository(UserRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first()
```

### Adapter — Wrap External Services

Third-party APIs (Stripe, SendGrid, S3) change. An Adapter wraps them so the rest of your app doesn't depend on their SDK directly.

```python
# Your interface — stable, domain-language
class IPaymentService(ABC):
    @abstractmethod
    async def charge(self, amount: Decimal, currency: str, source_token: str) -> str:
        """Returns transaction ID."""

# Stripe adapter — only this class knows about stripe SDK
class StripePaymentService(IPaymentService):
    def __init__(self, api_key: str) -> None:
        stripe.api_key = api_key

    async def charge(self, amount: Decimal, currency: str, source_token: str) -> str:
        charge = stripe.Charge.create(
            amount=int(amount * 100),   # Stripe uses cents
            currency=currency,
            source=source_token,
        )
        return charge["id"]
```

When you switch from Stripe to Braintree, you write one new class and change one DI binding — no use case code changes.

### Decorator — Add Behavior Without Changing a Class

Wrap an object to add cross-cutting concerns (caching, logging, metrics) without touching the original implementation.

```python
# Caching decorator for a repository
class CachedUserRepository(UserRepositoryInterface):
    def __init__(self, inner: UserRepositoryInterface, cache: dict) -> None:
        self._inner = inner
        self._cache = cache

    async def get_by_email(self, email: str) -> User | None:
        if email in self._cache:
            return self._cache[email]
        user = await self._inner.get_by_email(email)
        if user:
            self._cache[email] = user
        return user

    async def create(self, user: User) -> User:
        result = await self._inner.create(user)
        self._cache[result.email] = result
        return result

# Wiring: wrap the real repo with the caching decorator
repo = CachedUserRepository(UserRepository(session), cache={})
```

The use case receives a `UserRepositoryInterface` — it can't tell whether it's cached or not.

---

## Behavioral Patterns

### Strategy — Swappable Algorithms

Define a family of algorithms, put each in its own class, and make them interchangeable. Use cases select the strategy at construction time.

```python
# Pricing strategies for a SaaS subscription
class PricingStrategy(Protocol):
    def calculate(self, base_price: Decimal, user_count: int) -> Decimal: ...

class FlatRatePricing:
    def calculate(self, base_price: Decimal, user_count: int) -> Decimal:
        return base_price   # same price regardless of seats

class PerSeatPricing:
    def calculate(self, base_price: Decimal, user_count: int) -> Decimal:
        return base_price * user_count

class VolumeDiscountPricing:
    def calculate(self, base_price: Decimal, user_count: int) -> Decimal:
        discount = Decimal("0.9") if user_count > 10 else Decimal("1.0")
        return base_price * user_count * discount


class CalculateInvoiceUseCase:
    def __init__(self, pricing: PricingStrategy) -> None:
        self.pricing = pricing   # injected — no if/elif chain inside

    async def execute(self, base_price: Decimal, user_count: int) -> Decimal:
        return self.pricing.calculate(base_price, user_count)
```

Without Strategy, you'd have a growing `if plan == "flat": ... elif plan == "per_seat": ...` chain inside the use case — every new pricing model requires editing existing code.

### Command — Encapsulate an Operation

Every use case **is** a Command. The Command pattern formalizes this: wrap an operation (and its parameters) in an object with a single `execute()` method.

```python
# Use cases are commands — consistent interface across the entire application
class CreateUserUseCase:
    def __init__(self, repo: UserRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, dto: CreateUserDto) -> UserDto:
        ...

class DeleteUserUseCase:
    def __init__(self, repo: UserRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, user_id: int) -> None:
        ...
```

This consistency means every developer knows where to look for the implementation of any operation: `src/application/use_cases/<domain>/<verb>.py`.

### Observer — Decouple Side Effects

When an event happens (user registered, payment succeeded), multiple things need to happen (send email, provision account, notify Slack). Instead of the use case calling each handler directly, it publishes an event.

```python
from typing import Callable, Awaitable

EventHandler = Callable[[dict], Awaitable[None]]

class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event, []).append(handler)

    async def publish(self, event: str, payload: dict) -> None:
        for handler in self._handlers.get(event, []):
            await handler(payload)

# Wiring at startup
bus = EventBus()
bus.subscribe("user.registered", send_welcome_email)
bus.subscribe("user.registered", provision_free_tier)
bus.subscribe("user.registered", notify_slack_channel)

# Use case publishes — knows nothing about the handlers
class RegisterUserUseCase:
    def __init__(self, repo: UserRepositoryInterface, bus: EventBus) -> None:
        self.repo = repo
        self.bus = bus

    async def execute(self, dto: CreateUserDto) -> UserDto:
        user = User(email=dto.email)
        user.password = dto.password
        saved = await self.repo.create(user)
        await self.bus.publish("user.registered", {"user_id": saved.id, "email": saved.email})
        return UserDto.model_validate(saved)
```

Adding a new side effect (e.g., log to analytics) requires zero changes to the use case — just `bus.subscribe("user.registered", log_to_analytics)`.

### Chain of Responsibility — FastAPI Middleware Pipeline

FastAPI middleware is a Chain of Responsibility. Each middleware handles a request, optionally modifies it, and passes it to the next:

**`src/presentation/middleware/request_id.py`**
```python
import uuid
from fastapi import Request

async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# src/presentation/middleware/timing.py
import time

async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
    return response

# view.py — add to the chain
def register_middleware(app: FastAPI) -> None:
    app.middleware("http")(timing_middleware)
    app.middleware("http")(request_id_middleware)
    app.add_middleware(CORSMiddleware, ...)
```

---

## Pattern Selection Guide

| Problem | Pattern | Where it lives |
|---|---|---|
| Need one shared instance (DB engine, config) | Singleton (`lru_cache`) | `infrastructure/` factory functions |
| Create objects of different types by name | Factory Method | `infrastructure/services/` |
| Isolate external SDK from your code | Adapter | `infrastructure/services/` |
| Add caching/logging without modifying a class | Decorator | Wrap in `infrastructure/` |
| Swap algorithm at runtime (pricing, auth) | Strategy | Injected via `__init__` |
| Encapsulate one business operation | Command | `application/use_cases/` |
| Decouple side effects from the main flow | Observer | `EventBus` in `application/` |
| Process requests through sequential steps | Chain of Responsibility | FastAPI middleware |

---

## Anti-Pattern: The Procedural God Function

```python
# ❌ WRONG — AI often generates this
@router.post("/register")
async def register(email: str, password: str, plan: str, db=Depends(get_session)):
    # validate
    if "@" not in email: raise HTTPException(400, "bad email")
    if len(password) < 8: raise HTTPException(400, "too short")
    # check duplicate
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalars().first(): raise HTTPException(409, "exists")
    # hash
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    # create
    user = User(email=email, _password_hash=hashed)
    db.add(user)
    await db.commit()
    # provision plan
    if plan == "free": ...
    elif plan == "pro": ...
    # send email
    await send_email(email, "Welcome!")
    # create token
    token = jwt.encode({"sub": str(user.id)}, SECRET)
    return {"token": token}
```

This is zero patterns. It's one function doing validation, duplicate-checking, hashing, persistence, plan provisioning, emailing, and token generation. Every concern violates SRP. Nothing is testable in isolation. Adding a new plan type requires editing this function.

**The fix:** `RegisterUserUseCase` (Command) + `UserRepository` (Repository) + `PricingStrategy` (Strategy) + `EventBus.publish("user.registered")` (Observer).

---

## Quick Checklist

- [ ] Singletons use `lru_cache(maxsize=1)` — no module-level mutable globals
- [ ] External SDKs (Stripe, SendGrid, S3) are behind an Adapter interface
- [ ] Swappable algorithms are Strategy classes injected via `__init__`, not `if/elif` chains
- [ ] Every business operation is a Command (use case) with a single `execute()` method
- [ ] Side effects (emails, notifications, analytics) are decoupled via events, not called directly
- [ ] Cross-cutting concerns (logging, timing, auth) are middleware or Decorator wrappers
- [ ] Factory functions create complex objects — callers never call constructors with >2 args
