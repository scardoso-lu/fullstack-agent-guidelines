import pytest
from pathlib import Path

from src.infrastructure.repositories.guideline_repository import GuidelineRepository

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "guidelines"


@pytest.mark.asyncio
async def test_get_all_loads_all_fixture_files():
    repo = GuidelineRepository(FIXTURES_DIR)
    results = await repo.get_all()
    assert len(results) == 2
    slugs = {g.slug for g in results}
    assert "01-test-alpha" in slugs
    assert "02-test-beta" in slugs


@pytest.mark.asyncio
async def test_get_by_slug_found():
    repo = GuidelineRepository(FIXTURES_DIR)
    g = await repo.get_by_slug("01-test-alpha")
    assert g is not None
    assert g.title == "Test Alpha Guideline"
    assert "architecture" in g.content


@pytest.mark.asyncio
async def test_get_by_slug_missing_returns_none():
    repo = GuidelineRepository(FIXTURES_DIR)
    g = await repo.get_by_slug("99-nonexistent")
    assert g is None


@pytest.mark.asyncio
async def test_search_finds_keyword_in_content():
    repo = GuidelineRepository(FIXTURES_DIR)
    results = await repo.search("architecture")
    assert any(g.slug == "01-test-alpha" for g in results)


@pytest.mark.asyncio
async def test_search_case_insensitive():
    repo = GuidelineRepository(FIXTURES_DIR)
    results_lower = await repo.search("solid")
    results_upper = await repo.search("SOLID")
    assert len(results_lower) == len(results_upper)


@pytest.mark.asyncio
async def test_search_no_match_returns_empty():
    repo = GuidelineRepository(FIXTURES_DIR)
    results = await repo.search("xyznotfound12345")
    assert results == []


@pytest.mark.asyncio
async def test_cache_is_none_before_first_call():
    repo = GuidelineRepository(FIXTURES_DIR)
    assert repo._cache is None


@pytest.mark.asyncio
async def test_cache_is_populated_after_first_call():
    repo = GuidelineRepository(FIXTURES_DIR)
    await repo.get_all()
    assert repo._cache is not None
    assert len(repo._cache) == 2


@pytest.mark.asyncio
async def test_tags_derived_from_slug():
    repo = GuidelineRepository(FIXTURES_DIR)
    g = await repo.get_by_slug("01-test-alpha")
    assert "test" in g.tags
    assert "alpha" in g.tags
