from src.application.dto.note_dto import NoteDto, UpdateNoteDto
from src.infrastructure.repositories.contract import NoteRepositoryInterface
from src.utils.exc import NotFoundError


class UpdateNoteUseCase:
    def __init__(self, note_repository: NoteRepositoryInterface) -> None:
        self.note_repository = note_repository

    async def execute(self, note_id: int, dto: UpdateNoteDto) -> NoteDto:
        if not note_id:
            raise ValueError("Note ID cannot be empty")
        note = await self.note_repository.get_by_id(note_id)
        if note is None:
            raise NotFoundError(f"Note {note_id} not found")
        if dto.title is not None:
            if not dto.title.strip():
                raise ValueError("Title cannot be empty")
            note.title = dto.title.strip()
        if dto.content is not None:
            note.content = dto.content
        updated = await self.note_repository.update(note)
        return NoteDto.model_validate(updated)
