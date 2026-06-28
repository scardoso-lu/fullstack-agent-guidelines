---
model: sonnet
effort: extract
---

# Makefile as the Gate — One Command Surface for Dev and CI

Use when setting up a new repo's command surface, when the team's local commands have drifted from CI, or when an engineer asks "what's the command to run the gate locally?". Defines the **Makefile-as-portable-surface** pattern: every common operation gets a target, CI runs the same targets, and the Definition of Done gate (lint + format + type-check + tests + coverage) is reproducible with `make gate`.

A team without a single source of truth for "how do you run X?" answers it differently in three places: in the README, in CI, and in chat. They drift; CI green on something that's red locally (or vice versa) becomes a recurring debugging dead-end. A Makefile pins it.

## The rule

> Every common dev operation is a Makefile target.
> CI runs **the same Makefile targets** — not a parallel set of commands buried in YAML.
> The **DoD gate** (`make gate`) reproduces every check CI runs before merge.

If the same command is typed in two places, one of them is going to drift. The Makefile is the *only* place.

## Why Make, specifically

- **Universal** — installed on every developer machine without language-specific tooling.
- **Self-documenting** — `make help` lists every target.
- **Composable** — `make gate` calls `make lint`, `make typecheck`, `make test` in order, each of which works standalone.
- **Stack-agnostic** — wraps `uv`, `pnpm`, `docker compose`, anything else. The Makefile recipe calls the **raw tools** so CI and contributors without exotic dev tooling can run them.

If your team genuinely prefers `just` or `task`, the principle is identical — pick one, make it canonical, and call it from CI.

## A skeleton — backend + frontend monorepo

**`Makefile — single command surface for the project`**
```makefile
# Every recipe calls raw tools so CI and contributors run the same commands.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------- help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- install

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Install backend dependencies (uv sync)
	cd backend && uv sync

install-frontend: ## Install frontend dependencies (pnpm install)
	cd frontend && pnpm install --frozen-lockfile

# ---------------------------------------------------------------- services

up: ## Start dev services (db, broker, etc.)
	docker compose -f docker-compose.dev.yml up -d

down: ## Stop dev services
	docker compose -f docker-compose.dev.yml down

logs: ## Tail dev service logs
	docker compose -f docker-compose.dev.yml logs -f

# ---------------------------------------------------------------- run

dev-api: ## Run the API in dev mode
	cd backend && uv run uvicorn src.api_main:app --reload

dev-worker: ## Run the task worker in dev mode
	cd backend && uv run taskiq worker src.worker:broker --reload

dev-web: ## Run the Next.js dev server
	cd frontend && pnpm dev

# ---------------------------------------------------------------- migrations

migrate: ## Apply pending migrations
	cd backend && uv run alembic upgrade head

migration: ## Generate a new migration (usage: make migration name="<slug>")
	cd backend && uv run alembic revision --autogenerate -m "$(name)"

# ---------------------------------------------------------------- gate (DoD)

gate: gate-backend gate-frontend ## Run the full Definition of Done gate

gate-backend: lint-backend format-check-backend typecheck-backend test-backend ## Backend gate

gate-frontend: lint-frontend format-check-frontend typecheck-frontend test-frontend e2e-frontend ## Frontend gate

# ---- individual steps

lint-backend:
	cd backend && uv run ruff check src tests

format-check-backend:
	cd backend && uv run ruff format --check src tests

typecheck-backend:
	cd backend && uv run mypy --strict src

test-backend:
	docker compose -f docker-compose.test.yml run --rm backend-test

lint-frontend:
	cd frontend && pnpm lint

format-check-frontend:
	cd frontend && pnpm format:check

typecheck-frontend:
	cd frontend && pnpm typecheck

test-frontend:
	docker compose -f docker-compose.test.yml run --rm frontend-test

e2e-frontend:
	cd frontend && pnpm exec playwright test

# ---------------------------------------------------------------- format

format: ## Apply all formatters (writes changes)
	cd backend && uv run ruff format src tests
	cd backend && uv run ruff check --fix src tests
	cd frontend && pnpm format

# ---------------------------------------------------------------- security

security: ## Run dependency + image + secret scans
	cd backend && uv run pip-audit
	cd frontend && pnpm audit --audit-level=high
	@command -v trivy >/dev/null && trivy fs --severity HIGH,CRITICAL . || echo "trivy not installed; skipping"
	@command -v gitleaks >/dev/null && gitleaks detect --source=. || echo "gitleaks not installed; skipping"

.PHONY: help install install-backend install-frontend up down logs \
        dev-api dev-worker dev-web migrate migration \
        gate gate-backend gate-frontend \
        lint-backend format-check-backend typecheck-backend test-backend \
        lint-frontend format-check-frontend typecheck-frontend test-frontend e2e-frontend \
        format security
```

