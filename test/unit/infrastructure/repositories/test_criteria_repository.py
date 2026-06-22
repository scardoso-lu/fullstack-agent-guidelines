import pytest

from src.infrastructure.repositories.criteria_repository import CriteriaRepository


@pytest.fixture
def repo():
    return CriteriaRepository()


@pytest.mark.asyncio
async def test_get_all_returns_non_empty_list(repo):
    result = await repo.get_all()
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_by_stack_backend_returns_only_backend_criteria(repo):
    result = await repo.get_by_stack("backend")
    assert len(result) > 0
    assert all(c.stack == "backend" for c in result)


@pytest.mark.asyncio
async def test_get_by_stack_frontend_returns_only_frontend_criteria(repo):
    result = await repo.get_by_stack("frontend")
    assert len(result) > 0
    assert all(c.stack == "frontend" for c in result)


@pytest.mark.asyncio
async def test_get_by_stack_unknown_returns_empty_list(repo):
    result = await repo.get_by_stack("nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_get_by_id_known_criterion(repo):
    result = await repo.get_by_id("backend/dod/lint-clean")
    assert result is not None
    assert result.id == "backend/dod/lint-clean"
    assert result.stack == "backend"


@pytest.mark.asyncio
async def test_get_by_id_unknown_returns_none(repo):
    result = await repo.get_by_id("does/not/exist")
    assert result is None


@pytest.mark.asyncio
async def test_all_criteria_have_valid_severities(repo):
    result = await repo.get_all()
    valid = {"required", "recommended"}
    for c in result:
        assert c.severity in valid, f"{c.id} has invalid severity {c.severity!r}"


@pytest.mark.asyncio
async def test_all_criteria_have_valid_check_types(repo):
    result = await repo.get_all()
    valid = {"command", "code_pattern", "manual"}
    for c in result:
        assert c.check_type in valid, f"{c.id} has invalid check_type {c.check_type!r}"
