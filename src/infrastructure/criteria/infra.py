from src.domain.entities.compliance import ComplianceCriterion

CRITERIA: list[ComplianceCriterion] = [
    # Makefile as gate (infra/04-makefile-as-gate)
    ComplianceCriterion(
        id="infra/makefile/help-target-exists",
        guideline_slug="infra/04-makefile-as-gate",
        stack="infra",
        text="Makefile has a self-documenting `help` target; `make help` is the onboarding entry point",
        category="makefile",
        severity="recommended",
        check_type="manual",
        verification_hint="Paste the relevant section of the project Makefile.",
    ),
]
