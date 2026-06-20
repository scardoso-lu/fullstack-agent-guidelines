from src.application.dto.guideline_dto import GuidelineDto, SearchResultDto
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface

_VALID_STACKS = frozenset({"backend", "frontend"})


class SearchGuidelinesUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, query: str, stack: str | None = None) -> SearchResultDto:
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        if stack is not None:
            stack = stack.strip().lower()
            if stack not in _VALID_STACKS:
                raise ValueError(
                    f"Unknown stack '{stack}'. Valid values: {sorted(_VALID_STACKS)}"
                )

        guidelines = await self.repo.search(query.strip())

        if stack is not None:
            guidelines = [g for g in guidelines if g.stack == stack]

        items = [
            GuidelineDto(
                slug=g.slug,
                stack=g.stack,
                title=g.title,
                content=g.content,
                tags=g.tags,
                summary=g.summary,
            )
            for g in guidelines
        ]
        return SearchResultDto(items=items, query=query.strip(), total=len(items), stack_filter=stack)
