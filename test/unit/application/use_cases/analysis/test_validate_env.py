import pytest

from src.application.use_cases.analysis.validate_env import ValidateEnvCompletenessUseCase


async def _run(settings_source: str, env_example: str) -> dict:
    result = await ValidateEnvCompletenessUseCase().execute(settings_source, env_example)
    return result.model_dump()


_SETTINGS_SOURCE = """\
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    DEBUG: bool = False
    MAX_CONNECTIONS: int = 10
"""

_ENV_EXAMPLE_FULL = """\
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=supersecretkey
DEBUG=false
MAX_CONNECTIONS=10
"""

_ENV_EXAMPLE_PARTIAL = """\
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=supersecretkey
"""


# ── clean ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_fields_documented_is_clean():
    r = await _run(_SETTINGS_SOURCE, _ENV_EXAMPLE_FULL)
    assert r["status"] == "clean"
    assert r["findings"] == []
    assert r["total_items"] == 4


# ── violations ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_field_in_env_example_is_violation():
    r = await _run(_SETTINGS_SOURCE, _ENV_EXAMPLE_PARTIAL)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/env/missing-in-env-example" in ids


@pytest.mark.asyncio
async def test_missing_debug_and_max_connections_are_reported():
    r = await _run(_SETTINGS_SOURCE, _ENV_EXAMPLE_PARTIAL)
    locations = [f["location"] for f in r["findings"]]
    assert "field:DEBUG" in locations
    assert "field:MAX_CONNECTIONS" in locations


@pytest.mark.asyncio
async def test_required_count_matches_missing_fields():
    r = await _run(_SETTINGS_SOURCE, _ENV_EXAMPLE_PARTIAL)
    assert r["required_count"] == 2


# ── env.example with comments ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_comments_in_env_example_are_ignored():
    env_with_comments = """\
# Database configuration
DATABASE_URL=postgresql://user:pass@localhost/db
# Auth
SECRET_KEY=supersecretkey
DEBUG=false
MAX_CONNECTIONS=10
"""
    r = await _run(_SETTINGS_SOURCE, env_with_comments)
    assert r["status"] == "clean"


# ── settings class detection ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_class_not_named_settings_raises():
    source = """\
class Config:
    DATABASE_URL: str
"""
    with pytest.raises(ValueError, match="No Settings fields detected"):
        await _run(source, "DATABASE_URL=test\n")


@pytest.mark.asyncio
async def test_empty_settings_source_raises():
    with pytest.raises(ValueError, match="settings_source is empty"):
        await _run("", "DATABASE_URL=test\n")


@pytest.mark.asyncio
async def test_empty_env_example_raises():
    with pytest.raises(ValueError, match="env_example is empty"):
        await _run(_SETTINGS_SOURCE, "")


# ── class name variants ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_class_ending_in_settings_is_detected():
    source = """\
class ProductionSettings(BaseSettings):
    API_KEY: str
"""
    r = await _run(source, "API_KEY=test\n")
    assert r["status"] == "clean"
    assert r["total_items"] == 1
