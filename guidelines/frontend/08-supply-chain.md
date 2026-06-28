---
model: opus
effort: high
---

# Supply Chain Security - Next.js and pnpm

Use when adding a frontend package, setting up CI, configuring Docker, or reviewing dependency changes. Covers exact version pinning, frontend-local pnpm lockfiles, `.npmrc`, pnpm audit, SHA-pinned GitHub Actions, Dependabot/Renovate, and SRI for CDN assets.

Every package you install is someone else's code running in your build and, often, your users' browsers. Supply-chain attacks compromise trusted packages, publish typosquats, or abuse install scripts. The defense is strict: exact versions, frozen lockfiles, disabled lifecycle scripts, package review, and reproducible CI.

---

## Frontend Package Boundary

The standard project layout keeps frontend package state under `frontend/`:

```text
frontend/
  .npmrc
  package.json
  pnpm-lock.yaml
  pnpm-workspace.yaml
```

Do not generate `pnpm-lock.yaml` or `pnpm-workspace.yaml` at the repository root for a single frontend app. Docker builds use `context: ./frontend`, so the lockfile that `pnpm install --frozen-lockfile` reads must be `frontend/pnpm-lock.yaml` and must match `frontend/package.json`.

Only real multi-package pnpm monorepos use root pnpm workspace files. In that case, Docker must also build from the repo root and copy workspace files deliberately.

---

## Pin Exact Versions

Semver ranges (`^`, `~`, `>=`) mean "install whatever is latest within this range." If a maintainer account is compromised and a malicious patch is published, the next install can pick it up.

```json
{
  "dependencies": {
    "next": "15.3.4",
    "react": "19.1.0",
    "react-dom": "19.1.0",
    "react-hook-form": "7.55.0",
    "zod": "3.24.2"
  },
  "devDependencies": {
    "typescript": "5.8.3",
    "vitest": "3.2.4",
    "@playwright/test": "1.52.0"
  }
}
```

`frontend/.npmrc` enforces exact saves and blocks lifecycle scripts:

```ini
ignore-scripts=true
save-exact=true
engine-strict=true
```

---

## Frozen Installs

```bash
cd frontend
pnpm install --frozen-lockfile
```

Rules:

- Always commit `frontend/pnpm-lock.yaml`.
- Commit `frontend/pnpm-workspace.yaml` when pnpm workspace tooling is used.
- Never add `frontend/pnpm-lock.yaml` to `.gitignore`.
- Treat a lockfile diff in a PR with the same scrutiny as a code diff.
- Do not use `pnpm install --no-frozen-lockfile` in CI or Docker to work around a stale lockfile. Regenerate the lockfile under `frontend/` and commit it.

---

## Audit in CI

```yaml
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      - uses: pnpm/action-setup@v4
        with:
          version: "9.15.4"
      - uses: actions/setup-node@1a4442cacd436585916779262731d1f68fbc272a
        with:
          node-version: "22"
          cache: "pnpm"
          cache-dependency-path: frontend/pnpm-lock.yaml
      - run: cd frontend && pnpm install --frozen-lockfile
      - run: cd frontend && pnpm audit --audit-level high
```

`--audit-level high` fails the build on High and Critical findings.

---

## Docker Install Pattern

`frontend/Dockerfile` is built with `context: ./frontend`; the files copied below must live in `frontend/`.

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

COPY .npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
```

Do not copy a root lockfile into a frontend-context Docker build. That produces stale-lockfile failures because the lockfile is not tied to the `package.json` inside the build context.

---

## Vet Packages Before Installing

Before adding a package:

```bash
pnpm view <package> version
pnpm view <package> time
pnpm view <package> maintainers
```

Red flags:

- Published less than a week ago and trending
- Maintainer account recently changed
- Very low weekly downloads unless it is internal or intentionally niche
- Install scripts that download binaries or execute shell commands
- VCS, direct URL, or `file:` dependency sources

---

## Pin CI Actions to SHA

Tags like `actions/checkout@v4` are mutable. SHA references are immutable.

```yaml
# WRONG - tag can move
- uses: actions/checkout@v4

# CORRECT - exact commit
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
```

---

## Subresource Integrity

If you load a script or stylesheet from a CDN, use SRI:

```html
<script
  src="https://cdn.example.com/library.min.js"
  integrity="sha384-abc123xyz..."
  crossorigin="anonymous"
></script>
```

---

## Anti-Patterns

```bash
# WRONG - executes unreviewed package code immediately
npx create-something-app

# WRONG - hides a stale lockfile in CI/Docker
pnpm install --no-frozen-lockfile

# WRONG - creates lock/workspace files at repo root for a single frontend app
pnpm install
# Do not commit root pnpm files for a single frontend app.

# CORRECT - generate frontend package state inside frontend/
cd frontend
pnpm install
cd ..
git add frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.npmrc
```

---

## Quick Checklist

- [ ] `frontend/package.json` dependencies are exact versions; no `^`, `~`, wildcard, or `latest`
- [ ] `frontend/.npmrc` has `ignore-scripts=true`, `save-exact=true`, and `engine-strict=true`
- [ ] `frontend/pnpm-lock.yaml` is committed and matches `frontend/package.json`
- [ ] `frontend/pnpm-workspace.yaml` is committed when workspace tooling is used
- [ ] No frontend pnpm lock/workspace files exist at repo root unless the project is a real root pnpm monorepo
- [ ] CI runs `cd frontend && pnpm install --frozen-lockfile`
- [ ] CI runs `cd frontend && pnpm audit --audit-level high`
- [ ] Docker copies frontend-local `.npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml` before install
- [ ] New packages were checked for age, maintainers, source, and install scripts
- [ ] GitHub Actions are pinned to SHA, not floating tags
- [ ] External scripts use Subresource Integrity hashes
