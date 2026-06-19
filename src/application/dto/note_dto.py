from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NoteDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateNoteDto(BaseModel):
    title: str
    content: str = ""


class UpdateNoteDto(BaseModel):
    title: str | None = None
    content: str | None = None


class PagedNotesDto(BaseModel):
    items: list[NoteDto]
    total: int
    page: int
    page_size: int
