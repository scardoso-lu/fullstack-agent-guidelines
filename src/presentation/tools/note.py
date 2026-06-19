from mcp.server.fastmcp import FastMCP

from src.application.dto.note_dto import CreateNoteDto, UpdateNoteDto
from src.application.use_cases.note.create import CreateNoteUseCase
from src.application.use_cases.note.delete import DeleteNoteUseCase
from src.application.use_cases.note.get_by_id import GetNoteByIdUseCase
from src.application.use_cases.note.list_all import ListNotesUseCase
from src.application.use_cases.note.update import UpdateNoteUseCase
from src.infrastructure.db.engine import get_session
from src.infrastructure.repositories.note_repository import NoteRepository
from src.utils.exc import NotFoundError


def register_note_tools(mcp: FastMCP) -> None:

    @mcp.tool(name="create_note", description="Create a new note with a title and optional content.")
    async def create_note(title: str, content: str = "") -> dict:
        async with get_session() as session:
            use_case = CreateNoteUseCase(NoteRepository(session))
            note = await use_case.execute(CreateNoteDto(title=title, content=content))
            return note.model_dump()

    @mcp.tool(name="get_note", description="Retrieve a note by its ID.")
    async def get_note(note_id: str) -> dict | None:
        async with get_session() as session:
            use_case = GetNoteByIdUseCase(NoteRepository(session))
            note = await use_case.execute(int(note_id))
            return note.model_dump() if note else None

    @mcp.tool(name="list_notes", description="List all notes with optional pagination.")
    async def list_notes(page: int = 1, page_size: int = 20) -> dict:
        async with get_session() as session:
            use_case = ListNotesUseCase(NoteRepository(session))
            result = await use_case.execute(page=page, page_size=page_size)
            return result.model_dump()

    @mcp.tool(name="update_note", description="Update the title and/or content of an existing note.")
    async def update_note(note_id: str, title: str | None = None, content: str | None = None) -> dict:
        async with get_session() as session:
            use_case = UpdateNoteUseCase(NoteRepository(session))
            note = await use_case.execute(int(note_id), UpdateNoteDto(title=title, content=content))
            return note.model_dump()

    @mcp.tool(name="delete_note", description="Delete a note by its ID. Returns true on success.")
    async def delete_note(note_id: str) -> dict:
        async with get_session() as session:
            try:
                use_case = DeleteNoteUseCase(NoteRepository(session))
                await use_case.execute(int(note_id))
                return {"deleted": True, "note_id": note_id}
            except NotFoundError as exc:
                return {"deleted": False, "error": str(exc)}
