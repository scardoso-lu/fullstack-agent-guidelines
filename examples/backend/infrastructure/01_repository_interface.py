# Description: Repository interface — the contract that decouples application from storage
# Layer: infrastructure
#
# Key rules:
#   - Interface lives in contract.py — the APPLICATION imports it, not the concrete class
#   - Only domain entities in method signatures — no SQLAlchemy types, no dicts
#   - The interface doesn't know HOW data is stored (SQL, filesystem, Redis, API)
#   - Adding a new method here is the ONLY place to touch when extending the contract
#   - Concrete implementations in separate files (SQLAlchemy, filesystem, in-memory)

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.guideline import Guideline


class GuidelineRepositoryInterface(ABC):
    """
    What use cases need from storage — nothing more, nothing less.

    Production code: GuidelineRepository (reads .md files with aiofiles)
    Test code:       AsyncMock()  — no files, no DB, no network
    """

    @abstractmethod
    async def get_all(self) -> list[Guideline]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Guideline | None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str) -> list[Guideline]:
        raise NotImplementedError


# =============================================================================
# ANTI-PATTERN — do NOT do this
# =============================================================================

# Importing the concrete repo directly in a use case:
#
# from src.infrastructure.repositories.guideline_repository import GuidelineRepository
#
# class GetGuidelineUseCase:
#     def __init__(self):
#         self.repo = GuidelineRepository(Path("guidelines"))   ← hardcoded path
#
# Problems:
#   - Can't test without real files on disk
#   - Changing storage (SQL → Redis) requires editing every use case
#   - Violates Dependency Inversion Principle
