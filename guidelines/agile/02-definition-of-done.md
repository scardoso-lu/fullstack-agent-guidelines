---
model: sonnet
effort: extract
---

# Definition of Done — The Gate Every Slice Crosses

Use at the end of every slice, before merging the PR. Defines what "done" means across backend, frontend, and security. Anything not on a checklist is not part of DoD; everything on a checklist is a hard gate (except documentation, which is soft).

The Definition of Done (DoD) is the contract between the engineer who wrote the slice and the rest of the team. "Done" means **every item on the relevant checklists is green** — not "tests pass on my machine," not "I'll fix the lint warnings later," not "the E2E is flaky so I skipped it."

The DoD is a **hard gate**. Soft checks (ERD diagram refresh, observability spot-checks) are flagged but do not block; everything else blocks until green.

## The checklists

Pull the checklist for your stack. A fullstack slice pulls both.

- **Backend** → `agile/05-dod-backend`
- **Frontend** → `agile/06-dod-frontend`
- **Security** → `agile/07-dod-security` (hard gate — owned by the security review)

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
