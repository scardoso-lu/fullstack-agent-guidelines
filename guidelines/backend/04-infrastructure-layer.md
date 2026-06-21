# Infrastructure Layer: Repositories and Database

Use when implementing a repository or managing SQLAlchemy sessions. Covers the contract.py interface pattern, async session lifecycle, flush vs commit, filesystem repositories, and Alembic migrations.

The infrastructure layer implements the interfaces defined by the domain and application layers. It knows about SQLAlchemy, filesystems, external APIs, and message queues — none of the other layers do.

## The Repository Pattern

A repository abstracts data access behind an interface. Use cases depend on the interface; the concrete implementation lives in infrastructure.

**Step 1 — Define the interface in `contract.py`** (the only file use cases import):

```python
# src/infrastructure/repositories/contract.py
from abc import ABC, abstractmethod
from src.domain.entities.note import Note

class NoteRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, note_id: int) -> Note | None:
        raise NotImplementedError

    @abstractmethod
    async def create(self, note: Note) -> Note:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, note_id: int) -> bool:
        raise NotImplementedError
```

**Step 2 — Implement it with SQLAlchemy**:

```python
# src/infrastructure/repositories/note_repository.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.note import Note
from src.infrastructure.repositories.contract import NoteRepositoryInterface

class NoteRepository(NoteRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, note_id: int) -> Note | None:
        result = await self.session.execute(
            select(Note).where(Note._id == note_id)
        )
        return result.scalar_one_or_none()

    async def create(self, note: Note) -> Note:
        self.session.add(note)
        await self.session.flush()       # write to DB without committing
        await self.session.refresh(note) # reload from DB (timestamps, defaults)
        return note
```

The concrete class is only ever named in the **presentation/tools layer** when wiring up the dependency:
```python
# In a tool handler:
async with get_session() as session:
    repo = NoteRepository(session)          # ← only here
    use_case = CreateNoteUseCase(repo)      # ← use case sees the interface
```

## SQLAlchemy Async Session Lifecycle

```python
# src/infrastructure/db/engine.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    config = get_config()
    return create_async_engine(
        config.DATABASE_URL,
        echo=config.DATABASE_ECHO,
        pool_pre_ping=True,    # test connection before borrowing from pool
    )

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(bind=get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
            await session.commit()   # commit on clean exit
        except Exception:
            await session.rollback() # rollback on any error
            raise
        finally:
            await session.close()
```

Key design choices:
- `expire_on_commit=False` — keeps entity attributes accessible after commit in async contexts
- `pool_pre_ping=True` — avoids "server closed the connection" errors after idle periods
- `flush()` vs `commit()` — use `flush()` inside a repository to write to DB within the unit of work; `commit()` happens at the session context manager level
- `lru_cache(maxsize=1)` on `get_engine()` ensures a single engine instance (and connection pool) per process

## Pagination with PagedItems

```python
# src/infrastructure/repositories/contract.py (from mdip-backend)
from dataclasses import dataclass
from typing import Generic, TypeVar, Sequence

T = TypeVar("T")

@dataclass
class PagedItems(Generic[T]):
    items: Sequence[T]
    total_count: int
    current_page: int
    page_size: int
```

Use case returns `PagedItems[Note]`; the DTO layer maps it to `PagedNotesDto`. The generic `T` keeps this reusable across all repository interfaces.

`PagedItems[T]` is the **offset**-pagination envelope (with `current_page` + `total_count`). For **cursor**-pagination at the API boundary — which is the default for list endpoints — use `Page[T]` and the conventions in `backend/21-api-pagination`.

## Filesystem Repository (No Database)

When data is static (like markdown files), skip the database entirely:

```python
# src/infrastructure/repositories/guideline_repository.py
import aiofiles
from pathlib import Path

class GuidelineRepository(GuidelineRepositoryInterface):
    def __init__(self, guidelines_dir: Path) -> None:
        self._dir = guidelines_dir
        self._cache: dict[str, Guideline] | None = None

    async def _load_all(self) -> dict[str, Guideline]:
        if self._cache is not None:
            return self._cache  # served from memory after first load
        md_files = sorted(self._dir.glob("*.md"))
        cache = {}
        for path in md_files:
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
            slug = path.stem
            cache[slug] = Guideline(slug=slug, title=..., content=content, tags=...)
        self._cache = cache
        return cache
```

Use `aiofiles` for non-blocking I/O — calling `open()` directly inside an `async def` function blocks the event loop.

## Alembic Migrations

When using a database, Alembic manages schema evolution:

```bash
# Create a migration from model changes
poetry run task autorevision   # alembic revision --autogenerate -m 'autogenerated'

# Apply migrations
poetry run task auhead          # alembic upgrade head

# Roll back
poetry run task adbase          # alembic downgrade base
```

The `alembic/env.py` must import all entity modules to register them with `Base.metadata`:

```python
# alembic/env.py
from src.infrastructure.db.base import Base
import src.domain.entities  # noqa — registers all models
```

## Anti-Pattern: Business Logic in Repository

```python
# ❌ WRONG
class NoteRepository(NoteRepositoryInterface):
    async def create(self, title: str, content: str) -> Note:
        if len(title) < 3:               # business rule in infrastructure!
            raise ValueError(...)
        note = Note(title=title, content=content)
        self.session.add(note)
        await self.session.flush()
        return note
```

Repository methods receive domain objects, not raw strings. Validation is the use case's job.

## Quick Checklist

- [ ] `contract.py` contains only abstract interfaces — no imports from concrete implementations
- [ ] Concrete repositories are instantiated only in the presentation/tools layer
- [ ] Repository methods use `flush()` not `commit()` (commit is managed by context manager)
- [ ] `get_engine()` is `lru_cache`'d to a single instance
- [ ] `aiofiles` is used for any filesystem reads in async context
- [ ] No business logic (validation, computation) in repository methods
