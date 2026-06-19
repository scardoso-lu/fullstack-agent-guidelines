import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.guideline_dto import GuidelineDto
from src.application.use_cases.guideline.get_by_slug import GetGuidelineBySlugUseCase
from src.domain.entities.guideline import Guideline
from src.utils.exc import NotFoundError


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_slug = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_get_found_returns_dto(mock_repo):
    # Arrange
    mock_repo.get_by_slug.return_value = Guideline._mock("01-alpha", "Alpha")

    # Act
    result = await GetGuidelineBySlugUseCase(mock_repo).execute("01-alpha")

    # Assert
    assert isinstance(result, GuidelineDto)
    assert result.slug == "01-alpha"
    assert result.title == "Alpha"
    mock_repo.get_by_slug.assert_called_once_with("01-alpha")


@pytest.mark.asyncio
async def test_get_strips_whitespace_from_slug(mock_repo):
    mock_repo.get_by_slug.return_value = Guideline._mock("01-alpha")
    await GetGuidelineBySlugUseCase(mock_repo).execute("  01-alpha  ")
    mock_repo.get_by_slug.assert_called_once_with("01-alpha")


@pytest.mark.asyncio
async def test_get_not_found_raises_not_found_error(mock_repo):
    mock_repo.get_by_slug.return_value = None
    with pytest.raises(NotFoundError):
        await GetGuidelineBySlugUseCase(mock_repo).execute("99-missing")


@pytest.mark.asyncio
async def test_empty_slug_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Slug cannot be empty"):
        await GetGuidelineBySlugUseCase(mock_repo).execute("   ")
    mock_repo.get_by_slug.assert_not_called()
