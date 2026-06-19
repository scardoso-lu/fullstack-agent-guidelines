from mcp.server.fastmcp import FastMCP

from src.application.use_cases.example.get_by_name import GetExampleByNameUseCase
from src.application.use_cases.example.list_all import ListExamplesUseCase
from src.infrastructure.repositories.example_repository import get_example_repository
from src.utils.exc import NotFoundError


def register_example_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="list_examples",
        description=(
            "List available annotated code examples organized by architectural layer. "
            "Pass layer='domain'|'application'|'infrastructure'|'presentation' to filter. "
            "Each example shows a correct pattern and an anti-pattern to avoid."
        ),
    )
    async def list_examples(layer: str | None = None) -> dict:
        try:
            result = await ListExamplesUseCase(get_example_repository()).execute(layer)
            return result.model_dump()
        except ValueError as exc:
            return {"error": str(exc)}

    @mcp.tool(
        name="get_example",
        description=(
            "Get the full annotated Python source of a code example by name "
            "(e.g. 'domain/01_entity' or 'presentation/02_fastapi_route'). "
            "Call list_examples first to see all available names."
        ),
    )
    async def get_example(name: str) -> dict:
        try:
            result = await GetExampleByNameUseCase(get_example_repository()).execute(name)
            return result.model_dump()
        except NotFoundError as exc:
            return {"error": str(exc), "name": name}
