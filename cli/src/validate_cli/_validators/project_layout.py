from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Mapping

from validate_cli._models import AnalysisReportDto, FindingDto


def _norm(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def _line_for(source: str, needle: str) -> str:
    for lineno, line in enumerate(source.splitlines(), 1):
        if needle in line:
            return f"line:{lineno}"
    return "file"


def _has_path(paths: set[str], path: str) -> bool:
    return _norm(path) in paths


def _has_any(paths: set[str], *candidates: str) -> bool:
    return any(_has_path(paths, candidate) for candidate in candidates)


def _add(
    findings: list[FindingDto],
    rule_id: str,
    location: str,
    message: str,
    hint: str,
    severity: str = "required",
) -> None:
    findings.append(FindingDto(rule_id, severity, location, message, hint))


def _check_required_files(paths: set[str], findings: list[FindingDto]) -> None:
    required = [
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
    ]
    for path in required:
        if not _has_path(paths, path):
            _add(
                findings,
                "project-layout/missing-stack-artifact",
                path,
                f"Missing expected stack-local artifact: {path}",
                "Generate stack-owned artifacts under backend/ or frontend/, not at the repo root.",
            )

    forbidden_root = [
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "package-lock.json",
        ".env.backend",
        ".env.frontend",
        ".env.backend.test",
        ".env.frontend.test",
    ]
    for path in forbidden_root:
        if _has_path(paths, path):
            _add(
                findings,
                "project-layout/no-root-stack-artifact",
                path,
                f"Stack artifact must not live at repo root: {path}",
                "Move frontend artifacts under frontend/ and backend artifacts under backend/.",
            )

    for path in sorted(paths):
        if path == "coverage.xml" or path.startswith("htmlcov/") or path.startswith("test-results/"):
            _add(
                findings,
                "project-layout/no-root-test-artifact",
                path,
                f"Test or coverage artifact must not live at repo root: {path}",
                "Write test output under backend/test-results/ or frontend/test-results/.",
            )


def _check_backend_docker(files: Mapping[str, str], findings: list[FindingDto]) -> None:
    prod = files.get("backend/Dockerfile", "")
    test = files.get("backend/Dockerfile.test", "")

    if prod:
        if re.search(r"\bAS\s+test\b", prod, re.IGNORECASE):
            _add(
                findings,
                "project-layout/backend-prod-no-test-stage",
                "backend/Dockerfile",
                "backend/Dockerfile defines a test stage.",
                "Keep backend/Dockerfile production-only and put test tooling in backend/Dockerfile.test.",
            )
        if re.search(r"uv\s+sync\s+--frozen(?![^\n]*--no-dev)", prod):
            _add(
                findings,
                "project-layout/backend-prod-no-dev-deps",
                _line_for(prod, "uv sync --frozen"),
                "backend/Dockerfile installs dev dependencies.",
                "Use `uv sync --frozen --no-dev` in the production Dockerfile.",
            )
        if re.search(r"\bCOPY\s+test/?\s+", prod):
            _add(
                findings,
                "project-layout/backend-prod-no-tests",
                _line_for(prod, "COPY test"),
                "backend/Dockerfile copies tests into the production image.",
                "Copy test/ only in backend/Dockerfile.test.",
            )

    if test:
        if not re.search(r"uv\s+sync\s+--frozen\b", test):
            _add(
                findings,
                "project-layout/backend-test-installs-dev-deps",
                "backend/Dockerfile.test",
                "backend/Dockerfile.test does not run `uv sync --frozen`.",
                "The test image should install dev dependencies from the lockfile.",
            )
        if not re.search(r"\bCOPY\s+test/?\s+", test):
            _add(
                findings,
                "project-layout/backend-test-copies-tests",
                "backend/Dockerfile.test",
                "backend/Dockerfile.test does not copy test/.",
                "The backend test image must copy test/ so pytest can run inside the container.",
            )


def _check_frontend_docker(files: Mapping[str, str], findings: list[FindingDto]) -> None:
    dockerfile = files.get("frontend/Dockerfile", "")
    if not dockerfile:
        return

    copy_re = re.compile(
        r"COPY\s+\.npmrc\s+package\.json\s+pnpm-lock\.yaml\s+pnpm-workspace\.yaml\s+\./"
    )
    if not copy_re.search(dockerfile):
        _add(
            findings,
            "project-layout/frontend-docker-copies-local-pnpm-files",
            "frontend/Dockerfile",
            "frontend/Dockerfile does not copy .npmrc, package.json, pnpm-lock.yaml, and pnpm-workspace.yaml before install.",
            "With build context ./frontend, copy frontend-local pnpm files before `pnpm install --frozen-lockfile`.",
        )
    if "pnpm install --frozen-lockfile" not in dockerfile:
        _add(
            findings,
            "project-layout/frontend-docker-frozen-install",
            "frontend/Dockerfile",
            "frontend/Dockerfile does not use `pnpm install --frozen-lockfile`.",
            "Use frozen installs in Docker so package.json and pnpm-lock.yaml must agree.",
        )


def _check_compose(files: Mapping[str, str], findings: list[FindingDto]) -> None:
    compose = files.get("docker-compose.yml", "")
    if compose:
        for service, context, env_file in [
            ("backend", "./backend", "./backend/.env"),
            ("frontend", "./frontend", "./frontend/.env"),
        ]:
            if context not in compose:
                _add(
                    findings,
                    f"project-layout/{service}-compose-context",
                    "docker-compose.yml",
                    f"{service} service is not built with context {context}.",
                    f"Use `build.context: {context}` so Docker copies stack-local artifacts.",
                )
            if env_file not in compose:
                _add(
                    findings,
                    f"project-layout/{service}-compose-env-file",
                    "docker-compose.yml",
                    f"{service} service does not use stack-local env file {env_file}.",
                    "Use stack-local env files instead of root .env aliases.",
                )

    test_compose = files.get("docker-compose.test.yml", "")
    if test_compose:
        if "dockerfile: Dockerfile.test" not in test_compose:
            _add(
                findings,
                "project-layout/test-compose-dockerfile-test",
                "docker-compose.test.yml",
                "docker-compose.test.yml does not use Dockerfile.test for test services.",
                "Use dedicated test Dockerfiles instead of production Dockerfile targets.",
            )
        if re.search(r"target:\s*test\b", test_compose):
            _add(
                findings,
                "project-layout/test-compose-no-target-test",
                _line_for(test_compose, "target: test"),
                "docker-compose.test.yml targets a test stage.",
                "Use `dockerfile: Dockerfile.test`; do not target test stages in production Dockerfiles.",
            )
        for path in ["./backend/test-results", "./frontend/test-results"]:
            if path not in test_compose:
                _add(
                    findings,
                    "project-layout/test-compose-stack-results",
                    "docker-compose.test.yml",
                    f"Missing stack-local test-results mount: {path}",
                    "Mount test output under backend/test-results/ or frontend/test-results/.",
                )


def _check_makefile_ci(files: Mapping[str, str], findings: list[FindingDto]) -> None:
    makefile = files.get("Makefile", "")
    if makefile:
        for target in ["gate:", "install-frontend:", "install-backend:"]:
            if target not in makefile:
                _add(
                    findings,
                    "project-layout/makefile-target",
                    "Makefile",
                    f"Makefile is missing target `{target}`.",
                    "Expose common operations through the Makefile so CI and local commands stay aligned.",
                )
        if "cd frontend && pnpm install --frozen-lockfile" not in makefile:
            _add(
                findings,
                "project-layout/makefile-frontend-install",
                "Makefile",
                "Makefile does not install frontend dependencies from frontend/ with a frozen pnpm lockfile.",
                "Use `cd frontend && pnpm install --frozen-lockfile`.",
            )
        if "test-backend:" in makefile and (
            "docker compose -f docker-compose.test.yml run --rm backend-test" not in makefile
        ):
            _add(
                findings,
                "project-layout/makefile-backend-tests-via-compose",
                "Makefile",
                "Makefile test-backend target does not run backend tests through docker-compose.test.yml.",
                "Use `docker compose -f docker-compose.test.yml run --rm backend-test`.",
            )
        if "test-frontend:" in makefile and (
            "docker compose -f docker-compose.test.yml run --rm frontend-test" not in makefile
        ):
            _add(
                findings,
                "project-layout/makefile-frontend-tests-via-compose",
                "Makefile",
                "Makefile test-frontend target does not run frontend tests through docker-compose.test.yml.",
                "Use `docker compose -f docker-compose.test.yml run --rm frontend-test`.",
            )

    ci = "\n".join(
        content for path, content in files.items() if PurePosixPath(path).match(".github/workflows/*.yml")
        or PurePosixPath(path).match(".github/workflows/*.yaml")
    )
    if ci:
        if not re.search(r"\bmake\s+\w+", ci):
            _add(
                findings,
                "project-layout/ci-calls-make",
                ".github/workflows",
                "CI workflow does not call Makefile targets.",
                "CI should call `make <target>` instead of duplicating raw stack commands.",
            )
        if "cache-dependency-path: frontend/pnpm-lock.yaml" not in ci:
            _add(
                findings,
                "project-layout/ci-frontend-cache-path",
                ".github/workflows",
                "CI pnpm cache does not point at frontend/pnpm-lock.yaml.",
                "Use `cache-dependency-path: frontend/pnpm-lock.yaml`.",
                severity="recommended",
            )
        if re.search(r"run:\s+(?:cd\s+backend\s+&&\s+uv\s+run\s+pytest|cd\s+frontend\s+&&\s+pnpm\s+test)", ci):
            _add(
                findings,
                "project-layout/ci-tests-via-compose",
                ".github/workflows",
                "CI runs raw stack test commands instead of the Makefile/docker test path.",
                "CI should call Makefile targets that run tests through docker-compose.test.yml.",
            )


def validate_project_layout(file_tree: str, files: Mapping[str, str] | None = None) -> AnalysisReportDto:
    if not file_tree.strip():
        raise ValueError("file_tree is empty - pass repo-relative file paths, one per line")

    files = files or {}
    paths = {_norm(line.strip()) for line in file_tree.splitlines() if line.strip()}
    normalized_files = {_norm(path): content for path, content in files.items()}
    paths.update(normalized_files)

    findings: list[FindingDto] = []
    _check_required_files(paths, findings)
    _check_backend_docker(normalized_files, findings)
    _check_frontend_docker(normalized_files, findings)
    _check_compose(normalized_files, findings)
    _check_makefile_ci(normalized_files, findings)

    required_count = sum(1 for finding in findings if finding.severity == "required")
    recommended_count = sum(1 for finding in findings if finding.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    summary = (
        f"Found {required_count} project layout violation(s) and {recommended_count} recommendation(s)."
        if findings
        else f"Project layout artifacts are consistently scoped across {len(paths)} path(s)."
    )
    return AnalysisReportDto(
        analysis="validate_project_layout",
        total_items=len(paths),
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
