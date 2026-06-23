import pytest

from src.application.use_cases.structure.validate import ValidateProjectStructureUseCase


async def _run(stack: str, paths: list[str]) -> dict:
    file_tree = "\n".join(paths)
    result = await ValidateProjectStructureUseCase().execute(stack, file_tree)
    return result.model_dump()


# ── backend: required violations ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_repo_outside_infrastructure_is_violation():
    r = await _run("backend", ["src/application/use_cases/note/note_repository.py"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/repo-in-infrastructure" in ids


@pytest.mark.asyncio
async def test_repo_in_infrastructure_is_clean():
    r = await _run("backend", ["src/infrastructure/repositories/note_repository.py"])
    assert r["status"] == "compliant"
    assert r["violations"] == []


@pytest.mark.asyncio
async def test_dto_outside_application_dto_is_violation():
    r = await _run("backend", ["src/infrastructure/repositories/note_dto.py"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/dto-in-application" in ids


@pytest.mark.asyncio
async def test_dto_in_application_dto_is_clean():
    r = await _run("backend", ["src/application/dto/note_dto.py"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_loose_file_directly_in_domain_is_violation():
    r = await _run("backend", ["src/domain/note.py"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/no-loose-domain-files" in ids


@pytest.mark.asyncio
async def test_init_directly_in_domain_is_allowed():
    r = await _run("backend", ["src/domain/__init__.py"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_entity_in_domain_entities_is_clean():
    r = await _run("backend", ["src/domain/entities/note.py"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_use_cases_under_infrastructure_is_violation():
    r = await _run("backend", ["src/infrastructure/use_cases/create.py"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/use-cases-not-in-wrong-layer" in ids


@pytest.mark.asyncio
async def test_use_cases_under_application_is_clean():
    r = await _run("backend", ["src/application/use_cases/note/create.py"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_contract_outside_infrastructure_is_violation():
    r = await _run("backend", ["src/application/contract.py"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/contract-in-infrastructure" in ids


@pytest.mark.asyncio
async def test_contract_in_infrastructure_is_clean():
    r = await _run("backend", ["src/infrastructure/repositories/contract.py"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_router_outside_presentation_is_violation():
    r = await _run("backend", ["src/application/note_router.py"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/routes-in-presentation" in ids


@pytest.mark.asyncio
async def test_router_in_presentation_routes_is_clean():
    r = await _run("backend", ["src/presentation/routes/note_router.py"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_infra_file_in_domain_is_violation():
    r = await _run("backend", ["src/domain/note_repository.py"])
    ids = [v["rule_id"] for v in r["violations"]]
    # Triggers both no-loose-domain-files AND no-infra-in-domain
    assert "backend/structure/no-infra-in-domain" in ids


# ── backend: recommended violations ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_pascal_case_python_file_is_recommended_violation():
    r = await _run("backend", ["src/application/use_cases/note/CreateNote.py"])
    assert r["recommended_violations"] >= 1
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/snake-case-filenames" in ids


@pytest.mark.asyncio
async def test_snake_case_python_file_is_clean():
    r = await _run("backend", ["src/application/use_cases/note/create_note.py"])
    assert r["status"] == "compliant"


# ── frontend: required violations ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_outside_services_dir_is_violation():
    r = await _run("frontend", ["src/components/app/NoteService.ts"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/services-in-services-dir" in ids


@pytest.mark.asyncio
async def test_service_in_services_dir_is_clean():
    r = await _run("frontend", ["src/services/notes.ts"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_provider_outside_providers_dir_is_violation():
    r = await _run("frontend", ["src/components/app/UserProvider.tsx"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/providers-in-providers-dir" in ids


@pytest.mark.asyncio
async def test_provider_in_providers_dir_is_clean():
    r = await _run("frontend", ["src/providers/user-provider.tsx"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_actions_outside_actions_dir_is_violation():
    r = await _run("frontend", ["src/app/[lang]/(private)/admin/actions.ts"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/actions-in-actions-dir" in ids


@pytest.mark.asyncio
async def test_actions_in_actions_dir_is_clean():
    r = await _run("frontend", ["src/actions/notes.ts"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_index_tsx_in_app_is_violation():
    r = await _run("frontend", ["src/app/[lang]/(private)/admin/index.tsx"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/pages-as-page-tsx" in ids


@pytest.mark.asyncio
async def test_page_tsx_in_app_is_clean():
    r = await _run("frontend", ["src/app/[lang]/(private)/admin/page.tsx"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_ts_logic_file_directly_in_app_is_violation():
    r = await _run("frontend", ["src/app/helpers.ts"])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/no-ts-logic-in-app-root" in ids


# ── frontend: recommended violations ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_tsx_in_services_dir_is_recommended():
    r = await _run("frontend", ["src/services/NoteService.tsx"])
    assert r["recommended_violations"] >= 1
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/no-tsx-in-services" in ids


@pytest.mark.asyncio
async def test_pascal_component_is_recommended_violation():
    r = await _run("frontend", ["src/components/app/UserCard.tsx"])
    assert r["recommended_violations"] >= 1
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/kebab-case-components" in ids


@pytest.mark.asyncio
async def test_kebab_component_is_clean():
    r = await _run("frontend", ["src/components/app/user-card.tsx"])
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_utils_outside_lib_is_recommended():
    r = await _run("frontend", ["src/components/utils.ts"])
    assert r["recommended_violations"] >= 1
    ids = [v["rule_id"] for v in r["violations"]]
    assert "frontend/structure/lib-utilities" in ids


@pytest.mark.asyncio
async def test_utils_in_lib_is_clean():
    r = await _run("frontend", ["src/lib/utils.ts"])
    assert r["status"] == "compliant"


# ── both stack ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_both_stack_catches_backend_and_frontend_violations():
    r = await _run("both", [
        "src/application/note_repository.py",  # backend violation
        "src/components/app/UserProvider.tsx",  # frontend violation
    ])
    assert r["status"] == "non-compliant"
    ids = [v["rule_id"] for v in r["violations"]]
    assert "backend/structure/repo-in-infrastructure" in ids
    assert "frontend/structure/providers-in-providers-dir" in ids


# ── status logic ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_only_recommended_violations_gives_warnings_status():
    r = await _run("backend", ["src/application/use_cases/note/CreateNote.py"])
    assert r["status"] == "warnings"
    assert r["required_violations"] == 0
    assert r["recommended_violations"] >= 1


@pytest.mark.asyncio
async def test_no_violations_gives_compliant_status():
    r = await _run("backend", [
        "src/domain/entities/note.py",
        "src/application/dto/note_dto.py",
        "src/application/use_cases/note/create.py",
        "src/infrastructure/repositories/note_repository.py",
        "src/infrastructure/repositories/contract.py",
        "src/presentation/routes/note_router.py",
    ])
    assert r["status"] == "compliant"
    assert r["violations"] == []


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_file_tree_raises_value_error():
    with pytest.raises(ValueError, match="file_tree is empty"):
        await ValidateProjectStructureUseCase().execute("backend", "")


@pytest.mark.asyncio
async def test_whitespace_only_file_tree_raises_value_error():
    with pytest.raises(ValueError, match="file_tree is empty"):
        await ValidateProjectStructureUseCase().execute("backend", "   \n  \n")


@pytest.mark.asyncio
async def test_comment_lines_are_ignored():
    r = await _run("backend", ["# generated by find", "src/domain/entities/note.py"])
    assert r["total_files"] == 1
    assert r["status"] == "compliant"


@pytest.mark.asyncio
async def test_invalid_stack_raises_value_error():
    with pytest.raises(ValueError, match="stack must be"):
        await ValidateProjectStructureUseCase().execute("unknown", "src/some/file.py")


@pytest.mark.asyncio
async def test_total_files_counts_non_comment_lines():
    r = await _run("backend", [
        "src/domain/entities/note.py",
        "src/application/dto/note_dto.py",
    ])
    assert r["total_files"] == 2
