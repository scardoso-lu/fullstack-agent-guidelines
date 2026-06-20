from src.application.dto.guideline_dto import GuidelineListDto, GuidelineSummaryDto
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface

_VALID_STACKS = {"backend", "frontend", "infra"}


class ListGuidelinesUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, stack: str | None = None) -> GuidelineListDto:
        if stack is not None:
            stack = stack.strip().lower()
            if stack not in _VALID_STACKS:
                raise ValueError(
                    f"Unknown stack '{stack}'. Valid values: {sorted(_VALID_STACKS)}"
                )

        guidelines = await self.repo.get_all()

        if stack is not None:
            guidelines = [g for g in guidelines if g.stack == stack]

        items = [
            GuidelineSummaryDto(slug=g.slug, stack=g.stack, title=g.title, tags=g.tags, summary=g.summary)
            for g in guidelines
        ]
        return GuidelineListDto(items=items, total=len(items), stack_filter=stack)
