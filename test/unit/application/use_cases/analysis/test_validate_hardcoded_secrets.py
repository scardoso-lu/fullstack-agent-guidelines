import pytest

from src.application.use_cases.analysis.validate_hardcoded_secrets import ValidateHardcodedSecretsUseCase


async def _run(source: str, filename: str = "module.py") -> dict:
    result = await ValidateHardcodedSecretsUseCase().execute(source, filename)
    return result.model_dump()


# ── provider API key patterns (required, always) ──────────────────────────────

@pytest.mark.asyncio
async def test_stripe_live_key_is_violation():
    source = 'STRIPE_KEY = "sk_live_abcdefghijklmnopqrst"\n'
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


@pytest.mark.asyncio
async def test_stripe_test_key_is_violation():
    source = 'key = "sk_test_abcdefghijklmnopqrst"\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


@pytest.mark.asyncio
async def test_stripe_webhook_secret_is_violation():
    source = 'WEBHOOK = "whsec_abcdefghijklmnopqrst"\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


@pytest.mark.asyncio
async def test_aws_access_key_is_violation():
    source = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


@pytest.mark.asyncio
async def test_github_pat_is_violation():
    source = 'GH_TOKEN = "ghp_' + 'a' * 36 + '"\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


@pytest.mark.asyncio
async def test_slack_bot_token_is_violation():
    # Clearly fake value constructed to match the pattern without being a real token
    fake_slack = "xoxb-" + "X" * 12 + "-" + "Y" * 12 + "-" + "Z" * 24
    source = f'SLACK = "{fake_slack}"\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


@pytest.mark.asyncio
async def test_provider_key_flagged_even_in_test_file():
    source = 'key = "sk_live_abcdefghijklmnopqrst"\n'
    r = await _run(source, "test_payments.py")
    # Provider keys are always flagged regardless of file type
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-provider-key" in ids


# ── encoded JWT (required, non-test files only) ───────────────────────────────

@pytest.mark.asyncio
async def test_encoded_jwt_is_violation():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV"
    r = await _run(f'TOKEN = "{token}"\n')
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-jwt" in ids


@pytest.mark.asyncio
async def test_jwt_in_test_file_is_exempt():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV"
    r = await _run(f'TOKEN = "{token}"\n', "test_auth.py")
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-jwt" not in ids


# ── generic sensitive variable assignment (required, non-test files) ──────────

@pytest.mark.asyncio
async def test_hardcoded_password_is_violation():
    source = 'password = "SuperSecret123!"\n'
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-secret-variable" in ids


@pytest.mark.asyncio
async def test_hardcoded_api_key_is_violation():
    source = 'api_key = "real-key-value-here"\n'
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-secret-variable" in ids


@pytest.mark.asyncio
async def test_placeholder_value_is_not_flagged():
    # Placeholder values like "changeme", "your_secret" are exempt
    r = await _run('secret = "changeme"\n')
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-secret-variable" not in ids


@pytest.mark.asyncio
async def test_example_placeholder_is_not_flagged():
    r = await _run('password = "example"\n')
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-secret-variable" not in ids


@pytest.mark.asyncio
async def test_generic_secret_in_test_file_is_exempt():
    r = await _run('password = "TestPassword123"\n', "test_auth.py")
    ids = [f["rule_id"] for f in r["findings"]]
    assert "security/secrets/hardcoded-secret-variable" not in ids


# ── clean code ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_settings_field_without_default_is_clean():
    source = "class Settings(BaseSettings):\n    SECRET_KEY: str\n    DATABASE_URL: str\n"
    r = await _run(source)
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_env_var_read_is_clean():
    source = 'api_key = os.environ["API_KEY"]\n'
    r = await _run(source)
    assert r["status"] == "clean"


# ── comments are ignored ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_commented_secret_is_ignored():
    source = '# password = "SuperSecret"  # do not hardcode!\n'
    r = await _run(source)
    assert r["status"] == "clean"


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_source_raises_value_error():
    with pytest.raises(ValueError, match="source is empty"):
        await ValidateHardcodedSecretsUseCase().execute("")


@pytest.mark.asyncio
async def test_finding_includes_line_location():
    source = "x = 1\npassword = \"real-password\"\n"
    r = await _run(source, "config.py")
    f = next(f for f in r["findings"] if f["rule_id"] == "security/secrets/hardcoded-secret-variable")
    assert f["location"] == "config.py:2"
