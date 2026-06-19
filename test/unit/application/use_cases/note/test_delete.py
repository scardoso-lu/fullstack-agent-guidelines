import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.note.delete import DeleteNoteUseCase
from src.utils.exc import NotFoundError


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.delete = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_delete_note_success(mock_repo):
    mock_repo.delete.return_value = True
    use_case = DeleteNoteUseCase(mock_repo)
    await use_case.execute(1)
    mock_repo.delete.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_delete_note_not_found_raises(mock_repo):
    mock_repo.delete.return_value = False
    use_case = DeleteNoteUseCase(mock_repo)
    with pytest.raises(NotFoundError):
        await use_case.execute(999)
