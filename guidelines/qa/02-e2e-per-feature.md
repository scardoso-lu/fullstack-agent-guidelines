# E2E-per-Feature — Every New Variant Gets a Playwright Walk

Use when writing or reviewing tests for a slice with a user-facing change. Defines the **hard rule** that every new user-facing flow or rendered variant gets at least one Playwright E2E that opens the page, performs the action, and asserts the result *renders*, plus the rationale (unit/integration green is not sufficient — one per-action render crash will eventually ship if E2E never opens the page for the new state).

Unit tests verify functions. Integration tests verify routes + DB. **Only E2E verifies that the user can actually use the feature.** A slice without an E2E for its new variant will eventually ship a render crash — the unit and integration suites stay green because no test ever opens the page for the new state.

## The rule (hard gate)

> Every **new user-facing flow** the slice implements MUST ship **at least one Playwright E2E** that walks its flow end-to-end:
>
> 1. Open the page (signed in if required).
> 2. Perform the action(s).
> 3. Assert the result *renders* (the new content/state/affordance is visible).
>
> AND every **new rendered variant** the slice introduces (new lifecycle action, status, tab, enum value, role-conditional widget) MUST be exercised by **at least one E2E** — even if "exercising" means opening the page with the new state present and asserting it renders without error.
>
> A new feature with no E2E, or a new rendered variant with no E2E touching it, is a **DoD BLOCK**.

This applies regardless of how thorough the unit and integration tests are. They're necessary; they're not sufficient.

## Why this rule exists

The motivating bug, in every codebase that doesn't have this rule: a new status (say, `archived`) is added to a dataset enum. The backend tests pass. The status filter on the dataset list renders correctly. But the *detail page* for an archived dataset throws on render because a sub-component assumes the status is always one of the previous values — and no test ever opens the detail page for an archived dataset.

The bug is invisible until a real user clicks on an archived dataset in production. The fix is mechanical (one branch in a switch); the cost is the outage.

E2E-per-variant catches this class of bug for free, because the test forces the page to render with the new state.

## What counts as a "new variant"

Anything the UI renders **conditionally** that didn't exist before:

- **New lifecycle action** — `archive`, `restore`, `publish`, `deprecate`. Each gets an E2E that triggers it.
- **New status / enum** — `draft`, `archived`, `failed`. Each gets an E2E that opens a page where this status is visible.
- **New tab / route / page** — visit it, assert it renders.
- **New role-conditional widget** — sign in as each role for which the widget renders/hides; assert each case.
- **New empty state / loading state / error state** — each is a render path; each needs an E2E (or at least a Playwright component test if your project has that seam).
- **New form field** — fill, submit, assert the result.

If the engineer wonders "does this count as a new variant?" → it does. The cost of adding an extra E2E is small; the cost of a missing one is the next outage.

## Test shape

A good E2E is **short** and asserts **what the user sees**, not implementation details:

```ts
test("admin can archive a dataset", async ({ page, login }) => {
  await login({ role: "admin" });
  await page.goto("/datasets/123");

  await page.getByRole("button", { name: "Archive" }).click();
  await page.getByRole("button", { name: "Confirm archive" }).click();

  await expect(page.getByText("Dataset archived")).toBeVisible();
  await expect(page.getByRole("button", { name: "Restore" })).toBeVisible();
});
```

Three things this gets right:

1. **Selectors are role-based** (`getByRole`), not CSS class names. CSS changes shouldn't break tests.
2. **Assertions are user-visible** — a banner, a button. Not "the DOM has a `<div data-state="archived">`".
3. **One flow per test** — archive, not "archive then restore then delete". Each gets its own test.

## Test shape — assert it renders, even when there's no action

For a new rendered variant without an action (a new status badge, an empty state), the E2E can be very small:

```ts
test("archived dataset renders without crashing", async ({ page, login }) => {
  await login({ role: "admin" });
  await page.goto("/datasets/archived-123");
  await expect(page.getByText("Archived")).toBeVisible();
});
```

This catches the entire class of "renders crash because a sub-component doesn't handle the new state" bugs. The seed data / fixture provides the archived state; the test just opens the page.

## Where the tests live

- One file per **feature** or **flow** (`datasets-archive.spec.ts`, `password-reset.spec.ts`), not per page.
- Co-locate with the feature when the project supports it (`frontend/src/features/<feature>/e2e/`); otherwise a flat `e2e/` directory keyed by feature.
- Fixtures (logged-in user, seeded data) are factored into a `playwright.fixtures.ts` so tests don't reinvent setup.

## What does NOT replace E2E

- **Storybook stories.** Useful for design review; they don't exercise the page's data wiring.
- **Component tests in Vitest with JSDOM.** Don't catch real-browser bugs (layout, hydration, navigation).
- **Integration tests on the backend.** They verify the API contract; they don't render anything.
- **Manual smoke tests.** Don't scale, can't gate, and "I clicked through it" is not auditable.

These all have their place; none of them removes the E2E requirement.

## Cost control — keep the suite fast

The hard rule produces a growing E2E suite, which has to stay maintainable:

- **Parallelize.** Playwright workers, sharded across CI runners.
- **Reuse storage state.** Log in once per role, save cookies, reuse across tests.
- **Seed via API or factory, not via the UI.** Tests that "go through the login form" to set up state are slow and brittle — log in via API and inject the cookie.
- **No `sleep`.** Use Playwright's auto-waiting (`expect(locator).toBeVisible()`); never `await page.waitForTimeout(2000)`. Sleeps are flake.
- **Trace on first failure, not always.** `trace: 'on-first-retry'` keeps the artifact volume down.

A 50-test E2E suite that runs in 5 minutes is healthy. A 50-test suite that runs in 40 minutes is on its way to being skipped.

## Flake is a finding

A flaky E2E is **not** "an E2E with intermittent value." It's a finding that something — the test, the app, or the seed — is non-deterministic. Treat it like a Sev-2 bug:

- **Quarantine** the test (skip with a tag) so it stops blocking CI.
- **File a ticket** to fix the underlying non-determinism.
- **Fix before the slice's flake budget is exceeded** — e.g. ≤ 3 quarantined tests at any time.

Skipping flaky tests permanently without a ticket erodes trust in the entire gate.

## Authoring & ownership

- The **test engineer** writes most E2E. The **frontend engineer** writes the testability seams (data-testid where role queries are insufficient, deterministic IDs in fixtures, predictable URLs).
- A slice without an E2E goes back to the test engineer (and frontend engineer if a seam is missing) before it can merge.
- The **QA reviewer** confirms E2E coverage at the gate — every new variant has at least one test touching it.

## Anti-patterns

- **"It's covered by unit tests."** Doesn't matter for this rule. The render path is what's being tested.
- **"E2E is slow, we'll add it later."** Later never comes; the next outage does.
- **One mega-E2E that walks every flow.** Brittle, slow, useless when it fails. One flow per test.
- **E2E that asserts on internal IDs.** Tests fail every time the database is reseeded. Assert on what the user sees.
- **E2E that uses `page.evaluate` to poke React state.** That's a unit test in disguise; rewrite to drive the UI.
