from __future__ import annotations

from src.application.dto.example_dto import ExampleListDto, ExampleSummaryDto
from src.infrastructure.repositories.contract import ExampleRepositoryInterface

_VALID_LAYERS = {"domain", "application", "infrastructure", "presentation", "frontend"}


class ListExamplesUseCase:
    def __init__(self, repo: ExampleRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, layer: str | None = None) -> ExampleListDto:
        if layer is not None:
            layer = layer.strip().lower()
            if layer not in _VALID_LAYERS:
                raise ValueError(
                    f"Unknown layer '{layer}'. Valid layers: {sorted(_VALID_LAYERS)}"
                )
            examples = await self.repo.get_by_layer(layer)
        else:
            examples = await self.repo.get_all()

        items = [
            ExampleSummaryDto(
                name=e.name,
                layer=e.layer,
                filename=e.filename,
                description=e.description,
            )
            for e in examples
        ]
        return ExampleListDto(items=items, total=len(items), layer_filter=layer)
