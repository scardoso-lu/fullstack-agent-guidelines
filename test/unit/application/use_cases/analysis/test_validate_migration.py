import pytest

from src.application.use_cases.analysis.validate_migration import ValidateMigrationUseCase


async def _run(source: str) -> dict:
    result = await ValidateMigrationUseCase().execute(source)
    return result.model_dump()


# ── destructive ops (required) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_drop_column_is_violation():
    r = await _run("    op.drop_column('notes', 'body')\n")
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/no-drop-column" in ids


@pytest.mark.asyncio
async def test_drop_table_is_violation():
    r = await _run("    op.drop_table('notes')\n")
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/no-drop-table" in ids


@pytest.mark.asyncio
async def test_rename_table_is_violation():
    r = await _run("    op.rename_table('notes', 'entries')\n")
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/no-rename-table" in ids


@pytest.mark.asyncio
async def test_rename_column_is_violation():
    r = await _run("    op.rename_column('notes', 'body', 'content')\n")
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/no-rename-column" in ids


# ── add_column nullable=False without server_default (required) ───────────────

@pytest.mark.asyncio
async def test_add_column_nullable_false_without_server_default_is_violation():
    source = (
        "    op.add_column(\n"
        "        'notes',\n"
        "        sa.Column('priority', sa.Integer(), nullable=False),\n"
        "    )\n"
    )
    r = await _run(source)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/add-column-nullable-false-needs-server-default" in ids


@pytest.mark.asyncio
async def test_add_column_nullable_false_with_server_default_is_clean():
    source = (
        "    op.add_column(\n"
        "        'notes',\n"
        "        sa.Column('priority', sa.Integer(), nullable=False, server_default=sa.text('0')),\n"
        "    )\n"
    )
    r = await _run(source)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/add-column-nullable-false-needs-server-default" not in ids


@pytest.mark.asyncio
async def test_add_column_nullable_true_is_clean():
    source = (
        "    op.add_column(\n"
        "        'notes',\n"
        "        sa.Column('archived_at', sa.DateTime(), nullable=True),\n"
        "    )\n"
    )
    r = await _run(source)
    assert r["status"] == "clean"


# ── recommended ops ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alter_column_is_recommended():
    r = await _run("    op.alter_column('notes', 'body', type_=sa.Text())\n")
    assert r["status"] == "warnings"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/alter-column-type-risk" in ids


@pytest.mark.asyncio
async def test_execute_raw_sql_is_recommended():
    r = await _run("    op.execute(\"UPDATE notes SET body = '' WHERE body IS NULL\")\n")
    assert r["status"] == "warnings"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/raw-sql-execute" in ids


# ── clean migration ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_simple_add_column_is_clean():
    source = (
        "def upgrade():\n"
        "    op.add_column('notes', sa.Column('archived', sa.Boolean(), nullable=True))\n"
        "\n"
        "def downgrade():\n"
        "    op.drop_column('notes', 'archived')\n"
    )
    r = await _run(source)
    # drop_column in downgrade is still flagged
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/migration/no-drop-column" in ids


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_source_raises_value_error():
    with pytest.raises(ValueError, match="source is empty"):
        await ValidateMigrationUseCase().execute("")


@pytest.mark.asyncio
async def test_finding_includes_line_location():
    r = await _run("line1\n    op.drop_column('notes', 'body')\nline3\n")
    f = next(f for f in r["findings"] if f["rule_id"] == "backend/migration/no-drop-column")
    assert f["location"] == "line:2"
