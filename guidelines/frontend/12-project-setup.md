---
model: sonnet
effort: extract
---

# Node.js Project Setup - Docker + Next.js + pnpm

Use when creating the frontend Dockerfile, initializing a Next.js frontend, configuring pnpm supply-chain hardening, or adding npm packages. Covers Node.js 22 alpine, pnpm via Corepack, frontend-local lock/workspace files, `.npmrc`, standalone Next.js output, and non-root production images.

---

## Directory Boundary

The frontend is its own package-manager boundary. All frontend package metadata lives under `frontend/`:

```text
frontend/
  Dockerfile
  Dockerfile.test
  .npmrc
  package.json
  pnpm-lock.yaml
  pnpm-workspace.yaml
  .env
  .env.example
  next.config.ts
  src/
```

Do not create `pnpm-lock.yaml` or `pnpm-workspace.yaml` at the repository root for a single frontend app. Docker builds use `context: ./frontend`, so the lockfile and workspace file must be inside that context. A root lockfile will not match `frontend/package.json` inside the container and `pnpm install --frozen-lockfile` will fail with an outdated lockfile error.

If the project is a real monorepo with multiple pnpm packages, make the Docker build context the repo root and copy the workspace files deliberately. Do not mix a root pnpm workspace with `context: ./frontend`.

---

## pnpm Setup

Use Corepack to activate the pinned pnpm version in Docker. Pin the same major version in CI and local setup.

```bash
cd frontend
corepack enable
corepack prepare pnpm@9.15.4 --activate
pnpm install --frozen-lockfile
```

`frontend/.npmrc` is committed and applies to local installs and Docker builds:

```ini
ignore-scripts=true
save-exact=true
engine-strict=true
```

`ignore-scripts=true` blocks package lifecycle scripts during install. Native-module exceptions must be explicit and narrow: install with scripts disabled, then rebuild only the named package, with a `ponytail:` comment explaining why.

---

## Dockerfile

`frontend/Dockerfile` is built with `context: ./frontend`, so every copied dependency file is relative to `frontend/`.

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS deps
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

COPY .npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

Standalone output requires this in `next.config.ts`:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  productionBrowserSourceMaps: false,
};

export default nextConfig;
```

---

## package.json

Use exact versions. No `^`, `~`, `latest`, prerelease, VCS URL, direct URL, or `file:` dependency unless a documented exception has been approved.

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit",
    "format:check": "prettier --check .",
    "test": "vitest run",
    "e2e": "playwright test"
  },
  "dependencies": {
    "next": "15.3.4",
    "react": "19.1.0",
    "react-dom": "19.1.0"
  },
  "devDependencies": {
    "typescript": "5.8.3",
    "vitest": "3.2.4"
  }
}
```

---

## Lockfile Rules

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
git add frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.npmrc
```

Never generate the frontend pnpm lockfile from the repository root unless the project is intentionally configured as a root pnpm monorepo and Docker also builds from the root context.

---

## Environment Variables

**`frontend/.env` - real secrets; gitignored**

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_SECRET=...
```

**`frontend/.env.example` - committed template; no real values**

```bash
NEXT_PUBLIC_API_URL=http://backend:8000
NEXTAUTH_SECRET=<generate: openssl rand -hex 32>
```

`NEXT_PUBLIC_` values are embedded in the client bundle and visible to anyone in DevTools. Never add a secret with this prefix.

---

## Anti-Patterns

```dockerfile
# WRONG - Docker context is ./frontend but lockfile was generated at repo root
# A root pnpm lockfile/workspace file for a single frontend app is wrong.
COPY .npmrc package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# CORRECT - lockfile and workspace file live inside frontend/
# frontend/pnpm-lock.yaml
# frontend/pnpm-workspace.yaml
COPY .npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# WRONG - package manager mismatch; do not generate an npm lockfile for the pnpm frontend

# WRONG - semver range in package.json; different versions can install later
"next": "^15.0.0"

# CORRECT - exact version
"next": "15.3.4"

# WRONG - single-stage production image ships source and dev deps
FROM node:22-alpine
COPY . .
RUN pnpm install --frozen-lockfile && pnpm build
CMD ["pnpm", "start"]
```

---

## Quick Checklist

- [ ] `frontend/package.json` exists and uses exact dependency versions
- [ ] `frontend/pnpm-lock.yaml` is committed and matches `frontend/package.json`
- [ ] `frontend/pnpm-workspace.yaml` is committed when pnpm workspace tooling is used
- [ ] No frontend `pnpm-lock.yaml` or `pnpm-workspace.yaml` is generated at repo root for a single frontend app
- [ ] `frontend/.npmrc` has `ignore-scripts=true`, `save-exact=true`, and `engine-strict=true`
- [ ] `frontend/Dockerfile` copies `.npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml` before `pnpm install --frozen-lockfile`
- [ ] Docker compose uses `build.context: ./frontend` for the frontend service
- [ ] `frontend/.env` is gitignored and `frontend/.env.example` is committed
- [ ] `next.config.ts` has `output: "standalone"` and `productionBrowserSourceMaps: false`
- [ ] Non-root user is set before production `CMD`
- [ ] `NEXT_PUBLIC_` is used only for values intentionally visible to users
