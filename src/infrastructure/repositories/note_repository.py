from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.note import Note
from src.infrastructure.repositories.contract import NoteRepositoryInterface, PagedItems


class NoteRepository(NoteRepositoryInterface):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, note_id: int) -> Note | None:
        result = await self.session.execute(
            select(Note).where(Note._id == note_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, page: int = 1, page_size: int = 20) -> PagedItems[Note]:
        offset = (page - 1) * page_size

        total_result = await self.session.execute(select(func.count()).select_from(Note))
        total = total_result.scalar_one()

        items_result = await self.session.execute(
            select(Note).order_by(Note._id.desc()).offset(offset).limit(page_size)
        )
        items = list(items_result.scalars().all())

        return PagedItems(items=items, total=total, page=page, page_size=page_size)

    async def create(self, note: Note) -> Note:
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def update(self, note: Note) -> Note:
        merged = await self.session.merge(note)
        await self.session.flush()
        await self.session.refresh(merged)
        return merged

    async def delete(self, note_id: int) -> bool:
        note = await self.get_by_id(note_id)
        if note is None:
            return False
        await self.session.delete(note)
        await self.session.flush()
        return True
