import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.guideline_dto import SearchResultDto
from src.application.use_cases.guideline.search import SearchGuidelinesUseCase
from src.domain.entities.guideline import Guideline


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.search = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_search_returns_matching_results(mock_repo):
    # Arrange
    mock_repo.search.return_value = [
        Guideline._mock(slug="backend/01-alpha", stack="backend", title="Alpha")
    ]

    # Act
    result = await SearchGuidelinesUseCase(mock_repo).execute("alpha")

    # Assert
    assert isinstance(result, SearchResultDto)
    assert result.query == "alpha"
    assert result.total == 1
    assert result.items[0].stack == "backend"
    mock_repo.search.assert_called_once_with("alpha")


@pytest.mark.asyncio
async def test_search_strips_whitespace_from_query(mock_repo):
    mock_repo.search.return_value = []
    result = await SearchGuidelinesUseCase(mock_repo).execute("  solid  ")
    assert result.query == "solid"
    mock_repo.search.assert_called_once_with("solid")


@pytest.mark.asyncio
async def test_search_no_results_returns_empty(mock_repo):
    mock_repo.search.return_value = []
    result = await SearchGuidelinesUseCase(mock_repo).execute("xyznotfound")
    assert result.total == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_empty_query_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Search query cannot be empty"):
        await SearchGuidelinesUseCase(mock_repo).execute("")
    mock_repo.search.assert_not_called()
