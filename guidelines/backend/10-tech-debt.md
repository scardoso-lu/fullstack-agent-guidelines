# Recognizing and Managing Technical Debt

Use when a codebase is drifting — fat routes, hardcoded values, logic leaking into repositories, or N+1 queries. Covers each code smell with its refactoring strategy and when NOT to refactor.

Technical debt is code that works today but makes tomorrow harder. It's unavoidable in fast development — what matters is recognizing it early and paying it down deliberately.

## Warning Signs

### Fat Route Handlers / Tool Handlers

```python
# ❌ FAT ROUTE — 40 lines of business logic in a route
@router.post("/notes")
async def create_note(data: dict, session: AsyncSession = Depends(get_session)):
    if len(data.get("title", "")) < 3:               # business rule
        raise HTTPException(400, "Title too short")
    
    existing = await session.execute(                 # direct SQL in route
        select(Note).where(Note.title == data["title"])
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Already exists")
    
    note = Note(title=data["title"], content=data.get("content", ""))
    session.add(note)
    await session.commit()
    await session.refresh(note)
    
    # send notification email...
    # log audit event...
    return {"id": str(note._id), "title": note.title}
```

**Refactor signals:** business validation, duplicate detection, email sending, and audit logging all in one function. Each is a separate concern and a separate reason to change.

### Concrete Class Imports in Use Cases

```python
# ❌ WRONG — imports concrete class, not the interface
from src.infrastructure.repositories.note_repository import NoteRepository

class CreateNoteUseCase:
    def __init__(self):
        self.repo = NoteRepository()  # hardcoded dependency
```

You can't unit test this without a real database. The `_mock()` pattern and `AsyncMock` become useless.

### Hardcoded Configuration Values

```python
# ❌ WRONG — hardcoded everywhere
engine = create_async_engine("postgresql://admin:secret@prod-db/app")
jwt_secret = "abc123"
max_file_size = 10 * 1024 * 1024
```

These must live in `config/settings/`. If the value appears in more than one place, it's tech debt.

### Mixed Responsibility in a Single Class

```python
# ❌ WRONG — repository doing business logic
class UserRepository:
    async def create_user_and_send_welcome_email(self, name, email, password):
        user = User(name=name, email=email, password=password)
        self.session.add(user)
        await self.session.flush()
        await send_email(email, "Welcome!")  # I/O side effect in repository!
        return user
```

Repository methods are pure data access. Side effects (email, notifications, events) belong in use cases or dedicated infrastructure services.

## The "Working but Wrong" Category

These pass all tests but violate architecture:

| Code that works | Why it's still debt |
|---|---|
| Use case imports `NoteRepository` directly | Untestable without DB; violates DI |
| JWT secret has a default value in Settings | Works in dev, security hole in prod |
| `paginate()` function in `utils.py` with 10 callers | Should be on the repository; utils becomes a dumping ground |
| Route handler calling two use cases in sequence | Cross-cutting concern; should be one use case or a transaction |
| DTO with a computed property that queries the DB | Presentation model with infrastructure dependency |

## N+1 Query Pattern

```python
# ❌ N+1 — one query per item in the loop
notes = await repo.list_all()  # query 1: get all notes
for note in notes.items:
    note.author = await user_repo.get_by_sub(note.author_sub)  # query 2..N+1!
```

Fix with SQLAlchemy `joinedload` or explicit JOIN queries. This is a performance debt that becomes critical at scale.

## Incremental Refactoring Strategy

Pay debt in small steps, never in a Big Bang rewrite:

1. **Add tests first** — write tests for the behavior you're about to change. If you can't test it, that's the debt.
2. **Extract the use case** — move business logic from the route to a use case class
3. **Introduce the interface** — add an abstract interface between the use case and the concrete repo
4. **Test the use case in isolation** — with `AsyncMock`, no DB needed
5. **Delete the old code** — the route is now just 4 lines of wiring

## The Boy Scout Rule

> Leave the code cleaner than you found it.

If you touch a file, improve one small thing: rename a confusing variable, extract a 3-line helper, add a missing type annotation. You don't have to refactor everything — just leave it slightly better.

## When NOT to Refactor

- **Stable code with good coverage** — if it works, is tested, and isn't being changed, leave it alone
- **Code you don't understand** — add tests first, understand behavior, then refactor
- **The week before a release** — refactoring introduces risk; schedule it for after the release
- **"Just to make it cleaner"** — without a specific smell to fix, refactoring is noise

## Quick Checklist

- [ ] No route/tool handler exceeds ~10 lines
- [ ] No concrete repository class imported inside a use case
- [ ] All configuration values are in `config/settings/` with `pydantic-settings`
- [ ] Repository methods have no side effects (no email, no events, no external calls)
- [ ] No `utils.py` dumping ground — every utility lives in the layer it belongs to
- [ ] N+1 queries are caught in code review before merging
