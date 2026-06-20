from mcp.server.fastmcp import FastMCP

from src.application.use_cases.metadata.get_metadata import GetMetadataUseCase
from src.infrastructure.repositories.example_repository import get_example_repository
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.logger import get_logger

_logger = get_logger("tools.metadata")


def register_metadata_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="get_metadata",
        description=(
            "Return a lightweight catalog of every available guideline and code example. "
            "Call this FIRST before any other tool. "
            "Each guideline entry includes its slug, stack ('backend'|'frontend'), title, "
            "and a one-paragraph summary so you can decide whether to fetch the full content. "
            "Each example entry includes its name, stack, layer, and description. "
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
        _logger.info(
            "tool=get_metadata returned guidelines=%d examples=%d",
            len(data.get("guidelines", [])),
            len(data.get("examples", [])),
        )
        return data
