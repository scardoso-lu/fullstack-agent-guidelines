# Description: Use case — one file, one operation, constructor-injected repository
# Layer: application
#
# Key rules:
#   - Single Responsibility: one use case = one business operation (SRP)
#   - Dependency is ALWAYS the interface, never the concrete class (DIP)
#   - Constructor injection — no globals, no imports of concrete repos
#   - Validate input at the top, before any async work
#   - Return a DTO, never an ORM entity

from __future__ import annotations

from src.application.dto.guideline_dto import GuidelineDto
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface
from src.utils.exc import NotFoundError


class GetGuidelineBySlugUseCase:
    """Fetch a single guideline. Raises NotFoundError if the slug is unknown."""

    def __init__(self, repo: GuidelineRepositoryInterface) -> None:
        # Receives the INTERFACE — production code passes GuidelineRepository,
        # tests pass AsyncMock. The use case never knows the difference.
        self.repo = repo

    async def execute(self, slug: str) -> GuidelineDto:
        # 1. Validate — fail fast with a clear error before any I/O
        if not slug or not slug.strip():
            raise ValueError("Slug cannot be empty")

        # 2. Fetch — always await; never block the event loop
        guideline = await self.repo.get_by_slug(slug.strip())

        # 3. Handle missing — convert to domain error, not None propagation
        if guideline is None:
            raise NotFoundError(f"Guideline '{slug}' not found")

        # 4. Map — entity → DTO; presentation layer never sees the domain object
        return GuidelineDto(
            slug=guideline.slug,
            title=guideline.title,
            content=guideline.content,
            tags=guideline.tags,
        )


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# Fat route — business logic inside a FastAPI handler:
#
# @router.get("/guidelines/{slug}")
# async def get_guideline(slug: str, db: AsyncSession = Depends(get_session)):
#     result = await db.execute(select(Guideline).where(Guideline.slug == slug))
#     guideline = result.scalars().first()
#     if not guideline:
#         raise HTTPException(404)
#     return guideline          ← returns ORM object directly; bypasses DTO layer
#
# Problems: untestable without a real DB, logic duplicated across routes,
# changing DB schema breaks the route response shape silently.
