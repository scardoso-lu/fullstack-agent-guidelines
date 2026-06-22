---
model: opus
effort: high
---

# SQLAlchemy Async Session Lifecycle

Use when wiring the database engine, configuring the session factory, or deciding between `flush()` and `commit()`. For the repository pattern (how use cases talk to the database through contracts) see `backend/04-infrastructure-layer`. For schema evolution see `backend/29-alembic-migrations`.

---

## Engine and session factory

**`src/infrastructure/db/engine.py`**
```python
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

| Setting | Reason |
|---|---|
| `expire_on_commit=False` | Keeps entity attributes accessible after commit in async contexts |
| `pool_pre_ping=True` | Avoids "server closed the connection" errors after idle periods |
| `lru_cache(maxsize=1)` on `get_engine()` | Single engine instance (and connection pool) per process |

---

## `flush()` vs `commit()`

| Operation | When to use | Who calls it |
|---|---|---|
| `session.flush()` | Write to DB *within* the current transaction — rows are visible to subsequent queries in the same session but not yet committed | Repository methods, after `session.add()` or DML, when you need the row's DB-generated values (timestamps, sequences) before returning |
| `session.commit()` | Persist the transaction and release the connection back to the pool | The `get_session()` context manager on clean exit — **never called inside a repository** |
| `session.rollback()` | Undo all unflushed + uncommitted work | The `get_session()` context manager on any exception |

### Anti-pattern: committing inside a repository

```python
# ❌ WRONG — repository commits its own work, bypassing the unit of work
class NoteRepository(NoteRepositoryInterface):
    async def create(self, note: Note) -> Note:
        self.session.add(note)
        await self.session.commit()   # breaks transactional integrity
        return note
```

```python
# ✅ CORRECT — repository flushes; the session context manager commits
class NoteRepository(NoteRepositoryInterface):
    async def create(self, note: Note) -> Note:
        self.session.add(note)
        await self.session.flush()       # write to DB without committing
        await self.session.refresh(note) # reload DB-generated values
        return note
```

The context manager at the boundary (`get_session`) is the single commit point. This ensures that a use case that calls multiple repositories either commits everything or rolls back everything.

---

## Quick Checklist

- [ ] `get_engine()` is `lru_cache`'d — single engine instance per process
- [ ] `expire_on_commit=False` set on the session factory
- [ ] `pool_pre_ping=True` set on the engine
- [ ] Repository methods use `flush()`, never `commit()`
- [ ] `commit()` and `rollback()` live only in the `get_session()` context manager
- [ ] `refresh()` called after `flush()` when DB-generated values (timestamps, IDs) are needed before returning the entity
