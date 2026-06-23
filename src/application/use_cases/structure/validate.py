import re
from dataclasses import dataclass

from src.application.dto.structure_dto import StructureReportDto, StructureViolationDto
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_project_structure")

_LAYER_NAMES = frozenset({"domain", "application", "infrastructure", "presentation"})


@dataclass(frozen=True)
class PathRule:
    id: str
    description: str
    severity: str           # "required" | "recommended"
    hint: str
    guideline_slug: str
    trigger_pattern: str    # rule fires when path matches this
    safe_pattern: str | None = None         # if path also matches this, it is NOT a violation …
    canonical_first_dir: str | None = None  # … UNLESS the first dir after src/ is not this value


def _first_dir(path: str) -> str | None:
    """First directory segment after stripping any leading ./ and src/ prefix."""
    parts = path.replace("\\", "/").strip("./").split("/")
    start = 1 if parts and parts[0] == "src" else 0
    return parts[start] if start < len(parts) and parts[start] else None


_BACKEND_RULES: list[PathRule] = [
    PathRule(
        id="backend/structure/repo-in-infrastructure",
        description="Repository files (*_repository.py) must live in infrastructure/repositories/",
        severity="required",
        hint="Move to src/infrastructure/repositories/<entity>_repository.py",
        guideline_slug="backend/01-project-structure",
        trigger_pattern=r"_repository\.py$",
        safe_pattern=r"/infrastructure/repositories/",
        canonical_first_dir="infrastructure",
    ),
    PathRule(
        id="backend/structure/dto-in-application",
        description="DTO files (*_dto.py) must live in application/dto/",
        severity="required",
        hint="Move to src/application/dto/<domain>_dto.py",
        guideline_slug="backend/01-project-structure",
        trigger_pattern=r"_dto\.py$",
        safe_pattern=r"/application/dto/",
        canonical_first_dir="application",
    ),
    PathRule(
        id="backend/structure/no-loose-domain-files",
        description=(
            "Python files directly in domain/ root must be in a subdirectory "
            "(entities/, services/, or value_objects/)"
        ),
        severity="required",
        hint="Move to src/domain/entities/, src/domain/services/, or src/domain/value_objects/",
        guideline_slug="backend/02-domain-layer",
        trigger_pattern=r"/domain/[^/]+\.py$",
        safe_pattern=r"__init__\.py$",
    ),
    PathRule(
        id="backend/structure/use-cases-not-in-wrong-layer",
        description="use_cases/ directories must live under application/ — not in domain/ or infrastructure/",
        severity="required",
        hint="Move the use_cases/ subtree to src/application/use_cases/",
        guideline_slug="backend/01-project-structure",
        trigger_pattern=r"/(?:domain|infrastructure|presentation)/use_cases?/",
        safe_pattern=None,
    ),
    PathRule(
        id="backend/structure/contract-in-infrastructure",
        description="Repository interface file (contract.py) must live in infrastructure/repositories/",
        severity="required",
        hint="Move to src/infrastructure/repositories/contract.py",
        guideline_slug="backend/01-project-structure",
        trigger_pattern=r"/contract\.py$",
        safe_pattern=r"/infrastructure/repositories/contract\.py$",
        canonical_first_dir="infrastructure",
    ),
    PathRule(
        id="backend/structure/routes-in-presentation",
        description="Route/router files must live in presentation/routes/",
        severity="required",
        hint="Move to src/presentation/routes/<domain>.py",
        guideline_slug="backend/05-presentation-layer",
        trigger_pattern=r"(?:_router|_routes)\.py$",
        safe_pattern=r"/presentation/routes?/",
        canonical_first_dir="presentation",
    ),
    PathRule(
        id="backend/structure/no-infra-in-domain",
        description="Infrastructure concerns must not be placed inside domain/",
        severity="required",
        hint="Move DB/repository/session files to src/infrastructure/",
        guideline_slug="backend/02-domain-layer",
        trigger_pattern=r"/domain/.*(?:_repository|_session|_engine|_db)\.py$",
        safe_pattern=None,
    ),
    PathRule(
        id="backend/structure/snake-case-filenames",
        description="Python source files must use snake_case — no PascalCase or camelCase filenames",
        severity="recommended",
        hint="Rename the file to snake_case.py (e.g., NoteService.py → note_service.py)",
        guideline_slug="backend/01-project-structure",
        trigger_pattern=r"/[A-Z][^/]*\.py$",
        safe_pattern=None,
    ),
]

