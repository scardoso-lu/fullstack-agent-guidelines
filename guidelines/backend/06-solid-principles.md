---
model: opus
effort: high
---

# SOLID Principles in Python — Concrete Examples

Use when designing a new class, interface, or module. Maps each SOLID letter to a concrete pattern: one-file-per-use-case (S), add-new-file-not-edit-existing (O), swap-any-impl (L), interface-per-aggregate (I), inject-via-contract (D).

SOLID is a set of five design principles that make code easier to maintain, extend, and test. Each principle maps directly to patterns used throughout this codebase.

## S — Single Responsibility Principle

> A class should have one reason to change.

**Applied:** Each use case is one file, one class, one operation.

```python
# ✅ CORRECT — five files, each with one responsibility
CreateNoteUseCase    # changes when note creation rules change
GetNoteByIdUseCase   # changes when retrieval logic changes
ListNotesUseCase     # changes when listing/pagination logic changes
UpdateNoteUseCase    # changes when update rules change
DeleteNoteUseCase    # changes when deletion rules change
```

```python
# ❌ WRONG — one class with five reasons to change
class NoteService:
    async def create(self, ...): ...
    async def get(self, ...): ...
    async def list(self, ...): ...
    async def update(self, ...): ...
    async def delete(self, ...): ...
```

`utils/exc.py` is also SRP: it is solely an exception taxonomy. It never imports from application or infrastructure.

## O — Open/Closed Principle

> Software should be open for extension, closed for modification.

**Applied:** Add new behavior by adding new files, not editing existing ones.

Adding a new use case (`ExportNoteUseCase`) requires:
- Creating `src/application/use_cases/note/export.py` ← new file
- Adding one `@router.get` endpoint in `src/presentation/routes/note.py`

What you do NOT touch: `contract.py`, `note_repository.py`, any existing use case.

Adding a new repository implementation (e.g., an in-memory repo for testing):
```python
class InMemoryNoteRepository(NoteRepositoryInterface):
    def __init__(self): self._store: dict[int, Note] = {}
    async def get_by_id(self, note_id: int) -> Note | None: return self._store.get(note_id)
    async def create(self, note: Note) -> Note:
        self._store[note._id] = note
        return note
    # ... other methods
```

`NoteRepositoryInterface` (contract.py) is never modified. The new class extends behavior.

## L — Liskov Substitution Principle

> Subtypes must be substitutable for their base types.

**Applied:** `NoteRepository` and `InMemoryNoteRepository` are interchangeable wherever `NoteRepositoryInterface` is typed.

```python
# CreateNoteUseCase works identically regardless of which repo is passed:
use_case = CreateNoteUseCase(NoteRepository(session))      # production
use_case = CreateNoteUseCase(InMemoryNoteRepository())      # test
use_case = CreateNoteUseCase(mock_repo)                     # unit test
```

If a concrete repository raises unexpected exceptions or returns values outside the interface contract, it violates LSP and breaks use cases that were working.

## I — Interface Segregation Principle

> Clients should not be forced to depend on methods they don't use.

**Applied:** Repository interfaces are defined per aggregate, not as one mega-interface.

```python
# ✅ CORRECT — separate interfaces, each with focused methods
class NoteRepositoryInterface(ABC):      # only note methods
class UserRepositoryInterface(ABC):      # only user methods
class GuidelineRepositoryInterface(ABC): # only guideline methods
```

```python
# ❌ WRONG — one interface that forces every repo to implement everything
class RepositoryInterface(ABC):
    async def get_note(self, ...): ...
    async def get_user(self, ...): ...
    async def get_guideline(self, ...): ...
    # A NoteRepository is forced to implement get_user() and get_guideline()
```

From mdip-backend, notice each aggregate gets its own interface: `UserRepositoryInterface`, `DrugCatalogRepositoryInterface`, `MappingRepositoryInterface` — never a shared superinterface.

## D — Dependency Inversion Principle

> High-level modules should not depend on low-level modules. Both should depend on abstractions.

**Applied:** Use cases (high-level) depend on `NoteRepositoryInterface` (abstraction). `NoteRepository` (low-level) implements that abstraction. The concrete class is only named in the tool handler (composition root).

```
CreateNoteUseCase          ← depends on →   NoteRepositoryInterface (abstract)
                                                      ↑ implements
                                              NoteRepository (concrete)
```

Import trace:
```python
# application/use_cases/note/create.py
from src.infrastructure.repositories.contract import NoteRepositoryInterface  # ✅ abstract

# presentation/routes/note.py
from src.infrastructure.repositories.note_repository import NoteRepository    # ✅ only here
from src.infrastructure.repositories.contract import NoteRepositoryInterface  # not needed here
```

The use case never imports `NoteRepository`. This means you can replace the database implementation with a filesystem or in-memory implementation without touching any business logic.

## Quick Reference Table

| Letter | Principle | Violation looks like | Fix |
|---|---|---|---|
| **S** | Single Responsibility | `NoteService` with 10 methods | One file per operation |
| **O** | Open/Closed | Editing `contract.py` to add a feature | Add new file, implement existing interface |
| **L** | Liskov Substitution | Concrete repo raises exceptions not in interface | Test every impl with the same use case test |
| **I** | Interface Segregation | One repo interface with unrelated methods | Separate interface per aggregate |
| **D** | Dependency Inversion | `from .note_repository import NoteRepository` in a use case | Depend on `NoteRepositoryInterface` from `contract.py` |

## Quick Checklist

- [ ] Each use case file has exactly one class
- [ ] New features are new files, not modifications to existing ones
- [ ] Use cases import from `contract.py`, never from concrete repository files
- [ ] Each aggregate has its own repository interface
- [ ] Concrete classes are only instantiated in the presentation/routes layer
