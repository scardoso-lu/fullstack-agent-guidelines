from __future__ import annotations

from src.application.dto.example_dto import ExampleDto
from src.infrastructure.repositories.contract import ExampleRepositoryInterface
from src.utils.exc import NotFoundError


class GetExampleByNameUseCase:
    def __init__(self, repo: ExampleRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, name: str) -> ExampleDto:
        if not name or not name.strip():
            raise ValueError("Example name cannot be empty")
        example = await self.repo.get_by_name(name.strip())
        if example is None:
            raise NotFoundError(f"Example '{name}' not found")
        return ExampleDto(
            name=example.name,
            layer=example.layer,
            filename=example.filename,
            description=example.description,
            content=example.content,
        )
