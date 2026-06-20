# Python Project Setup — Docker + uv

Use when creating the backend Dockerfile, initialising a new Python service, or switching from pip/poetry to uv. Covers Python 3.13, uv installation from the official image, lockfile-first install, non-root user, and .env convention.

---

## Why uv

uv replaces pip, virtualenv, and poetry in a single binary. `uv sync --frozen` is the Python equivalent of `npm ci` — it installs exactly what the lockfile says or fails. It is 10–100× faster than pip and produces a content-addressed `uv.lock` that must be committed to git.

---

## Dockerfile

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

# Install uv from the official image — no pip, no curl, no apt dependency
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy lockfile and manifest first — Docker layer cache only rebuilds
# the install layer when dependencies actually change
COPY pyproject.toml uv.lock ./

# Install production dependencies exactly from the lockfile — never resolves
RUN uv sync --frozen --no-dev

# Copy source after dependencies — preserves cache on code-only changes
COPY src/ ./src/

# Non-root user — process must not run as root in production
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uv", "run", "python", "-m", "src.main"]
```

---

## uv Commands

```bash
# New project — creates pyproject.toml and uv.lock
uv init my-service

# Add a production dependency (pinned exactly in pyproject.toml + uv.lock)
uv add fastapi

# Add a dev-only dependency
uv add --dev pytest pytest-asyncio ruff

# Install exactly what the lockfile says (use in CI and Dockerfile)
uv sync --frozen

# Install without dev tools (use in production Dockerfile)
uv sync --frozen --no-dev

# Run a command inside the uv environment without activating it
uv run python -m src.main
uv run pytest
uv run task run    # taskipy task defined in pyproject.toml
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

[tool.uv]
dev-dependencies = [
    "pytest==8.4.2",
    "pytest-asyncio==0.26.0",
    "ruff==0.9.0",
    "taskipy==1.14.1",
]

[tool.taskipy.tasks]
run   = "uvicorn src.main:app --reload"
test  = "pytest test/"
lint  = "ruff check src/"
```

All version pins are exact — no `^` or `~`. Run `uv add package==x.y.z` to add, `uv lock --upgrade-package package` to upgrade.

---

## Lockfile Rules

```bash
# ✅ Always commit uv.lock — it is the reproducibility contract
git add uv.lock

# ❌ Never gitignore it
# uv.lock   ← never add this line to .gitignore

# ✅ On CI — fails fast if lockfile is stale
uv sync --frozen

# ✅ On developer machine — updates lockfile; commit the diff
uv sync
```

---

## Environment Variables

```bash
# .env.backend — real secrets; gitignored
ENVIRONMENT=DEV
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/mydb
JWT_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
```

```bash
# .env.backend.example — committed template; no real values
ENVIRONMENT=DEV
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/mydb
JWT_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
```

Pydantic Settings loads from the env file via `env_file = ".env.backend"` in `BaseEnvs`. See the infrastructure layer guideline for the Settings class pattern.

---

## Anti-Patterns

```dockerfile
# ❌ WRONG — pip without a lockfile; resolves "latest" on every build
RUN pip install fastapi

# ❌ WRONG — poetry install without --no-root can pull dev deps into production
RUN poetry install

# ❌ WRONG — COPY . . before uv sync; invalidates dependency cache on any file change
COPY . .
RUN uv sync --frozen --no-dev

# ✅ CORRECT — lockfile first, source second
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src/ ./src/

# ❌ WRONG — running as root in production (no USER instruction)
CMD ["uv", "run", "python", "-m", "src.main"]

# ✅ CORRECT — non-root user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser
CMD ["uv", "run", "python", "-m", "src.main"]
```

---

## Quick Checklist

- [ ] `uv.lock` committed to git — never in `.gitignore`
- [ ] Dockerfile copies `pyproject.toml uv.lock` before `src/` — layer cache correct
- [ ] `uv sync --frozen --no-dev` in production Dockerfile — exact versions, no dev tools
- [ ] Non-root `USER appuser` set before `CMD`
- [ ] `.env.backend` in `.gitignore`; `.env.backend.example` committed with placeholder values
- [ ] All version pins in `pyproject.toml` are exact — no `^` or `~`
