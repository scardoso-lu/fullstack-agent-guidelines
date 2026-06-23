import pytest

from src.application.use_cases.analysis.validate_tests import ValidateTestNamesUseCase


async def _run(source: str, filename: str = "test_note.py") -> dict:
    result = await ValidateTestNamesUseCase().execute(source, filename)
    return result.model_dump()


_GOOD_SOURCE = """\
import pytest


async def test_create_note_returns_created_id():
    pass


async def test_get_note_returns_not_found_when_missing():
    pass


async def test_delete_note_removes_from_repository():
    pass
"""

_DUPLICATE_SOURCE = """\
async def test_create_note_returns_created_id():
    pass

async def test_create_note_returns_created_id():
    pass
"""

_SHORT_NAME_SOURCE = """\
async def test_note():
    pass

async def test_it():
    pass
"""


# ── clean ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_descriptive_unique_names_is_clean():
    r = await _run(_GOOD_SOURCE)
    assert r["status"] == "clean"
    assert r["findings"] == []
    assert r["total_items"] == 3


# ── duplicate detection (required) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_test_name_is_violation():
    r = await _run(_DUPLICATE_SOURCE)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/tests/no-duplicate-test-names" in ids


@pytest.mark.asyncio
async def test_duplicate_finding_location_includes_name():
    r = await _run(_DUPLICATE_SOURCE, "test_module.py")
    f = next(f for f in r["findings"] if f["rule_id"] == "qa/tests/no-duplicate-test-names")
    assert "test_create_note_returns_created_id" in f["location"]
    assert "test_module.py" in f["location"]


# ── short names (recommended) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_short_test_name_is_recommended():
    r = await _run(_SHORT_NAME_SOURCE)
    assert r["status"] == "warnings"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/tests/descriptive-test-names" in ids


@pytest.mark.asyncio
async def test_two_token_name_is_recommended():
    source = "async def test_create_note():\n    pass\n"
    r = await _run(source)
    # "create_note" → 2 tokens, below threshold of 3
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/tests/descriptive-test-names" in ids


@pytest.mark.asyncio
async def test_three_token_name_is_clean():
    source = "async def test_create_note_ok():\n    pass\n"
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/tests/descriptive-test-names" not in ids


# ── sync tests are also detected ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_test_functions_are_detected():
    source = "def test_create_note_returns_id():\n    pass\n"
    r = await _run(source)
    assert r["total_items"] == 1
    assert r["status"] == "clean"


# ── class-method tests are detected ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_class_method_tests_are_detected():
    source = (
        "class TestNotes:\n"
        "    def test_create_note_returns_id(self):\n"
        "        pass\n"
        "\n"
        "    async def test_get_note_returns_not_found(self):\n"
        "        pass\n"
    )
    r = await _run(source)
    assert r["total_items"] == 2
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_class_method_duplicate_is_violation():
    source = (
        "class TestNotes:\n"
        "    def test_create_note_returns_id(self):\n"
        "        pass\n"
        "\n"
        "    def test_create_note_returns_id(self):\n"
        "        pass\n"
    )
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/tests/no-duplicate-test-names" in ids


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_source_raises_value_error():
    with pytest.raises(ValueError, match="source is empty"):
        await ValidateTestNamesUseCase().execute("")


@pytest.mark.asyncio
async def test_no_test_functions_raises_value_error():
    with pytest.raises(ValueError, match="No test functions found"):
        await _run("def helper():\n    pass\n")
