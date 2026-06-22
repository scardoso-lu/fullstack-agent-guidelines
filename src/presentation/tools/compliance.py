from mcp.server.fastmcp import FastMCP

from src.application.dto.compliance_dto import AssessmentInputDto
from src.application.use_cases.compliance.verify import VerifyComplianceUseCase
from src.infrastructure.repositories.criteria_repository import get_criteria_repository
from src.utils.logger import get_logger

_logger = get_logger("tools.compliance")


def register_compliance_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="verify_compliance",
        description=(
            "Verify that an implementation complies with the fullstack engineering guidelines. "
            "Submit one assessment per criterion you have checked. "
            "For 'command' criteria: provide command_output (stdout+stderr). "
            "For 'code_pattern' criteria: provide code_snippet (paste the relevant file or function). "
            "For 'manual' criteria: provide passed (bool) and evidence (specific file path or description). "
            "Returns per-stack compliance score (0–1), per-criterion pass/fail with the exact regex finding, "
            "and overall status ('compliant' | 'partial' | 'non-compliant'). "
            "Call get_metadata() first to get all criterion IDs, check_types, and verification hints."
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