_FRONTEND_RULES: list[PathRule] = [
    PathRule(
        id="frontend/structure/services-in-services-dir",
        description="API service files must live in services/ — not inside components/ or app/",
        severity="required",
        hint="Move to src/services/<domain>.ts",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"(?:[Ss]ervice)\.tsx?$",
        safe_pattern=r"/services/",
        canonical_first_dir="services",
    ),
    PathRule(
        id="frontend/structure/providers-in-providers-dir",
        description="Context provider files (*-provider.tsx / *Provider.tsx) must live in providers/",
        severity="required",
        hint="Move to src/providers/<name>-provider.tsx",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"[Pp]rovider\.tsx$",
        safe_pattern=r"/providers/",
        canonical_first_dir="providers",
    ),
    PathRule(
        id="frontend/structure/actions-in-actions-dir",
        description="Server Action files must live in actions/ — not in app/ or components/",
        severity="required",
        hint="Move to src/actions/<feature>.ts and ensure 'use server' is at the top",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"[Aa]ctions?\.ts$",
        safe_pattern=r"/actions/",
        canonical_first_dir="actions",
    ),
    PathRule(
        id="frontend/structure/no-tsx-in-services",
        description="Service files in services/ must be .ts not .tsx — they contain no JSX",
        severity="recommended",
        hint="Rename to .ts (remove the x suffix)",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"/services/[^/]+\.tsx$",
        safe_pattern=None,
    ),
    PathRule(
        id="frontend/structure/kebab-case-components",
        description="Component .tsx files must use kebab-case filenames — no PascalCase",
        severity="recommended",
        hint="Rename to kebab-case.tsx (e.g., UserCard.tsx → user-card.tsx)",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"/components/(?:[^/]+/)*[A-Z][^/]*\.tsx$",
        safe_pattern=None,
    ),
    PathRule(
        id="frontend/structure/pages-as-page-tsx",
        description=(
            "Next.js App Router pages must be named page.tsx — "
            "index.tsx / home.tsx / main.tsx are not recognised by the router"
        ),
        severity="required",
        hint="Rename to page.tsx as required by the Next.js App Router convention",
        # (?:.*/)? makes the intermediate path optional — catches root-level app/index.tsx too
        trigger_pattern=r"/app/(?:.*/)?(?:index|home|main)\.tsx$",
        safe_pattern=None,
        guideline_slug="frontend/01-project-structure",
    ),
    PathRule(
        id="frontend/structure/lib-utilities",
        description="Utility/helper files (utils.ts, helpers.ts) must live in lib/ — not in components/ or app/",
        severity="recommended",
        hint="Move to src/lib/<utility>.ts",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"(?:[Uu]tils?|[Hh]elpers?)\.ts$",
        safe_pattern=r"/lib/",
        canonical_first_dir="lib",
    ),
    PathRule(
        id="frontend/structure/no-ts-logic-in-app-root",
        description=(
            "Non-routing .ts files must not live directly inside app/ — "
            "business logic belongs in services/, lib/, or actions/"
        ),
        severity="required",
        hint="Move to services/, lib/, or actions/ depending on the file's purpose",
        guideline_slug="frontend/01-project-structure",
        trigger_pattern=r"/app/[^/]+\.ts$",
        safe_pattern=r"/(?:layout|page|loading|error|not-found|globals|metadata|route)\.ts$",
        canonical_first_dir="app",
    ),
]


def _rules_for(stack: str) -> list[PathRule]:
    if stack == "backend":
        return _BACKEND_RULES
    if stack == "frontend":
        return _FRONTEND_RULES
    if stack == "both":
        return [*_BACKEND_RULES, *_FRONTEND_RULES]
    raise ValueError(f"stack must be 'backend', 'frontend', or 'both' — got {stack!r}")


def get_all_rules() -> list[PathRule]:
    return [*_BACKEND_RULES, *_FRONTEND_RULES]


def _parse_paths(file_tree: str) -> list[str]:
    return [
        line.strip()
        for line in file_tree.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _check(path: str, rule: PathRule) -> StructureViolationDto | None:
    normalized = path.replace("\\", "/")
    if not re.search(rule.trigger_pattern, normalized):
        return None
    if rule.safe_pattern and re.search(rule.safe_pattern, normalized):
        # If a canonical first-dir is specified, the safe match only counts when
        # the first meaningful directory (after src/) is the expected one.
        # This prevents a nested look-alike path such as
        # src/application/infrastructure/repositories/note_repository.py from
        # being treated as safe just because it contains /infrastructure/repositories/.
        if rule.canonical_first_dir is None or _first_dir(normalized) == rule.canonical_first_dir:
            return None
    return StructureViolationDto(
        rule_id=rule.id,
        severity=rule.severity,
        file_path=path,
        message=rule.description,
        hint=rule.hint,
        guideline_slug=rule.guideline_slug,
    )


class ValidateProjectStructureUseCase:
    async def execute(self, stack: str, file_tree: str) -> StructureReportDto:
        rules = _rules_for(stack)
        paths = _parse_paths(file_tree)

        if not paths:
            raise ValueError(
                "file_tree is empty — provide output of: "
                "find src/ -type f -name '*.py'  (backend)  "
                "or find src/ -type f \\( -name '*.ts' -o -name '*.tsx' \\)  (frontend)"
            )

        violations: list[StructureViolationDto] = []
        for path in paths:
            for rule in rules:
                v = _check(path, rule)
                if v:
                    violations.append(v)

        required_count = sum(1 for v in violations if v.severity == "required")
        recommended_count = sum(1 for v in violations if v.severity == "recommended")

        if required_count > 0:
            status = "non-compliant"
        elif recommended_count > 0:
            status = "warnings"
        else:
            status = "compliant"

        if violations:
            parts: list[str] = []
            if required_count:
                parts.append(f"{required_count} required violation(s)")
            if recommended_count:
                parts.append(f"{recommended_count} recommended violation(s)")
            summary = f"Found {' and '.join(parts)} across {len(paths)} file(s)."
        else:
            summary = f"All {len(paths)} file(s) respect the expected folder and module structure."

        _logger.info(
            "validate_structure stack=%r files=%d violations=%d status=%r",
            stack,
            len(paths),
            len(violations),
            status,
        )

        return StructureReportDto(
            stack=stack,
            total_files=len(paths),
            violations=violations,
            required_violations=required_count,
            recommended_violations=recommended_count,
            status=status,
            summary=summary,
        )
