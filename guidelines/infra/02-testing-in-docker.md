---
model: sonnet
effort: high
---

# Testing in Docker — Running Tests from Outside the Container

Use when an agent needs to run the test suite, check CI status locally, or read test output. Covers the Dockerfile `test` stage, `docker-compose.test.yml`, the agent-facing shell commands, and the `test-results/` volume pattern for structured output.

Tests always execute **inside** the container (reproducible environment, correct Python/Node version, correct deps). Agents trigger them from **outside** using `docker compose run --rm` and read results from stdout or the mounted `test-results/` directory.

---

## Dockerfile — Add a `test` Stage

The production image uses `--no-dev`. The test stage inherits from the same base and adds dev dependencies. No duplication.

### Backend (`backend/Dockerfile`)

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./

# ── production ────────────────────────────────────────────────────────────────
FROM base AS production
RUN uv sync --frozen --no-dev
COPY src/ ./src/
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
CMD ["uv", "run", "python", "-m", "src.main"]

# ── test ──────────────────────────────────────────────────────────────────────
FROM base AS test
RUN uv sync --frozen          # includes dev deps (pytest, pytest-asyncio, ruff…)
COPY src/ ./src/
COPY test/ ./test/
# Default command — overridable in docker-compose.test.yml
CMD ["uv", "run", "pytest", "test/", "--tb=short", "-v"]
```

### Frontend (`frontend/Dockerfile`)

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

# ── test ──────────────────────────────────────────────────────────────────────
FROM deps AS test
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
CMD ["npm", "run", "test:ci"]
```

Add the test script to `package.json`:

```json
{
  "scripts": {
    "test":    "vitest",
    "test:ci": "vitest run --reporter=verbose --reporter=junit --outputFile=test-results/results.xml"
  }
}
```

---

## docker-compose.test.yml

**`docker-compose.test.yml`**
```yaml
services:
  backend-test:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: test
    env_file:
      - .env.backend.test
    volumes:
      - ./test-results/backend:/app/test-results
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
      dockerfile: Dockerfile
      target: test
    env_file:
      - .env.frontend.test
    volumes:
      - ./test-results/frontend:/app/test-results
    command: npm run test:ci
```

---

## Agent Commands

Agents run these from outside the container. `--rm` removes the container after exit. The exit code is the test result: `0` = pass, non-zero = failure.

```bash
# Run backend tests — output to stdout + test-results/backend/
docker compose -f docker-compose.test.yml run --rm backend-test

# Run frontend tests — output to stdout + test-results/frontend/
docker compose -f docker-compose.test.yml run --rm frontend-test

# Run both stacks
docker compose -f docker-compose.test.yml run --rm backend-test && \
docker compose -f docker-compose.test.yml run --rm frontend-test

# Capture exit code explicitly (for CI or conditional logic)
docker compose -f docker-compose.test.yml run --rm backend-test
BACKEND_EXIT=$?

# Re-build before running (required after source or dep changes)
docker compose -f docker-compose.test.yml build backend-test && \
docker compose -f docker-compose.test.yml run --rm backend-test
```

---

## Reading Test Output

Output goes to two places simultaneously:

### 1. stdout (immediate, always available)

The agent reads stdout directly from the `docker compose run` command above. This is the fastest path — no file reading needed.

### 2. `test-results/` volume (structured, parseable)

```
test-results/
├── backend/
│   ├── results.xml     ← JUnit XML — one <testcase> per test
│   └── coverage.xml    ← Cobertura coverage report
└── frontend/
    └── results.xml     ← JUnit XML from vitest --reporter=junit
```

After the run, agents read these files directly on the host:

```bash
# Full JUnit XML
cat test-results/backend/results.xml

# Quick failure summary (failures only)
grep -A3 'failure\|error' test-results/backend/results.xml

# Coverage summary
grep -E 'line-rate|branch-rate' test-results/backend/coverage.xml
```

Add `test-results/` to `.gitignore`:

```bash
# .gitignore
test-results/
```

---

## Test Environment Variables

**`.env.backend.test — gitignored; overrides for the test environment`**
```bash
ENVIRONMENT=TEST
DATABASE_URL=sqlite+aiosqlite:///./test.db
JWT_SECRET=test-secret-not-for-production
```

**`.env.backend.test.example — committed template`**
```bash
ENVIRONMENT=TEST
DATABASE_URL=sqlite+aiosqlite:///./test.db
JWT_SECRET=test-secret-not-for-production
```

The test env file is separate from `.env.backend` — the test container must never connect to a real database.

---

## Anti-Patterns

```bash
# ❌ WRONG — running tests on the host; different Python/Node version, wrong deps
cd backend && uv run pytest

# ❌ WRONG — running tests in the production stage; dev deps not installed
docker compose exec backend uv run pytest

# ❌ WRONG — running tests in the production stage via run
docker compose run --rm backend uv run pytest

# ✅ CORRECT — dedicated test stage with dev deps
docker compose -f docker-compose.test.yml run --rm backend-test

# ❌ WRONG — not capturing exit code; CI passes even when tests fail
docker compose -f docker-compose.test.yml run --rm backend-test
# (no exit code check)

# ✅ CORRECT — let the exit code propagate naturally
docker compose -f docker-compose.test.yml run --rm backend-test
echo "Tests exited with: $?"

# ❌ WRONG — no test-results volume; agent must exec into container to read output
# (no volumes: in docker-compose.test.yml)

# ✅ CORRECT — mount test-results so host can read structured output without exec
volumes:
  - ./test-results/backend:/app/test-results
```

---

## Quick Checklist

- [ ] Backend `Dockerfile` has a `test` stage that runs `uv sync --frozen` (with dev deps)
- [ ] Frontend `Dockerfile` has a `test` stage built from the `deps` stage
- [ ] `docker-compose.test.yml` defines `backend-test` and `frontend-test` services with `target: test`
- [ ] Both test services mount `./test-results/<stack>:/app/test-results`
- [ ] pytest writes `--junitxml=/app/test-results/results.xml` and `--cov-report=xml`
- [ ] vitest writes `--reporter=junit --outputFile=test-results/results.xml`
- [ ] `.env.backend.test` and `.env.frontend.test` exist; test DB is not the production DB
- [ ] `test-results/` is in `.gitignore`
- [ ] Agent always uses `docker compose -f docker-compose.test.yml run --rm <service>` — never `exec` into production container
