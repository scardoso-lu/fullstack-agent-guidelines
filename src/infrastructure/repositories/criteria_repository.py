from functools import lru_cache

from src.domain.entities.compliance import ComplianceCriterion
from src.infrastructure.criteria import ALL_CRITERIA
from src.infrastructure.repositories.contract import CriteriaRepositoryInterface
from src.utils.logger import get_logger

_logger = get_logger("repo.criteria")


class CriteriaRepository(CriteriaRepositoryInterface):
    def __init__(self) -> None:
        self._all = ALL_CRITERIA
        _logger.info("CriteriaRepository init total=%d", len(self._all))

    async def get_all(self) -> list[ComplianceCriterion]:
        return list(self._all)

    async def get_by_stack(self, stack: str) -> list[ComplianceCriterion]:
        return [c for c in self._all if c.stack == stack]

    async def get_by_id(self, criterion_id: str) -> ComplianceCriterion | None:
        for c in self._all:
            if c.id == criterion_id:
                return c
        return None


@lru_cache(maxsize=1)
def get_criteria_repository() -> CriteriaRepository:
    return CriteriaRepository()
