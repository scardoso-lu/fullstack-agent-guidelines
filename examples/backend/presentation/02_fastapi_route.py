# Description: FastAPI route — thin HTTP adapter that delegates to use cases
# Layer: presentation
#
# Key rules:
#   - Routes are adapters only: parse request → call use case → return response_model
#   - response_model on the decorator enforces the output schema and generates OpenAPI docs
#   - Depends() injects the repository — FastAPI resolves it per-request
#   - HTTPException is the ONLY exception allowed to escape this layer
#   - No SQL, no ORM, no file I/O inside route handlers

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.dto.guideline_dto import GuidelineDto, GuidelineListDto
from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.application.use_cases.guideline.list_all import ListGuidelinesUseCase
from src.infrastructure.repositories.contract import GuidelineRepositoryInterface
from src.infrastructure.repositories.guideline_repository import get_guideline_repository
from src.utils.exc import NotFoundError

router = APIRouter(prefix="/guidelines", tags=["guidelines"])


# Dependency function — FastAPI calls this and injects the result
def _get_repo() -> GuidelineRepositoryInterface:
    return get_guideline_repository()


@router.get("/", response_model=GuidelineListDto)
async def list_guidelines(repo: GuidelineRepositoryInterface = Depends(_get_repo)) -> GuidelineListDto:
    return await ListGuidelinesUseCase(repo).execute()


@router.get("/{slug}", response_model=GuidelineDto)
async def get_guideline(
    slug: str,
    repo: GuidelineRepositoryInterface = Depends(_get_repo),
) -> GuidelineDto:
    try:
        return await GetGuidelineBySlugUseCase(repo).execute(slug)
    except NotFoundError as exc:
        # Convert domain error → HTTP 404 at the presentation boundary
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# Fat route — SQL query and business logic inside the handler:
#
# @router.get("/{slug}")
# async def get_guideline(slug: str, db: AsyncSession = Depends(get_session)):
#     row = await db.execute(select(Guideline).where(Guideline.slug == slug))
#     g = row.scalars().first()
#     if not g:
#         raise HTTPException(404, "not found")
#     return {"slug": g.slug, "title": g.title}   ← dict, not response_model
#
# Problems: impossible to unit-test (needs real DB), business logic in HTTP layer,
# no schema validation on output, Guideline ORM object exposed directly.
