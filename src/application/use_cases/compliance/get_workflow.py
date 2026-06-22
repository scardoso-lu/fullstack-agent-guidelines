from src.application.dto.compliance_dto import WorkflowDto, WorkflowStepDto
from src.domain.entities.guideline import VALID_STACKS
from src.infrastructure.repositories.contract import CriteriaRepositoryInterface
from src.utils.logger import get_logger

_logger = get_logger("use_case.get_compliance_workflow")

_SUBMIT_TEMPLATES: dict[str, dict] = {
    "command": {"criterion_id": "<criterion_id>", "command_output": "<paste full stdout+stderr>", "exit_code": 0},
    "code_pattern": {"criterion_id": "<criterion_id>", "code_snippet": "<paste relevant code>"},
    "manual": {"criterion_id": "<criterion_id>", "passed": True, "evidence": "<path:line — description>"},
}

_ACTIONS: dict[str, str] = {
    "command": "run_command",
    "code_pattern": "provide_code_snippet",
    "manual": "provide_evidence",
}


class GetComplianceWorkflowUseCase:
    def __init__(self, repo: CriteriaRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, stack: str) -> WorkflowDto:
        if not stack or stack not in VALID_STACKS:
            raise ValueError(f"Invalid stack {stack!r}. Valid stacks: {sorted(VALID_STACKS)}")

        criteria = await self.repo.get_by_stack(stack)
        _logger.info("get_compliance_workflow stack=%r criteria=%d", stack, len(criteria))

        steps: list[WorkflowStepDto] = []
        for criterion in criteria:
            template = dict(_SUBMIT_TEMPLATES[criterion.check_type])
            template["criterion_id"] = criterion.id

            instruction = criterion.verification_hint
            command: str | None = None
            if criterion.check_type == "command":
                command = criterion.check_command

            steps.append(WorkflowStepDto(
                criterion_id=criterion.id,
                text=criterion.text,
                severity=criterion.severity,
                action=_ACTIONS[criterion.check_type],
                command=command,
                instruction=instruction,
                submit=template,
            ))

        return WorkflowDto(
            stack=stack,
            steps=steps,
            next_step=(
                "Fill each submit object above with real values, replacing placeholders. "
                "Then call verify_compliance(assessments=[<filled submit objects>])."
            ),
        )
