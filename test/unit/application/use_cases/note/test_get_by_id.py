import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.note_dto import NoteDto
from src.application.use_cases.note.get_by_id import GetNoteByIdUseCase
from src.domain.entities.note import Note


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_get_note_found(mock_repo):
    mock_repo.get_by_id.return_value = Note._mock(note_id=42)
    use_case = GetNoteByIdUseCase(mock_repo)
    result = await use_case.execute(42)

    assert isinstance(result, NoteDto)
    mock_repo.get_by_id.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_get_note_not_found_returns_none(mock_repo):
    mock_repo.get_by_id.return_value = None
    use_case = GetNoteByIdUseCase(mock_repo)
    result = await use_case.execute(99)

    assert result is None


@pytest.mark.asyncio
async def test_get_note_zero_id_raises(mock_repo):
    use_case = GetNoteByIdUseCase(mock_repo)
    with pytest.raises(ValueError):
        await use_case.execute(0)
