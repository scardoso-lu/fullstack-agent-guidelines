from src.application.dto.note_dto import CreateNoteDto, NoteDto
from src.domain.entities.note import Note
from src.infrastructure.repositories.contract import NoteRepositoryInterface


class CreateNoteUseCase:
    def __init__(self, note_repository: NoteRepositoryInterface) -> None:
        self.note_repository = note_repository

    async def execute(self, dto: CreateNoteDto) -> NoteDto:
        if not dto.title.strip():
            raise ValueError("Title cannot be empty")
        note = Note(title=dto.title.strip(), content=dto.content)
        saved = await self.note_repository.create(note)
        return NoteDto.model_validate(saved)
