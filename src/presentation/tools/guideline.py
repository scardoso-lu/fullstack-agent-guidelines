from mcp.server.fastmcp import FastMCP

from src.application.use_cases.guideline.get_all_context import GetAllContextUseCase
from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.application.use_cases.guideline.list_all import ListGuidelinesUseCase
from src.application.use_cases.guideline.recommend import RecommendGuidelinesUseCase
from src.application.use_cases.guideline.search import SearchGuidelinesUseCase
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.exc import NotFoundError


def register_guideline_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_guidelines",
        description=(
            "List available architecture guidelines. "
            "Pass stack='backend' or stack='frontend' to filter by technology. "
            "Returns slugs, titles, summaries, and tags — use get_guideline to fetch full content."
        ),
    )
    async def list_guidelines(stack: str | None = None) -> dict:
        try:
            use_case = ListGuidelinesUseCase(get_guideline_repository())
            result = await use_case.execute(stack)
            return result.model_dump()
        except ValueError as exc:
            return {"error": str(exc)}

    @mcp.tool(
        name="get_guideline",
        description=(
            "Retrieve the full Markdown content of a specific guideline by its slug "
            "(e.g. 'backend/03-application-layer' or 'frontend/02-server-vs-client'). "
            "Call list_guidelines or recommend_guidelines first to find available slugs."
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
        description=(
            "Search guidelines by keyword across title, content, and tags. "
            "Pass stack='backend' or stack='frontend' to limit results to one technology."
        ),
    )
    async def search_guidelines(query: str, stack: str | None = None) -> dict:
        try:
            use_case = SearchGuidelinesUseCase(get_guideline_repository())
            result = await use_case.execute(query, stack)
            return result.model_dump()
        except ValueError as exc:
            return {"error": str(exc)}

    @mcp.tool(
        name="recommend_guidelines",
        description=(
            "Given a description of what you are about to implement or change, returns the "
            "most relevant guideline slugs and summaries ranked by relevance. "
            "Pass stack='backend' or stack='frontend' to restrict results. "
            "Call get_guideline on any returned slug to read the full content."
        ),
    )
    async def recommend_guidelines(task: str, stack: str | None = None) -> dict:
        try:
            use_case = RecommendGuidelinesUseCase(get_guideline_repository())
            result = await use_case.execute(task, stack)
            return result.model_dump()
        except ValueError as exc:
            return {"error": str(exc)}

    @mcp.tool(
        name="get_all_context",
        description=(
            "Return all guidelines concatenated into one document. "
            "Pass stack='backend' or stack='frontend' to limit scope. "
            "Use for full architectural context injection into an agent."
        ),
    )
    async def get_all_context(stack: str | None = None) -> str:
        repo = get_guideline_repository()
        use_case = GetAllContextUseCase(repo)
        return await use_case.execute(stack)
