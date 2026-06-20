from __future__ import annotations

from collections import defaultdict

from src.application.dto.metadata_dto import ExampleMetaDto, GuidelineMetaDto, MetadataDto
from src.infrastructure.repositories.contract import (
    ExampleRepositoryInterface,
    GuidelineRepositoryInterface,
)


class GetMetadataUseCase:
    def __init__(
        self,
        guideline_repo: GuidelineRepositoryInterface,
        example_repo: ExampleRepositoryInterface,
    ) -> None:
        self._guidelines = guideline_repo
        self._examples = example_repo

    async def execute(self) -> MetadataDto:
        guidelines = await self._guidelines.get_all()
        examples = await self._examples.get_all()

        # Group guidelines by stack, sorted by slug within each group
        g_by_stack: dict[str, list[GuidelineMetaDto]] = defaultdict(list)
        for g in sorted(guidelines, key=lambda x: x.slug):
            g_by_stack[g.stack].append(
                GuidelineMetaDto(
                    slug=g.slug,
                    stack=g.stack,
                    title=g.title,
                    summary=g.summary,
                )
            )

        # Group examples by stack, sorted by name within each group
        e_by_stack: dict[str, list[ExampleMetaDto]] = defaultdict(list)
        for e in sorted(examples, key=lambda x: x.name):
            e_by_stack[e.stack].append(
                ExampleMetaDto(
                    name=e.name,
                    stack=e.stack,
                    layer=e.layer,
                    filename=e.filename,
                    description=e.description,
                )
            )

        return MetadataDto(
            guidelines=dict(g_by_stack),
            examples=dict(e_by_stack),
            total_guidelines=len(guidelines),
            total_examples=len(examples),
        )
