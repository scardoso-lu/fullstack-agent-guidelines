from src.application.dto.guideline_dto import GuidelineListDto, GuidelineSummaryDto
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface


class ListGuidelinesUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self) -> GuidelineListDto:
        guidelines = await self.repo.get_all()
        items = [
            GuidelineSummaryDto(slug=g.slug, title=g.title, tags=g.tags)
            for g in guidelines
        ]
        return GuidelineListDto(items=items, total=len(items))
