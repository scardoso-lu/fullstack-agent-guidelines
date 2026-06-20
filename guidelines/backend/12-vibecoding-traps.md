# Vibecoding Traps: What Not to Ask AI to Do Blindly

Use before accepting AI-generated code. Lists eight common AI mistakes — fat routes, missing interfaces, god use cases, swallowed errors, hardcoded secrets — with the corrective prompt template for each.

Vibecoding — describing what you want to an AI and accepting the output — is fast for prototypes but dangerous for production. AI models optimize for "code that runs" not "code that scales." Here are the most common traps.

## Trap 1: "Create a [feature] endpoint"

When you say "create a user registration endpoint," AI generates:

```python
# ❌ What AI generates (everything in one route)
@app.post("/register")
async def register(name: str, email: str, password: str, db: Session = Depends()):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, "Email already registered")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    user = User(name=name, email=email, password=hashed)
    db.add(user)
    db.commit()
    token = jwt.encode({"sub": email, "exp": ...}, SECRET_KEY)
    send_welcome_email(email, name)  # blocks the event loop
    return {"token": token}
```

This has five responsibilities, no tests, a synchronous email call, and hardcoded `SECRET_KEY`. The fix is to tell the AI exactly where logic belongs:

**Better prompt:** "Create a `RegisterUserUseCase` class in `src/application/use_cases/user/register.py` that takes a `UserRepositoryInterface` in `__init__` and has an `async execute(dto: RegisterUserDto) -> UserDto` method. It should validate the email is unique, create a `User` entity, and return a `UserDto`. Do NOT handle tokens or email — that's a separate use case."

## Trap 2: Skipping the Interface

AI will almost always generate:

```python
# ❌ Use case with hardcoded dependency
from src.infrastructure.repositories.note_repository import NoteRepository

class CreateNoteUseCase:
    def __init__(self):
        self.repo = NoteRepository()  # can't test without a DB
```

Always specify in your prompt: "The use case constructor receives a `NoteRepositoryInterface` (from `contract.py`), not a concrete `NoteRepository`."

## Trap 3: The God Use Case

Asking "write a checkout use case" produces one class with 200 lines:

```python
# ❌ God use case
class CheckoutUseCase:
    async def execute(self, cart_id, user_id, payment_info):
        cart = await self.cart_repo.get(cart_id)
        # validate inventory...
        # calculate total with taxes...
        # charge payment method...
        # create order record...
        # send confirmation email...
        # update loyalty points...
        # trigger fulfillment...
```

This is seven use cases jammed into one. Each action is a separate operation:
- `ValidateCartUseCase`
- `CreateOrderUseCase`
- `ChargePaymentUseCase`
- etc.

## Trap 4: "Make it production-ready"

This prompt causes AI to add unnecessary complexity:

```python
# ❌ AI-generated "production-ready" bloat
class RepositoryFactory:
    _instances: ClassVar[dict] = {}

    @classmethod
    def get_instance(cls, repo_type: type, *args):
        key = (repo_type, args)
        if key not in cls._instances:
            cls._instances[key] = repo_type(*args)
        return cls._instances[key]
```

You didn't need a factory. Direct instantiation in the tool handler was already correct.

## Trap 5: Missing Error Propagation

AI rarely propagates typed errors through the layers:

```python
# ❌ AI-generated use case swallows errors
class GetNoteUseCase:
    async def execute(self, note_id: int):
        note = await self.repo.get_by_id(note_id)
        if note is None:
            return None  # silent None — caller doesn't know why
```

```python
# ✅ Correct — typed error that callers can handle specifically
class GetNoteUseCase:
    async def execute(self, note_id: int) -> NoteDto:
        note = await self.repo.get_by_id(note_id)
        if note is None:
            raise NotFoundError(f"Note {note_id} not found")
        return NoteDto.model_validate(note)
```

Add to your prompts: "Raise `NotFoundError` from `utils/exc.py` if not found. Never return `None` from use cases."

## Trap 6: AI-Generated Tests Test Implementation, Not Behavior

```python
# ❌ Testing how the code works (fragile, breaks on refactoring)
async def test_create_note():
    mock_repo = MagicMock()
    use_case = CreateNoteUseCase(mock_repo)
    await use_case.execute(CreateNoteDto(title="Hello"))
    mock_repo.create.assert_called_once()  # ← tests that create() was called
    mock_repo.session.add.assert_called()  # ← tests SQLAlchemy internals!
```

```python
# ✅ Testing what the system does (durable)
async def test_create_note_returns_dto_with_correct_title():
    mock_repo = AsyncMock()
    mock_repo.create.return_value = Note._mock()
    result = await CreateNoteUseCase(mock_repo).execute(CreateNoteDto(title="Hello"))
    assert result.title == "Test Note 1"  # ← tests observable behavior
```

## Trap 7: Hardcoded Paths and Values

```python
# ❌ AI-generated hardcoded path
GUIDELINES_DIR = "/home/user/project/guidelines"  # breaks on every other machine

# ✅ Correct — relative to project root via settings
GUIDELINES_DIR: str = str(Path(__file__).resolve().parents[3] / "guidelines")
```

## Trap 8: Not Separating Input Validation from Business Rules

```python
# ❌ AI mixes Pydantic validation with business rules
class CreateNoteDto(BaseModel):
    title: str

    @validator("title")
    def title_must_be_unique_in_db(cls, v, values):
        # THIS REQUIRES A DATABASE QUERY — in a validator!
        if note_exists(v):
            raise ValueError("Title taken")
        return v
```

Pydantic validators run during model construction — before you have a session or repository. Business rules go in use cases.

## Checklist: Before Accepting AI-Generated Code

Ask these questions before committing:

1. **Layer boundaries** — Does each import respect the inward dependency rule?
2. **Interfaces** — Does the use case import from `contract.py`, not a concrete repo?
3. **Errors** — Does every "not found" or "invalid" path raise a typed domain error?
4. **Secrets** — Are there any hardcoded strings that should be in `.env`?
5. **Tests** — Are there unit tests using `AsyncMock`, not a real database?
6. **Async I/O** — Is `aiofiles` used for filesystem reads? `asyncpg` for PostgreSQL?
7. **Responsibilities** — Does each function/class have exactly one reason to change?

## How to Prompt AI for Better Architecture

| Instead of... | Say... |
|---|---|
| "Write a CRUD API for notes" | "Write `CreateNoteUseCase` in `src/application/use_cases/note/create.py` that takes `NoteRepositoryInterface` and returns `NoteDto`" |
| "Make it production-ready" | "Add `NotFoundError` propagation and input validation; no other changes" |
| "Add tests" | "Write `test_create.py` using `AsyncMock` for the repository and `Note._mock()` for test entities; follow Arrange/Act/Assert" |
| "Refactor this" | "Extract the validation logic from the route handler into a use case; preserve behavior" |

The more specific and layer-aware your prompt, the more useful the output.

## Quick Checklist

- [ ] AI output was reviewed against the layer diagram before committing
- [ ] No concrete class imported in a use case (only interfaces from `contract.py`)
- [ ] Every possible error path raises a named domain exception
- [ ] No hardcoded secrets, paths, or configuration values
- [ ] Tests use `AsyncMock` and `_mock()` — not real infrastructure
- [ ] The prompt specified the exact file name and class signature before asking AI to generate
