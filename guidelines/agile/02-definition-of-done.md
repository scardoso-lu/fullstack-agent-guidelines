---
model: sonnet
effort: extract
---

# Definition of Done — The Gate Every Slice Crosses

Use at the end of every slice, before merging the PR. Defines the exact set of checks that determine whether a slice is shippable: lint, format, type-check, unit + integration + E2E tests, coverage, audit-on-write, authorization checks, security verification, and documentation/diagram freshness. Anything not on the list is not part of DoD; everything on the list is a hard gate.

The Definition of Done (DoD) is the contract between the engineer who wrote the slice and the rest of the team. "Done" means **every item below is green** — not "tests pass on my machine," not "I'll fix the lint warnings later," not "the E2E is flaky so I skipped it."

The DoD is a **hard gate**. Soft checks (ERD diagram refresh, observability spot-checks) are flagged but do not block; everything else blocks until green.

## The DoD checklist

### Backend

- [ ] **Lint clean** — `ruff check .` exits 0. No `# noqa` added without a comment naming the reason.
- [ ] **Format clean** — `ruff format --check .` exits 0. CI does not auto-format; the engineer does.
- [ ] **Type-check clean** — `mypy --strict src/` exits 0. No `# type: ignore` added without a one-line justification.
- [ ] **Unit tests green** — every new use-case has at least one test; every branch in the use-case is covered.
- [ ] **Integration tests green** — routes + DB tested with **testcontainers** (not mocks). Mocking the DB hides migration and query bugs.
- [ ] **Coverage meets the project threshold** — the project contract names the percentage (commonly 80% or 90%).
- [ ] **Audit-on-write check** — every write path in the slice emits a structured audit event in the **same transaction** as the write. Reviewer checks this explicitly; see `backend/19-audit-on-write`.
- [ ] **Authorization check** — every new route is guarded by a `require("<permission>")` dependency (or the project's equivalent). Owner bypass and 403 behavior verified.
- [ ] **Complexity cap** — every new function has cyclomatic complexity ≤ 10 (ruff `C90`). Functions over the limit are decomposed, not exempted.

### Frontend

- [ ] **Lint clean** — `eslint` exits 0.
- [ ] **Format clean** — `prettier --check` exits 0.
- [ ] **Type-check clean** — `tsc --noEmit` exits 0. No `any` introduced.
- [ ] **Unit tests green** — `vitest` passes; new hooks/components have at least one test.
- [ ] **Playwright E2E green** for the affected critical flow.
- [ ] **E2E per new variant** — every new user-facing state/action introduced by the slice (a new lifecycle action, status, tab, enum that renders) has at least one E2E that walks the flow and asserts it *renders*. See `qa/02-e2e-per-feature`.

### Security (hard gate — owned by the security review)

- [ ] **No open Critical or High finding** across code SAST, dependency CVEs, Docker image scan, secrets, and supply-chain checks (see `backend/13-owasp-top10` and `frontend/07-owasp-top10` for the catalog).
- [ ] **Slice honored the security guidance** set at slice start (threat model + secure-coding requirements).
- [ ] **Per-ticket security report** exists at the project's security-report location (e.g. `docs/security/<ticket>.md`).

### Documentation (soft — flagged, not blocked)

- [ ] If the slice changed a SQLAlchemy model, FK, or table constraint → the canonical ERD was refreshed.
- [ ] If the slice introduced a non-trivial flow → a Mermaid diagram was added or updated (sequence/state/flow).
- [ ] ADRs cited in the ticket are referenced in the PR description; new decisions have their own ADR.

## How to run the gate

The DoD's *structure* is fixed; the *commands* are project-specific. The project contract (typically a root `Makefile`) names the gate target:

```bash
make gate           # full DoD: lint + format + type-check + tests + coverage
make gate-backend   # backend-only subset
make gate-frontend  # frontend-only subset
```

If the project doesn't have a Makefile, the gate commands belong in the project README or `OPERATING.md`. Either way, **CI runs the same commands** — the local gate must mirror CI exactly, or you'll merge red.

## Failure handling

A failing gate item is routed back to the **owning layer**, not to whoever opened the PR:

- Failing backend test → backend engineer fixes it.
- Missing E2E → frontend engineer (sometimes test engineer) adds it.
- Lint/format failure → whoever wrote the offending lines.
- Open Critical/High security finding → owning layer fixes; re-run security verification.

Re-gate after fixes. The slice ships only when **every** item is green simultaneously — a green DoD that goes red on the next rebase is not "done."

## Things that look like DoD but aren't

- **Code review.** A separate gate; runs alongside DoD. A reviewer can block a slice that passes DoD if the code is wrong.
- **Performance benchmarks.** Project-specific. If a slice claims a perf target, add a measurable criterion to the ticket; otherwise don't bolt it on at gate time.
- **Manual smoke tests.** A nice-to-have; not a substitute for E2E. If a manual step is the only way to verify a flow, that's a testability gap to file as its own ticket.

## Why the gate is hard

Soft gates rot. Once "we'll fix the lint warnings later" is allowed once, the backlog of warnings grows until nobody trusts the linter at all. The gate works because **every** item is mandatory — engineers calibrate their work to the gate, not against it.
