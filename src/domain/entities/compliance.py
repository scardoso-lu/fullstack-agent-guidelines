from dataclasses import dataclass

VALID_SEVERITIES: frozenset[str] = frozenset({"required", "recommended"})
VALID_CHECK_TYPES: frozenset[str] = frozenset({"command", "code_pattern", "manual"})


@dataclass(frozen=True)
class ComplianceCriterion:
    id: str               # "backend/dod/lint-clean"
    guideline_slug: str   # "agile/05-dod-backend"
    stack: str            # "backend" | "frontend" | "agile" | ...
    text: str
    category: str         # "code-quality" | "testing" | "security" | ...
    severity: str         # "required" | "recommended"
    check_type: str       # "command" | "code_pattern" | "manual"
    verification_hint: str
    check_command: str | None = None
    pass_pattern: str | None = None    # regex; output must match (after fail_pattern check)
    fail_pattern: str | None = None    # regex; output must NOT match (takes priority)
    required_pattern: str | None = None   # regex; code snippet must contain this
    forbidden_pattern: str | None = None  # regex; code snippet must NOT contain this

    @staticmethod
    def _mock(
        id: str = "backend/dod/lint-clean",
        stack: str = "backend",
        check_type: str = "command",
    ) -> "ComplianceCriterion":
        return ComplianceCriterion(
            id=id,
            guideline_slug="agile/05-dod-backend",
            stack=stack,
            text="Mock criterion",
            category="code-quality",
            severity="required",
            check_type=check_type,
            verification_hint="Run the check and provide output",
            check_command="ruff check ." if check_type == "command" else None,
            pass_pattern=r"All checks passed\." if check_type == "command" else None,
            fail_pattern=r"\d+ error" if check_type == "command" else None,
        )


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    text: str
    category: str
    severity: str
    passed: bool
    validation: str  # "automated" | "manual"
    reason: str      # what the regex matched, or the evidence provided
