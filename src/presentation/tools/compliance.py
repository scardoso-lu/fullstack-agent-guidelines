from mcp.server.fastmcp import FastMCP

from src.application.dto.compliance_dto import AssessmentInputDto
from src.application.use_cases.compliance.generate_table import GenerateComplianceTableUseCase
from src.application.use_cases.compliance.get_workflow import GetComplianceWorkflowUseCase
from src.application.use_cases.compliance.validate_table import ValidateComplianceTableUseCase
from src.application.use_cases.compliance.verify import VerifyComplianceUseCase
from src.infrastructure.repositories.criteria_repository import get_criteria_repository
from src.utils.logger import get_logger

_logger = get_logger("tools.compliance")


def register_compliance_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_compliance_workflow",
        description=(
            "Get a step-by-step checklist to help assess whether an implementation aligns with "
            "the fullstack engineering guidelines for a given stack ('backend', 'frontend', or 'agile'). "
            "This is an additional aid for structured self-review — not an authoritative audit. "
            "Results indicate alignment with the encoded criteria and should be treated as a "
            "starting point for human review, not a definitive compliance verdict. "
            "Returns one step per criterion with: the action to take "
            "(run_command / provide_code_snippet / provide_evidence), "
            "the command to run (for command checks), a plain-English instruction, "
            "and a pre-filled submit object showing the JSON shape expected by verify_compliance(). "
            "Replace placeholders with real values, then call verify_compliance(assessments=[...])."
        ),
    )
    async def get_compliance_workflow(stack: str) -> dict:
        _logger.info("tool=get_compliance_workflow stack=%r", stack)
        try:
            use_case = GetComplianceWorkflowUseCase(get_criteria_repository())
            result = await use_case.execute(stack)
            data = result.model_dump()
            _logger.info("tool=get_compliance_workflow stack=%r steps=%d", stack, len(data["steps"]))
            return data
        except ValueError as exc:
            _logger.warning("tool=get_compliance_workflow stack=%r error=%r", stack, str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="verify_compliance",
        description=(
            "Score the evidence collected via get_compliance_workflow() against the encoded criteria. "
            "This is a supplementary self-assessment tool — results reflect alignment with the "
            "regex-based criteria defined here and are not a substitute for human code review. "
            "Submit one assessment per criterion: "
            "For 'command' criteria: provide command_output (stdout+stderr). "
            "For 'code_pattern' criteria: provide code_snippet (paste the relevant file or function). "
            "For 'manual' criteria: provide passed (bool) and evidence (specific file path or description). "
            "Returns per-stack score (0–1), per-criterion pass/fail with the exact finding, "
            "and an indicative status ('compliant' | 'partial' | 'non-compliant') to guide review."
        ),
    )
    async def verify_compliance(
        assessments: list[dict],
        stacks: list[str] | None = None,
    ) -> dict:
        _logger.info(
            "tool=verify_compliance assessments=%d stacks=%r",
            len(assessments),
            stacks,
        )
        try:
            parsed = [AssessmentInputDto(**a) for a in assessments]
            use_case = VerifyComplianceUseCase(get_criteria_repository())
            result = await use_case.execute(parsed, stacks)
            data = result.model_dump()
            _logger.info(
                "tool=verify_compliance overall_score=%.4f overall_status=%r",
                data["overall_score"],
                data["overall_status"],
            )
            return data
        except (ValueError, TypeError) as exc:
            _logger.warning("tool=verify_compliance error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="generate_compliance_table",
        description=(
            "Generate a Guidelines Compliance Report as a markdown document, ready to post "
            "as a GitHub PR comment. Evaluates every criterion against the provided assessments "
            "and renders a summary table plus per-stack collapsible detail sections. "
            "Assessments follow the same format as verify_compliance(): each item needs a "
            "criterion_id plus the relevant payload (command_output for command checks, "
            "code_snippet for code-pattern checks, or passed+evidence for manual checks). "
            "Omit assessments or pass an empty list to produce a fully-pending table that "
            "shows all criteria awaiting evaluation. "
            "Returns { table: '<markdown string>' } bounded by "
            "<!-- compliance-table-start --> / <!-- compliance-table-end --> markers."
        ),
    )
    async def generate_compliance_table(
        assessments: list[dict] | None = None,
    ) -> dict:
        items = assessments or []
        _logger.info("tool=generate_compliance_table assessments=%d", len(items))
        try:
            use_case = GenerateComplianceTableUseCase(get_criteria_repository())
            result = await use_case.execute(items)
            _logger.info("tool=generate_compliance_table table_len=%d", len(result.table))
            return result.model_dump()
        except Exception as exc:
            _logger.warning("tool=generate_compliance_table error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_compliance_table",
        description=(
            "Validate that a compliance table markdown document is correctly formatted. "
            "Checks: start/end HTML comment markers, required heading, all expected stacks "
            "listed in the summary table, and at least one score column. "
            "Returns { valid: bool, errors: list[str] }. "
            "Use after generate_compliance_table() to confirm output integrity, "
            "or before posting a manually-edited table as a PR comment."
        ),
    )
    async def validate_compliance_table(table: str) -> dict:
        _logger.info("tool=validate_compliance_table table_len=%d", len(table))
        try:
            use_case = ValidateComplianceTableUseCase(get_criteria_repository())
            result = await use_case.execute(table)
            _logger.info(
                "tool=validate_compliance_table valid=%r errors=%d",
                result.valid,
                len(result.errors),
            )
            return result.model_dump()
        except Exception as exc:
            _logger.warning("tool=validate_compliance_table error=%r", str(exc))
            return {"error": str(exc)}
