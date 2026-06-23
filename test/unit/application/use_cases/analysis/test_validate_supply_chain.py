import pytest

from src.application.use_cases.analysis.validate_supply_chain import ValidateSupplyChainUseCase


async def _run(manifest: str) -> dict:
    result = await ValidateSupplyChainUseCase().execute(manifest)
    return result.model_dump()


# ── clean manifests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clean_pyproject_toml_is_clean():
    manifest = """
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "0.115.0"
pydantic = "2.11.1"
sqlalchemy = "2.0.36"
"""
    r = await _run(manifest)
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_clean_package_json_is_clean():
    manifest = """
{
  "dependencies": {
    "next": "15.1.0",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  }
}
"""
    r = await _run(manifest)
    assert r["status"] == "clean"


# ── VCS sources (required) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toml_git_source_is_violation():
    manifest = 'requests = {git = "https://github.com/psf/requests", rev = "main"}\n'
    r = await _run(manifest)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-vcs-source" in ids


@pytest.mark.asyncio
async def test_npm_git_plus_https_is_violation():
    manifest = '"my-pkg": "git+https://github.com/org/my-pkg#abc123"\n'
    r = await _run(manifest)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-vcs-source" in ids


@pytest.mark.asyncio
async def test_npm_github_shorthand_is_violation():
    manifest = '"my-pkg": "github:org/my-pkg#abc123"\n'
    r = await _run(manifest)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-vcs-source" in ids


# ── direct URL sources (required) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toml_url_source_is_violation():
    manifest = 'evil = {url = "https://example.com/evil-1.0.tar.gz"}\n'
    r = await _run(manifest)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-direct-url-source" in ids


@pytest.mark.asyncio
async def test_npm_direct_url_is_violation():
    manifest = '"pkg": "https://example.com/pkg.tgz"\n'
    r = await _run(manifest)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-direct-url-source" in ids


# ── local path sources (required) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toml_local_path_is_violation():
    manifest = 'my-lib = {path = "../my-lib"}\n'
    r = await _run(manifest)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-local-path-source" in ids


@pytest.mark.asyncio
async def test_npm_file_protocol_is_violation():
    manifest = '"local-pkg": "file:../local-pkg"\n'
    r = await _run(manifest)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-local-path-source" in ids


# ── wildcard / unconstrained (required) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_wildcard_asterisk_is_violation():
    manifest = 'requests = "*"\n'
    r = await _run(manifest)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-wildcard-version" in ids


@pytest.mark.asyncio
async def test_npm_latest_is_violation():
    manifest = '"react": "latest"\n'
    r = await _run(manifest)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-wildcard-version" in ids


# ── pre-release versions (recommended) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_pep440_beta_version_is_recommended():
    manifest = 'some-lib = "2.0.0b2"\n'
    r = await _run(manifest)
    assert r["status"] == "warnings"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-prerelease-version" in ids


@pytest.mark.asyncio
async def test_pep440_rc_version_is_recommended():
    manifest = 'some-lib = "1.0.0rc1"\n'
    r = await _run(manifest)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-prerelease-version" in ids


@pytest.mark.asyncio
async def test_npm_beta_semver_is_recommended():
    manifest = '"pkg": "1.0.0-beta.1"\n'
    r = await _run(manifest)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "supply-chain/no-prerelease-version" in ids


@pytest.mark.asyncio
async def test_stable_version_is_not_flagged_as_prerelease():
    manifest = 'fastapi = "0.115.0"\n'
    r = await _run(manifest)
    assert r["status"] == "clean"


# ── comments and blank lines are ignored ─────────────────────────────────────

@pytest.mark.asyncio
async def test_comment_with_git_url_is_ignored():
    manifest = '# git = "https://github.com/..." — do not use this\nfastapi = "0.115.0"\n'
    r = await _run(manifest)
    assert r["status"] == "clean"


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_manifest_raises_value_error():
    with pytest.raises(ValueError, match="manifest is empty"):
        await ValidateSupplyChainUseCase().execute("")


@pytest.mark.asyncio
async def test_finding_location_includes_line_number():
    manifest = "fastapi = \"0.115.0\"\nevil = {git = \"https://github.com/evil/evil\"}\n"
    r = await _run(manifest)
    f = next(f for f in r["findings"] if f["rule_id"] == "supply-chain/no-vcs-source")
    assert f["location"] == "line:2"
