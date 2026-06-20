from mcp.server.fastmcp import FastMCP

from src.application.use_cases.example.get_by_name import GetExampleByNameUseCase
from src.application.use_cases.example.list_all import ListExamplesUseCase
from src.infrastructure.repositories.example_repository import get_example_repository
from src.utils.exc import NotFoundError


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
        try:
            result = await ListExamplesUseCase(get_example_repository()).execute(stack, layer)
            return result.model_dump()
        except ValueError as exc:
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
        try:
            result = await GetExampleByNameUseCase(get_example_repository()).execute(name)
            return result.model_dump()
        except NotFoundError as exc:
            return {"error": str(exc), "name": name}
