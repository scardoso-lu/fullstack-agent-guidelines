import pytest

from src.application.use_cases.analysis.validate_logs import ValidateLogCallsUseCase


async def _run(source: str, filename: str = "module.py") -> dict:
    result = await ValidateLogCallsUseCase().execute(source, filename)
    return result.model_dump()


# ── print() violations (required) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_print_call_is_violation():
    r = await _run('print("hello")\n')
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/logging/no-print-statements" in ids


@pytest.mark.asyncio
async def test_print_with_variable_is_violation():
    r = await _run("print(result)\n")
    assert r["status"] == "violations"


@pytest.mark.asyncio
async def test_finding_location_includes_line_number():
    source = "x = 1\nprint(x)\n"
    r = await _run(source, "my_module.py")
    f = next(f for f in r["findings"] if f["rule_id"] == "backend/logging/no-print-statements")
    assert f["location"] == "my_module.py:2"


# ── f-string in log (recommended) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fstring_in_logger_info_is_recommended():
    r = await _run('logger.info(f"result is {result}")\n')
    assert r["status"] == "warnings"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/logging/no-fstring-in-log" in ids


@pytest.mark.asyncio
async def test_fstring_in_logger_warning_is_recommended():
    r = await _run('logger.warning(f"error: {err}")\n')
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/logging/no-fstring-in-log" in ids


@pytest.mark.asyncio
async def test_fstring_in_logging_module_is_recommended():
    r = await _run('logging.error(f"bad thing: {e}")\n')
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/logging/no-fstring-in-log" in ids


# ── clean patterns ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lazy_logger_format_is_clean():
    r = await _run('logger.info("result is %s", result)\n')
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_no_logging_issues_is_clean():
    source = (
        "from src.utils.logger import get_logger\n"
        "_logger = get_logger(__name__)\n"
        "\n"
        "def do_thing(x: int) -> int:\n"
        '    _logger.info("processing %d", x)\n'
        "    return x * 2\n"
    )
    r = await _run(source)
    assert r["status"] == "clean"


# ── comment lines are skipped ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_print_in_comment_is_ignored():
    r = await _run("# print(debug_info)  <- old debug line\n")
    assert r["status"] == "clean"


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_source_raises_value_error():
    with pytest.raises(ValueError, match="source is empty"):
        await ValidateLogCallsUseCase().execute("")


@pytest.mark.asyncio
async def test_total_items_is_line_count():
    source = "x = 1\ny = 2\nz = 3\n"
    r = await _run(source)
    assert r["total_items"] == 3
