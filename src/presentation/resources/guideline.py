from mcp.server.fastmcp import FastMCP

from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.exc import NotFoundError


def register_guideline_resources(mcp: FastMCP) -> None:

    @mcp.resource("guidelines://{slug}")
    async def guideline_resource(slug: str) -> str:
        """Access a guideline by its slug as a resource URI (e.g. guidelines://08-security)."""
        try:
            use_case = GetGuidelineBySlugUseCase(get_guideline_repository())
            result = await use_case.execute(slug)
            return result.content
        except NotFoundError:
            return f"Guideline '{slug}' not found."
