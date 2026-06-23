from src.domain.entities.compliance import ComplianceCriterion

CRITERIA: list[ComplianceCriterion] = [
    # ── Code review gates (qa/01-code-review) ───────────────────────────────
    ComplianceCriterion(
        id="qa/review/pr-description-filled",
        guideline_slug="qa/01-code-review",
        stack="qa",
        text="PR description states the ticket ID, user story, and slice scope — not empty or vague",
        category="code-review",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm the PR description includes: (1) ticket/issue reference, "
            "(2) what user story it implements, (3) which files/layers are in scope. "
            "Paste the first two sentences of the PR description."
        ),
    ),
    ComplianceCriterion(
        id="qa/review/tests-exist-before-review",
        guideline_slug="qa/01-code-review",
        stack="qa",
        text="Tests for new behavior exist before implementation review — reviewing untested code is a block",
        category="code-review",
        severity="required",
        check_type="manual",
        verification_hint=(
            "List every test file and test name that covers behavior introduced by this slice. "
            "If no tests exist yet, this is a block — the slice goes back to the author."
        ),
    ),
    ComplianceCriterion(
        id="qa/review/no-undeclared-scope",
        guideline_slug="qa/01-code-review",
        stack="qa",
        text="No undeclared scope — every new route/table/env var/UI affordance maps to an acceptance criterion",
        category="code-review",
        severity="required",
        check_type="manual",
        verification_hint=(
            "For each new file, route, DB column, or env var in the diff, "
            "confirm it is tied to a ticket acceptance criterion. "
            "List any additions that have no ticket reference."
        ),
    ),
    ComplianceCriterion(
        id="qa/review/no-print-console-log",
        guideline_slug="qa/01-code-review",
        stack="qa",
        text="No print() or console.log() in production paths — all output goes through the structured logger",
        category="observability",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the new/modified source files (exclude test files)",
        forbidden_pattern=r"\bprint\s*\(|console\.log\s*\(",
    ),
    ComplianceCriterion(
        id="qa/review/complexity-review",
        guideline_slug="qa/01-code-review",
        stack="qa",
        text="No new function exceeds cyclomatic complexity 10 — over-limit functions are decomposed, not exempted",
        category="code-quality",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm that no function introduced by this slice exceeds cyclomatic complexity 10. "
            "If using ruff, run `ruff check . --select C90` and paste the output."
        ),
    ),
    # ── E2E-per-feature gate (qa/02-e2e-per-feature) ────────────────────────
    ComplianceCriterion(
        id="qa/e2e/new-variant-covered",
        guideline_slug="qa/02-e2e-per-feature",
        stack="qa",
        text="Every new user-facing flow and rendered variant ships at least one Playwright E2E",
        category="testing",
        severity="required",
        check_type="manual",
        verification_hint=(
            "List every new user-facing flow and rendered variant introduced by this slice. "
            "For each, provide the Playwright test file path and test name that exercises it."
        ),
    ),
    ComplianceCriterion(
        id="qa/e2e/role-based-selectors",
        guideline_slug="qa/02-e2e-per-feature",
        stack="qa",
        text="E2E selectors use getByRole / getByText / getByLabel — not CSS classes or arbitrary data-testid",
        category="testing",
        severity="recommended",
        check_type="code_pattern",
        verification_hint="Paste the Playwright E2E test file(s) introduced in this slice",
        required_pattern=r"getByRole\s*\(|getByText\s*\(|getByLabel\s*\(",
    ),
    ComplianceCriterion(
        id="qa/e2e/no-sleep",
        guideline_slug="qa/02-e2e-per-feature",
        stack="qa",
        text="E2E tests use Playwright auto-waiting — no waitForTimeout() or setTimeout() sleep calls",
        category="testing",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the Playwright E2E test file(s) introduced in this slice",
        forbidden_pattern=r"waitForTimeout\s*\(|setTimeout\s*\(",
    ),
    ComplianceCriterion(
        id="qa/e2e/one-flow-per-test",
        guideline_slug="qa/02-e2e-per-feature",
        stack="qa",
        text="Each Playwright test exercises one flow — no mega-E2E that chains multiple unrelated user actions",
        category="testing",
        severity="recommended",
        check_type="manual",
        verification_hint=(
            "Confirm that each test function covers exactly one user flow or rendered variant. "
            "Provide the test names and a one-line description of what each one exercises."
        ),
    ),
]
