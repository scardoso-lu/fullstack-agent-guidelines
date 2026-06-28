---
model: sonnet
effort: extract
---

# Python Project Setup - Docker + uv

Use when creating the backend production Dockerfile, initializing a Python service, or switching from pip/poetry to uv. Covers Python 3.13, uv installation from the official image, lockfile-first installs, non-root production images, separate test images, and the backend env convention.

---

## Why uv

uv replaces pip, virtualenv, and poetry in a single binary. `uv sync --frozen` is the Python equivalent of `npm ci`: it installs exactly what the lockfile says or fails. It is fast, reproducible, and produces a content-addressed `uv.lock` that must be committed to git.

---

## Dockerfiles

Production and test images use separate files:

- `backend/Dockerfile` is production-only. It installs with `uv sync --frozen --no-dev`, copies only runtime code, and runs as a non-root user.
- `backend/Dockerfile.test` is for pytest, linters, type-checkers, and local/CI validation. It installs dev dependencies and copies tests.

Do not put a `test` stage inside `backend/Dockerfile`. Production and test concerns must be split at the file boundary, not hidden behind Docker build targets.

### `backend/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY src/ ./src/

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uv", "run", "python", "-m", "src.main"]
```

### `backend/Dockerfile.test`

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

COPY src/ ./src/
COPY test/ ./test/

CMD ["uv", "run", "pytest", "test/", "--tb=short", "-v"]
```

---

## uv Commands

```bash
# New project
uv init my-service

# Add a production dependency pinned in pyproject.toml and uv.lock
uv add fastapi

# Add dev-only dependencies
uv add --dev pytest pytest-asyncio ruff

# CI and Dockerfile install
uv sync --frozen

# Production Dockerfile install
uv sync --frozen --no-dev

# Run inside the uv environment
uv run python -m src.main
uv run pytest
```

---

## pyproject.toml

```toml
[project]
name = "my-service"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi==0.115.0",
    "uvicorn==0.32.0",
    "pydantic==2.10.0",
    "pydantic-settings==2.7.0",
]

[dependency-groups]
dev = [
    "pytest==8.4.2",
    "pytest-asyncio==0.26.0",
    "ruff==0.9.0",
]

[tool.pytest.ini_options]
testpaths = ["test"]
asyncio_mode = "auto"
```

All version pins are exact: no `^` or `~`. Run `uv add package==x.y.z` to add and `uv lock --upgrade-package package` to upgrade.

---

## Lockfile Rules

```bash
# Always commit uv.lock; it is the reproducibility contract
cd backend
git add pyproject.toml uv.lock

# CI fails fast if lockfile is stale
uv sync --frozen

# Developer machine updates lockfile; commit the diff
uv sync
```

Never add `uv.lock` to `.gitignore`.

---

## Environment Variables

**`backend/.env` - real secrets; gitignored**

```bash
ENVIRONMENT=DEV
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/mydb
JWT_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
```

**`backend/.env.example` - committed template; no real values**

```bash
ENVIRONMENT=DEV
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/mydb
JWT_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
```

Pydantic Settings loads from the env file via `env_file = ".env"` when the app runs with `backend/` as its working directory. See the infrastructure layer guideline for the Settings pattern.

---

## Anti-Patterns

```dockerfile
# WRONG - pip without a lockfile resolves latest on every build
RUN pip install fastapi

# WRONG - COPY . . before uv sync invalidates dependency cache on any source change
COPY . .
RUN uv sync --frozen --no-dev

# CORRECT - lockfile first, source second
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src/ ./src/

# WRONG - running production as root
CMD ["uv", "run", "python", "-m", "src.main"]

# CORRECT - non-root production user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser
CMD ["uv", "run", "python", "-m", "src.main"]

# WRONG - production image ships dev deps and test files
FROM python:3.13-slim
RUN uv sync --frozen
COPY test/ ./test/

# WRONG - production and test stages live in the same Dockerfile
# Do not define both production and test build targets in backend/Dockerfile.

# CORRECT - split production and test into separate files
# backend/Dockerfile      -> uv sync --frozen --no-dev
# backend/Dockerfile.test -> uv sync --frozen and COPY test/
```

---

## Quick Checklist

- [ ] `uv.lock` committed to git, never in `.gitignore`
- [ ] `backend/Dockerfile` is production-only; no `test` stage, no dev deps, no copied `test/`
- [ ] `backend/Dockerfile` copies `pyproject.toml uv.lock` before `src/`
- [ ] `backend/Dockerfile` uses `uv sync --frozen --no-dev`
- [ ] `backend/Dockerfile.test` exists for tests and dev validation
- [ ] `backend/Dockerfile.test` uses `uv sync --frozen`
- [ ] Non-root `USER appuser` is set before production `CMD`
- [ ] `backend/.env` is in `.gitignore`
- [ ] `backend/.env.example` is committed with placeholder values
- [ ] All version pins in `pyproject.toml` are exact
