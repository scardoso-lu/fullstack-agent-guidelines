import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.example_dto import ExampleDto
from src.application.use_cases.example.get_by_name import GetExampleByNameUseCase
from src.domain.entities.example import Example
from src.utils.exc import NotFoundError


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_name = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_get_found_returns_dto(mock_repo):
    mock_repo.get_by_name.return_value = Example._mock(
        "backend/domain/01_entity", "backend", "domain", "Test entity"
    )

    result = await GetExampleByNameUseCase(mock_repo).execute("backend/domain/01_entity")

    assert isinstance(result, ExampleDto)
    assert result.name == "backend/domain/01_entity"
    assert result.stack == "backend"
    assert result.layer == "domain"
    assert result.description == "Test entity"
    mock_repo.get_by_name.assert_called_once_with("backend/domain/01_entity")


@pytest.mark.asyncio
async def test_get_found_frontend_returns_dto(mock_repo):
    mock_repo.get_by_name.return_value = Example._mock(
        "frontend/01_api_service", "frontend", "frontend", "Service example"
    )

    result = await GetExampleByNameUseCase(mock_repo).execute("frontend/01_api_service")

    assert result.stack == "frontend"
    assert result.layer == "frontend"


@pytest.mark.asyncio
async def test_get_strips_whitespace(mock_repo):
    mock_repo.get_by_name.return_value = Example._mock(
        "backend/domain/01_entity", "backend", "domain"
    )
    await GetExampleByNameUseCase(mock_repo).execute("  backend/domain/01_entity  ")
    mock_repo.get_by_name.assert_called_once_with("backend/domain/01_entity")


@pytest.mark.asyncio
async def test_get_not_found_raises_not_found_error(mock_repo):
    mock_repo.get_by_name.return_value = None
    with pytest.raises(NotFoundError):
        await GetExampleByNameUseCase(mock_repo).execute("backend/domain/99_missing")


@pytest.mark.asyncio
async def test_empty_name_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Example name cannot be empty"):
        await GetExampleByNameUseCase(mock_repo).execute("   ")
    mock_repo.get_by_name.assert_not_called()
