# Async Python Patterns

Use when writing async code or debugging event loop issues. Covers the concurrency model, asynccontextmanager session lifecycle, flush vs commit, aiofiles for filesystem I/O, and lru_cache on sync factories.

Python's `async/await` syntax enables concurrent I/O without threads. Understanding the event loop model prevents subtle bugs and performance problems.

## The Mental Model

```
Event Loop
    │
    ├── coroutine A (waiting for DB query) ← suspended, not blocking
    ├── coroutine B (waiting for file read) ← suspended, not blocking
    └── coroutine C (running, CPU work) ← active
```

The event loop runs one coroutine at a time. When a coroutine hits an `await`, it suspends and lets another coroutine run. This is **concurrency**, not **parallelism** — no threads, no GIL contention.

**When async helps:** I/O-bound work — database queries, HTTP requests, file reads
**When async doesn't help:** CPU-bound work — image processing, JSON parsing, heavy computation

## The `asynccontextmanager` Pattern

The session lifecycle is managed with `@asynccontextmanager`:

```python
# src/infrastructure/db/engine.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session          # caller code runs here
            await session.commit() # commit on clean exit
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()  # always close
```

Usage:
```python
async with get_session() as session:
    repo = NoteRepository(session)
    result = await repo.create(note)
# session is automatically committed and closed here
```

The `try/yield/except/finally` pattern ensures cleanup happens even on exceptions. Never call `session.close()` or `session.commit()` manually in tool handlers — let the context manager do it.

## SQLAlchemy Async Session Gotchas

### `expire_on_commit=False`

```python
factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # ← critical for async
)
```

By default, SQLAlchemy expires all attributes after `commit()`. In async contexts, accessing those attributes would trigger a lazy load — but lazy loading is not supported in async SQLAlchemy. Setting `expire_on_commit=False` keeps attributes accessible after commit.

### `flush()` vs `commit()`

```python
# In a repository method:
self.session.add(note)
await self.session.flush()    # ← write to DB, stay in transaction
await self.session.refresh(note)  # ← reload from DB (get server defaults)
return note

# The context manager calls commit() after the tool handler returns
```

- `flush()` — writes changes to DB within the current transaction; can be rolled back
- `commit()` — makes changes permanent; called once per request by the context manager

### Never Use `session.execute(text(...))` for Business Queries

```python
# ❌ WRONG — raw SQL bypasses the ORM layer
result = await session.execute(text("SELECT * FROM notes WHERE id = :id"), {"id": note_id})

# ✅ CORRECT — ORM query is type-safe and portable
result = await session.execute(select(Note).where(Note._id == note_id))
```

## aiofiles for Filesystem I/O

```python
# ✅ CORRECT — non-blocking file read
import aiofiles

async def _read_file(self, path: Path) -> str:
    async with aiofiles.open(path, encoding="utf-8") as f:
        return await f.read()
```

```python
# ❌ WRONG — blocks the event loop
def _read_file(self, path: Path) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()  # blocks all other coroutines until this returns
```

Calling synchronous `open()` inside an `async def` function blocks the event loop. During the read, no other coroutine can run — the server appears unresponsive.

## `lru_cache` with Async

`lru_cache` is for **synchronous** functions only:

```python
# ✅ CORRECT — lru_cache on sync functions that return async-capable objects
@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(...)  # sync constructor, async usage

@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker:
    return async_sessionmaker(bind=get_engine())
```

```python
# ❌ WRONG — lru_cache on an async function
@lru_cache(maxsize=1)
async def get_guideline_count() -> int:    # doesn't work as expected
    ...
```

`lru_cache` on `async def` would cache the coroutine object, not the result. Use an instance-level `self._cache` dict for async-friendly caching.

## AsyncMock in Tests

```python
from unittest.mock import AsyncMock, MagicMock

# Use MagicMock for the object, AsyncMock for individual async methods
repo = MagicMock()
repo.get_by_slug = AsyncMock(return_value=Guideline._mock())
repo.search = AsyncMock(return_value=[])

# For methods that should raise:
repo.get_by_slug = AsyncMock(side_effect=Exception("DB error"))
```

`MagicMock()` for the whole object, `AsyncMock()` for each `async def` method on it.

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Calling sync I/O in async function | Server hangs on file/DB operations | Use `aiofiles`, `asyncpg`, SQLAlchemy async |
| Forgetting `await` | Returns a coroutine object instead of result | Add `await` before async calls |
| `lru_cache` on `async def` | Caches coroutine, not result | Cache result in instance variable |
| `time.sleep()` in async code | Blocks entire event loop | Use `asyncio.sleep()` |
| Creating new event loops in tests | "There is no current event loop" errors | Use `pytest-asyncio` with `asyncio_mode="auto"` or `@pytest.mark.asyncio` |

## Quick Checklist

- [ ] All file I/O uses `aiofiles.open()`, never built-in `open()`
- [ ] `expire_on_commit=False` is set on the session factory
- [ ] Repository methods use `flush()` + `refresh()`, not `commit()`
- [ ] `lru_cache` is applied only to sync functions (`get_engine`, `get_config`)
- [ ] `asyncio.sleep()` replaces `time.sleep()` in any async context
- [ ] `AsyncMock` is used for mocking async repository methods in tests
