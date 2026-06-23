from mcp.server.fastmcp import FastMCP

from src.application.use_cases.analysis.validate_commits import ValidateCommitMessagesUseCase
from src.application.use_cases.analysis.validate_coverage import ValidateCoverageDistributionUseCase
from src.application.use_cases.analysis.validate_env import ValidateEnvCompletenessUseCase
from src.application.use_cases.analysis.validate_imports import ValidateImportDirectionsUseCase
from src.application.use_cases.analysis.validate_logs import ValidateLogCallsUseCase
from src.application.use_cases.analysis.validate_migration import ValidateMigrationUseCase
from src.application.use_cases.analysis.validate_tests import ValidateTestNamesUseCase
from src.utils.logger import get_logger

_logger = get_logger("tools.analysis")


def register_analysis_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="validate_import_directions",
        description=(
            "Check that imports follow the Clean Architecture dependency rule: "
            "domain → no project imports; "
            "application → domain only (infrastructure/repositories/contract.py is the one allowed exception); "
            "infrastructure → domain + application; "
            "presentation → all layers.\n\n"
            "How to use:\n"
            '  grep -rn "^from\\|^import" src/ --include="*.py"\n\n'
            "Parameters:\n"
            "  grep_output — raw output of the grep command above (one match per line: file:line:statement)\n\n"
            "Returns per-violation findings with rule_id, location (file:line), message, and a fix hint. "
            "Status: 'clean' | 'warnings' | 'violations'."
        ),
    )
    async def validate_import_directions(grep_output: str) -> dict:
        _logger.info("tool=validate_import_directions")
        try:
            result = await ValidateImportDirectionsUseCase().execute(grep_output)
            data = result.model_dump()
            _logger.info(
                "tool=validate_import_directions files=%d findings=%d status=%r",
                data["total_items"],
                len(data["findings"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_import_directions error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_migration",
        description=(
            "Scan an Alembic migration file for dangerous operations: "
            "destructive ops (drop_column, drop_table, rename_table, rename_column), "
            "NOT NULL columns added without a server_default, "
            "raw SQL via op.execute(), and risky type changes via op.alter_column().\n\n"
            "How to use:\n"
            "  cat alembic/versions/<revision>_<name>.py\n\n"
            "Parameters:\n"
            "  source — content of one or more Alembic migration files\n\n"
            "Returns per-line findings. Status: 'clean' | 'warnings' | 'violations'."
        ),
    )
    async def validate_migration(source: str) -> dict:
        _logger.info("tool=validate_migration")
        try:
            result = await ValidateMigrationUseCase().execute(source)
            data = result.model_dump()
            _logger.info(
                "tool=validate_migration lines=%d findings=%d status=%r",
                data["total_items"],
                len(data["findings"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_migration error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_commit_messages",
        description=(
            "Validate git commit subjects against the Conventional Commits spec "
            "(type(scope)?: description) and the 72-character subject line limit. "
            "Merge and Revert auto-commits are skipped automatically.\n\n"
            "How to use:\n"
            '  git log --format="%H %s" origin/main..HEAD\n\n'
            "Parameters:\n"
            "  git_log — raw output of the git log command above (one commit per line)\n\n"
            "Returns per-commit findings. Status: 'clean' | 'warnings' | 'violations'."
        ),
    )
    async def validate_commit_messages(git_log: str) -> dict:
        _logger.info("tool=validate_commit_messages")
        try:
            result = await ValidateCommitMessagesUseCase().execute(git_log)
            data = result.model_dump()
            _logger.info(
                "tool=validate_commit_messages commits=%d findings=%d status=%r",
                data["total_items"],
                len(data["findings"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_commit_messages error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_env_completeness",
        description=(
            "Check that every UPPER_SNAKE_CASE field in your Pydantic BaseSettings class "
            "has a corresponding entry in .env.example so new developers know which "
            "environment variables are required.\n\n"
            "How to use:\n"
            "  settings_source: cat src/config/settings/base.py\n"
            "  env_example:     cat .env.example\n\n"
            "Parameters:\n"
            "  settings_source — Python source of the file containing the Settings class\n"
            "  env_example     — content of .env.example\n\n"
            "Returns one finding per missing key. Status: 'clean' | 'violations'."
        ),
    )
    async def validate_env_completeness(settings_source: str, env_example: str) -> dict:
        _logger.info("tool=validate_env_completeness")
        try:
            result = await ValidateEnvCompletenessUseCase().execute(settings_source, env_example)
            data = result.model_dump()
            _logger.info(
                "tool=validate_env_completeness fields=%d missing=%d status=%r",
                data["total_items"],
                data["required_count"],
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_env_completeness error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_test_names",
        description=(
            "Check pytest test function names for two issues: "
            "duplicate names within a file (required — pytest silently skips one), "
            "and names that are too short / not descriptive "
            "(recommended — fewer than 3 tokens after the 'test_' prefix).\n\n"
            "How to use:\n"
            "  cat test/unit/path/to/test_module.py\n\n"
            "Parameters:\n"
            "  source   — content of a pytest test file\n"
            "  filename — file name for display in findings (optional, default: test_file.py)\n\n"
            "Returns per-function findings. Status: 'clean' | 'warnings' | 'violations'."
        ),
    )
    async def validate_test_names(source: str, filename: str = "test_file.py") -> dict:
        _logger.info("tool=validate_test_names filename=%r", filename)
        try:
            result = await ValidateTestNamesUseCase().execute(source, filename)
            data = result.model_dump()
            _logger.info(
                "tool=validate_test_names tests=%d findings=%d status=%r",
                data["total_items"],
                len(data["findings"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_test_names error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_log_calls",
        description=(
            "Detect logging anti-patterns in Python source files: "
            "print() calls that should use the project logger (required), "
            "and f-strings passed directly to logger.*() that prevent lazy evaluation "
            "when the log level is disabled (recommended).\n\n"
            "How to use:\n"
            "  cat src/path/to/module.py\n\n"
            "Parameters:\n"
            "  source   — content of a Python source file\n"
            "  filename — file name for display in findings (optional, default: source.py)\n\n"
            "Returns per-line findings. Status: 'clean' | 'warnings' | 'violations'."
        ),
    )
    async def validate_log_calls(source: str, filename: str = "source.py") -> dict:
        _logger.info("tool=validate_log_calls filename=%r", filename)
        try:
            result = await ValidateLogCallsUseCase().execute(source, filename)
            data = result.model_dump()
            _logger.info(
                "tool=validate_log_calls lines=%d findings=%d status=%r",
                data["total_items"],
                len(data["findings"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_log_calls error=%r", str(exc))
            return {"error": str(exc)}

    @mcp.tool(
        name="validate_coverage_distribution",
        description=(
            "Parse a Cobertura XML coverage report and check per-layer coverage against "
            "thresholds: domain ≥90%, application ≥85%, infrastructure ≥65%, presentation ≥55%.\n\n"
            "How to use:\n"
            "  pytest --cov=src --cov-report=xml   # generates coverage.xml\n"
            "  cat coverage.xml\n\n"
            "Parameters:\n"
            "  cobertura_xml — raw content of the coverage.xml file\n\n"
            "Returns one finding per layer below threshold. Status: 'clean' | 'violations'."
        ),
    )
    async def validate_coverage_distribution(cobertura_xml: str) -> dict:
        _logger.info("tool=validate_coverage_distribution")
        try:
            result = await ValidateCoverageDistributionUseCase().execute(cobertura_xml)
            data = result.model_dump()
            _logger.info(
                "tool=validate_coverage_distribution packages=%d findings=%d status=%r",
                data["total_items"],
                len(data["findings"]),
                data["status"],
            )
            return data
        except ValueError as exc:
            _logger.warning("tool=validate_coverage_distribution error=%r", str(exc))
            return {"error": str(exc)}
