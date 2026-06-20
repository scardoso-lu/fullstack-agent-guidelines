import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.metadata_dto import MetadataDto
from src.application.use_cases.metadata.get_metadata import GetMetadataUseCase
from src.domain.entities.example import Example
from src.domain.entities.guideline import Guideline
from src.utils.markdown import extract_summary as _extract_summary


@pytest.fixture
def mock_guideline_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


@pytest.fixture
def mock_example_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock()
    return repo


# ── Unit: summary extraction ──────────────────────────────────────────────────

def test_extract_summary_returns_first_paragraph():
    content = "# Title\n\nThis is the intro paragraph.\n\n## Section\n\nMore content."
    assert _extract_summary(content) == "This is the intro paragraph."


def test_extract_summary_collapses_internal_newlines():
    content = "# Title\n\nLine one\nLine two\nLine three\n\n## Next"
    result = _extract_summary(content)
    assert "\n" not in result
    assert "Line one" in result


def test_extract_summary_truncates_at_max_chars():
    long_para = "A" * 300
    content = f"# Title\n\n{long_para}"
    result = _extract_summary(content)
    assert len(result) <= 220


def test_extract_summary_empty_content_returns_empty():
    assert _extract_summary("") == ""


def test_extract_summary_skips_leading_blockquote():
    content = '# Title\n\n> "The best code is the code you never wrote."\n\nReal first paragraph here.'
    assert _extract_summary(content) == "Real first paragraph here."


def test_extract_summary_skips_blockquote_returns_second_paragraph():
    content = "# Rework Clean\n\n> Some quote\n\nAI agents over-build. This is the real summary.\n\n## Section"
    result = _extract_summary(content)
    assert "AI agents over-build" in result
    assert ">" not in result


def test_extract_summary_strips_inline_markdown():
    content = "# Title\n\nUse **React Query** for all `server state` fetching."
    result = _extract_summary(content)
    assert "**" not in result
    assert "`" not in result
    assert "React Query" in result
    assert "server state" in result


# ── Integration: use case ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_metadata_groups_by_stack(mock_guideline_repo, mock_example_repo):
    # Arrange
    mock_guideline_repo.get_all.return_value = [
        Guideline._mock(slug="backend/01-alpha", stack="backend", title="Backend Alpha"),
        Guideline._mock(slug="frontend/01-alpha", stack="frontend", title="Frontend Alpha"),
    ]
    mock_example_repo.get_all.return_value = [
        Example._mock("backend/domain/01_entity", "backend", "domain", "Backend entity"),
        Example._mock("frontend/01_service", "frontend", "frontend", "Frontend service"),
    ]

    # Act
    result = await GetMetadataUseCase(mock_guideline_repo, mock_example_repo).execute()

    # Assert
    assert isinstance(result, MetadataDto)
    assert "backend" in result.guidelines
    assert "frontend" in result.guidelines
    assert "backend" in result.examples
    assert "frontend" in result.examples
    assert result.total_guidelines == 2
    assert result.total_examples == 2


@pytest.mark.asyncio
async def test_get_metadata_guidelines_sorted_by_slug(mock_guideline_repo, mock_example_repo):
    mock_guideline_repo.get_all.return_value = [
        Guideline._mock(slug="backend/02-beta", stack="backend", title="Beta"),
        Guideline._mock(slug="backend/01-alpha", stack="backend", title="Alpha"),
    ]
    mock_example_repo.get_all.return_value = []

    result = await GetMetadataUseCase(mock_guideline_repo, mock_example_repo).execute()

    slugs = [g.slug for g in result.guidelines["backend"]]
    assert slugs == ["backend/01-alpha", "backend/02-beta"]


@pytest.mark.asyncio
async def test_get_metadata_includes_summary(mock_guideline_repo, mock_example_repo):
    g = Guideline(
        slug="backend/01-alpha",
        stack="backend",
        title="Alpha",
        content="# Alpha\n\nThis is the summary paragraph.\n\n## Details\n\nMore here.",
        tags=[],
        summary="This is the summary paragraph.",
    )
    mock_guideline_repo.get_all.return_value = [g]
    mock_example_repo.get_all.return_value = []

    result = await GetMetadataUseCase(mock_guideline_repo, mock_example_repo).execute()

    assert result.guidelines["backend"][0].summary == "This is the summary paragraph."


@pytest.mark.asyncio
async def test_get_metadata_empty_repos(mock_guideline_repo, mock_example_repo):
    mock_guideline_repo.get_all.return_value = []
    mock_example_repo.get_all.return_value = []

    result = await GetMetadataUseCase(mock_guideline_repo, mock_example_repo).execute()

    assert result.total_guidelines == 0
    assert result.total_examples == 0
    assert result.guidelines == {}
    assert result.examples == {}


@pytest.mark.asyncio
async def test_get_metadata_example_fields(mock_guideline_repo, mock_example_repo):
    mock_guideline_repo.get_all.return_value = []
    mock_example_repo.get_all.return_value = [
        Example._mock("frontend/01_api_service", "frontend", "frontend", "API service pattern"),
    ]

    result = await GetMetadataUseCase(mock_guideline_repo, mock_example_repo).execute()

    fe = result.examples["frontend"][0]
    assert fe.name == "frontend/01_api_service"
    assert fe.stack == "frontend"
    assert fe.layer == "frontend"
    assert fe.description == "API service pattern"
