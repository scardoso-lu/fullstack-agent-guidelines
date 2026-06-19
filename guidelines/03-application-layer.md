# Application Layer: Use Cases and DTOs

The application layer orchestrates the domain and infrastructure layers to fulfill a single business operation. It is the home of business logic — not the routes, not the repositories.

## One Use Case = One File = One Operation

Every use case is a class with a single `execute()` method. It lives in its own file:

```
src/application/use_cases/
└── note/
    ├── create.py        ← CreateNoteUseCase
    ├── get_by_id.py     ← GetNoteByIdUseCase
    ├── list_all.py      ← ListNotesUseCase
    ├── update.py        ← UpdateNoteUseCase
    └── delete.py        ← DeleteNoteUseCase
```

This is the **Single Responsibility Principle** in practice. Each class changes for one reason only.

## Use Case Structure

```python
# src/application/use_cases/note/create.py
from src.application.dto.note_dto import CreateNoteDto, NoteDto
from src.domain.entities.note import Note
from src.infrastructure.repositories.contract import NoteRepositoryInterface

class CreateNoteUseCase:
    def __init__(self, note_repository: NoteRepositoryInterface) -> None:
        self.note_repository = note_repository  # depends on interface, not concrete class

    async def execute(self, dto: CreateNoteDto) -> NoteDto:
        if not dto.title.strip():
            raise ValueError("Title cannot be empty")   # business rule validation
        note = Note(title=dto.title.strip(), content=dto.content)
        saved = await self.note_repository.create(note)
        return NoteDto.model_validate(saved)             # return DTO, not entity
```

Three rules every use case must follow:
1. **Constructor injection** — receive repository interface in `__init__`, never import the concrete class
2. **Return DTOs** — never return raw SQLAlchemy entities to the presentation layer
3. **Validate business rules** — `raise ValueError` or a domain error for invalid input; never raise `HTTPException`

## DTOs (Data Transfer Objects)

DTOs are Pydantic models that define the shape of data crossing layer boundaries.

```python
# src/application/dto/__init__.py
from pydantic import BaseModel, ConfigDict

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,      # allows model_validate(orm_object)
        arbitrary_types_allowed=True,
    )
```

All DTOs extend `BaseSchema`. The `from_attributes=True` config enables:

```python
saved_note = await repo.create(note)  # returns SQLAlchemy Note entity
return NoteDto.model_validate(saved_note)  # ← this works because from_attributes=True
```

### Input vs Output DTOs

```python
# src/application/dto/note_dto.py
class CreateNoteDto(BaseSchema):  # ← input: what the caller provides
    title: str
    content: str = ""

class NoteDto(BaseSchema):        # ← output: what the caller receives
    id: str
    title: str
    content: str
    created_at: datetime | None = None
```

Keep input and output DTOs separate — they evolve independently and have different validation needs.

### Authentication DTOs (from mdip-backend)

```python
# src/application/dto/auth_dto.py
class AuthDto(BaseSchema):
    username: EmailStr = Field(examples=["johndoe@example.com"])
    password: str = Field(examples=["mysecretpassword"])

class AuthSuccessDto(BaseSchema):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
```

`Field(examples=[...])` improves auto-generated API documentation without cluttering the model.

## Retrieving the Current User (Cross-Cutting Concern)

Some use cases need the currently authenticated user. In mdip-backend this is solved with a domain service that acts as a dependency:

```python
# src/domain/services/auth_service.py
async def manager(security_scopes, token, session):
    user_repository = IUserRepository(session)
    access_token_service = IAccessTokenService(get_config().JWT_SECRET)
    api_auth = ApiAuthorizationUseCase(user_repository, access_token_service)
    return await api_auth.execute(token, security_scopes)
```

The `manager` function is a FastAPI dependency that runs `ApiAuthorizationUseCase` and returns the authenticated `User` entity. Route handlers declare it with `Depends(manager)`.

## Anti-Pattern: Fat Use Case

```python
# ❌ WRONG — one class doing everything for "notes"
class NoteService:
    async def create(self, title, content): ...
    async def get(self, note_id): ...
    async def list(self, page, size): ...
    async def update(self, note_id, title, content): ...
    async def delete(self, note_id): ...
    async def export_to_pdf(self, note_id): ...      # unrelated concern
    async def send_email_notification(self, ...): ... # really unrelated concern
```

This class has six reasons to change. When `send_email_notification` needs a new parameter, you risk breaking `create`. Split into separate use case files.

## Anti-Pattern: Logic in DTOs

```python
# ❌ WRONG — business logic in a DTO
class CreateNoteDto(BaseSchema):
    title: str

    @validator("title")
    def title_must_be_meaningful(cls, v):
        if len(v.split()) < 3:
            raise ValueError("Title must have at least 3 words")  # business rule!
        return v
```

Pydantic validators enforce *type* and *format*. Business rules belong in use cases where they can be unit-tested independently and expressed as domain errors.

## Quick Checklist

- [ ] Every use case is a class with only `__init__(self, repo)` and `async execute(...)`
- [ ] Use cases import the repository **interface** from `contract.py`, not the concrete class
- [ ] Use cases return DTOs, never SQLAlchemy entities
- [ ] Input validation (business rules) is in `execute()`, not in the DTO validator
- [ ] `HTTPException` never appears in the application layer
- [ ] DTOs extend `BaseSchema` for consistent config
