---
model: sonnet
effort: extract
---

# Node.js Project Setup — Docker + Next.js

Use when creating the frontend Dockerfile, configuring npm to block postinstall scripts, or adding new npm packages. Covers Node.js 22 alpine, `.npmrc` with `ignore-scripts`, multi-stage Next.js build with standalone output, and non-root user.

---

## Why Block Postinstall Scripts

npm packages can declare `postinstall`, `preinstall`, and `install` lifecycle hooks that execute arbitrary shell commands during `npm install` or `npm ci`. Compromised or typosquatted packages use these to exfiltrate environment variables, download payloads, or install backdoors. `ignore-scripts=true` disables all lifecycle hooks at install time — no exceptions by default.

---

## .npmrc

```ini
# .npmrc — committed to git; applies on every npm install and npm ci
ignore-scripts=true   # block all lifecycle hook execution
save-exact=true       # pin versions — no ^ or ~ on npm install <pkg>
engine-strict=true    # fail if node version doesn't match engines field
```

Commit `.npmrc`. It applies on developer machines and inside Docker builds alike.

> **Native module exception**: packages that compile C++ bindings (`sharp`, `bcrypt`, `canvas`) need their postinstall script. After `npm ci --ignore-scripts`, rebuild only the specific package: `npm rebuild sharp`. Note this explicitly in a `ponytail:` comment.

---

## Dockerfile (multi-stage)

```dockerfile
# syntax=docker/dockerfile:1.7

# ── Stage 1: install deps ────────────────────────────────────────────────────
FROM node:22-alpine AS deps
WORKDIR /app
# .npmrc must be present before npm ci so ignore-scripts applies inside Docker
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

# ── Stage 2: build ───────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ── Stage 3: production runtime (Next.js standalone output) ─────────────────
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public           ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
```

**Standalone output requires this in `next.config.ts`:**

```ts
// next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  productionBrowserSourceMaps: false,
};

export default nextConfig;
```

The standalone build copies only the files needed to run `node server.js` — no dev dependencies, no source maps, minimal attack surface.

---

## npm ci vs npm install

```bash
# ✅ Always use npm ci in Docker and CI — installs exactly from package-lock.json
RUN npm ci --ignore-scripts

# ❌ npm install resolves versions at build time — not reproducible
RUN npm install
```

---

## TypeScript Tooling via npx

Run TypeScript tools through `npx` or `package.json` scripts — never install them globally:

```bash
# Type-check without emitting output
npx tsc --noEmit

# Run the dev server
npx next dev

# Linting
npx eslint src/

# Unit tests
npx vitest run
npx jest --passWithNoTests
```

In `package.json`, wire these as scripts so Dockerfile `CMD` and CI both use the same entry points:

```json
{
  "scripts": {
    "dev":        "next dev",
    "build":      "next build",
    "start":      "next start",
    "lint":       "next lint",
    "typecheck":  "tsc --noEmit",
    "test":       "vitest run"
  }
}
```

---

## Lockfile Rules

```bash
# ✅ Commit package-lock.json — it contains SHA hashes of every dependency
git add package-lock.json

# ❌ Never delete or gitignore it
# package-lock.json   ← never add this to .gitignore
```

---

## Environment Variables

```bash
# .env.frontend — real secrets; gitignored
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXTAUTH_SECRET=...
```

```bash
# .env.frontend.example — committed template; no real values
NEXT_PUBLIC_API_URL=http://backend:8000
NEXTAUTH_SECRET=<generate: openssl rand -hex 32>
```

`NEXT_PUBLIC_` values are embedded in the client bundle and visible to anyone in DevTools. Never add a secret with this prefix.

---

## Anti-Patterns

```dockerfile
# ❌ WRONG — .npmrc not copied; ignore-scripts doesn't apply inside Docker
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# ✅ CORRECT — .npmrc copied first
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

# ❌ WRONG — single-stage; ships node_modules, dev deps, and source into production image
FROM node:22-alpine
COPY . .
RUN npm ci && npm run build
CMD ["npm", "start"]

# ❌ WRONG — semver range in package.json; different versions on each install
"next": "^15.0.0"

# ✅ CORRECT — exact version; same on every npm ci
"next": "15.3.3"

# ❌ WRONG — running as root (no USER instruction)
CMD ["node", "server.js"]
```

---

## Quick Checklist

- [ ] `.npmrc` has `ignore-scripts=true` and `save-exact=true` — committed to git
- [ ] Dockerfile copies `.npmrc` before `npm ci --ignore-scripts`
- [ ] Multi-stage build: deps → builder → runner (no dev files in production image)
- [ ] `next.config.ts` has `output: "standalone"` and `productionBrowserSourceMaps: false`
- [ ] Non-root user set before `CMD`
- [ ] `package-lock.json` committed — never in `.gitignore`
- [ ] `NEXT_PUBLIC_` only on values intentionally visible to users
- [ ] `.env.frontend` gitignored; `.env.frontend.example` committed with placeholder values
- [ ] Native module exceptions documented with `ponytail:` comment
