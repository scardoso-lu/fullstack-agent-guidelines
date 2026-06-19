from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, List, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.note import Note

T = TypeVar("T")


@dataclass
class PagedItems(Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int


class BaseRepository(ABC):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


class NoteRepositoryInterface(BaseRepository):
    @abstractmethod
    async def get_by_id(self, note_id: int) -> Note | None:
        raise NotImplementedError

    @abstractmethod
    async def list_all(
        self, page: int = 1, page_size: int = 20
    ) -> PagedItems[Note]:
        raise NotImplementedError

    @abstractmethod
    async def create(self, note: Note) -> Note:
        raise NotImplementedError

    @abstractmethod
    async def update(self, note: Note) -> Note:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, note_id: int) -> bool:
        raise NotImplementedError
