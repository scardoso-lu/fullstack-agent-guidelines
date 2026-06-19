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
        Guideline._mock(slug="01-alpha", title="Alpha"),
        Guideline._mock(slug="02-beta", title="Beta"),
    ]

    # Act
    result = await ListGuidelinesUseCase(mock_repo).execute()

    # Assert
    assert isinstance(result, GuidelineListDto)
    assert result.total == 2
    slugs = [item.slug for item in result.items]
    assert "01-alpha" in slugs
    assert "02-beta" in slugs
    mock_repo.get_all.assert_called_once()


@pytest.mark.asyncio
async def test_list_empty_repo_returns_zero(mock_repo):
    mock_repo.get_all.return_value = []
    result = await ListGuidelinesUseCase(mock_repo).execute()
    assert result.total == 0
    assert result.items == []
