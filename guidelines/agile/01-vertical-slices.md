---
model: sonnet
effort: extract
---

# Vertical Slices — Ship One Capability End-to-End

Use when picking up a backlog ticket, planning the next chunk of work, or deciding how to split a feature. Defines what a vertical slice is, the dependency order it travels (domain → use-case → API → schema → UI → tests), the "one branch per slice" rule, and how to keep slices from turning into long-lived feature branches.

A **vertical slice** is one backlog ticket implemented end-to-end through every layer of the stack — from the domain model down to the user-facing flow and its tests — so that merging the slice produces a working, demoable capability. **Horizontal slices** (a week of pure schema changes, then a week of pure UI) are an anti-pattern: nothing is shippable until the last piece lands, and the integration risk piles up at the end.

## The rule

> One ticket → one branch → one slice through all layers → one gate → merge.

Concretely, a slice for the ticket **"User can reset their password"** touches, in this order:

1. **Domain** — the entity/value-object change (e.g. `PasswordResetToken` with TTL).
2. **Application** — the use-case (`RequestPasswordReset`, `ConfirmPasswordReset`) and any new repository interface.
3. **Infrastructure** — the repository implementation, migration, mailer adapter.
4. **Presentation (API)** — the routes + schemas (`POST /auth/reset/request`, `POST /auth/reset/confirm`).
5. **Frontend** — the page/feature and its data-fetching hook.
6. **Tests** — unit (use-case), integration (route + DB), and **at least one E2E** for the user-facing flow.

The slice merges only when every layer is green. No "we'll add the frontend next sprint" — that's a horizontal slice in disguise.

## One branch per slice

- Create `slice/<TICKET-ID>-<short-slug>` off the up-to-date default branch **before** any work starts.
- Never build a slice directly on `main`.
- The slice's life ends with one PR. If it's growing past ~1 week of work, the ticket was too big — split it (see "When to split" below).
- Commit **incrementally along the slice** — one commit per meaningful checkpoint (domain shape locked, use-case green, route wired, UI wired, tests green). Not one dump at the end. See `agile/03-conventional-commits` for the commit format.

## Why vertical, not horizontal

Vertical slices give you:

- **Shippable increments.** Every merged slice could be released. The build/deferred boundary is enforced by what actually ships, not by intent.
- **Early integration feedback.** A schema decision that doesn't survive contact with the UI is caught in the same week, not three sprints later.
- **A meaningful gate.** A Definition of Done that runs unit + integration + E2E across the slice (see `agile/02-definition-of-done`) is only possible because the slice is end-to-end.
- **Parallelism.** Two slices that don't share an entity can be built concurrently on separate branches; horizontal slices serialize the team.

Horizontal slices fail the opposite way: the database team finishes "tickets" that nobody can use, the frontend team blocks on the backend, and the integration bug surfaces at merge.

## When to split a slice

Split if **any** of these is true:

- The slice touches more than ~3 entities or ~5 routes.
- The slice spans more than ~1 week of focused work.
- The slice has internal "phases" the team is tempted to ship separately (e.g. "phase 1: read-only, phase 2: writes"). Each phase is its own slice.
- The slice introduces a new dependency *and* a new feature. Land the dependency adoption (with its ADR) in its own slice first.

Splitting rule: each child slice must still be vertical and shippable on its own. "Read-only view of dataset" is a valid first slice; "the bottom three layers of dataset" is not.

## What does not belong inside a slice

- **Architectural decisions.** If the slice needs a new dependency, a new bounded context, or a cross-cutting change, lock that decision separately first (see `architecture/01-technology-selection` for the dependency case). The slice consumes the decision; it does not relitigate it.
- **Scope expansion.** If you discover work outside the ticket while implementing it, file a new ticket. Don't grow the slice.
- **Drive-by refactors.** A refactor of unrelated code goes on its own branch with its own PR. The slice diff stays readable.

## The slice loop

```
pick ticket  →  cut branch  →  security guidance (threat-model)
            →  implement layer-by-layer (commit per checkpoint)
            →  run the DoD gate locally
            →  qa-review + security-verify
            →  green? merge.   red? loop back to the owning layer.
```

No parallel half-finished slices. Finish one before starting the next — unless the parallel slice is on a disjoint surface (different aggregate, different files) and unblocked by everything you've already shipped.

## Anti-patterns to call out in review

- **"Backend-only" PR** for a user-facing ticket. The frontend is part of the slice.
- **No E2E** for a new user-facing flow. A slice without an E2E for its new variant is incomplete — see `qa/02-e2e-per-feature`.
- **Branch off another in-flight slice.** Stacking slices on each other couples their gates. Branch off `main`; rebase if you must.
- **Long-lived `slice/foo` branch** with weeks of drift. That's a feature branch — split the work.
- **Mixing scope.** Two tickets' worth of changes in one PR. Reviewers can't reason about it; the gate can't either.
