---
model: sonnet
effort: extract
---

# Definition of Done — Frontend Checklist

Use before merging any PR that touches the Next.js frontend. Every item is a hard gate — nothing ships until all are green. For the full DoD overview (how to run the gate, failure handling, why it's hard) see `agile/02-definition-of-done`.

## Frontend checklist

- [ ] **Lint clean** — `eslint` exits 0.
- [ ] **Format clean** — `prettier --check` exits 0.
- [ ] **Type-check clean** — `tsc --noEmit` exits 0. No `any` introduced.
- [ ] **Unit tests green** — `vitest` passes; new hooks/components have at least one test.
- [ ] **Playwright E2E green** for the affected critical flow.
- [ ] **E2E per new variant** — every new user-facing state/action introduced by the slice (a new lifecycle action, status, tab, enum that renders) has at least one E2E that walks the flow and asserts it *renders*. See `qa/02-e2e-per-feature`.
