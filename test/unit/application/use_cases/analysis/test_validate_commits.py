import pytest

from src.application.use_cases.analysis.validate_commits import ValidateCommitMessagesUseCase


async def _run(git_log: str) -> dict:
    result = await ValidateCommitMessagesUseCase().execute(git_log)
    return result.model_dump()


# ── format violations (required) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_conventional_commit_is_violation():
    r = await _run("abc12345 Added note feature")
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "agile/commits/conventional-format" in ids


@pytest.mark.asyncio
async def test_wip_commit_is_violation():
    r = await _run("abc12345 WIP: half done")
    assert r["status"] == "violations"


# ── subject length (recommended) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_long_subject_is_recommended():
    long_subject = "feat(auth): " + "a" * 65  # > 72 chars total
    r = await _run(f"abc12345 {long_subject}")
    ids = [f["rule_id"] for f in r["findings"]]
    assert "agile/commits/subject-length" in ids


@pytest.mark.asyncio
async def test_exactly_72_char_subject_is_clean():
    subject = "feat(auth): " + "a" * 60  # exactly 72 chars
    assert len(subject) == 72
    r = await _run(f"abc12345 {subject}")
    ids = [f["rule_id"] for f in r["findings"]]
    assert "agile/commits/subject-length" not in ids


# ── clean commits ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_conventional_commit_is_clean():
    r = await _run("abc12345 feat(notes): add create note endpoint")
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_all_conventional_types_are_accepted():
    types = ["feat", "fix", "docs", "chore", "refactor", "test", "ci", "perf", "build", "style", "revert"]
    for t in types:
        r = await _run(f"abc12345 {t}: do something")
        ids = [f["rule_id"] for f in r["findings"]]
        assert "agile/commits/conventional-format" not in ids, f"type {t!r} should be valid"


@pytest.mark.asyncio
async def test_scope_in_parens_is_accepted():
    r = await _run("abc12345 feat(auth): add password reset")
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_breaking_change_exclamation_is_accepted():
    r = await _run("abc12345 feat(api)!: remove deprecated endpoint")
    assert r["status"] == "clean"


# ── skipped commits ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_merge_commit_is_skipped():
    r = await _run("abc12345 Merge branch 'feature/foo' into main")
    assert r["status"] == "clean"
    assert r["total_items"] == 0


@pytest.mark.asyncio
async def test_revert_auto_commit_is_skipped():
    r = await _run('abc12345 Revert "feat(notes): add create note endpoint"')
    assert r["status"] == "clean"
    assert r["total_items"] == 0


# ── multiple commits ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mixed_commits_reports_all_violations():
    log = (
        "abc12345 feat(notes): add create note endpoint\n"
        "def67890 Added update feature\n"
        "ghi11111 fix: resolve null pointer\n"
    )
    r = await _run(log)
    assert r["status"] == "violations"
    assert r["required_count"] == 1
    assert r["total_items"] == 3


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_git_log_raises_value_error():
    with pytest.raises(ValueError, match="git_log is empty"):
        await ValidateCommitMessagesUseCase().execute("")


@pytest.mark.asyncio
async def test_finding_location_is_short_hash():
    r = await _run("abcdefgh12345 bad commit message")
    f = r["findings"][0]
    assert len(f["location"]) == 8
