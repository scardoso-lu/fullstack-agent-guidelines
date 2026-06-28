import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli" / "src"))

from validate_cli._validators.project_layout import validate_project_layout


def _clean_tree() -> str:
    return "\n".join(
        [
            "backend/Dockerfile",
            "backend/Dockerfile.test",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "backend/.env.example",
            "frontend/Dockerfile",
            "frontend/package.json",
            "frontend/pnpm-lock.yaml",
            "frontend/pnpm-workspace.yaml",
            "frontend/.npmrc",
            "frontend/.env.example",
            "docker-compose.yml",
            "docker-compose.test.yml",
            "Makefile",
            ".github/workflows/ci.yml",
        ]
    )


def _clean_files() -> dict[str, str]:
    return {
        "backend/Dockerfile": "RUN uv sync --frozen --no-dev\nCOPY src/ ./src/\n",
        "backend/Dockerfile.test": "RUN uv sync --frozen\nCOPY test/ ./test/\n",
        "frontend/Dockerfile": (
            "COPY .npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml ./\n"
            "RUN pnpm install --frozen-lockfile\n"
        ),
        "docker-compose.yml": (
            "services:\n"
            "  backend:\n"
            "    build:\n"
            "      context: ./backend\n"
            "    env_file:\n"
            "      - ./backend/.env\n"
            "  frontend:\n"
            "    build:\n"
            "      context: ./frontend\n"
            "    env_file:\n"
            "      - ./frontend/.env\n"
        ),
        "docker-compose.test.yml": (
            "services:\n"
            "  backend-test:\n"
            "    build:\n"
            "      context: ./backend\n"
            "      dockerfile: Dockerfile.test\n"
            "    volumes:\n"
            "      - ./backend/test-results:/app/test-results\n"
            "  frontend-test:\n"
            "    build:\n"
            "      context: ./frontend\n"
            "      dockerfile: Dockerfile.test\n"
            "    volumes:\n"
            "      - ./frontend/test-results:/app/test-results\n"
        ),
        "Makefile": (
            "gate:\n\tmake install-backend\n"
            "install-backend:\n\tcd backend && uv sync\n"
            "install-frontend:\n\tcd frontend && pnpm install --frozen-lockfile\n"
        ),
        ".github/workflows/ci.yml": (
            "steps:\n"
            "  - run: make gate\n"
            "  - uses: actions/setup-node@v4\n"
            "    with:\n"
            "      cache-dependency-path: frontend/pnpm-lock.yaml\n"
        ),
    }


def test_clean_layout_passes():
    report = validate_project_layout(_clean_tree(), _clean_files())

    assert report.status == "clean"
    assert report.findings == []


def test_root_frontend_lockfile_is_violation():
    report = validate_project_layout(_clean_tree() + "\npnpm-lock.yaml", _clean_files())

    assert report.status == "violations"
    assert any(f.rule_id == "project-layout/no-root-stack-artifact" for f in report.findings)


def test_backend_production_dockerfile_cannot_have_test_stage():
    files = _clean_files()
    files["backend/Dockerfile"] = "FROM python:3.13-slim AS base\nFROM base AS test\n"

    report = validate_project_layout(_clean_tree(), files)

    assert report.status == "violations"
    assert any(f.rule_id == "project-layout/backend-prod-no-test-stage" for f in report.findings)


def test_test_compose_cannot_target_test_stage():
    files = _clean_files()
    files["docker-compose.test.yml"] += "      target: test\n"

    report = validate_project_layout(_clean_tree(), files)

    assert report.status == "violations"
    assert any(f.rule_id == "project-layout/test-compose-no-target-test" for f in report.findings)


def test_makefile_tests_must_run_via_compose():
    files = _clean_files()
    files["Makefile"] += "test-backend:\n\tcd backend && uv run pytest\n"

    report = validate_project_layout(_clean_tree(), files)

    assert report.status == "violations"
    assert any(
        f.rule_id == "project-layout/makefile-backend-tests-via-compose"
        for f in report.findings
    )


def test_root_coverage_artifact_is_violation():
    report = validate_project_layout(_clean_tree() + "\ncoverage.xml", _clean_files())

    assert report.status == "violations"
    assert any(f.rule_id == "project-layout/no-root-test-artifact" for f in report.findings)


def test_ci_tests_must_go_through_makefile_and_compose():
    files = _clean_files()
    files[".github/workflows/ci.yml"] += "  - run: cd frontend && pnpm test\n"

    report = validate_project_layout(_clean_tree(), files)

    assert report.status == "violations"
    assert any(f.rule_id == "project-layout/ci-tests-via-compose" for f in report.findings)
