from src.application.dto.note_dto import NoteDto, PagedNotesDto
from src.infrastructure.repositories.contract import NoteRepositoryInterface


class ListNotesUseCase:
    def __init__(self, note_repository: NoteRepositoryInterface) -> None:
        self.note_repository = note_repository

    async def execute(self, page: int = 1, page_size: int = 20) -> PagedNotesDto:
        if page < 1:
            raise ValueError("Page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("Page size must be between 1 and 100")
        paged = await self.note_repository.list_all(page=page, page_size=page_size)
        return PagedNotesDto(
            items=[NoteDto.model_validate(n) for n in paged.items],
            total=paged.total,
            page=paged.page,
            page_size=paged.page_size,
        )
