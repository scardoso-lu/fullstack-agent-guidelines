from src.application.dto import BaseSchema


class WorkflowStepDto(BaseSchema):
    criterion_id: str
    text: str
    severity: str
    action: str        # "run_command" | "provide_code_snippet" | "provide_evidence"
    command: str | None
    instruction: str
    submit: dict       # exact JSON shape the agent fills and passes to verify_compliance


class WorkflowDto(BaseSchema):
    stack: str
    steps: list[WorkflowStepDto]
    next_step: str


class AssessmentInputDto(BaseSchema):
    criterion_id: str
    # command-type fields
    command_output: str | None = None
    exit_code: int | None = None
    # code_pattern-type fields
    code_snippet: str | None = None
    # manual-type fields
    passed: bool | None = None
    evidence: str = ""


class CriterionResultDto(BaseSchema):
    criterion_id: str
    text: str
    category: str
    severity: str
    passed: bool
    validation: str  # "automated" | "manual"
    reason: str


class StackReportDto(BaseSchema):
    stack: str
    score: float
    status: str  # "compliant" | "partial" | "non-compliant"
    passed: int
    failed: int
    results: list[CriterionResultDto]


class ComplianceReportDto(BaseSchema):
    overall_score: float
    overall_status: str  # "compliant" | "partial" | "non-compliant"
    stacks: dict[str, StackReportDto]
    unknown_ids: list[str]
