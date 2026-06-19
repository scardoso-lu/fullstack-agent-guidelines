from src.application.dto.guideline_dto import GuidelineDto
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface
from src.utils.exc import NotFoundError


class GetGuidelineBySlugUseCase:
    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, slug: str) -> GuidelineDto:
        if not slug or not slug.strip():
            raise ValueError("Slug cannot be empty")
        guideline = await self.repo.get_by_slug(slug.strip())
        if guideline is None:
            raise NotFoundError(f"Guideline '{slug}' not found")
        return GuidelineDto(
            slug=guideline.slug,
            stack=guideline.stack,
            title=guideline.title,
            content=guideline.content,
            tags=guideline.tags,
        )
