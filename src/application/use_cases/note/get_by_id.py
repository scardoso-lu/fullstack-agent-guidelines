from src.application.dto.note_dto import NoteDto
from src.infrastructure.repositories.contract import NoteRepositoryInterface


class GetNoteByIdUseCase:
    def __init__(self, note_repository: NoteRepositoryInterface) -> None:
        self.note_repository = note_repository

    async def execute(self, note_id: int) -> NoteDto | None:
        if not note_id:
            raise ValueError("Note ID cannot be empty")
        note = await self.note_repository.get_by_id(note_id)
        if note:
            return NoteDto.model_validate(note)
        return None
