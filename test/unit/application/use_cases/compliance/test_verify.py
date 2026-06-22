import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.compliance_dto import AssessmentInputDto
from src.application.use_cases.compliance.verify import VerifyComplianceUseCase
from src.domain.entities.compliance import ComplianceCriterion


def _cmd_criterion(
    id: str = "backend/dod/lint-clean",
    stack: str = "backend",
    severity: str = "required",
    pass_pattern: str = r"All checks passed\.",
    fail_pattern: str = r"\d+ error",
) -> ComplianceCriterion:
    return ComplianceCriterion(
        id=id,
        guideline_slug="agile/05-dod-backend",
        stack=stack,
        text="Lint clean",
        category="code-quality",
        severity=severity,
        check_type="command",
        verification_hint="Run ruff",
        check_command="ruff check .",
        pass_pattern=pass_pattern,
        fail_pattern=fail_pattern,
    )


def _pattern_criterion(
    id: str = "backend/dod/auth-on-routes",
    stack: str = "backend",
    required_pattern: str | None = r"Depends\(",
    forbidden_pattern: str | None = None,
) -> ComplianceCriterion:
    return ComplianceCriterion(
        id=id,
        guideline_slug="agile/05-dod-backend",
        stack=stack,
        text="Auth on routes",
        category="security",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste route code",
        required_pattern=required_pattern,
        forbidden_pattern=forbidden_pattern,
    )


def _manual_criterion(id: str = "backend/dod/integration-testcontainers") -> ComplianceCriterion:
    return ComplianceCriterion(
        id=id,
        guideline_slug="agile/05-dod-backend",
        stack="backend",
        text="Integration uses testcontainers",
        category="testing",
        severity="required",
        check_type="manual",
        verification_hint="Provide conftest path",
    )


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


# ── command checks ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_pass_pattern_matches(mock_repo):
    mock_repo.get_all.return_value = [_cmd_criterion()]
    assessment = AssessmentInputDto(criterion_id="backend/dod/lint-clean", command_output="All checks passed.")

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.overall_status == "compliant"
    assert result.overall_score == 1.0
    backend = result.stacks["backend"]
    assert backend.passed == 1
    assert backend.results[0].validation == "automated"


@pytest.mark.asyncio
async def test_command_fail_pattern_takes_priority_over_pass(mock_repo):
    mock_repo.get_all.return_value = [_cmd_criterion()]
    # output that contains BOTH patterns — fail_pattern wins
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/lint-clean",
        command_output="All checks passed. But also 1 error found.",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.overall_status == "non-compliant"
    assert result.stacks["backend"].results[0].passed is False
    assert "fail_pattern matched" in result.stacks["backend"].results[0].reason


@pytest.mark.asyncio
async def test_command_no_match_is_fail(mock_repo):
    mock_repo.get_all.return_value = [_cmd_criterion()]
    assessment = AssessmentInputDto(criterion_id="backend/dod/lint-clean", command_output="some random output")

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.overall_status == "non-compliant"
    assert result.stacks["backend"].results[0].passed is False


# ── code_pattern checks ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_required_pattern_found_passes(mock_repo):
    mock_repo.get_all.return_value = [_pattern_criterion()]
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/auth-on-routes",
        code_snippet="def route(): return Depends(require_admin)",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["backend"].results[0].passed is True
    assert "required_pattern found" in result.stacks["backend"].results[0].reason


@pytest.mark.asyncio
async def test_required_pattern_missing_fails(mock_repo):
    mock_repo.get_all.return_value = [_pattern_criterion()]
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/auth-on-routes",
        code_snippet="def route(): return {'ok': True}",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["backend"].results[0].passed is False


@pytest.mark.asyncio
async def test_forbidden_pattern_absent_passes(mock_repo):
    mock_repo.get_all.return_value = [
        _pattern_criterion(required_pattern=None, forbidden_pattern=r"\bany\b")
    ]
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/auth-on-routes",
        code_snippet="const x: string = 'hello'",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["backend"].results[0].passed is True


@pytest.mark.asyncio
async def test_forbidden_pattern_present_fails(mock_repo):
    mock_repo.get_all.return_value = [
        _pattern_criterion(required_pattern=None, forbidden_pattern=r"\bany\b")
    ]
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/auth-on-routes",
        code_snippet="const x: any = getUser()",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["backend"].results[0].passed is False
    assert "forbidden_pattern found" in result.stacks["backend"].results[0].reason


# ── manual checks ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_with_evidence_and_passed_true(mock_repo):
    mock_repo.get_all.return_value = [_manual_criterion()]
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/integration-testcontainers",
        passed=True,
        evidence="conftest.py:L42 — PostgreSqlContainer",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    r = result.stacks["backend"].results[0]
    assert r.passed is True
    assert r.validation == "manual"
    assert "conftest.py" in r.reason


