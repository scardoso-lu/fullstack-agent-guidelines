---
model: opus
effort: high
---

# Infrastructure Layer: Repository Pattern

Use when implementing a repository or wiring data access behind an interface. Covers the `contract.py` interface pattern, concrete SQLAlchemy and filesystem implementations, and the `PagedItems` envelope. For the session lifecycle (flush vs commit, engine config) see `backend/28-database-session`. For schema migrations see `backend/29-alembic-migrations`.

The infrastructure layer implements the interfaces defined by the domain and application layers. It knows about SQLAlchemy, filesystems, external APIs, and message queues — none of the other layers do.

---

## The Repository Pattern

A repository abstracts data access behind an interface. Use cases depend on the interface; the concrete implementation lives in infrastructure.

**Step 1 — Define the interface in `contract.py`** (the only file use cases import):

**`src/infrastructure/repositories/contract.py`**
```python
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

**`src/infrastructure/repositories/note_repository.py`**
```python
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

---

## Pagination with PagedItems

**`src/infrastructure/repositories/contract.py`**
```python
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

`PagedItems[T]` is the **offset**-pagination envelope (with `current_page` + `total_count`). For **cursor**-pagination at the API boundary — the default for new list endpoints — use `Page[T]` from `backend/21-api-pagination`.

---

## Filesystem Repository (No Database)

When data is static (like markdown files), skip the database entirely:

**`src/infrastructure/repositories/guideline_repository.py`**
```python
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

---

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

---

## Quick Checklist

- [ ] `contract.py` contains only abstract interfaces — no imports from concrete implementations
- [ ] Concrete repositories are instantiated only in the presentation/tools layer
- [ ] Repository methods use `flush()` not `commit()` — see `backend/28-database-session`
- [ ] `aiofiles` used for any filesystem reads in async context
- [ ] No business logic (validation, computation) in repository methods
