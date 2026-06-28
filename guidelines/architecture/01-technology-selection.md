---
model: opus
effort: high
---

# Technology Selection — Choosing Dependencies and Peripheral Tech

Use when proposing a new dependency, a new container image, a new SaaS, or a new peripheral technology (task queue, vector store, cache, broker, observability stack). Defines the checklist every selection passes (need, alternatives, license, maintenance, security, fit) and the rule that **every adopted dependency is recorded** — no silent adoption.

The application stack is **locked** (e.g. FastAPI + Next.js + the project's package managers). Peripheral technology is **chosen per project** — the task queue, the vector store, the cache/broker, the observability stack. Each choice is **written down** with rationale (a short markdown decision record under `docs/decisions/` or equivalent) so the team can answer "why this?" a year from now.

## The rule

> No dependency, image, or external service is adopted without:
>
> 1. A documented **need** (the problem it solves, not the technology it represents).
> 2. **Two alternatives** evaluated and rejected with reasons.
> 3. A clean pass on **license**, **maintenance**, **security**, and **fit**.
> 4. A **written decision record** that captures the choice and its rationale (one short markdown file under `docs/decisions/` or wherever the project keeps them).

Skipping any of these produces the kind of dependency choice nobody remembers a year later, when the package is unmaintained and CVE-flagged.

## The checklist

### 1. Need

State the problem in the project's own terms, not the technology's:

- ✅ "We need a way to run bulk imports (10k–1M rows) without holding an API request open or losing a partial run on a worker restart."
- ❌ "We need Taskiq." (That's the answer, not the problem.)

If the need can be met **without** a new dependency — by the standard library, an already-adopted dep, or a 50-line in-repo solution — that's the answer. Prefer reuse over adoption.

### 2. Alternatives

Name **at least two real alternatives** and reject each with a reason. "I evaluated only one option and it was good" usually means the comparison wasn't done.

Real alternatives are:

- Same category, different technology (Taskiq vs Celery vs Dramatiq vs RQ).
- Different category that solves the same problem (a task queue vs a serverless function vs a cron job vs PostgreSQL `LISTEN/NOTIFY`).
- The null option: not adopting anything, doing the work in-process or in a script.

"None of the alternatives applied" is almost always wrong — there are always alternatives.

### 3. License

- Approved licenses for the project (typical defaults: MIT, BSD-2/3, Apache-2.0, MPL-2.0, ISC).
- **GPL/AGPL** need explicit legal sign-off — copyleft can require source disclosure.
- **No-license** packages are not adoptable (no permission to use).
- **Commercial / EULA** packages need procurement + legal sign-off + a budget owner.

Check the stack-local manifest (`frontend/package.json` or `backend/pyproject.toml`) of the candidate and its transitive deps (`cd frontend && pnpm licenses list`, `cd backend && pip-licenses`).

### 4. Maintenance posture

Open the package's repository and check:

- **Last release date.** A package with no release in 2+ years is a yellow flag for active projects.
- **Open-issues / closed-issues ratio.** A package with 800 open and 50 closed has a different culture than 50 open and 800 closed.
- **Number of maintainers.** Single-maintainer is a higher bus-factor risk than an organization-backed project.
- **Recent commit cadence.** Active maintenance vs. abandoned-in-place.
- **Major version churn.** A v0.x package that breaks API between every minor is high-cost over time.

Document the posture in the decision record (one or two sentences), so the next person can re-evaluate.

### 5. Security

- **Known CVEs?** `pip-audit` / `pnpm audit` on the proposed version pin.
- **Postinstall scripts** (Node)? Treat as supply-chain risk; require a reason.
- **Typosquat check** — is the name suspiciously close to a more-popular package?
- **Transitive dep count** — a package that pulls in 200 sub-deps expands the attack surface a lot.
- **Self-update / phone-home behavior** — disqualifying unless explicitly desired.

Anything with an open Critical/High CVE on the version under consideration is blocked until upstream patches it (or another package wins).

### 6. Fit with the locked stack

- **Toolchain.** Python deps installed via the project's manager (`uv` / `poetry`); Node deps via the project's manager (`pnpm` / `npm` / `yarn`). Bare `pip` / `npm` operations bypass the lockfile.
- **Async model.** A library that's sync-only doesn't fit an async FastAPI codebase; either reject or wrap it (and the wrapper's cost is a real reason to reject).
- **Type quality.** First-class types (`py.typed`, `*.d.ts`) save more time over a year than the package's headline features.
- **Existing patterns.** Does the package's API conflict with the project's repository / use-case / DI patterns? An import that drags in a global is a fit problem.
- **Containerization.** If the package needs a system library not in the base image, the Dockerfile change is part of the cost.

### 7. Pin and lock

- Pin the version explicitly (`^1.2.3` is not a pin; `1.2.3` is).
- Commit the lockfile beside its manifest (`backend/uv.lock`, `frontend/pnpm-lock.yaml`).
- Add the new dependency in the smallest reasonable PR — ideally **its own slice**, separate from the feature that consumes it.

## Peripheral technology decisions

For decisions beyond a single library — picking a task queue, a vector store, a cache/broker, an observability stack — apply the same checklist with extra weight on:

- **Operational footprint.** Does it need its own deployment? Storage? Backups? Monitoring? On-call coverage?
- **Local-dev experience.** Can a developer run the system end-to-end on their laptop? If not, the test environment is now further from production.
- **Migration story.** If we adopt this and it doesn't work out, how do we get off it? A piece of tech with no exit is a long-term liability.
- **Cost model.** SaaS pricing, self-hosted resource consumption, license seats. The accountant cares.

These decisions usually warrant **diagrams** in the decision record — a sequence diagram showing how the API, the new tech, and the existing systems interact; a deployment diagram showing where it runs.

## What the decision record captures

Every adoption record includes:

```markdown
## Decision

- **Adopt:** `<name>` `<version pin>`
- **Reason:** <one sentence — the problem it solves>
- **Rejected alternatives:**
  - `<alt 1>` — <reason>
  - `<alt 2>` — <reason>
- **License:** <SPDX identifier>
- **Maintenance posture:** <one or two sentences>
- **Security baseline:** <CVE check result, postinstall check, transitive dep count>

## Consequences

- ...
- Tests must assert: ...
```

A future engineer asking "why did we pick this?" gets the answer from this section alone.

## What this prevents

- **Silent adoption.** A package appears in the lockfile via a side-channel PR; nobody can explain why a year later.
- **Multiple solutions for the same problem.** Three logging libraries, two HTTP clients, four date utilities — because each was added without checking what already existed.
- **Stale, unmaintained dependencies.** Adopted in a rush, never re-evaluated, eventually a CVE risk.
- **Vendor lock-in by accident.** A SaaS adopted "just to ship the demo" becomes load-bearing because nobody documented the exit.

## When in doubt

- **Standard library first.** It's always there; it never has a CVE you didn't ask for.
- **Already-adopted dependencies second.** Reuse beats addition.
- **A small in-repo helper third** if the need is narrow and the helper is easy to test.
- **A new dependency last** — and only with the full checklist.

The cost of a dependency isn't its install time; it's the year of "wait, this still works, right?" that follows. Choose accordingly.
