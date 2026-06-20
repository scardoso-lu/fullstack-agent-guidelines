# DRY, KISS, YAGNI — When Abstraction Hurts

Use when tempted to extract an abstraction, create a base class, or build for a future requirement that doesn't exist yet. Covers when DRY helps vs hurts, the Rule of Three, and YAGNI violations common in AI-generated code.

Three principles that prevent over-engineering and unnecessary complexity.

## DRY — Don't Repeat Yourself

Extract duplication when the same *concept* appears more than twice and changes for the same reason.

**Good DRY — `BaseSchema` shared across all DTOs:**

```python
# src/application/dto/__init__.py (from mdip-backend)
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )

# Every DTO inherits consistent config without repeating model_config
class NoteDto(BaseSchema): ...
class UserDto(BaseSchema): ...
class GuidelineDto(BaseSchema): ...
```

**Good DRY — parse logic extracted to a helper:**

```python
# ✅ extract when logic appears in 3+ places
@staticmethod
def _parse_title(content: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else ""
```

**Bad DRY — extracting accidental similarity:**

```python
# ❌ WRONG — these look similar but change for completely different reasons
class CreateNoteValidator:
    def validate(self, title): return len(title) > 0

class CreateUserValidator:
    def validate(self, email): return "@" in email

# Don't extract into BaseValidator just because they're both "validators"
```

The test: would both callsites need to change if the shared code changes? If not, it's accidental similarity, not real duplication.

## KISS — Keep It Simple, Stupid

Write the simplest code that solves the problem.

**The three-line dependency wiring:**

```python
# ✅ KISS — obvious, readable, no indirection
async with get_session() as session:
    use_case = CreateNoteUseCase(NoteRepository(session))
    return await use_case.execute(dto)
```

```python
# ❌ Over-engineered — a service locator adds indirection with no benefit
class ServiceLocator:
    _registry = {}

    @classmethod
    def register(cls, name, factory): cls._registry[name] = factory

    @classmethod
    def get(cls, name): return cls._registry[name]()

# Now you need to trace through the registry to understand what executes
use_case = ServiceLocator.get("create_note")
```

**The `_mock()` factory on entities:**

```python
# ✅ KISS — one static method, no factory framework
@staticmethod
def _mock(note_id: int = 1) -> "Note":
    note = Note(title=f"Test Note {note_id}", content="Mock")
    note._id = note_id
    return note
```

You don't need a `MockFactory`, `TestDataBuilder`, or fixture library for this.

## YAGNI — You Aren't Gonna Need It

Don't add code for hypothetical future requirements.

**YAGNI violations common in AI-generated code:**

```python
# ❌ YAGNI — added "in case we need it later"
class BaseUseCase(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs): ...
    
    async def before_execute(self): pass   # not used anywhere
    async def after_execute(self): pass    # not used anywhere
    
    def log(self, msg): logger.debug(msg)  # not used anywhere
```

If nothing currently needs `BaseUseCase`, don't create it. Three concrete use cases with identical structure is better than a premature abstraction.

```python
# ❌ YAGNI — pagination for a list that has 12 items and never grows
async def get_all(self, page: int = 1, page_size: int = 20) -> PagedItems[Guideline]:
    ...

# ✅ YAGNI-compliant — just return the list
async def get_all(self) -> list[Guideline]:
    ...
```

## The Rule of Three

Abstract on the **third** occurrence, not the second:

1. First time: write it
2. Second time: write it again (resist the urge to abstract)
3. Third time: now extract

The second occurrence might be coincidence. The third occurrence proves a pattern.

## When NOT to Create an Interface

Interfaces (ABCs) make sense when:
- There are (or will soon be) two or more concrete implementations
- You need to swap implementations in tests

Don't create `IFileReader` if there will ever be only one file reader. Don't create `ILogger` if you're just wrapping the standard library `logging` module.

```python
# ❌ YAGNI — interface for something that never varies
class IGuidelinesLoader(ABC):
    @abstractmethod
    async def load(self, path: Path) -> str: ...

class FilesystemGuidelinesLoader(IGuidelinesLoader):
    async def load(self, path: Path) -> str:
        async with aiofiles.open(path) as f:
            return await f.read()
```

`GuidelineRepository` already encapsulates the filesystem. No additional abstraction is needed until you need a second implementation.

## Code Smells These Principles Prevent

| Smell | Which principle | Fix |
|---|---|---|
| Copy-pasted validation in 5 routes | DRY | Extract to use case |
| 15-class "framework" for 3 use cases | YAGNI | Delete the framework |
| Service locator / registry | KISS | Direct instantiation |
| `BaseEntity` / `BaseUseCase` with no shared behavior | YAGNI | Delete base class |
| Helper module that became a dumping ground | DRY applied wrong | Split by cohesion |
| Abstract factory for a single concrete class | YAGNI | Use the class directly |

## Quick Checklist

- [ ] No abstraction exists "for the future" — only for current needs
- [ ] `BaseSchema` is the only shared base class (genuine DRY)
- [ ] Tool/route handlers do direct instantiation — no service locator
- [ ] Interfaces exist only where there are (or imminently will be) two implementations
- [ ] "The Rule of Three" was applied before extracting any pattern
