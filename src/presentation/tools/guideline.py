from mcp.server.fastmcp import FastMCP

from src.application.use_cases.guideline.get_all_context import GetAllContextUseCase
from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.application.use_cases.guideline.list_all import ListGuidelinesUseCase
from src.application.use_cases.guideline.search import SearchGuidelinesUseCase
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.exc import NotFoundError


def register_guideline_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_guidelines",
        description="List all available architecture guideline topics with their slugs and tags.",
    )
    async def list_guidelines() -> dict:
        use_case = ListGuidelinesUseCase(get_guideline_repository())
        result = await use_case.execute()
        return result.model_dump()

    @mcp.tool(
        name="get_guideline",
        description=(
            "Retrieve the full Markdown content of a specific guideline by its slug "
            "(e.g. '03-application-layer'). Call list_guidelines first to see available slugs."
        ),
    )
    async def get_guideline(slug: str) -> dict:
        try:
            use_case = GetGuidelineBySlugUseCase(get_guideline_repository())
            result = await use_case.execute(slug)
            return result.model_dump()
        except NotFoundError as exc:
            return {"error": str(exc), "slug": slug}

    @mcp.tool(
        name="search_guidelines",
        description="Search guidelines by keyword. Searches titles, content, and tags.",
    )
    async def search_guidelines(query: str) -> dict:
        use_case = SearchGuidelinesUseCase(get_guideline_repository())
        result = await use_case.execute(query)
        return result.model_dump()

    @mcp.tool(
        name="get_all_context",
        description=(
            "Return all 12 guidelines concatenated into one document. "
            "Use when you need complete architectural context injected at once."
        ),
    )
    async def get_all_context() -> str:
        use_case = GetAllContextUseCase(get_guideline_repository())
        return await use_case.execute()
