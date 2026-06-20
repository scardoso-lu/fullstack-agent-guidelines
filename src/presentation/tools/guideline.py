from mcp.server.fastmcp import FastMCP

from src.application.use_cases.guideline.get_all_context import GetAllContextUseCase
from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.application.use_cases.guideline.list_all import ListGuidelinesUseCase
from src.application.use_cases.guideline.search import SearchGuidelinesUseCase
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.exc import NotFoundError
from src.utils.logger import get_logger

_logger = get_logger("tools.guideline")


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
        _logger.info("tool=list_guidelines stack=%r", stack)
        try:
            use_case = ListGuidelinesUseCase(get_guideline_repository())
            result = await use_case.execute(stack)
            data = result.model_dump()
            _logger.info("tool=list_guidelines stack=%r returned %d items", stack, len(data.get("guidelines", [])))
            return data
        except ValueError as exc:
            _logger.warning("tool=list_guidelines stack=%r error=%r", stack, str(exc))
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
        _logger.info("tool=get_guideline slug=%r", slug)
        try:
            use_case = GetGuidelineBySlugUseCase(get_guideline_repository())
            result = await use_case.execute(slug)
            _logger.info("tool=get_guideline slug=%r found", slug)
            return result.model_dump()
        except NotFoundError as exc:
            _logger.warning("tool=get_guideline slug=%r not_found error=%r", slug, str(exc))
            return {"error": str(exc), "slug": slug}

    @mcp.tool(
        name="search_guidelines",
        description=(
            "Search guidelines by keyword across title, content, and tags. "
            "Pass stack='backend' or stack='frontend' to limit results to one technology."
        ),
    )
    async def search_guidelines(query: str, stack: str | None = None) -> dict:
        _logger.info("tool=search_guidelines query=%r stack=%r", query, stack)
        try:
            use_case = SearchGuidelinesUseCase(get_guideline_repository())
            result = await use_case.execute(query, stack)
            data = result.model_dump()
            _logger.info("tool=search_guidelines query=%r stack=%r returned %d items", query, stack, len(data.get("guidelines", [])))
            return data
        except ValueError as exc:
            _logger.warning("tool=search_guidelines query=%r stack=%r error=%r", query, stack, str(exc))
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
        _logger.info("tool=get_all_context stack=%r", stack)
        repo = get_guideline_repository()
        use_case = GetAllContextUseCase(repo)
        result = await use_case.execute(stack)
        _logger.info("tool=get_all_context stack=%r returned %d chars", stack, len(result))
        return result
