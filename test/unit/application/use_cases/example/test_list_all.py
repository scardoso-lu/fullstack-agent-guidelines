import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.example_dto import ExampleListDto
from src.application.use_cases.example.list_all import ListExamplesUseCase
from src.domain.entities.example import Example


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_list_returns_all_examples(mock_repo):
    mock_repo.get_all.return_value = [
        Example._mock("backend/domain/01_entity", "backend", "domain"),
        Example._mock("frontend/01_api_service", "frontend", "frontend"),
    ]

    result = await ListExamplesUseCase(mock_repo).execute()

    assert isinstance(result, ExampleListDto)
    assert result.total == 2
    assert result.stack_filter is None
    assert result.layer_filter is None
    mock_repo.get_all.assert_called_once()


@pytest.mark.asyncio
async def test_list_filters_by_stack(mock_repo):
    mock_repo.get_all.return_value = [
        Example._mock("backend/domain/01_entity", "backend", "domain"),
        Example._mock("frontend/01_api_service", "frontend", "frontend"),
    ]

    result = await ListExamplesUseCase(mock_repo).execute(stack="backend")

    assert result.total == 1
    assert result.stack_filter == "backend"
    assert result.items[0].name == "backend/domain/01_entity"


@pytest.mark.asyncio
async def test_list_filters_by_layer(mock_repo):
    mock_repo.get_all.return_value = [
        Example._mock("backend/domain/01_entity", "backend", "domain"),
        Example._mock("backend/application/01_dto", "backend", "application"),
    ]

    result = await ListExamplesUseCase(mock_repo).execute(layer="domain")

    assert result.total == 1
    assert result.layer_filter == "domain"


@pytest.mark.asyncio
async def test_list_empty_repo_returns_zero(mock_repo):
    mock_repo.get_all.return_value = []
    result = await ListExamplesUseCase(mock_repo).execute()
    assert result.total == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_list_invalid_stack_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Unknown stack"):
        await ListExamplesUseCase(mock_repo).execute(stack="nonexistent")
    mock_repo.get_all.assert_not_called()


@pytest.mark.asyncio
async def test_list_invalid_layer_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Unknown layer"):
        await ListExamplesUseCase(mock_repo).execute(layer="nonexistent")
    mock_repo.get_all.assert_not_called()
