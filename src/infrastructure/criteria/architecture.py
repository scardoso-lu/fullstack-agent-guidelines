from src.domain.entities.compliance import ComplianceCriterion

CRITERIA: list[ComplianceCriterion] = [
    # ── Technology selection / dependency adoption (architecture/01) ──────────
    ComplianceCriterion(
        id="architecture/dependency/decision-record-exists",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="Every new dependency or peripheral technology has a written decision record under docs/decisions/",
        category="dependency-governance",
        severity="required",
        check_type="manual",
        verification_hint=(
            "List every package added in this slice. For each, provide the path to its decision record "
            "(docs/decisions/<name>.md or equivalent). If no new packages were added, confirm with 'no new dependencies'."
        ),
    ),
    ComplianceCriterion(
        id="architecture/dependency/two-alternatives-evaluated",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="New dependency decision record documents at least two rejected alternatives with reasons",
        category="dependency-governance",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Paste the 'Rejected alternatives' section from the decision record for each new dependency. "
            "Each alternative must include the package name and a reason for rejection."
        ),
    ),
    ComplianceCriterion(
        id="architecture/dependency/license-verified",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="License verified: MIT/BSD/Apache/MPL allowed without approval; GPL/AGPL/commercial require sign-off",
        category="dependency-governance",
        severity="required",
        check_type="manual",
        verification_hint=(
            "State the SPDX license identifier for each new dependency. "
            "Confirm it is on the approved list, or provide the sign-off reference if it requires one."
        ),
    ),
    ComplianceCriterion(
        id="architecture/dependency/version-pinned",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="New dependencies use an exact version pin — not a range (^1.2.3 or ~1.2) in the manifest",
        category="dependency-governance",
        severity="recommended",
        check_type="code_pattern",
        verification_hint=(
            "Paste the relevant lines from pyproject.toml [tool.poetry.dependencies] (backend) "
            "or package.json (frontend) for the new packages"
        ),
        forbidden_pattern=r'(?:"[\w\-]+"|\b[\w][\w\-]*)\s*[=:]\s*"[\^~][\d]',
    ),
    ComplianceCriterion(
        id="architecture/dependency/installed-via-package-manager",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="Dependencies are installed via the project's package manager (uv/poetry for Python, pnpm for Node) — no bare pip install",
        category="dependency-governance",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the CI workflow file and the Makefile install target",
        forbidden_pattern=r"\bpip\s+install\b(?!\s+--upgrade\s+pip)",
    ),
    ComplianceCriterion(
        id="architecture/dependency/audit-clean",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="pip-audit / pnpm audit reports no Critical or High CVEs for the newly adopted dependency",
        category="dependency-governance",
        severity="required",
        check_type="command",
        verification_hint=(
            "Run `uv run pip-audit` (backend) or `pnpm audit --audit-level=high` (frontend) "
            "and paste the full output"
        ),
        check_command="uv run pip-audit",
        pass_pattern=r"No known vulnerabilities found|0 vulnerabilit",
        fail_pattern=r"CRITICAL|HIGH|Found \d+ vulnerabilit",
    ),
    ComplianceCriterion(
        id="architecture/dependency/lockfile-committed",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="Lockfile (uv.lock or pnpm-lock.yaml) is committed alongside the new dependency",
        category="dependency-governance",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm that uv.lock (backend) or pnpm-lock.yaml (frontend) is updated and included "
            "in this PR's diff. Provide the git diff --stat line showing the lockfile change."
        ),
    ),
]
