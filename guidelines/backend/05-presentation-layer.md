---
model: sonnet
effort: high
---

# Presentation Layer: FastAPI Routes

Use when writing a FastAPI route or MCP tool handler. Covers the thin-layer rule (≤10 lines), response_model enforcement, Depends() injection, domain-error-to-HTTP mapping, and correct status codes.

The presentation layer is the thinnest layer. It translates between HTTP and the application layer. It contains zero business logic — only wiring.

## The Thin Layer Rule

If a route handler exceeds ~10 lines, something that belongs in a use case has leaked into the presentation layer.

**Correct pattern — 5 lines of wiring:**

```python
@router.post("/users", response_model=UserDto, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserDto,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDto:
    return await CreateUserUseCase(UserRepository(session)).execute(body)
```

The handler does exactly three things:
1. Declares the input shape (`body: CreateUserDto`) and output shape (`response_model=UserDto`)
2. Sets up the dependency (`session` via `Depends`)
3. Delegates everything to the use case

## APIRouter — One File Per Domain

Never register routes on `app` directly. Use `APIRouter` so each domain module is self-contained:

**`src/presentation/routes/user.py`**
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from src.application.dto.user_dto import CreateUserDto, UserDto, UserListDto
from src.application.use_cases.user.create import CreateUserUseCase
from src.application.use_cases.user.list_all import ListUsersUseCase
from src.infrastructure.db.engine import get_session
from src.infrastructure.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=UserListDto)
async def list_users(session: Annotated[AsyncSession, Depends(get_session)]) -> UserListDto:
    return await ListUsersUseCase(UserRepository(session)).execute()


@router.post("/", response_model=UserDto, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserDto,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDto:
    return await CreateUserUseCase(UserRepository(session)).execute(body)
```

## view.py — The Wiring Hub

All routers and middleware are registered in one place. `api_main.py` stays clean:

**`src/presentation/view.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.presentation.routes.auth import router as auth_router
from src.presentation.routes.user import router as user_router
from src.config.constants import C


def register_api_routes(app: FastAPI) -> None:
    app.include_router(auth_router, prefix=C.URL_PREFIX)
    app.include_router(user_router, prefix=C.URL_PREFIX)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # tighten in production via settings
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

**`src/api_main.py`**
```python
from fastapi import FastAPI
from src.config.constants import C
from src.presentation.view import register_api_routes, register_middleware


def create_app() -> FastAPI:
    app = FastAPI(title=C.TITLE, version=C.PROJECT_VERSION)
    register_middleware(app)
    register_api_routes(app)
    return app


app = create_app()
```

## response_model — Always Declare It

`response_model` enforces the output schema, strips extra fields, and generates OpenAPI docs automatically:

```python
# ✅ CORRECT — output is validated and documented
@router.get("/{user_id}", response_model=UserDto)
async def get_user(user_id: int, ...) -> UserDto: ...

# ❌ WRONG — no schema enforcement, no docs, silent data leaks
@router.get("/{user_id}")
async def get_user(user_id: int, ...):
    return user_orm_object   # may expose _password_hash, internal fields, etc.
```

## Depends() — Dependency Injection

`Depends()` wires external resources into route handlers without global state:

**`src/infrastructure/db/engine.py`**
```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
        await session.commit()


# Route receives the session automatically — no manual setup
@router.get("/{user_id}", response_model=UserDto)
async def get_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserDto:
    return await GetUserByIdUseCase(UserRepository(session)).execute(user_id)
```

For auth, a reusable dependency extracts the current user from the JWT:

**`src/infrastructure/services/auth_dependency.py`**
```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    payload = decode_access_token(token)   # raises UnauthorizedAccessError if invalid
    return await UserRepository(session).get_by_sub(payload["sub"])


# Any route can require authentication with one line:
@router.get("/me", response_model=UserDto)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserDto:
    return UserDto.model_validate(current_user)
```

## Exception Handling — Domain Errors → HTTP

Catch domain errors at the presentation boundary and convert to HTTP status codes:

```python
from fastapi import HTTPException, status
from src.utils.exc import NotFoundError, UnauthorizedAccessError

@router.get("/{user_id}", response_model=UserDto)
async def get_user(user_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> UserDto:
    try:
        return await GetUserByIdUseCase(UserRepository(session)).execute(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

**Prefer global exception handlers** (see `backend/20-error-handling`) — they keep routes thin and map domain exceptions to HTTP consistently in one place. Inline `try/except` in routes is acceptable only for cases where a specific route needs a status code that differs from the global default. The inline example above is kept for illustration; in a real project, register the global handler instead.

For global handling across all routes, register exception handlers on the app:

**`src/presentation/view.py`**
```python
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UnauthorizedAccessError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedAccessError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})
```

## HTTP Status Codes — Use Them Correctly

| Operation | Status code |
|---|---|
| Resource created | `201 Created` |
| Successful read/update | `200 OK` |
| Successful delete | `204 No Content` |
| Not found | `404 Not Found` |
| Invalid input | `422 Unprocessable Entity` (FastAPI default) |
| Unauthorized | `401 Unauthorized` |
| Forbidden | `403 Forbidden` |

```python
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    await DeleteUserUseCase(UserRepository(session)).execute(user_id)
```

## Authentication Route Pattern

**`src/presentation/routes/auth.py`**
```python
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=AuthSuccessDto)
async def login(
    body: AuthDto,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthSuccessDto:
    try:
        return await UserLoginUseCase(
            UserRepository(session),
            AccessTokenService(get_config().JWT_SECRET),
            RefreshTokenService(get_config().JWT_SECRET),
        ).execute(body)
    except UnauthorizedAccessError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh", response_model=AuthSuccessDto)
async def refresh(body: RefreshDto, session: Annotated[AsyncSession, Depends(get_session)]) -> AuthSuccessDto:
    try:
        return await RefreshTokenUseCase(
            UserRepository(session),
            AccessTokenService(get_config().JWT_SECRET),
            RefreshTokenService(get_config().JWT_SECRET),
        ).execute(body)
    except UnauthorizedAccessError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
```

## Anti-Pattern: Fat Route

```python
# ❌ WRONG — business logic, SQL, and hashing all inside the route handler
@router.post("/users")
async def create_user(email: str, password: str, db: AsyncSession = Depends(get_session)):
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalars().first():
        raise HTTPException(400, "Email already in use")   # business rule in route
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()  # hashing in route
    user = User(email=email, _password_hash=hashed)
    db.add(user)
    await db.commit()
    token = jwt.encode({"sub": str(user.id)}, SECRET_KEY)   # token logic in route
    return {"token": token}
```

This is untestable, irreplaceable, and impossible to reuse. Every concern that should live in a use case or entity is jammed into one function.

## Quick Checklist

- [ ] Route handlers are ≤ 10 lines — no SQL, no hashing, no business rules
- [ ] Every route has `response_model` declared for validation and OpenAPI docs
- [ ] `Depends(get_session)` is the only way to get a DB session — no manual `AsyncSession()` calls
- [ ] Domain errors (`NotFoundError`, `UnauthorizedAccessError`) are caught here and mapped to `HTTPException`
- [ ] All routers are registered in `view.py`, never directly on `app` in `api_main.py`
- [ ] `status_code=201` on create, `204` on delete
- [ ] Auth-protected routes use `Depends(get_current_user)` — one line, no token parsing in the handler
