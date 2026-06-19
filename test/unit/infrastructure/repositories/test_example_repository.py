import pytest
from pathlib import Path

from src.infrastructure.repositories.example_repository import ExampleRepository

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "examples"


@pytest.mark.asyncio
async def test_get_all_loads_fixture_files():
    repo = ExampleRepository(FIXTURES_DIR)
    results = await repo.get_all()
    assert len(results) == 3
    names = {e.name for e in results}
    assert "domain/01_test_fixture" in names
    assert "application/01_test_fixture" in names
    assert "frontend/01_test_fixture" in names


@pytest.mark.asyncio
async def test_get_by_name_found():
    repo = ExampleRepository(FIXTURES_DIR)
    e = await repo.get_by_name("domain/01_test_fixture")
    assert e is not None
    assert e.layer == "domain"
    assert e.filename == "01_test_fixture.py"


@pytest.mark.asyncio
async def test_get_by_name_missing_returns_none():
    repo = ExampleRepository(FIXTURES_DIR)
    e = await repo.get_by_name("domain/99_nonexistent")
    assert e is None


@pytest.mark.asyncio
async def test_get_by_layer_returns_correct_examples():
    repo = ExampleRepository(FIXTURES_DIR)
    results = await repo.get_by_layer("domain")
    assert len(results) == 1
    assert results[0].layer == "domain"


@pytest.mark.asyncio
async def test_get_by_layer_unknown_returns_empty():
    repo = ExampleRepository(FIXTURES_DIR)
    results = await repo.get_by_layer("nonexistent")
    assert results == []


@pytest.mark.asyncio
async def test_description_parsed_from_comment():
    repo = ExampleRepository(FIXTURES_DIR)
    e = await repo.get_by_name("domain/01_test_fixture")
    assert e is not None
    assert "frozen dataclass" in e.description


@pytest.mark.asyncio
async def test_cache_is_none_before_first_call():
    repo = ExampleRepository(FIXTURES_DIR)
    assert repo._cache is None


@pytest.mark.asyncio
async def test_cache_populated_after_first_call():
    repo = ExampleRepository(FIXTURES_DIR)
    await repo.get_all()
    assert repo._cache is not None
    assert len(repo._cache) == 3
