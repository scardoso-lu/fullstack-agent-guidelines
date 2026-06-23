import pytest

from src.application.use_cases.analysis.validate_imports import ValidateImportDirectionsUseCase


async def _run(grep_output: str) -> dict:
    result = await ValidateImportDirectionsUseCase().execute(grep_output)
    return result.model_dump()


# ── violations ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_domain_importing_application_is_violation():
    r = await _run(
        "src/domain/entities/note.py:3:from src.application.dto.note_dto import NoteDto"
    )
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/imports/domain-no-application" in ids


@pytest.mark.asyncio
async def test_domain_importing_infrastructure_is_violation():
    r = await _run(
        "src/domain/entities/note.py:5:from src.infrastructure.repositories import something"
    )
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/imports/domain-no-infrastructure" in ids


@pytest.mark.asyncio
async def test_domain_importing_presentation_is_violation():
    r = await _run(
        "src/domain/entities/note.py:7:from src.presentation.tools import something"
    )
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/imports/domain-no-presentation" in ids


@pytest.mark.asyncio
async def test_application_importing_presentation_is_violation():
    r = await _run(
        "src/application/use_cases/note/create.py:2:from src.presentation.tools import something"
    )
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/imports/application-no-presentation" in ids


@pytest.mark.asyncio
async def test_infrastructure_importing_presentation_is_violation():
    r = await _run(
        "src/infrastructure/repositories/note_repository.py:2:from src.presentation.tools import something"
    )
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/imports/infrastructure-no-presentation" in ids


# ── allowed imports ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_application_importing_domain_is_clean():
    r = await _run(
        "src/application/use_cases/note/create.py:2:from src.domain.entities.note import Note"
    )
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_application_importing_contract_is_clean():
    r = await _run(
        "src/application/use_cases/note/create.py:3:"
        "from src.infrastructure.repositories.contract import NoteRepositoryInterface"
    )
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_infrastructure_importing_domain_is_clean():
    r = await _run(
        "src/infrastructure/repositories/note_repository.py:2:"
        "from src.domain.entities.note import Note"
    )
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_infrastructure_importing_application_is_clean():
    r = await _run(
        "src/infrastructure/repositories/note_repository.py:3:"
        "from src.application.dto.note_dto import NoteDto"
    )
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_presentation_importing_any_layer_is_clean():
    lines = "\n".join([
        "src/presentation/routes/note_router.py:2:from src.domain.entities.note import Note",
        "src/presentation/routes/note_router.py:3:from src.application.use_cases.note.create import CreateNoteUseCase",
        "src/presentation/routes/note_router.py:4:from src.infrastructure.repositories.contract import NoteRepositoryInterface",
    ])
    r = await _run(lines)
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_domain_importing_stdlib_is_clean():
    r = await _run(
        "src/domain/entities/note.py:1:from datetime import datetime"
    )
    assert r["status"] == "clean"


# ── application → infrastructure (non-contract) ───────────────────────────────

@pytest.mark.asyncio
async def test_application_importing_non_contract_infrastructure_is_violation():
    r = await _run(
        "src/application/use_cases/note/create.py:5:"
        "from src.infrastructure.repositories.note_repository import NoteRepository"
    )
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "backend/imports/application-no-infrastructure" in ids


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_grep_output_raises_value_error():
    with pytest.raises(ValueError, match="grep_output is empty"):
        await ValidateImportDirectionsUseCase().execute("")


@pytest.mark.asyncio
async def test_comment_lines_are_ignored():
    r = await _run("# grep output follows\nsrc/domain/entities/note.py:1:from datetime import datetime")
    assert r["status"] == "clean"
    assert r["total_items"] == 1


@pytest.mark.asyncio
async def test_unknown_layer_file_is_skipped():
    r = await _run("scripts/seed.py:1:from src.application.dto import something")
    assert r["status"] == "clean"
    assert r["findings"] == []


@pytest.mark.asyncio
async def test_total_items_counts_unique_files():
    lines = "\n".join([
        "src/domain/entities/note.py:1:from datetime import datetime",
        "src/domain/entities/note.py:2:from typing import Optional",
        "src/application/use_cases/note/create.py:1:from src.domain.entities.note import Note",
    ])
    r = await _run(lines)
    assert r["total_items"] == 2  # 2 unique files
