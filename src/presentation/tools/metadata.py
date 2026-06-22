from mcp.server.fastmcp import FastMCP

from src.application.use_cases.metadata.get_metadata import GetMetadataUseCase
from src.infrastructure.repositories.criteria_repository import get_criteria_repository
from src.infrastructure.repositories.example_repository import get_example_repository
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.logger import get_logger

_logger = get_logger("tools.metadata")


def register_metadata_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_metadata",
        description=(
            "Return a lightweight catalog of every available guideline, code example, and compliance criterion. "
            "Call this FIRST before any other tool. "
            "Each guideline entry includes its slug, stack ('backend'|'frontend'), title, "
            "and a one-paragraph summary so you can decide whether to fetch the full content. "
            "Each example entry includes its name, stack, layer, and description. "
            "Each compliance criterion includes its id, stack, severity, check_type, and verification_hint — "
            "use these ids when calling verify_compliance(). "
            "Use get_guideline(slug) or get_example(name) to fetch full content on demand."
        ),
    )
    async def get_metadata() -> dict:
        _logger.info("tool=get_metadata")
        use_case = GetMetadataUseCase(
            guideline_repo=get_guideline_repository(),
            example_repo=get_example_repository(),
        )
        result = await use_case.execute()
        data = result.model_dump()

        criteria = await get_criteria_repository().get_all()
        criteria_by_stack: dict[str, list[dict]] = {}
        for c in criteria:
            criteria_by_stack.setdefault(c.stack, []).append({
                "id": c.id,
                "text": c.text,
                "category": c.category,
                "severity": c.severity,
                "check_type": c.check_type,
                "verification_hint": c.verification_hint,
            })
        data["compliance_criteria"] = criteria_by_stack

        _logger.info(
            "tool=get_metadata returned guidelines=%d examples=%d criteria=%d",
            len(data.get("guidelines", [])),
            len(data.get("examples", [])),
            len(criteria),
        )
        return data
