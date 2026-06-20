import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.guideline_dto import GuidelineListDto
from src.application.use_cases.guideline.list_all import ListGuidelinesUseCase
from src.domain.entities.guideline import Guideline


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_list_returns_all_summaries(mock_repo):
    # Arrange
    mock_repo.get_all.return_value = [
        Guideline._mock(slug="backend/01-alpha", stack="backend", title="Alpha"),
        Guideline._mock(slug="frontend/01-alpha", stack="frontend", title="FE Alpha"),
    ]

    # Act
    result = await ListGuidelinesUseCase(mock_repo).execute()

    # Assert
    assert isinstance(result, GuidelineListDto)
    assert result.total == 2
    assert result.stack_filter is None
    slugs = [item.slug for item in result.items]
    assert "backend/01-alpha" in slugs
    assert "frontend/01-alpha" in slugs
    mock_repo.get_all.assert_called_once()


@pytest.mark.asyncio
async def test_list_filters_by_stack(mock_repo):
    mock_repo.get_all.return_value = [
        Guideline._mock(slug="backend/01-alpha", stack="backend", title="Alpha"),
        Guideline._mock(slug="frontend/01-alpha", stack="frontend", title="FE Alpha"),
    ]

    result = await ListGuidelinesUseCase(mock_repo).execute(stack="backend")

    assert result.total == 1
    assert result.stack_filter == "backend"
    assert result.items[0].slug == "backend/01-alpha"


@pytest.mark.asyncio
async def test_list_invalid_stack_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Unknown stack"):
        await ListGuidelinesUseCase(mock_repo).execute(stack="invalid")
    mock_repo.get_all.assert_not_called()


@pytest.mark.asyncio
async def test_list_empty_repo_returns_zero(mock_repo):
    mock_repo.get_all.return_value = []
    result = await ListGuidelinesUseCase(mock_repo).execute()
    assert result.total == 0
    assert result.items == []
