# Project Structure and Layer Conventions

Understanding how to organize a backend project is the first step to writing maintainable code. Without structure, codebases become tangled webs where changing one thing breaks three others.

## Overview of the Four Layers

Every module in the project belongs to exactly one layer. Each layer has a single responsibility and strict import rules.

```
src/
├── domain/          ← Core business objects. Zero external dependencies.
├── application/     ← Orchestrates domain + infrastructure. No HTTP, no SQL.
├── infrastructure/  ← Implements interfaces. Knows about DBs, filesystems, APIs.
└── presentation/    ← Thin protocol layer. Translates HTTP/MCP ↔ application DTOs.
```

The dependency rule is **inward only**:

```
presentation → application → domain
infrastructure → domain (implements domain interfaces)
```

Nothing in `domain/` imports from any other layer. Nothing in `application/` imports from `presentation/`. Infrastructure can only be named in the presentation layer when wiring up dependencies.

## Standard Directory Tree

```
src/
├── __init__.py
├── mcp_main.py                  ← Server factory (entry point)
├── config/
│   ├── constants.py             ← Static string constants (class C)
│   └── settings/
│       ├── base.py              ← BaseEnvs class (plain class, no pydantic)
│       └── __init__.py          ← Settings (pydantic-settings) + get_config()
├── domain/
│   ├── entities/                ← SQLAlchemy models or frozen dataclasses
│   ├── services/                ← Pure domain logic spanning multiple entities
│   └── value_objects/           ← Immutable types with structural equality
├── application/
│   ├── dto/                     ← Pydantic models for input/output
│   └── use_cases/
│       └── <domain>/            ← One subdirectory per aggregate
│           └── <action>.py      ← One file, one use case class
├── infrastructure/
│   ├── db/                      ← Engine, session, base (when using a DB)
│   ├── repositories/
│   │   ├── contract.py          ← Abstract interfaces (the only thing use cases import)
│   │   └── <entity>_repository.py  ← Concrete SQLAlchemy / filesystem implementation
│   └── services/                ← External APIs, token services, blob storage
├── presentation/
│   ├── view.py                  ← Registers all tools/routes into the server
│   ├── tools/                   ← MCP tool handlers (one file per domain)
│   └── resources/               ← MCP resource handlers
└── utils/
    └── exc.py                   ← Typed domain exceptions
```

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Python files | `snake_case.py` | `note_repository.py` |
| Classes | `PascalCase` | `CreateNoteUseCase` |
| Use case files | `<verb>.py` or `<verb>_<noun>.py` | `create.py`, `get_by_id.py` |
| DTO files | `<domain>_dto.py` | `guideline_dto.py` |
| Repository files | `<entity>_repository.py` | `guideline_repository.py` |
| Interface file | `contract.py` | always `contract.py` |
| Constants class | `C` | `C.TITLE`, `C.URL_PREFIX` |

## File Placement Decision Guide

| You have... | It belongs in... |
|---|---|
| SQLAlchemy model | `domain/entities/` |
| Pydantic input/output model | `application/dto/` |
| Business rule (validate, compute) | `application/use_cases/<domain>/` |
| Abstract repository interface | `infrastructure/repositories/contract.py` |
| SQLAlchemy implementation | `infrastructure/repositories/<entity>_repository.py` |
| JWT / bcrypt / API call | `infrastructure/services/` |
| HTTP route / MCP tool | `presentation/tools/` or `presentation/routes/` |
| Custom exception | `utils/exc.py` |
| App-wide strings | `config/constants.py` |
| Environment config | `config/settings/` |

## Anti-Pattern: The God Module

```python
# ❌ WRONG — everything in one file
# src/app.py
from fastapi import FastAPI
import sqlalchemy
import bcrypt
import jwt

app = FastAPI()
engine = create_engine(DATABASE_URL)

@app.post("/users")
def create_user(name: str, email: str, password: str):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    # ... SQL directly in route handler
    token = jwt.encode({"sub": email}, SECRET)
    return {"token": token}
```

This is the first thing AI will generate if you don't constrain it. One file contains routing, hashing, SQL, and token logic — they all change for different reasons, all break together, and none can be tested in isolation.

## Quick Checklist

- [ ] Every `.py` file lives in exactly one layer directory
- [ ] No `src/infrastructure/` import appears in `src/application/`
- [ ] No `src/presentation/` import appears in `src/application/`
- [ ] Use cases are one-per-file with a single `execute()` method
- [ ] Routes/tools contain no business logic (max ~10 lines)
