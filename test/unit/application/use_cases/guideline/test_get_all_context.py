import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.guideline.get_all_context import GetAllContextUseCase
from src.domain.entities.guideline import Guideline


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_get_all_context_concatenates_content(mock_repo):
    # Arrange
    mock_repo.get_all.return_value = [
        Guideline._mock(slug="01-alpha", title="Alpha"),
        Guideline._mock(slug="02-beta", title="Beta"),
    ]

    # Act
    result = await GetAllContextUseCase(mock_repo).execute()

    # Assert
    assert isinstance(result, str)
    assert "<!-- Guideline: 01-alpha -->" in result
    assert "<!-- Guideline: 02-beta -->" in result
    assert "---" in result  # separator present


@pytest.mark.asyncio
async def test_get_all_context_empty_repo_returns_empty_string(mock_repo):
    mock_repo.get_all.return_value = []
    result = await GetAllContextUseCase(mock_repo).execute()
    assert result == ""