## CI calls the targets

Instead of duplicating the commands in CI YAML, CI calls `make`:

**`.github/workflows/ci.yml`**
```yaml
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: pnpm/action-setup@v3
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm, cache-dependency-path: frontend/pnpm-lock.yaml }
      - uses: actions/setup-python@v5
        with: { python-version-file: backend/.python-version }

      - run: make install
      - run: make up                  # start any dev services CI needs
      - run: make migrate
      - run: make gate                # same command developers run locally
      - run: make security            # advisory; failures non-blocking unless project says otherwise
```

A failing CI is reproducible with **one local command** (`make gate`). If a check is added in CI but not in the Makefile, it's a CI bug to fix.

## Targets are short and composable

A target should be one logical operation, callable on its own:

- `make lint-backend` — runs lint only.
- `make test-backend` — runs tests only.
- `make gate-backend` — runs all backend checks (composed of the individual targets).
- `make gate` — runs everything (composed of `gate-backend` + `gate-frontend`).

This composition is what makes the Makefile usable both for "I just want to lint" and for "I need to run the full gate before I push."

## `help` is mandatory

Every Makefile gets a self-documenting `help` target. New engineers' first command in the repo is `make help`; if it doesn't list everything they need, the Makefile is broken.

## Naming conventions

- **Verb-noun, kebab-case.** `lint-backend`, not `BackendLint` or `backend_lint`.
- **Common verbs:** `install`, `up`, `down`, `dev-<thing>`, `lint`, `format`, `format-check`, `typecheck`, `test`, `e2e`, `gate`, `migrate`, `migration`, `security`.
- **Per-stack suffixes** (`-backend`, `-frontend`) when both stacks have the same verb.

Consistency across projects matters more than personal preference — an engineer joining a new repo should already know the verbs.

## What the Makefile is NOT

- **Not a build system.** Use the language's native build (`uv`, `pnpm`, etc.) underneath; Make just wraps it.
- **Not the only entry point.** A developer can still call `pnpm test` directly. The Makefile is the **canonical** way; it's not the only legal way.
- **Not a substitute for documentation.** `make help` covers commands; the README covers concepts.

## Keeping it in sync

The Makefile drifts when a new gate check is added to CI without a target. The rule that prevents this:

> **CI MUST call `make <target>`. CI MUST NOT call raw `pnpm` / `uv` / `pytest`.**

A code review of the CI workflow rejects any direct command — it gets turned into a Make target first. That's how the Makefile stays as complete as CI.

## Windows note

`make` works on Windows via WSL, Git Bash, or `make` for Windows. If your team is mixed-OS:

- Pin the shell at the top of the Makefile (`SHELL := /bin/bash`) — Windows users run from a bash shell.
- Or provide an equivalent `Taskfile.yml` / `justfile` with the same targets if `make` is genuinely off-limits.

Either way, **one canonical surface per project** — never two parallel ones that can drift.

## A two-sentence summary

> *Every command is a Makefile target; CI calls the same targets.*
>
> *`make gate` reproduces the Definition of Done — locally and in CI, byte for byte.*
