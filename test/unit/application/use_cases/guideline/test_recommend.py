import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.guideline_dto import RecommendationResultDto
from src.application.use_cases.guideline.recommend import RecommendGuidelinesUseCase
from src.domain.entities.guideline import Guideline


def _guide(slug: str, stack: str, title: str, content: str, tags: list[str]) -> Guideline:
    """Helper to build a Guideline with explicit content for scoring tests."""
    return Guideline(slug=slug, stack=stack, title=title, content=content, tags=tags, summary="")


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_recommend_returns_relevant_guidelines(mock_repo):
    # Arrange
    mock_repo.get_all.return_value = [
        _guide(
            slug="backend/08-security",
            stack="backend",
            title="Security Patterns",
            content="# Security Patterns\n\nJWT authentication and token validation.",
            tags=["security"],
        ),
        _guide(
            slug="backend/01-project-structure",
            stack="backend",
            title="Project Structure",
            content="# Project Structure\n\nDirectory layout and naming conventions.",
            tags=["project", "structure"],
        ),
    ]

    # Act
    result = await RecommendGuidelinesUseCase(mock_repo).execute("implement JWT authentication")

    # Assert
    assert isinstance(result, RecommendationResultDto)
    assert result.total >= 1
    assert result.items[0].slug == "backend/08-security"
    mock_repo.get_all.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_filters_by_stack(mock_repo):
    mock_repo.get_all.return_value = [
        _guide("backend/08-security", "backend", "Security Patterns",
               "# Security Patterns\n\nJWT authentication.", ["security"]),
        _guide("frontend/05-authentication", "frontend", "Frontend Authentication",
               "# Frontend Authentication\n\nJWT cookie authentication patterns.", ["authentication"]),
    ]

    result = await RecommendGuidelinesUseCase(mock_repo).execute(
        "implement JWT auth", stack="frontend"
    )

    assert result.total == 1
    assert result.items[0].stack == "frontend"
    assert result.items[0].slug == "frontend/05-authentication"


@pytest.mark.asyncio
async def test_recommend_respects_top_5_cap(mock_repo):
    mock_repo.get_all.return_value = [
        _guide(
            slug=f"backend/0{i}-security",
            stack="backend",
            title=f"Security Item {i}",
            content=f"# Security Item {i}\n\nSecurity testing and authentication patterns.",
            tags=["security"],
        )
        for i in range(1, 9)
    ]

    result = await RecommendGuidelinesUseCase(mock_repo).execute("security authentication testing")

    assert result.total <= 5


@pytest.mark.asyncio
async def test_recommend_empty_task_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Task description cannot be empty"):
        await RecommendGuidelinesUseCase(mock_repo).execute("")
    mock_repo.get_all.assert_not_called()


@pytest.mark.asyncio
async def test_recommend_whitespace_only_task_raises(mock_repo):
    with pytest.raises(ValueError, match="Task description cannot be empty"):
        await RecommendGuidelinesUseCase(mock_repo).execute("   ")
    mock_repo.get_all.assert_not_called()


@pytest.mark.asyncio
async def test_recommend_invalid_stack_raises_value_error(mock_repo):
    with pytest.raises(ValueError, match="Unknown stack"):
        await RecommendGuidelinesUseCase(mock_repo).execute("some task", stack="ruby")
    mock_repo.get_all.assert_not_called()


@pytest.mark.asyncio
async def test_recommend_all_stopwords_returns_empty(mock_repo):
    mock_repo.get_all.return_value = [
        Guideline._mock(slug="backend/01-alpha", stack="backend", title="Alpha"),
    ]

    result = await RecommendGuidelinesUseCase(mock_repo).execute("the a an of")

    assert result.total == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_recommend_no_match_returns_empty(mock_repo):
    mock_repo.get_all.return_value = [
        _guide("backend/01-alpha", "backend", "Alpha", "# Alpha\n\nSome unrelated content.", []),
    ]

    result = await RecommendGuidelinesUseCase(mock_repo).execute("quantum cryptography")

    assert result.total == 0


@pytest.mark.asyncio
async def test_recommend_result_carries_summary(mock_repo):
    mock_repo.get_all.return_value = [
        Guideline(
            slug="backend/08-security",
            stack="backend",
            title="Security Patterns",
            content="# Security Patterns\n\nJWT authentication patterns.",
            tags=["security"],
            summary="JWT authentication patterns.",
        ),
    ]

    result = await RecommendGuidelinesUseCase(mock_repo).execute("jwt authentication")

    assert result.items[0].summary == "JWT authentication patterns."
