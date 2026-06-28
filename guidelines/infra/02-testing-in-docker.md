---
model: sonnet
effort: high
---

# Testing in Docker - Running Tests from Outside the Container

Use when an agent needs to run the test suite, check CI status locally, or read test output. Covers dedicated test Dockerfiles, `docker-compose.test.yml`, agent-facing shell commands, and stack-local `backend/test-results/` and `frontend/test-results/` output.

Tests execute inside containers for reproducible Python/Node versions and dependency sets. Agents trigger them from outside using `docker compose run --rm` and read results from stdout or mounted stack-local result files.

---

## Dockerfiles

Production and test images are separate files. The production Dockerfile uses production dependencies only. Test Dockerfiles install dev dependencies and copy tests. Do not add a test stage to the production Dockerfile.

### Backend Production: `backend/Dockerfile`

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

### Backend Tests: `backend/Dockerfile.test`

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

### Frontend Tests

Use the same split when frontend production and test needs diverge:

- `frontend/Dockerfile` builds the production runner image.
- `frontend/Dockerfile.test` installs test tooling and runs unit/component tests.

If a project deliberately keeps a frontend multi-stage Dockerfile, that exception must be documented in the repo. The backend rule is stricter: backend production and test Dockerfiles are always separate.

---

## docker-compose.test.yml

```yaml
services:
  backend-test:
    build:
      context: ./backend
      dockerfile: Dockerfile.test
    env_file:
      - ./backend/.env.test
    volumes:
      - ./backend/test-results:/app/test-results
    command: >
      uv run pytest test/
        --tb=short
        -v
        --junitxml=/app/test-results/results.xml
        --cov=src
        --cov-report=xml:/app/test-results/coverage.xml
        --cov-report=term-missing

  frontend-test:
    build:
      context: ./frontend
      dockerfile: Dockerfile.test
    env_file:
      - ./frontend/.env.test
    volumes:
      - ./frontend/test-results:/app/test-results
    command: npm run test:ci
```

---

## Agent Commands

Agents run these from outside the container. `--rm` removes the container after exit. The exit code is the test result: `0` means pass, non-zero means failure.

```bash
# Run backend tests
docker compose -f docker-compose.test.yml run --rm backend-test

# Run frontend tests
docker compose -f docker-compose.test.yml run --rm frontend-test

# Rebuild before running after Dockerfile or dependency changes
docker compose -f docker-compose.test.yml build backend-test
docker compose -f docker-compose.test.yml run --rm backend-test
```

---

## Reading Test Output

Output goes to two places:

1. stdout, which the agent reads directly from `docker compose run`.
2. Stack-local `test-results/`, mounted from the host for structured JUnit and coverage reports.

```
backend/
  test-results/
    results.xml
    coverage.xml
frontend/
  test-results/
    results.xml
```

After the run, agents read these files directly on the host:

```bash
cat backend/test-results/results.xml
grep -A3 'failure\|error' backend/test-results/results.xml
grep -E 'line-rate|branch-rate' backend/test-results/coverage.xml
```

Add `backend/test-results/` and `frontend/test-results/` to `.gitignore`.

---

## Test Environment Variables

**`backend/.env.test` - gitignored; overrides for the backend test environment**

```bash
ENVIRONMENT=TEST
DATABASE_URL=sqlite+aiosqlite:///./test.db
JWT_SECRET=test-secret-not-for-production
```

**`backend/.env.test.example` - committed template**

```bash
ENVIRONMENT=TEST
DATABASE_URL=sqlite+aiosqlite:///./test.db
JWT_SECRET=test-secret-not-for-production
```

The test env file is separate from `backend/.env`; the test container must never connect to a real database.

---

## Anti-Patterns

```bash
# WRONG - running tests on the host; version and deps can drift
cd backend && uv run pytest

# WRONG - running tests in the production service
docker compose exec backend uv run pytest
docker compose run --rm backend uv run pytest

# WRONG - backend test stage inside backend/Dockerfile
docker build --target test ./backend

# CORRECT - dedicated backend test Dockerfile
docker compose -f docker-compose.test.yml run --rm backend-test
```

```yaml
# WRONG - test service targets a stage inside the production Dockerfile
services:
  backend-test:
    build:
      context: ./backend
      dockerfile: Dockerfile
      # Do not target a test stage in the production Dockerfile.

# CORRECT - test service uses the separate test Dockerfile
services:
  backend-test:
    build:
      context: ./backend
      dockerfile: Dockerfile.test
```

---

## Quick Checklist

- [ ] Backend `Dockerfile` is production-only and has no `test` stage
- [ ] Backend `Dockerfile.test` runs `uv sync --frozen` with dev deps
- [ ] Backend test image copies `test/`; production image does not
- [ ] `docker-compose.test.yml` defines `backend-test` with `dockerfile: Dockerfile.test`
- [ ] `docker-compose.test.yml` mounts `./backend/test-results:/app/test-results`
- [ ] pytest writes `--junitxml=/app/test-results/results.xml` and `--cov-report=xml`
- [ ] Frontend test image strategy is explicit; prefer `frontend/Dockerfile.test` when test deps differ from production
- [ ] `backend/.env.test` and `frontend/.env.test` exist and do not point at production systems
- [ ] `backend/test-results/` and `frontend/test-results/` are in `.gitignore`
- [ ] Agents use `docker compose -f docker-compose.test.yml run --rm <service>` and never exec into the production container for tests
