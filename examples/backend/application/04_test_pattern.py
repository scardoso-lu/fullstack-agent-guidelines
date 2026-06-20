# Description: Unit test pattern — AsyncMock repos, _mock() entity factories, Arrange/Act/Assert
# Layer: application (tests live in test/unit/, this file shows the pattern)
#
# Key rules:
#   - Use AsyncMock for every async repository method — never hit real files or DB
#   - Use entity._mock() factories for clean test fixtures — no fixture files needed
#   - Arrange / Act / Assert structure in every test — no exceptions
#   - Assert what WAS called and with what args, not just what was returned
#   - pytest.raises() for error paths — never catch exceptions manually in tests

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.domain.entities.guideline import Guideline
from src.utils.exc import NotFoundError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repo():
    repo = MagicMock()                    # sync attributes (e.g. repo.cache)
    repo.get_by_slug = AsyncMock()        # async methods need AsyncMock
    repo.get_all = AsyncMock()
    return repo


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_dto_when_found(mock_repo):
    # Arrange — build a domain entity using the _mock() factory
    guideline = Guideline._mock(slug="backend/01-test", title="Test Guideline")
    mock_repo.get_by_slug.return_value = guideline

    # Act
    result = await GetGuidelineBySlugUseCase(mock_repo).execute("backend/01-test")

    # Assert — verify output AND that the repo was called correctly
    assert result.slug == "backend/01-test"
    assert result.title == "Test Guideline"
    mock_repo.get_by_slug.assert_awaited_once_with("backend/01-test")


# ── Error paths ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_raises_not_found_when_slug_unknown(mock_repo):
    # Arrange
    mock_repo.get_by_slug.return_value = None

    # Act + Assert — use pytest.raises, never try/except in tests
    with pytest.raises(NotFoundError, match="backend/unknown"):
        await GetGuidelineBySlugUseCase(mock_repo).execute("backend/unknown")


@pytest.mark.asyncio
async def test_raises_value_error_on_empty_slug(mock_repo):
    with pytest.raises(ValueError):
        await GetGuidelineBySlugUseCase(mock_repo).execute("")

    # Input validation fired before any I/O — repo was never called
    mock_repo.get_by_slug.assert_not_awaited()


@pytest.mark.asyncio
async def test_raises_value_error_on_whitespace_slug(mock_repo):
    with pytest.raises(ValueError):
        await GetGuidelineBySlugUseCase(mock_repo).execute("   ")

    mock_repo.get_by_slug.assert_not_awaited()


# ── Multiple results ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_returns_sorted_by_slug(mock_repo):
    from src.application.use_cases.guideline.list_all import ListGuidelinesUseCase

    mock_repo.get_all.return_value = [
        Guideline._mock(slug="backend/02-beta", title="Beta"),
        Guideline._mock(slug="backend/01-alpha", title="Alpha"),
        Guideline._mock(slug="frontend/01-alpha", stack="frontend", title="Frontend"),
    ]

    result = await ListGuidelinesUseCase(mock_repo).execute()

    slugs = [g.slug for g in result.items]
    assert slugs == ["backend/01-alpha", "backend/02-beta", "frontend/01-alpha"]


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# 1. Hitting real files in a unit test — makes it an integration test and slow:
#
# async def test_get_guideline():
#     repo = GuidelineRepository(Path("guidelines"))  ← real disk I/O
#     result = await GetGuidelineBySlugUseCase(repo).execute("backend/01-test")
#     assert result.slug == "backend/01-test"         ← fails if file doesn't exist

# 2. Manual exception handling instead of pytest.raises:
#
# async def test_not_found():
#     try:
#         await use_case.execute("unknown")
#         assert False, "Should have raised"   ← fragile; obscures what was expected
#     except NotFoundError:
#         pass

# 3. No Arrange/Act/Assert separation — all three collapsed into one expression:
#
# async def test_found():
#     assert (await GetGuidelineBySlugUseCase(mock_repo).execute("x")).slug == "x"
#     # ↑ impossible to tell what's being set up vs. what's being verified
