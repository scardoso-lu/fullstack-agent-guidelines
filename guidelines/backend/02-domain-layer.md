# Domain Layer: Entities and Value Objects

Use when creating or modifying a domain entity or value object. Covers SQLAlchemy ORM entities, frozen dataclass value objects, password hashing in setters, Snowflake IDs, and the _mock() factory pattern for tests.

The domain layer is the heart of the application. It contains the business objects and rules that exist independently of any framework, database, or API. If you delete FastAPI and SQLAlchemy, the domain still makes sense.

## What Belongs Here

- **Entities** — Objects with identity (usually persisted, have a primary key)
- **Value Objects** — Immutable objects with structural equality (no identity needed)
- **Domain Services** — Stateless logic that spans multiple entities

What does NOT belong here: imports from `fastapi`, `sqlalchemy.orm`, `infrastructure`, or `presentation`.

## SQLAlchemy Entity Pattern

```python
# src/domain/entities/note.py
import sqlalchemy as sq
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.db.base import Base, IdMixin, generate_snowflake_id

class Note(Base, IdMixin):
    __tablename__ = "notes"

    title: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    content: Mapped[str] = mapped_column(sq.Text, nullable=False, default="")
    created_at: Mapped[sq.DateTime] = mapped_column(
        sq.DateTime(timezone=True),
        server_default=sq.func.now(),
    )

    def __init__(self, title: str, content: str = "") -> None:
        self._id = generate_snowflake_id()
        self.title = title
        self.content = content

    @staticmethod
    def _mock(note_id: int = 1) -> "Note":
        note = Note(title=f"Test Note {note_id}", content="Mock content")
        note._id = note_id
        return note
```

Key points:
- `Base` is the SQLAlchemy `DeclarativeBase` — entities inherit from it
- `IdMixin` provides the `_id` / `id` pattern with Snowflake ID generation
- `__init__` sets the ID explicitly so the entity is fully valid before being persisted
- `_mock()` is a test helper — it creates a valid entity without touching the database

## Snowflake IDs vs UUIDs

The project uses 64-bit Snowflake IDs (not UUIDs):

```python
# src/infrastructure/db/base.py
from functools import lru_cache
from snowflake import SnowflakeGenerator

@lru_cache(maxsize=1)
def _get_snowflake_generator(instance: int = 1) -> SnowflakeGenerator:
    return SnowflakeGenerator(instance)

def generate_snowflake_id() -> int:
    return next(_get_snowflake_generator())
```

Snowflake IDs are **sortable by creation time**, fit in a `BigInteger` column, and avoid the read/write overhead of UUID string comparison. The `lru_cache` ensures only one generator instance exists per process.

## Value Object Pattern

Use `@dataclass(frozen=True)` for objects that have no identity — equality is structural, not by reference.

```python
# src/domain/entities/guideline.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Guideline:
    slug: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)  # ← never use [] as default!
```

- `frozen=True` prevents accidental mutation; `hash()` works automatically
- `field(default_factory=list)` avoids the classic Python mutable-default-argument bug
- No `_id` needed — a guideline's identity IS its slug

## Password Hashing on the Entity

Domain-specific behavior like password hashing belongs on the entity, not in a service or route:

```python
# src/domain/entities/user.py (from mdip-backend)
import bcrypt

class User(Base):
    _password: Mapped[str] = mapped_column("password", sq.String, nullable=False)

    @property
    def password(self) -> str:
        return self._password

    @password.setter
    def password(self, raw_password: str) -> None:
        """Hashes before storing — never stores plaintext."""
        password_bytes = raw_password.encode("utf-8")
        password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        self._password = password_hash.decode("utf-8")

    def verify_password(self, raw_password: str) -> bool:
        return bcrypt.checkpw(
            raw_password.encode("utf-8"), self.password.encode("utf-8")
        )
```

This encapsulation means no code outside `User` ever handles raw passwords. The setter is the single place where hashing happens.

## The `_mock()` Pattern

Every entity should have a `_mock()` static method for test construction:

```python
@staticmethod
def _mock(note_id: int = 1) -> "Note":
    note = Note(title=f"Test Note {note_id}", content="Mock content")
    note._id = note_id
    return note
```

This lets tests create valid domain objects without a database:
```python
mock_repo.get_by_id.return_value = Note._mock(note_id=42)
```

## Anti-Pattern: Entity with HTTP Knowledge

```python
# ❌ WRONG
from fastapi import HTTPException

class User(Base):
    def verify_password(self, raw: str) -> None:
        if not bcrypt.checkpw(...):
            raise HTTPException(status_code=401)  # HTTP in domain layer!
```

Domain objects must not know about HTTP. Raise a domain error (`UnauthorizedAccessError`) and let the presentation layer map it to HTTP status codes.

## Quick Checklist

- [ ] Entities inherit from `Base` (SQLAlchemy) or are `frozen=True` dataclasses (value objects)
- [ ] No imports from `fastapi`, `presentation/`, or `infrastructure/` except `db.base`
- [ ] Mutable collection defaults use `field(default_factory=...)` not `[]` or `{}`
- [ ] Every entity has a `_mock()` method for test construction
- [ ] Password/secret logic lives in setter methods, not in services or routes
