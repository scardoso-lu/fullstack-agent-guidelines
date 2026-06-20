from abc import ABC, abstractmethod

from src.domain.entities.example import Example
from src.domain.entities.guideline import Guideline


class GuidelineRepositoryInterface(ABC):
    @abstractmethod
    async def get_all(self) -> list[Guideline]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Guideline | None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str) -> list[Guideline]:
        raise NotImplementedError


class ExampleRepositoryInterface(ABC):
    @abstractmethod
    async def get_all(self) -> list[Example]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_name(self, name: str) -> Example | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_layer(self, layer: str) -> list[Example]:
        raise NotImplementedError
