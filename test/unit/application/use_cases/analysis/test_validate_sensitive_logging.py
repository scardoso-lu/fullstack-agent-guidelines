import pytest

from src.application.use_cases.analysis.validate_sensitive_logging import ValidateSensitiveLoggingUseCase


async def _run(source: str, filename: str = "module.py") -> dict:
    result = await ValidateSensitiveLoggingUseCase().execute(source, filename)
    return result.model_dump()


# ── clean patterns ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lazy_log_without_sensitive_data_is_clean():
    source = 'logger.info("user %s logged in", user_id)\n'
    r = await _run(source)
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_log_mentioning_password_in_message_text_is_clean():
    # The word "password" in a string literal is OK; it's the value that must not leak
    source = 'logger.info("Password reset link sent to %s", email)\n'
    r = await _run(source)
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_log_with_user_id_is_clean():
    source = 'logger.info("Created user id=%s", user.id)\n'
    r = await _run(source)
    assert r["status"] == "clean"


# ── f-string interpolation (required) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_fstring_password_in_log_is_violation():
    source = 'logger.warning(f"auth failed for {password}")\n'
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/sensitive-data-in-log" in ids


@pytest.mark.asyncio
async def test_fstring_token_in_log_is_violation():
    source = 'logger.debug(f"token={token}")\n'
    r = await _run(source)
    assert r["status"] == "violations"


@pytest.mark.asyncio
async def test_fstring_self_token_in_log_is_violation():
    source = 'logger.info(f"value={self.token}")\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/sensitive-data-in-log" in ids


# ── positional argument (required) ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_positional_password_arg_is_violation():
    source = 'logger.error("auth failed", password)\n'
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/sensitive-data-in-log" in ids


@pytest.mark.asyncio
async def test_print_with_password_is_violation():
    source = "print(password)\n"
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/sensitive-data-in-log" in ids


@pytest.mark.asyncio
async def test_print_with_token_positional_is_violation():
    source = 'print("debug:", token)\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/sensitive-data-in-log" in ids


# ── percent-style format (required) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_percent_style_secret_is_violation():
    source = 'logger.info("key=%(api_key)s", {"api_key": api_key})\n'
    r = await _run(source)
    assert r["status"] == "violations"


# ── credit card / CVV ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_credit_card_in_log_is_violation():
    source = 'logger.info(f"card={credit_card}")\n'
    r = await _run(source)
    assert r["status"] == "violations"


@pytest.mark.asyncio
async def test_cvv_in_log_is_violation():
    source = 'logger.debug(f"cvv={cvv}")\n'
    r = await _run(source)
    assert r["status"] == "violations"


# ── raw exception dump (recommended) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_str_exception_dump_is_recommended():
    source = "logger.error(str(e))\n"
    r = await _run(source)
    assert r["status"] == "warnings"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/raw-exception-dump" in ids


@pytest.mark.asyncio
async def test_repr_exception_dump_is_recommended():
    source = "logger.error(repr(e))\n"
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/logging/raw-exception-dump" in ids


# ── comments are ignored ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_comment_with_password_log_is_ignored():
    source = "# logger.info(f'password={password}')  # old debug line\n"
    r = await _run(source)
    assert r["status"] == "clean"


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_source_raises_value_error():
    with pytest.raises(ValueError, match="source is empty"):
        await ValidateSensitiveLoggingUseCase().execute("")


@pytest.mark.asyncio
async def test_finding_location_includes_filename_and_line():
    source = "x = 1\nlogger.info(f'token={token}')\n"
    r = await _run(source, "auth_service.py")
    f = next(f for f in r["findings"] if f["rule_id"] == "security/logging/sensitive-data-in-log")
    assert f["location"] == "auth_service.py:2"
