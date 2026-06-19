# Description: MCP tool registration — thin wrappers that delegate to use cases
# Layer: presentation
#
# Key rules:
#   - Tools contain ZERO business logic — one line: call use case, return DTO
#   - Use case is instantiated here with the singleton repository (DI at the edge)
#   - Return model_dump() so FastMCP can serialize the Pydantic model to JSON
#   - Catch domain errors (NotFoundError) at this layer — convert to structured dicts
#   - Tool descriptions are the user-visible doc — make them precise for AI agents

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

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
        # Thin wrapper: instantiate use case → execute → serialize
        result = await ListGuidelinesUseCase(get_guideline_repository()).execute()
        return result.model_dump()

    @mcp.tool(
        name="get_guideline",
        description=(
            "Retrieve the full Markdown content of a guideline by slug "
            "(e.g. '03-application-layer'). Call list_guidelines first to see all slugs."
        ),
    )
    async def get_guideline(slug: str) -> dict:
        try:
            result = await GetGuidelineBySlugUseCase(get_guideline_repository()).execute(slug)
            return result.model_dump()
        except NotFoundError as exc:
            # Convert domain error → structured response (MCP tools don't raise HTTP errors)
            return {"error": str(exc), "slug": slug}

    @mcp.tool(
        name="search_guidelines",
        description="Search guidelines by keyword. Searches titles, content, and tags.",
    )
    async def search_guidelines(query: str) -> dict:
        result = await SearchGuidelinesUseCase(get_guideline_repository()).execute(query)
        return result.model_dump()


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# Business logic inside the tool handler:
#
# @mcp.tool("get_guideline", "...")
# async def get_guideline(slug: str) -> dict:
#     path = Path("guidelines") / f"{slug}.md"   ← hardcoded path in presentation
#     if not path.exists():
#         return {"error": "not found"}
#     content = open(path).read()                ← sync I/O in async, no caching
#     title = content.split("\n")[0].strip("# ")
#     return {"slug": slug, "title": title, "content": content}
#
# Problem: untestable, duplicates repository logic, no separation of concerns.
