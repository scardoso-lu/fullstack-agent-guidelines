# Supply Chain Security — Next.js and npm

Every package you install is a piece of someone else's code running with full access to your application and your users' browsers. Supply chain attacks compromise trusted packages to inject malicious code — the xz utils backdoor, event-stream, and hundreds of typosquatted npm packages follow this pattern.

This is OWASP A03:2025 applied to the JavaScript ecosystem.

---

## Pin Exact Versions — No Semver Ranges in Production

Semver ranges (`^`, `~`, `>=`) mean "install whatever is latest" at the time of `npm install`. If a maintainer account is compromised and a malicious patch is published, your next `npm install` installs it.

**Vulnerable:**
```json
{
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "axios": ">=1.0.0"
  }
}
```

**Fixed — exact versions:**
```json
{
  "dependencies": {
    "next": "15.3.3",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "@tanstack/react-query": "5.80.7",
    "react-hook-form": "7.56.4",
    "zod": "3.25.55",
    "js-cookie": "3.0.5",
    "dompurify": "3.2.6",
    "nuqs": "2.4.3",
    "jwt-decode": "4.0.0"
  },
  "devDependencies": {
    "typescript": "5.8.3",
    "eslint": "9.28.0",
    "@types/react": "19.1.6"
  }
}
```

Setting `save-exact` in `.npmrc` makes this the default for every `npm install <pkg>`:

```ini
# .npmrc
save-exact=true
engine-strict=true
```

---

## Commit and Never Delete the Lockfile

The lockfile (`package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`) contains SHA hashes of every direct and transitive dependency. It is your content-addressed snapshot of the entire dependency tree.

```bash
# ✅ Install exactly what is in the lockfile — no version resolution
npm ci              # npm
pnpm install --frozen-lockfile  # pnpm

# ❌ WRONG — may upgrade packages on install
npm install
```

Rules:
- **Always commit** the lockfile — it belongs in version control
- **Never** add `package-lock.json` to `.gitignore`
- Use `npm ci` (not `npm install`) in CI/CD and Docker builds
- Treat a lockfile diff in a PR with the same scrutiny as a code change

---

## Audit in CI — Break the Build on Known CVEs

```yaml
# .github/workflows/ci.yml
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5   # pinned to SHA
      - uses: actions/setup-node@1a4442cacd436585916779262731d1f68fbc272a
        with:
          node-version: "22"
          cache: "npm"
      - run: npm ci
      - run: npm audit --audit-level=high   # fail on high/critical CVEs
```

`--audit-level=high` fails the build on High and Critical findings, passes on Low and Moderate. Adjust to your risk tolerance.

For pnpm:
```yaml
- run: pnpm audit --audit-level high
```

---

## Dependabot — Automated Dependency Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: npm
    directory: "/"
    schedule:
      interval: weekly
      day: monday
    open-pull-requests-limit: 5
    groups:
      # Group minor/patch updates to reduce PR noise
      minor-and-patch:
        update-types:
          - "minor"
          - "patch"
    ignore:
      # Review major version bumps manually
      - dependency-name: "next"
        update-types: ["version-update:semver-major"]
```

Dependabot opens PRs with version bumps. CI runs `npm audit` on each. Merge only after all checks pass.

---

## Vetting Packages Before Installing

Before running `npm install <package>`:

```bash
# Check before installing
npm show <package> version        # latest version
npm show <package> time           # when last published (stale = risk)
npm show <package> maintainers    # who controls it
```

Red flags:
- Published <1 week ago and trending (typosquatting)
- Maintainer account recently changed
- <1000 weekly downloads (unless it's internal)
- Very small code footprint for the claimed functionality
- `postinstall` scripts that download files at install time

**Typosquatting awareness:**
```
reqeust   ≠ request
expresss  ≠ express
nxt       ≠ next
lodahs    ≠ lodash
```

---

## Pinning CI Actions to SHA (Not Tags)

Tags like `actions/checkout@v4` are mutable — the `v4` tag can be moved to point to malicious code. SHA references are immutable.

```yaml
# ❌ WRONG — tag can be silently moved
- uses: actions/checkout@v4
- uses: actions/setup-node@v4

# ✅ Pin to the exact commit SHA
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5      # v4.2.2
- uses: actions/setup-node@1a4442cacd436585916779262731d1f68fbc272a    # v4.2.0
```

Find the SHA for any action at `github.com/<org>/<action>/releases`.

---

## Docker — Pin Base Image to Digest

```dockerfile
# ❌ WRONG — "latest" or a tag can change
FROM node:22-alpine

# ✅ Pin to immutable content digest
FROM node:22-alpine@sha256:f6b3e3c...

# Multi-stage build using exact image
FROM node:22-alpine@sha256:f6b3e3c... AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production  # exact lockfile install
```

---

## Subresource Integrity for External Scripts

If you load any script or stylesheet from a CDN, use SRI:

```html
<!-- Generate the hash: cat library.js | openssl dgst -sha384 -binary | openssl base64 -A -->
<script
  src="https://cdn.example.com/library.min.js"
  integrity="sha384-abc123xyz..."
  crossorigin="anonymous"
></script>
```

If the CDN serves a modified file, the browser refuses to execute it.

---

## Anti-Patterns

```bash
# ❌ Installing without reviewing
npx create-something-app  # executes code immediately — read the source first
npm install $(curl https://somesite.com/package-name)  # never do this

# ❌ Using --legacy-peer-deps to suppress errors
npm install --legacy-peer-deps   # hides dependency conflicts — investigate instead

# ❌ Running npm install in production
# Dockerfile: RUN npm install   ← resolves versions at build time, not deterministic
# Dockerfile: RUN npm ci        ← uses exact lockfile
```

---

## Quick Checklist

- [ ] All `package.json` dependencies use exact versions — no `^` or `~`
- [ ] `.npmrc` has `save-exact=true`
- [ ] Lockfile committed to git, never in `.gitignore`
- [ ] CI runs `npm ci` (not `npm install`) and `npm audit --audit-level=high`
- [ ] Dependabot (or Renovate) configured for weekly updates
- [ ] New packages checked for age, download count, and maintainers before install
- [ ] GitHub Actions pinned to SHA, not floating tags
- [ ] Docker base images pinned to digest, not tags
- [ ] External scripts use Subresource Integrity (SRI) hashes
