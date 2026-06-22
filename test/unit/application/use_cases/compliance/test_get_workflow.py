import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.compliance.get_workflow import GetComplianceWorkflowUseCase
from src.domain.entities.compliance import ComplianceCriterion


def _cmd_criterion(id: str = "backend/dod/lint-clean", stack: str = "backend") -> ComplianceCriterion:
    return ComplianceCriterion(
        id=id,
        guideline_slug="agile/05-dod-backend",
        stack=stack,
        text="Lint clean",
        category="code-quality",
        severity="required",
        check_type="command",
        verification_hint="Run `ruff check .` and paste the full output",
        check_command="ruff check .",
        pass_pattern=r"All checks passed\.",
        fail_pattern=r"\d+ error",
    )


def _pattern_criterion(id: str = "backend/dod/auth-on-routes") -> ComplianceCriterion:
    return ComplianceCriterion(
        id=id,
        guideline_slug="agile/05-dod-backend",
        stack="backend",
        text="Auth on routes",
        category="security",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the FastAPI route handler(s)",
        required_pattern=r"Depends\(",
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
        verification_hint="Provide the conftest.py path and fixture name",
    )


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_stack = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_valid_stack_returns_one_step_per_criterion(mock_repo):
    mock_repo.get_by_stack.return_value = [_cmd_criterion(), _pattern_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    assert result.stack == "backend"
    assert len(result.steps) == 2
    mock_repo.get_by_stack.assert_called_once_with("backend")


@pytest.mark.asyncio
async def test_command_step_has_run_command_action_and_command_field(mock_repo):
    mock_repo.get_by_stack.return_value = [_cmd_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    step = result.steps[0]
    assert step.action == "run_command"
    assert step.command == "ruff check ."
    assert step.criterion_id == "backend/dod/lint-clean"


@pytest.mark.asyncio
async def test_command_step_submit_contains_command_output_and_exit_code_keys(mock_repo):
    mock_repo.get_by_stack.return_value = [_cmd_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    submit = result.steps[0].submit
    assert "command_output" in submit
    assert "exit_code" in submit
    assert submit["criterion_id"] == "backend/dod/lint-clean"


@pytest.mark.asyncio
async def test_code_pattern_step_has_provide_code_snippet_action(mock_repo):
    mock_repo.get_by_stack.return_value = [_pattern_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    step = result.steps[0]
    assert step.action == "provide_code_snippet"
    assert step.command is None
    assert "code_snippet" in step.submit


@pytest.mark.asyncio
async def test_manual_step_has_provide_evidence_action(mock_repo):
    mock_repo.get_by_stack.return_value = [_manual_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    step = result.steps[0]
    assert step.action == "provide_evidence"
    assert "passed" in step.submit
    assert "evidence" in step.submit


@pytest.mark.asyncio
async def test_step_instruction_matches_verification_hint(mock_repo):
    criterion = _cmd_criterion()
    mock_repo.get_by_stack.return_value = [criterion]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    assert result.steps[0].instruction == criterion.verification_hint


@pytest.mark.asyncio
async def test_next_step_message_references_verify_compliance(mock_repo):
    mock_repo.get_by_stack.return_value = [_cmd_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    assert "verify_compliance" in result.next_step


@pytest.mark.asyncio
async def test_empty_stack_returns_empty_steps(mock_repo):
    mock_repo.get_by_stack.return_value = []

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("frontend")

    assert result.steps == []
    assert result.stack == "frontend"


@pytest.mark.asyncio
async def test_invalid_stack_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Invalid stack"):
        await GetComplianceWorkflowUseCase(mock_repo).execute("nonexistent")

    mock_repo.get_by_stack.assert_not_called()


@pytest.mark.asyncio
async def test_step_severity_matches_criterion(mock_repo):
    mock_repo.get_by_stack.return_value = [_cmd_criterion()]

    result = await GetComplianceWorkflowUseCase(mock_repo).execute("backend")

    assert result.steps[0].severity == "required"
