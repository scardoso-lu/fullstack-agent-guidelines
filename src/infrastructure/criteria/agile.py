from src.domain.entities.compliance import ComplianceCriterion

CRITERIA: list[ComplianceCriterion] = [
    ComplianceCriterion(
        id="agile/dod/conventional-commits",
        guideline_slug="agile/03-conventional-commits",
        stack="agile",
        text="Commit messages follow Conventional Commits format (type(scope): description)",
        category="process",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the commit message(s) from this slice",
        required_pattern=(
            r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)"
            r"(\([^)]+\))?!?:\s+\S"
        ),
    ),
    ComplianceCriterion(
        id="agile/dod/security-no-critical-findings",
        guideline_slug="agile/07-dod-security",
        stack="agile",
        text="No open Critical or High findings across SAST, CVEs, image scan, and secrets scan",
        category="security",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Provide the output or link to the security scan results "
            "(e.g. `bandit -r src/` output, `safety check` output, Trivy image scan summary). "
            "Confirm no Critical or High severity findings are present."
        ),
    ),
    ComplianceCriterion(
        id="agile/dod/security-report-exists",
        guideline_slug="agile/07-dod-security",
        stack="agile",
        text="Per-ticket security report exists at the project's security-report location",
        category="security",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Provide the path to the security report file "
            "(e.g. `docs/security/<ticket>.md`) and confirm it exists and is complete."
        ),
    ),
    ComplianceCriterion(
        id="agile/dod/security-guidance-honored",
        guideline_slug="agile/07-dod-security",
        stack="agile",
        text="Slice honored the security guidance set at slice start (threat model and secure-coding requirements)",
        category="security",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm the threat model and secure-coding requirements defined at slice start were followed. "
            "Provide a brief summary of the security requirements and how each was addressed in the implementation."
        ),
    ),
]
