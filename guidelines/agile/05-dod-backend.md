---
model: sonnet
effort: extract
---

# Definition of Done — Backend Checklist

Use before merging any PR that touches the FastAPI backend. Every item is a hard gate — nothing ships until all are green. For the full DoD overview (how to run the gate, failure handling, why it's hard) see `agile/02-definition-of-done`.

## Backend checklist

- [ ] **Lint clean** — `ruff check .` exits 0. No `# noqa` added without a comment naming the reason.
- [ ] **Format clean** — `ruff format --check .` exits 0. CI does not auto-format; the engineer does.
- [ ] **Type-check clean** — `mypy --strict src/` exits 0. No `# type: ignore` added without a one-line justification.
- [ ] **Unit tests green** — every new use-case has at least one test; every branch in the use-case is covered.
- [ ] **Integration tests green** — routes + DB tested with **testcontainers** (not mocks). Mocking the DB hides migration and query bugs.
- [ ] **Coverage meets the project threshold** — the project contract names the percentage (commonly 80% or 90%).
- [ ] **Audit-on-write check** — every write path in the slice emits a structured audit event in the **same transaction** as the write. Reviewer checks this explicitly; see `backend/19-audit-on-write`.
- [ ] **Authorization check** — every new route is guarded by a `require("<permission>")` dependency (or the project's equivalent). Owner bypass and 403 behavior verified.
- [ ] **Complexity cap** — every new function has cyclomatic complexity ≤ 10 (ruff `C90`). Functions over the limit are decomposed, not exempted.
