from __future__ import annotations

from src.application.dto.example_dto import ExampleListDto, ExampleSummaryDto
from src.infrastructure.repositories.contract import ExampleRepositoryInterface

_VALID_STACKS = {"backend", "frontend"}
_VALID_BACKEND_LAYERS = {"domain", "application", "infrastructure", "presentation"}


class ListExamplesUseCase:
    def __init__(self, repo: ExampleRepositoryInterface) -> None:
        self.repo = repo

    async def execute(
        self,
        stack: str | None = None,
        layer: str | None = None,
    ) -> ExampleListDto:
        if stack is not None:
            stack = stack.strip().lower()
            if stack not in _VALID_STACKS:
                raise ValueError(
                    f"Unknown stack '{stack}'. Valid values: {sorted(_VALID_STACKS)}"
                )

        if layer is not None:
            layer = layer.strip().lower()
            valid_layers = _VALID_BACKEND_LAYERS | {"frontend"}
            if layer not in valid_layers:
                raise ValueError(
                    f"Unknown layer '{layer}'. Valid layers: {sorted(valid_layers)}"
                )

        examples = await self.repo.get_all()

        if stack is not None:
            examples = [e for e in examples if e.stack == stack]
        if layer is not None:
            examples = [e for e in examples if e.layer == layer]

        items = [
            ExampleSummaryDto(
                name=e.name,
                stack=e.stack,
                layer=e.layer,
                filename=e.filename,
                description=e.description,
            )
            for e in examples
        ]
        return ExampleListDto(
            items=items,
            total=len(items),
            stack_filter=stack,
            layer_filter=layer,
        )
