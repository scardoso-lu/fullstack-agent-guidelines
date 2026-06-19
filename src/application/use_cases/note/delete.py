from src.infrastructure.repositories.contract import NoteRepositoryInterface
from src.utils.exc import NotFoundError


class DeleteNoteUseCase:
    def __init__(self, note_repository: NoteRepositoryInterface) -> None:
        self.note_repository = note_repository

    async def execute(self, note_id: int) -> None:
        if not note_id:
            raise ValueError("Note ID cannot be empty")
        deleted = await self.note_repository.delete(note_id)
        if not deleted:
            raise NotFoundError(f"Note {note_id} not found")
