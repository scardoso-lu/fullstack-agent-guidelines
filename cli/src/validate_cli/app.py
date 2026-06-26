from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import typer
from typing_extensions import Annotated

from validate_cli._output import output_report, print_error

app = typer.Typer(
    name="validate-tools",
    help=(
        "Run the fullstack validation checks locally — same rules as the MCP server, "
        "without the token overhead.\n\n"
        "Exit codes: 0 = clean, 1 = warnings (with --strict), 2 = violations."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_JSON = Annotated[bool, typer.Option("--json", help="Output JSON instead of a rich table")]
_STRICT = Annotated[bool, typer.Option("--strict", help="Exit 1 on warnings (default: only on violations)")]


def _read(source: Optional[Path]) -> str:
    """Read from a file or stdin."""
    if source is None:
        if sys.stdin.isatty():
            print_error("No input. Pass a file path or pipe data via stdin.")
            raise typer.Exit(1)
        return sys.stdin.read()
    return source.read_text()


def _read_files(files: list[Path]) -> list[tuple[str, str]]:
    """Return [(filename, content), ...] for each file."""
    return [(str(f), f.read_text()) for f in files]


# ── imports ───────────────────────────────────────────────────────────────────


@app.command(name="imports")
def cmd_imports(
    input: Annotated[Optional[Path], typer.Option("--input", "-i", help="File with grep output (default: stdin)")] = None,
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Validate Clean Architecture import directions.

    [dim]Feed the output of:[/dim]
      grep -rn "^from\\\\|^import" src/ --include="*.py" | validate-tools imports
    """
    from validate_cli._validators.imports import validate_import_directions
    try:
        report = validate_import_directions(_read(input))
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    output_report(report, json_output, strict)


# ── commits ───────────────────────────────────────────────────────────────────


@app.command(name="commits")
def cmd_commits(
    input: Annotated[Optional[Path], typer.Option("--input", "-i", help="File with git log output (default: stdin)")] = None,
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Validate Conventional Commits format and subject length.

    [dim]Feed the output of:[/dim]
      git log --format="%H %s" origin/main..HEAD | validate-tools commits
    """
    from validate_cli._validators.commits import validate_commit_messages
    try:
        report = validate_commit_messages(_read(input))
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    output_report(report, json_output, strict)


# ── migration ─────────────────────────────────────────────────────────────────


@app.command(name="migration")
def cmd_migration(
    files: Annotated[Optional[List[Path]], typer.Argument(help="Alembic migration file(s) (default: stdin)")] = None,
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Check Alembic migration files for dangerous operations.

    [dim]Examples:[/dim]
      validate-tools migration alembic/versions/001_add_users.py
      validate-tools migration alembic/versions/*.py
      cat migration.py | validate-tools migration
    """
    from validate_cli._validators.migration import validate_migration

    if not files:
        try:
            report = validate_migration(_read(None))
        except ValueError as exc:
            print_error(str(exc))
            raise typer.Exit(1)
        output_report(report, json_output, strict)
        return

    worst_exit = 0
    for path in files:
        try:
            report = validate_migration(path.read_text())
            # Prefix the analysis label with the filename for clarity
            report.analysis = f"validate_migration  [{path}]"
        except ValueError as exc:
            print_error(f"{path}: {exc}")
            worst_exit = max(worst_exit, 1)
            continue

        if json_output:
            from validate_cli._output import _print_json
            _print_json(report)
        else:
            from validate_cli._output import _print_rich
            _print_rich(report)

        if report.status == "violations":
            worst_exit = max(worst_exit, 2)
        elif strict and report.status == "warnings":
            worst_exit = max(worst_exit, 1)

    if worst_exit:
        sys.exit(worst_exit)


# ── env ───────────────────────────────────────────────────────────────────────


@app.command(name="env")
def cmd_env(
    settings: Annotated[Path, typer.Option("--settings", "-s", help="Python file containing the Settings class")],
    example: Annotated[Path, typer.Option("--example", "-e", help=".env.example file")],
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Check that every Settings field is documented in .env.example.

    [dim]Example:[/dim]
      validate-tools env --settings src/config/settings.py --example .env.example
    """
    from validate_cli._validators.env import validate_env_completeness
    try:
        report = validate_env_completeness(settings.read_text(), example.read_text())
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    output_report(report, json_output, strict)


# ── tests ─────────────────────────────────────────────────────────────────────


@app.command(name="tests")
def cmd_tests(
    files: Annotated[List[Path], typer.Argument(help="pytest test file(s)")],
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Check test function names for duplicates and descriptiveness.

    [dim]Example:[/dim]
      validate-tools tests test/unit/test_user.py test/unit/test_auth.py
    """
    from validate_cli._validators.tests import validate_test_names
    _run_per_file(files, validate_test_names, json_output, strict)


# ── logs ──────────────────────────────────────────────────────────────────────


@app.command(name="logs")
def cmd_logs(
    files: Annotated[List[Path], typer.Argument(help="Python source file(s) to check")],
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Detect print() calls and f-strings inside logger calls.

    [dim]Example:[/dim]
      validate-tools logs src/application/use_cases/auth_use_case.py
    """
    from validate_cli._validators.logs import validate_log_calls
    _run_per_file(files, validate_log_calls, json_output, strict)


# ── coverage ──────────────────────────────────────────────────────────────────


@app.command(name="coverage")
def cmd_coverage(
    file: Annotated[Optional[Path], typer.Argument(help="Cobertura XML file (default: coverage.xml)")] = None,
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Validate per-layer code coverage against thresholds.

    [dim]Generate coverage.xml with:[/dim]
      pytest --cov=src --cov-report=xml
      validate-tools coverage coverage.xml
    """
    from validate_cli._validators.coverage import validate_coverage_distribution
    path = file or Path("coverage.xml")
    if not path.exists():
        print_error(f"{path} not found. Generate it with: pytest --cov=src --cov-report=xml")
        raise typer.Exit(1)
    try:
        report = validate_coverage_distribution(path.read_text())
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    output_report(report, json_output, strict)


# ── supply-chain ──────────────────────────────────────────────────────────────


@app.command(name="supply-chain")
def cmd_supply_chain(
    file: Annotated[Optional[Path], typer.Argument(help="pyproject.toml or package.json (default: pyproject.toml)")] = None,
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Scan package manifests for supply-chain risks.

    [dim]Detects VCS sources, direct URLs, local paths, wildcards, and pre-release pins.[/dim]

    [dim]Example:[/dim]
      validate-tools supply-chain pyproject.toml
      validate-tools supply-chain package.json
    """
    from validate_cli._validators.supply_chain import validate_supply_chain
    path = file or Path("pyproject.toml")
    if not path.exists():
        print_error(f"{path} not found.")
        raise typer.Exit(1)
    try:
        report = validate_supply_chain(path.read_text())
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)
    output_report(report, json_output, strict)


# ── sensitive-logging ─────────────────────────────────────────────────────────


@app.command(name="sensitive-logging")
def cmd_sensitive_logging(
    files: Annotated[List[Path], typer.Argument(help="Python source file(s) to check")],
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Detect sensitive data (passwords, tokens, keys) in log/print calls.

    [dim]Example:[/dim]
      validate-tools sensitive-logging src/application/use_cases/auth_use_case.py
    """
    from validate_cli._validators.sensitive_logging import validate_sensitive_logging
    _run_per_file(files, validate_sensitive_logging, json_output, strict)


# ── secrets ───────────────────────────────────────────────────────────────────


@app.command(name="secrets")
def cmd_secrets(
    files: Annotated[List[Path], typer.Argument(help="Source file(s) to scan (Python or TypeScript)")],
    json_output: _JSON = False,
    strict: _STRICT = False,
) -> None:
    """Detect hardcoded API keys, JWTs, and secret variables.

    [dim]Example:[/dim]
      validate-tools secrets src/config/settings.py
    """
    from validate_cli._validators.hardcoded_secrets import validate_hardcoded_secrets
    _run_per_file(files, validate_hardcoded_secrets, json_output, strict)


# ── helpers ───────────────────────────────────────────────────────────────────


def _run_per_file(
    files: list[Path],
    validator,
    json_output: bool,
    strict: bool,
) -> None:
    """Run a per-file validator on each file; exit with the worst code seen."""
    from validate_cli._output import _print_json, _print_rich

    worst_exit = 0
    for path in files:
        try:
            report = validator(path.read_text(), str(path))
        except ValueError as exc:
            print_error(f"{path}: {exc}")
            worst_exit = max(worst_exit, 1)
            continue

        if json_output:
            _print_json(report)
        else:
            _print_rich(report)

        if report.status == "violations":
            worst_exit = max(worst_exit, 2)
        elif strict and report.status == "warnings":
            worst_exit = max(worst_exit, 1)

    if worst_exit:
        sys.exit(worst_exit)
