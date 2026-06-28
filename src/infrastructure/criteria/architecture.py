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
            "Paste the relevant lines from backend/pyproject.toml or frontend/package.json "
            "for the new packages"
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
            "Run `uv run pip-audit` (backend) or `cd frontend && pnpm audit --audit-level high` "
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
        text="Lockfile is committed beside its manifest (`backend/uv.lock` or `frontend/pnpm-lock.yaml`)",
        category="dependency-governance",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm that backend/uv.lock or frontend/pnpm-lock.yaml is updated and included "
            "in this PR's diff. Provide the git diff --stat line showing the lockfile change."
        ),
    ),
    # ── Supply chain hardening ────────────────────────────────────────────────
    ComplianceCriterion(
        id="architecture/supply-chain/no-vcs-or-url-source",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text=(
            "No dependency is installed from a VCS URL (git+https://, github:), "
            "direct URL, or local path — only registry sources are allowed"
        ),
        category="supply-chain",
        severity="required",
        check_type="code_pattern",
        verification_hint=(
            "Paste the dependency section of backend/pyproject.toml or frontend/package.json "
            "for all new packages"
        ),
        forbidden_pattern=(
            r'\b(?:git|hg|svn)\s*=\s*["\']'           # TOML VCS
            r'|:\s*"(?:git\+https?://|git\+ssh://|git://|github:|bitbucket:|gitlab:)'  # JSON VCS
            r'|\burl\s*=\s*["\']https?://'             # TOML direct URL
            r'|:\s*"https?://(?!registry\.npmjs\.org)' # JSON direct URL
            r'|\bpath\s*=\s*["\']\.\.?/'               # TOML local path
            r'|:\s*"file:'                              # JSON local path
        ),
    ),
    ComplianceCriterion(
        id="architecture/supply-chain/no-wildcard-version",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="No dependency uses a wildcard or unconstrained version specifier (* or latest)",
        category="supply-chain",
        severity="required",
        check_type="code_pattern",
        verification_hint=(
            "Paste the dependency declarations for new packages from backend/pyproject.toml or frontend/package.json"
        ),
        forbidden_pattern=r'[=:]\s*["\'](?:\*|latest|any)["\']',
    ),
    ComplianceCriterion(
        id="architecture/supply-chain/no-prerelease",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="No production dependency pins a pre-release version (alpha/beta/rc/dev)",
        category="supply-chain",
        severity="recommended",
        check_type="code_pattern",
        verification_hint=(
            "Paste the dependency declarations for new packages from backend/pyproject.toml or frontend/package.json"
        ),
        forbidden_pattern=(
            r'"[\d.]+(?:a\d+|b\d+|rc\d+|\.dev\d*)"'   # PEP 440: 1.0.0b2
            r'|"[\d.]+-(?:alpha|beta|rc)[\d.]*"'        # npm semver: 1.0.0-beta.1
        ),
    ),
    ComplianceCriterion(
        id="architecture/supply-chain/lockfile-has-hashes",
        guideline_slug="architecture/01-technology-selection",
        stack="architecture",
        text="Lockfile contains integrity hashes for every dependency (uv.lock hash = / pnpm integrity field)",
        category="supply-chain",
        severity="required",
        check_type="code_pattern",
        verification_hint=(
            "Paste 5-10 representative package entries from backend/uv.lock or frontend/pnpm-lock.yaml "
            "to confirm hash/integrity fields are present"
        ),
        required_pattern=r'hash\s*=\s*"sha|"integrity"\s*:\s*"sha',
    ),
]
