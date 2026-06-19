from src.application.dto.guideline_dto import GuidelineDto, SearchResultDto
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface


class SearchGuidelinesUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, query: str) -> SearchResultDto:
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        guidelines = await self.repo.search(query.strip())
        items = [
            GuidelineDto(slug=g.slug, title=g.title, content=g.content, tags=g.tags)
            for g in guidelines
        ]
        return SearchResultDto(items=items, query=query.strip(), total=len(items))
