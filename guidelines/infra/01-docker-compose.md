---
model: sonnet
effort: extract
---

# Docker Compose — Full-Stack Project Setup

Use when running both stacks together locally or in production, setting up per-stack environment files, or configuring service dependencies and health checks. Covers the two-service compose layout, `env_file` per stack, internal networking by service name, health checks, and the dev override pattern.

---

## Project Layout

```
my-project/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   └── src/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   ├── .npmrc
│   └── src/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.backend           ← gitignored — real secrets
├── .env.backend.example   ← committed — template with placeholder values
├── .env.frontend          ← gitignored — real secrets
├── .env.frontend.example  ← committed — template with placeholder values
└── .gitignore
```

---

## docker-compose.yml

**`docker-compose.yml`**
```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env.backend
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    networks:
      - app-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    env_file:
      - .env.frontend
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - app-net

networks:
  app-net:
    driver: bridge
```

---

## docker-compose.dev.yml (development override)

Extends the base compose with live-reloading mounts. Run both files together — the override replaces only what it declares:

**`docker-compose.dev.yml`**
```yaml
services:
  backend:
    volumes:
      - ./backend/src:/app/src:ro
    command: ["uv", "run", "uvicorn", "src.main:app", "--reload", "--host", "0.0.0.0"]

  frontend:
    volumes:
      - ./frontend/src:/app/src:ro
      - ./frontend/public:/app/public:ro
    command: ["npm", "run", "dev"]
```

```bash
# Start in development mode
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Start in production mode
docker compose up
```

---

## env_file Convention

Each service loads only its own secrets — no shared root `.env`:

**`.env.backend — gitignored`**
```bash
ENVIRONMENT=DEV
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/mydb
JWT_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">

# .env.frontend — gitignored
NEXT_PUBLIC_API_URL=http://backend:8000
NEXTAUTH_SECRET=<generate: openssl rand -hex 32>
NODE_ENV=production
```

```bash
# .gitignore
.env.backend
.env.frontend
.env.*.local
```

Keep `.env.*.example` files current whenever a new variable is added. They are the contract between the repo and the environment.

---

## Internal Service Networking

Inside the Docker network, services communicate by service name. The frontend container reaches the backend via `http://backend:8000`, not `http://localhost:8000`:

**`.env.frontend (inside Docker)`**
```bash
NEXT_PUBLIC_API_URL=http://backend:8000

# .env.frontend (local dev without Docker)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The `app-net` bridge network isolates these services from other Docker networks on the host.

---

## Backend /health Endpoint

`depends_on: condition: service_healthy` requires the backend to expose a health endpoint that returns HTTP 200. Without it, the healthcheck has nothing to probe and compose cannot sequence startup correctly.

```python
# FastAPI
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

```python
# FastMCP (MCP server)
@mcp.tool(name="health", description="Server liveness check.")
async def health() -> dict:
    return {"status": "ok"}
```

---

## Common Commands

```bash
# Build images (required after Dockerfile or dependency changes)
docker compose build

# Start all services in the background
docker compose up -d

# View live logs
docker compose logs -f

# Stop and remove containers (keeps volumes)
docker compose down

# Stop and remove containers AND volumes (full reset)
docker compose down -v

# Rebuild a single service
docker compose build backend
docker compose up -d backend
```

---

## Anti-Patterns

```yaml
# ❌ WRONG — single root .env; every service sees every secret
env_file:
  - .env

# ✅ CORRECT — each service gets only its own file
# backend service:
env_file:
  - .env.backend
# frontend service:
env_file:
  - .env.frontend

# ❌ WRONG — frontend starts before backend is ready
depends_on:
  - backend

# ✅ CORRECT — wait for the healthcheck to pass
depends_on:
  backend:
    condition: service_healthy

# ❌ WRONG — .env files committed to git
# (no .gitignore entry for .env.backend / .env.frontend)

# ❌ WRONG — .env.*.example files NOT committed
# (new developer has no idea what variables are needed)
```

---

## Quick Checklist

- [ ] Each service uses its own `env_file` (`env.backend`, `.env.frontend`) — no shared root `.env`
- [ ] `.env.backend` and `.env.frontend` in `.gitignore`
- [ ] `.env.backend.example` and `.env.frontend.example` committed with placeholder values
- [ ] Backend exposes `/health` returning HTTP 200 for the healthcheck to probe
- [ ] Frontend `depends_on` backend with `condition: service_healthy`
- [ ] Services on a named `app-net` network — frontend uses `http://backend:<port>`, not `localhost`
- [ ] Dev override in `docker-compose.dev.yml` — base `docker-compose.yml` stays clean for production
- [ ] `docker compose build` re-run after any Dockerfile or dependency file change
