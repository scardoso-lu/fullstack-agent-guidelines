from mcp.server.fastmcp import FastMCP

from src.application.use_cases.example.get_by_name import GetExampleByNameUseCase
from src.application.use_cases.example.list_all import ListExamplesUseCase
from src.infrastructure.repositories.example_repository import get_example_repository
from src.utils.exc import NotFoundError
from src.utils.logger import get_logger

_logger = get_logger("tools.example")


def register_example_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_examples",
        description=(
            "List annotated code examples. "
            "Filter by stack='backend'|'frontend' and/or "
            "layer='domain'|'application'|'infrastructure'|'presentation'|'frontend'. "
            "Each example shows the correct pattern and what to avoid."
        ),
    )
    async def list_examples(stack: str | None = None, layer: str | None = None) -> dict:
        _logger.info("tool=list_examples stack=%r layer=%r", stack, layer)
        try:
            result = await ListExamplesUseCase(get_example_repository()).execute(stack, layer)
            data = result.model_dump()
            _logger.info("tool=list_examples stack=%r layer=%r returned %d items", stack, layer, len(data.get("examples", [])))
            return data
        except ValueError as exc:
            _logger.warning("tool=list_examples stack=%r layer=%r error=%r", stack, layer, str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="get_example",
        description=(
            "Get the full annotated source of a code example by name "
            "(e.g. 'backend/domain/01_entity' or 'frontend/01_api_service'). "
            "Call list_examples first to see all available names."
        ),
    )
    async def get_example(name: str) -> dict:
        _logger.info("tool=get_example name=%r", name)
        try:
            result = await GetExampleByNameUseCase(get_example_repository()).execute(name)
            _logger.info("tool=get_example name=%r found", name)
            return result.model_dump()
        except NotFoundError as exc:
            _logger.warning("tool=get_example name=%r not_found error=%r", name, str(exc))
            return {"error": str(exc), "name": name}
