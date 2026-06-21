# Code Review — A Reviewer's Checklist

Use when reviewing a PR, when authoring code with future-review in mind, or when calibrating what the team's reviewers are expected to catch. Defines the **correctness-first** posture (does the code do what the ticket says?), the order in which a reviewer reads a diff, the categories of findings, and the etiquette that keeps review productive (severity-tagged comments, one round-trip per concern, no bikeshedding).

Code review is not lint. The linter and the type-checker handle mechanical correctness; the reviewer handles *substantive* correctness — does this diff actually implement the ticket, does it match the project's architecture, will it survive next week's rebase. A slice that lints clean and passes tests can still fail review.

## Read order — body first, diff second

A reviewer should read the PR in this order. Each step is a chance to bail out early if something is wrong:

1. **PR description.** What ticket, what user story, what slice. If the description is empty or vague, ask for one before reviewing the diff — the diff alone can't tell you whether the slice solves the right problem.
2. **The ticket / acceptance criteria.** Open the linked ticket. The diff must implement those criteria — no more, no less.
3. **The commits.** A slice committed incrementally along the layers (see `agile/03-conventional-commits`) reads as a logical progression. Out-of-order or "WIP" commits are a yellow flag.
4. **The diff itself.** Now go layer-by-layer in the same order as the slice: domain → application → infrastructure → presentation → frontend → tests.

If the slice has no tests for the new behavior, **stop reviewing the implementation** — the missing tests are the first finding. Reviewing untested code wastes effort because the implementation is likely to change.

## What the reviewer looks for

In rough priority order:

### 1. Does it match the ticket?

- Every acceptance criterion is implemented.
- No undeclared scope additions — a route/table/env var/UI affordance with no ticket/criterion tied to it.
- The "why" in the PR matches the "what" of the diff.

### 2. Does it match the architecture?

- Layering is respected (domain has no framework imports; routes are thin; use-cases own orchestration).
- New code reuses existing seams (repository interface, base use-case, DI provider) rather than reinventing them.
- A decision that should be in an ADR isn't being made silently in the diff.

### 3. Correctness bugs

- Off-by-one, wrong default, swapped argument order, missing `await`, race condition.
- Error paths — exceptions raised in the right layer, mapped to the right HTTP status, not swallowed.
- Edge cases the tests don't cover: empty inputs, large inputs, concurrent calls, retries.

### 4. The cross-cutting hard rules

- **Audit on every write.** A new write path with no audit event is a block (see `backend/19-audit-on-write`).
- **Authz on every new route.** `require("<permission>")` (or the project's equivalent) is present.
- **Tenant isolation.** Every tenant-scoped query filters on the tenant key.
- **No secrets in code, logs, or commits.**
- **Complexity ≤ 10** — a function over the cap is decomposed, not exempted.
- **Strong typing.** No silent `any` / `# type: ignore` without a one-line justification.

### 5. Simplicity & reuse

- Did the slice **rewrite** something it could have **reused**? Repository methods, hooks, components, utility functions — check first.
- Did it add an abstraction (factory, plugin point, generic config) without a second consumer? See the rework-clean guideline for both stacks. Three similar lines is better than a premature abstraction.
- Did it add backwards-compatibility shims for code that isn't called?

### 6. Tests

- Unit tests cover each branch of the use-case.
- Integration tests use a real DB (testcontainers), not mocks of the DB.
- E2E exists for every new user-facing variant (see `qa/02-e2e-per-feature`).
- Tests assert **external behavior**, not implementation details.
- Test names describe the scenario in English, not the assertions.

### 7. Observability

- Logs go through the shared structured logger; no `print` / `console.log`.
- One structured event per use-case boundary, not on every internal step.
- No secrets or PII in log messages.
- Log level matches intent (see `backend/18-observability-logging`).

### 8. Documentation

- ADRs cited in the PR are still accurate.
- ERD refreshed if a model / FK / constraint changed (soft check).
- A non-trivial new flow gets a Mermaid diagram in the relevant doc (soft check).

## How to leave comments

**Tag the severity** so the author knows what blocks:

- **`block:`** — must fix before merge. Bugs, security issues, missing audit, undeclared scope, broken tests.
- **`question:`** — I don't understand; please explain or amend. Resolves with either a change or an answer.
- **`suggest:`** — I'd do it differently; non-blocking. Author chooses.
- **`nit:`** — typo, style, microscopic. Never blocking. The lint/format gate is the source of truth for style — if the linter doesn't catch it, it's the author's choice.

The first three rotate the PR back to the author. `nit:` does not — bundle them or skip.

## Etiquette

- **One round-trip per concern.** Don't drip-feed comments across days. Read the whole diff, then comment.
- **Suggest concretely.** "Could you extract this?" is weaker than "Extract lines 23–48 into `<helper>` because it's used twice — see `<file>:<line>`." Concrete suggestions get acted on; vague ones get debated.
- **Ask before refactoring scope.** "Could we also refactor X?" — almost always no, file a separate ticket. The slice's job is to ship the slice.
- **Acknowledge what's good.** A PR that's well-shaped gets a one-line "this is clean, two questions below" so the author knows the bulk of it landed.
- **Reviewer SLA.** Pick one (24h, 48h) and hold to it. PRs that sit unread for a week erode the loop.

## Reviewer doesn't write the fix

The reviewer **routes** findings; the **owning layer** fixes them. Backend bug → backend engineer; missing E2E → frontend (sometimes test) engineer; security block → owning layer + security re-verifies. Reviewers who fix bugs in the diff bypass the author's understanding and the gate's accountability.

## What the reviewer does NOT do

- **Lint, format, type-check.** The CI gate does this. If a reviewer is leaving formatting comments, the gate is misconfigured.
- **Re-run the test suite by hand.** CI does this. The reviewer reads test results, not test output.
- **Decide architecture.** A non-trivial structural decision belongs in a written decision record, not inside a feature PR. If the diff makes an architectural decision silently, the block is "this needs to be locked as a decision before merging," not "rewrite it this way."

## A green review

A PR is approved when:

- Every acceptance criterion is implemented and tested.
- No `block:` comments remain.
- The cross-cutting hard rules pass (audit, authz, tenant isolation, secrets, complexity, typing).
- The DoD gate is green in CI (see `agile/02-definition-of-done`).
- The security verification has no open Critical/High findings (see `qa/02-security-review-process`).

Anything less is "approved with comments" — which doesn't exist. Either it's mergeable, or it's not.
