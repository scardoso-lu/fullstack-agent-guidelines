---
model: sonnet
effort: high
---

# Testing Strategy: pytest-asyncio and Unit Isolation

Use when writing tests for use cases or routes. Covers pytest-asyncio setup, AsyncMock for repositories, the _mock() entity factory, Arrange/Act/Assert structure, and AsyncClient for route integration tests.

Good tests prove that business rules work — not that Python syntax is correct. Every test should be readable as a specification of behavior.

## Test Philosophy

- **Unit tests** cover use cases — fast, no I/O, no database, mock the repository
- **Integration tests** cover repositories — real filesystem or DB, no mocking
- **Integration tests** for routes use FastAPI's `AsyncClient` (httpx) — no running server needed

## pytest-asyncio Setup

**`pyproject.toml`**
```toml
[tool.pytest.ini_options]
asyncio_default_fixture_loop_scope = "function"
addopts = "--cov=src --cov-report=html --cov-report=xml"
```

`asyncio_default_fixture_loop_scope = "function"` gives each test its own event loop. This prevents cross-test state from async fixtures and is the safest default.

Mark each async test explicitly:
```python
@pytest.mark.asyncio
async def test_something(): ...
```

Set `ENVIRONMENT = "TEST"` so tests use `TestSettings` (no real DB required):
```toml
[tool.pytest_env]
ENVIRONMENT = "TEST"
```

## AsyncMock Pattern — The Core Testing Tool

**`test/unit/application/use_cases/guideline/test_get_by_slug.py`**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.guideline_dto import GuidelineDto
from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.domain.entities.guideline import Guideline
from src.utils.exc import NotFoundError

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_slug = AsyncMock()   # ← AsyncMock for async methods
    return repo

@pytest.mark.asyncio
async def test_get_found(mock_repo):
    # Arrange
    mock_repo.get_by_slug.return_value = Guideline._mock("01-alpha", "Alpha")
    use_case = GetGuidelineBySlugUseCase(mock_repo)

    # Act
    result = await use_case.execute("01-alpha")

    # Assert
    assert isinstance(result, GuidelineDto)
    assert result.slug == "01-alpha"
    mock_repo.get_by_slug.assert_called_once_with("01-alpha")  # verify the call

@pytest.mark.asyncio
async def test_get_not_found_raises(mock_repo):
    mock_repo.get_by_slug.return_value = None  # simulate missing resource

    with pytest.raises(NotFoundError):
        await GetGuidelineBySlugUseCase(mock_repo).execute("99-missing")

@pytest.mark.asyncio
async def test_empty_slug_raises(mock_repo):
    with pytest.raises(ValueError, match="Slug cannot be empty"):
        await GetGuidelineBySlugUseCase(mock_repo).execute("   ")
    mock_repo.get_by_slug.assert_not_called()  # ← verify no DB call happened
```

## The `_mock()` Pattern

Every domain entity should have a static factory for test construction:

**`src/domain/entities/user.py (from mdip-backend)`**
```python
@staticmethod
def _mock(sub: int = 1) -> "User":
    user = User(name=f"Test User {sub}", email=f"test.{sub}@example.com", password="hashed")
    user.sub = sub
    return user
```

Usage in tests:
```python
mock_repo.get_by_sub.return_value = User._mock(sub=42)
```

This is better than constructing entities inline in every test because:
- The test doesn't need to know entity construction details
- Changing the entity's `__init__` only breaks `_mock()`, not every test

## Arrange / Act / Assert

Every test follows three sections:

```python
@pytest.mark.asyncio
async def test_create_note_success(mock_repo):
    # Arrange — set up preconditions
    note = Note._mock(note_id=1)
    mock_repo.create.return_value = note
    use_case = CreateNoteUseCase(mock_repo)
    dto = CreateNoteDto(title="Hello", content="World")

    # Act — execute the behavior under test
    result = await use_case.execute(dto)

    # Assert — verify outcomes
    assert isinstance(result, NoteDto)
    mock_repo.create.assert_called_once()
```

This structure makes it immediately clear what each test is checking.

## FastAPI Route Integration Tests

Use `httpx.AsyncClient` with `app` to test routes end-to-end in memory — no running server, no real DB needed when you override `get_session` with a test DB:

**`test/integration/routes/test_user_routes.py`**
```python
import pytest
from httpx import AsyncClient, ASGITransport

from src.api_main import create_app

app = create_app()


@pytest.mark.asyncio
async def test_create_user_returns_201():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/users", json={"email": "a@b.com", "password": "secret"})

    assert response.status_code == 201
    assert response.json()["email"] == "a@b.com"
    assert "password" not in response.json()   # ← verify sensitive fields are stripped


@pytest.mark.asyncio
async def test_get_user_not_found_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/99999")

    assert response.status_code == 404
```

Route tests verify that HTTP wiring is correct (status codes, response shape, auth headers). They do NOT test business logic — that's already covered by use case unit tests.

## Repository Tests with Real Filesystem

For filesystem-based repositories, use real files in a `test/fixtures/` directory:

**`test/unit/infrastructure/repositories/test_guideline_repository.py`**
```python
import pytest
from pathlib import Path
from src.infrastructure.repositories.guideline_repository import GuidelineRepository

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "guidelines"

@pytest.mark.asyncio
async def test_get_all_loads_files():
    repo = GuidelineRepository(FIXTURES_DIR)
    results = await repo.get_all()
    assert len(results) == 2  # matches number of fixture .md files

@pytest.mark.asyncio
async def test_cache_populated_after_first_call():
    repo = GuidelineRepository(FIXTURES_DIR)
    assert repo._cache is None
    await repo.get_all()
    assert repo._cache is not None  # loaded on first call, cached after
```

## Coverage Configuration

**`pyproject.toml`**
```toml
[tool.coverage.report]
omit = [
    'src/api_main.py',        # wire-up code, not logic
    'src/config/*',           # configuration, not logic
    'src/utils/exc.py',       # exception definitions
    'src/application/dto/*',  # Pydantic models, no logic
    'src/presentation/routes/*',   # thin wiring
]

exclude_also = [
    '@(abc\.)?abstractmethod',  # abstract method stubs
    'raise NotImplementedError', # abstract stubs
    'if TYPE_CHECKING:',         # import-only blocks
]
```

This omits wire-up and plumbing code. Coverage reports should reflect **business logic coverage**, not how well your Pydantic models are defined.

## Anti-Patterns in Testing

```python
# ❌ WRONG — testing framework behavior instead of your code
async def test_pydantic_validates_email():
    with pytest.raises(ValidationError):
        UserDto(email="not-an-email")  # Pydantic already tests this

# ❌ WRONG — testing implementation details instead of behavior
async def test_create_calls_session_add():
    # Don't test that session.add() was called — test that the entity was saved

# ❌ WRONG — integration test disguised as unit test
async def test_create_note_uses_real_db():
    engine = create_async_engine("sqlite:///test.db")
    # ... requires DB, slow, hard to isolate
```

## Quick Checklist

- [ ] Every `async def test_*` has `@pytest.mark.asyncio`
- [ ] `asyncio_default_fixture_loop_scope = "function"` is set in `pyproject.toml`
- [ ] Repository methods are `AsyncMock`, the repo object itself is `MagicMock`
- [ ] Tests follow Arrange / Act / Assert with clear section separation
- [ ] Entities are constructed via `_mock()`, not manually in each test
- [ ] `assert_called_once_with()` verifies that the mock was called with the right args
- [ ] Coverage omit list excludes wire-up code (dto, config, main files)
