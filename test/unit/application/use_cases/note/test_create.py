import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.dto.note_dto import CreateNoteDto, NoteDto
from src.application.use_cases.note.create import CreateNoteUseCase
from src.domain.entities.note import Note


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_create_note_success(mock_repo):
    note = Note._mock(note_id=1)
    mock_repo.create.return_value = note

    use_case = CreateNoteUseCase(mock_repo)
    dto = CreateNoteDto(title="Hello", content="World")
    result = await use_case.execute(dto)

    assert isinstance(result, NoteDto)
    assert result.title == "Test Note 1"
    mock_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_note_empty_title_raises(mock_repo):
    use_case = CreateNoteUseCase(mock_repo)
    dto = CreateNoteDto(title="   ", content="Some content")

    with pytest.raises(ValueError, match="Title cannot be empty"):
        await use_case.execute(dto)

    mock_repo.create.assert_not_called()