@pytest.mark.asyncio
async def test_manual_without_evidence_fails(mock_repo):
    mock_repo.get_all.return_value = [_manual_criterion()]
    assessment = AssessmentInputDto(
        criterion_id="backend/dod/integration-testcontainers",
        passed=True,
        evidence="",  # empty — should fail
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["backend"].results[0].passed is False


# ── scoring & status ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_required_failure_forces_non_compliant_regardless_of_score(mock_repo):
    # One pass (recommended) + one fail (required) → non-compliant even if score ≥ 0.5
    criteria = [
        _cmd_criterion(id="backend/dod/lint-clean", severity="required"),
        _cmd_criterion(id="backend/dod/format-clean", severity="recommended", pass_pattern=r"ok"),
    ]
    mock_repo.get_all.return_value = criteria
    assessments = [
        AssessmentInputDto(criterion_id="backend/dod/lint-clean", command_output="1 error"),
        AssessmentInputDto(criterion_id="backend/dod/format-clean", command_output="ok"),
    ]

    result = await VerifyComplianceUseCase(mock_repo).execute(assessments)

    assert result.overall_status == "non-compliant"


@pytest.mark.asyncio
async def test_partial_status_when_score_between_50_and_90(mock_repo):
    criteria = [
        _cmd_criterion(id=f"backend/dod/check-{i}", severity="recommended")
        for i in range(4)
    ]
    mock_repo.get_all.return_value = criteria
    # 2 pass, 2 fail → score = 0.5 → partial
    assessments = [
        AssessmentInputDto(criterion_id="backend/dod/check-0", command_output="All checks passed."),
        AssessmentInputDto(criterion_id="backend/dod/check-1", command_output="All checks passed."),
        AssessmentInputDto(criterion_id="backend/dod/check-2", command_output="1 error"),
        AssessmentInputDto(criterion_id="backend/dod/check-3", command_output="1 error"),
    ]

    result = await VerifyComplianceUseCase(mock_repo).execute(assessments)

    assert result.overall_status == "partial"
    assert result.overall_score == 0.5


# ── multi-stack ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_results_split_by_stack(mock_repo):
    mock_repo.get_all.return_value = [
        _cmd_criterion(id="backend/dod/lint-clean", stack="backend"),
        _cmd_criterion(id="frontend/dod/lint-clean", stack="frontend"),
    ]
    assessments = [
        AssessmentInputDto(criterion_id="backend/dod/lint-clean", command_output="All checks passed."),
        AssessmentInputDto(criterion_id="frontend/dod/lint-clean", command_output="All checks passed."),
    ]

    result = await VerifyComplianceUseCase(mock_repo).execute(assessments)

    assert "backend" in result.stacks
    assert "frontend" in result.stacks
    assert result.stacks["backend"].passed == 1
    assert result.stacks["frontend"].passed == 1


@pytest.mark.asyncio
async def test_stacks_filter_excludes_other_stacks(mock_repo):
    mock_repo.get_all.return_value = [
        _cmd_criterion(id="backend/dod/lint-clean", stack="backend"),
        _cmd_criterion(id="frontend/dod/lint-clean", stack="frontend"),
    ]
    assessments = [
        AssessmentInputDto(criterion_id="backend/dod/lint-clean", command_output="All checks passed."),
        AssessmentInputDto(criterion_id="frontend/dod/lint-clean", command_output="All checks passed."),
    ]

    result = await VerifyComplianceUseCase(mock_repo).execute(assessments, stacks=["backend"])

    assert "backend" in result.stacks
    assert "frontend" not in result.stacks


# ── unknown IDs ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_criterion_id_goes_to_unknown_ids(mock_repo):
    mock_repo.get_all.return_value = [_cmd_criterion()]
    assessments = [
        AssessmentInputDto(criterion_id="backend/dod/lint-clean", command_output="All checks passed."),
        AssessmentInputDto(criterion_id="backend/dod/nonexistent", command_output="x"),
    ]

    result = await VerifyComplianceUseCase(mock_repo).execute(assessments)

    assert "backend/dod/nonexistent" in result.unknown_ids


# ── edge cases ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_assessments_raises_value_error(mock_repo):
    mock_repo.get_all.return_value = []
    with pytest.raises(ValueError, match="assessments cannot be empty"):
        await VerifyComplianceUseCase(mock_repo).execute([])


@pytest.mark.asyncio
async def test_empty_snippet_fails_forbidden_only_check(mock_repo):
    # A caller that omits code_snippet on a forbidden-only criterion must not get a free pass.
    mock_repo.get_all.return_value = [
        _pattern_criterion(required_pattern=None, forbidden_pattern=r"\bany\b")
    ]
    assessment = AssessmentInputDto(criterion_id="backend/dod/auth-on-routes", code_snippet=None)

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["backend"].results[0].passed is False
    assert "no code snippet" in result.stacks["backend"].results[0].reason


@pytest.mark.asyncio
async def test_pass_pattern_anchored_to_whole_output_not_empty_line(mock_repo):
    # r"\A\s*\Z" must NOT match when output contains diagnostic lines alongside blank lines.
    criterion = ComplianceCriterion(
        id="frontend/dod/lint-clean",
        guideline_slug="agile/06-dod-frontend",
        stack="frontend",
        text="Lint clean",
        category="code-quality",
        severity="required",
        check_type="command",
        verification_hint="Run eslint",
        check_command="eslint .",
        pass_pattern=r"\A\s*\Z",
        fail_pattern=r"\d+ error",
    )
    mock_repo.get_all.return_value = [criterion]
    # Output has a blank line but also diagnostic content — must not pass.
    assessment = AssessmentInputDto(
        criterion_id="frontend/dod/lint-clean",
        command_output="src/app.ts: line 4 warning\n\n1 warning",
    )

    result = await VerifyComplianceUseCase(mock_repo).execute([assessment])

    assert result.stacks["frontend"].results[0].passed is False
