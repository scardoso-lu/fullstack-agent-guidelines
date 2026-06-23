from src.domain.entities.compliance import ComplianceCriterion

CRITERIA: list[ComplianceCriterion] = [
    # ── Makefile as gate (infra/04-makefile-as-gate) ─────────────────────────
    ComplianceCriterion(
        id="infra/makefile/gate-target-exists",
        guideline_slug="infra/04-makefile-as-gate",
        stack="infra",
        text="Makefile defines a `gate` target that runs lint + format-check + typecheck + tests in sequence",
        category="makefile",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the relevant targets section of the project Makefile",
        required_pattern=r"^gate\s*:",
    ),
    ComplianceCriterion(
        id="infra/makefile/ci-calls-make",
        guideline_slug="infra/04-makefile-as-gate",
        stack="infra",
        text="CI workflow calls `make <target>` — not raw pnpm/uv/pytest commands directly",
        category="makefile",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the CI workflow YAML file (.github/workflows/ci.yml or equivalent)",
        required_pattern=r"\bmake\s+\w",
        forbidden_pattern=r"run:\s+(?:uv run pytest|pnpm test|npm test|yarn test)\b",
    ),
    ComplianceCriterion(
        id="infra/makefile/help-target-exists",
        guideline_slug="infra/04-makefile-as-gate",
        stack="infra",
        text="Makefile has a self-documenting `help` target — `make help` is the onboarding entry point",
        category="makefile",
        severity="recommended",
        check_type="code_pattern",
        verification_hint="Paste the relevant section of the project Makefile",
        required_pattern=r"^help\s*:",
    ),
    ComplianceCriterion(
        id="infra/makefile/no-duplicate-commands",
        guideline_slug="infra/04-makefile-as-gate",
        stack="infra",
        text="No CI command appears twice — once in the Makefile target, once raw in CI YAML",
        category="makefile",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Compare the CI YAML and the Makefile. Confirm every command in CI is a `make <target>` call "
            "and that the same raw command does not also appear directly in the YAML."
        ),
    ),
    # ── Testing in Docker (infra/02-testing-in-docker) ───────────────────────
    ComplianceCriterion(
        id="infra/docker/test-stage-in-dockerfile",
        guideline_slug="infra/02-testing-in-docker",
        stack="infra",
        text="Backend Dockerfile defines a `test` stage (FROM … AS test) with dev dependencies installed",
        category="docker",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the backend Dockerfile",
        required_pattern=r"AS\s+test\b",
    ),
    ComplianceCriterion(
        id="infra/docker/test-compose-service-defined",
        guideline_slug="infra/02-testing-in-docker",
        stack="infra",
        text="docker-compose.test.yml defines at least one test service with `target: test`",
        category="docker",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the docker-compose.test.yml file",
        required_pattern=r"target:\s*test",
    ),
    ComplianceCriterion(
        id="infra/docker/test-results-volume-mounted",
        guideline_slug="infra/02-testing-in-docker",
        stack="infra",
        text="Test compose service mounts a test-results/ volume so structured output is readable on the host",
        category="docker",
        severity="required",
        check_type="code_pattern",
        verification_hint="Paste the docker-compose.test.yml file",
        required_pattern=r"test-results",
    ),
    ComplianceCriterion(
        id="infra/docker/tests-run-via-compose",
        guideline_slug="infra/02-testing-in-docker",
        stack="infra",
        text="Tests are invoked via `docker compose -f docker-compose.test.yml run --rm` — not directly on the host",
        category="docker",
        severity="required",
        check_type="manual",
        verification_hint=(
            "Confirm that the Makefile test target and the CI YAML both invoke tests via "
            "`docker compose -f docker-compose.test.yml run --rm <service>`. "
            "Paste the relevant make target and CI step."
        ),
    ),
]
