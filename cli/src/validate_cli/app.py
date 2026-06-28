from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

import typer
from typing_extensions import Annotated

from validate_cli._output import output_report, print_error, report_to_dict
from validate_cli._state import state

app = typer.Typer(
    name="validate-tools",
    help=(
        "Run the fullstack validation checks locally — same rules as the MCP server, "
        "without the token overhead.\n\n"
        "When stdout is not a TTY (e.g. piped to a script or agent), JSON is emitted "
        "automatically — no flags needed.\n\n"
        "Exit codes: 0 = clean, 1 = warnings (--strict), 2 = violations."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_STRICT = Annotated[bool, typer.Option("--strict", help="Exit 1 on warnings (default: only on violations)")]


@app.callback()
def _global_opts(
    human: Annotated[bool, typer.Option("--human", "-H", help="Force human/rich output even when piped")] = False,
    pretty: Annotated[bool, typer.Option("--pretty", help="Indent JSON output (default: compact)")] = False,
) -> None:
    state.human = human
    state.pretty = pretty


def _read(source: Optional[Path]) -> str:
    if source is None:
        if sys.stdin.isatty():
            print_error("No input. Pass a file path or pipe data via stdin.", force_human=state.human)
            raise typer.Exit(1)
        return sys.stdin.read()
    return source.read_text()


def _read_if_exists(path: Path) -> str | None:
    return path.read_text() if path.exists() and path.is_file() else None


def _emit(report, strict: bool) -> None:
    output_report(report, strict, force_human=state.human, pretty=state.pretty)


# ── imports ───────────────────────────────────────────────────────────────────


@app.command(name="imports")
def cmd_imports(
    input: Annotated[Optional[Path], typer.Option("--input", "-i", help="File with grep output (default: stdin)")] = None,
    strict: _STRICT = False,
) -> None:
    """Validate Clean Architecture import directions.

    [bold]Rules (required):[/bold]
      domain       → must not import application, infrastructure, or presentation
      application  → must not import infrastructure or presentation
                     (exception: infrastructure.repositories.contract is allowed)
      infrastructure → must not import presentation

    [bold]Input:[/bold]
      grep -rn "^from\\\\|^import" src/ --include="*.py" | validate-tools imports
    """
    from validate_cli._validators.imports import validate_import_directions
    try:
        _emit(validate_import_directions(_read(input)), strict)
    except ValueError as exc:
        print_error(str(exc), "validate_import_directions", state.human)
        raise typer.Exit(1)


# ── commits ───────────────────────────────────────────────────────────────────


@app.command(name="commits")
def cmd_commits(
    input: Annotated[Optional[Path], typer.Option("--input", "-i", help="File with git log output (default: stdin)")] = None,
    strict: _STRICT = False,
) -> None:
    """Validate Conventional Commits format and subject length.

    [bold]Rules:[/bold]
      required    subject must match type(scope)?: description
      recommended subject must be ≤72 characters

    [bold]Allowed types:[/bold] feat fix docs chore refactor test ci perf build style revert

    Merge and Revert auto-commits are skipped.

    [bold]Input:[/bold]
      git log --format="%H %s" origin/main..HEAD | validate-tools commits
    """
    from validate_cli._validators.commits import validate_commit_messages
    try:
        _emit(validate_commit_messages(_read(input)), strict)
    except ValueError as exc:
        print_error(str(exc), "validate_commit_messages", state.human)
        raise typer.Exit(1)


# ── migration ─────────────────────────────────────────────────────────────────


@app.command(name="migration")
def cmd_migration(
    files: Annotated[Optional[List[Path]], typer.Argument(help="Alembic migration file(s) (default: stdin)")] = None,
    strict: _STRICT = False,
) -> None:
    """Check Alembic migration files for dangerous operations.

    [bold]Rules:[/bold]
      required    op.drop_column, op.drop_table, op.rename_table, op.rename_column
      required    op.add_column with nullable=False and no server_default
      recommended op.alter_column  (type changes risk backward incompatibility)
      recommended op.execute       (raw SQL bypasses Alembic schema tracking)
    """
    from validate_cli._validators.migration import validate_migration
    if not files:
        try:
            _emit(validate_migration(_read(None)), strict)
        except ValueError as exc:
            print_error(str(exc), "validate_migration", state.human)
            raise typer.Exit(1)
        return

    # validate_migration takes (source) only — no filename arg
    worst_exit = 0
    for path in files:
        try:
            report = validate_migration(path.read_text())
        except ValueError as exc:
            print_error(str(exc), force_human=state.human)
            worst_exit = max(worst_exit, 1)
            continue
        code = output_report(report, strict=strict, force_human=state.human, pretty=state.pretty, exit_on_done=False)
        worst_exit = max(worst_exit, code)
    if worst_exit:
        sys.exit(worst_exit)


# ── env ───────────────────────────────────────────────────────────────────────


@app.command(name="env")
def cmd_env(
    settings: Annotated[Path, typer.Option("--settings", "-s", help="Python file containing the Settings class")],
    example: Annotated[Path, typer.Option("--example", "-e", help=".env.example file")],
    strict: _STRICT = False,
) -> None:
    """Check that every Settings field is documented in .env.example.

    [bold]Rules:[/bold]
      required    every UPPER_SNAKE_CASE field in class *Settings* must have
                  a matching KEY= entry in .env.example

    [bold]Example:[/bold]
      validate-tools env --settings src/config/settings.py --example .env.example
    """
    from validate_cli._validators.env import validate_env_completeness
    try:
        _emit(validate_env_completeness(settings.read_text(), example.read_text()), strict)
    except ValueError as exc:
        print_error(str(exc), "validate_env_completeness", state.human)
        raise typer.Exit(1)


# ── tests ─────────────────────────────────────────────────────────────────────


@app.command(name="tests")
def cmd_tests(
    files: Annotated[List[Path], typer.Argument(help="pytest test file(s)")],
    strict: _STRICT = False,
) -> None:
    """Check test function names for duplicates and descriptiveness.

    [bold]Rules:[/bold]
      required    duplicate def test_*() names in the same file
                  (pytest silently skips the second definition)
      recommended names with fewer than 3 tokens after the test_ prefix
                  (e.g. test_user is flagged; test_user_login_returns_200 is fine)
    """
    from validate_cli._validators.tests import validate_test_names
    _run_per_file(files, validate_test_names, strict)


# ── logs ──────────────────────────────────────────────────────────────────────


@app.command(name="logs")
def cmd_logs(
    files: Annotated[List[Path], typer.Argument(help="Python source file(s) to check")],
    strict: _STRICT = False,
) -> None:
    """Detect logging anti-patterns in Python source files.

    [bold]Rules:[/bold]
      required    print() calls — must use the project logger instead
      recommended f-strings passed to logger.*() — prefer lazy % formatting
                  to avoid eager interpolation when the log level is disabled
                  (e.g. logger.info("val %s", x) instead of logger.info(f"val {x}"))
    """
    from validate_cli._validators.logs import validate_log_calls
    _run_per_file(files, validate_log_calls, strict)


# ── coverage ──────────────────────────────────────────────────────────────────


@app.command(name="coverage")
def cmd_coverage(
    file: Annotated[Optional[Path], typer.Argument(help="Cobertura XML file (default: coverage.xml)")] = None,
    strict: _STRICT = False,
) -> None:
    """Validate per-layer code coverage against minimum thresholds.

    [bold]Thresholds (required):[/bold]
      domain         ≥ 90%
      application    ≥ 85%
      infrastructure ≥ 65%
      presentation   ≥ 55%

    [bold]Generate coverage.xml:[/bold]
      pytest --cov=src --cov-report=xml
    """
    from validate_cli._validators.coverage import validate_coverage_distribution
    path = file or Path("coverage.xml")
    if not path.exists():
        print_error(f"{path} not found. Run: pytest --cov=src --cov-report=xml", force_human=state.human)
        raise typer.Exit(1)
    try:
        _emit(validate_coverage_distribution(path.read_text()), strict)
    except ValueError as exc:
        print_error(str(exc), "validate_coverage_distribution", state.human)
        raise typer.Exit(1)


# ── supply-chain ──────────────────────────────────────────────────────────────


@app.command(name="supply-chain")
def cmd_supply_chain(
    file: Annotated[Optional[Path], typer.Argument(help="pyproject.toml or package.json (default: pyproject.toml)")] = None,
    strict: _STRICT = False,
) -> None:
    """Scan package manifests for supply-chain risks.

    [bold]Rules:[/bold]
      required    VCS sources      git = / hg = / svn = (TOML) or git+https:// (JSON)
      required    direct URL       url = "https://..."
      required    local path       path = "../..." or "file:..."
      required    wildcard version * / latest / any
      recommended pre-release      1.0.0b2 / 1.0.0.dev1 / 1.0.0-beta.1

    Accepts pyproject.toml (Python) or package.json (Node).
    """
    from validate_cli._validators.supply_chain import validate_supply_chain
    path = file or Path("pyproject.toml")
    if not path.exists():
        print_error(f"{path} not found.", force_human=state.human)
        raise typer.Exit(1)
    try:
        _emit(validate_supply_chain(path.read_text()), strict)
    except ValueError as exc:
        print_error(str(exc), "validate_supply_chain", state.human)
        raise typer.Exit(1)


# ── sensitive-logging ─────────────────────────────────────────────────────────


@app.command(name="project-layout")
def cmd_project_layout(
    root: Annotated[Path, typer.Argument(help="Project root to inspect (default: current directory)")] = Path("."),
    strict: _STRICT = False,
) -> None:
    """Validate stack-local artifacts plus Docker, compose, Makefile, and CI wiring."""
    from validate_cli._validators.project_layout import validate_project_layout

    if not root.exists() or not root.is_dir():
        print_error(f"{root} is not a directory.", force_human=state.human)
        raise typer.Exit(1)

    paths = sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(root).parts
        and "node_modules" not in path.relative_to(root).parts
        and ".venv" not in path.relative_to(root).parts
    )

    wanted = [
        "backend/Dockerfile",
        "backend/Dockerfile.test",
        "frontend/Dockerfile",
        "docker-compose.yml",
        "docker-compose.test.yml",
        "Makefile",
    ]
    files: dict[str, str] = {}
    for rel in wanted:
        content = _read_if_exists(root / rel)
        if content is not None:
            files[rel] = content

    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.exists():
        for path in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            files[str(path.relative_to(root)).replace("\\", "/")] = path.read_text()

    try:
        _emit(validate_project_layout("\n".join(paths), files), strict)
    except ValueError as exc:
        print_error(str(exc), "validate_project_layout", state.human)
        raise typer.Exit(1)


@app.command(name="sensitive-logging")
def cmd_sensitive_logging(
    files: Annotated[List[Path], typer.Argument(help="Python source file(s) to check")],
    strict: _STRICT = False,
) -> None:
    """Detect sensitive data leaked through log or print calls.

    [bold]Sensitive fields:[/bold]
      password, passwd, token, secret, api_key, apikey, access_token,
      refresh_token, auth_token, credit_card, card_number, cvv, cvc,
      ssn, private_key, authorization

    [bold]Rules:[/bold]
      required    sensitive field interpolated in a log/print call
                  (f-string, %-format, or positional argument)
      recommended logger.*(str(e)) / repr(e) — raw exception dumps can
                  expose DB connection strings or credentials
    """
    from validate_cli._validators.sensitive_logging import validate_sensitive_logging
    _run_per_file(files, validate_sensitive_logging, strict)


# ── secrets ───────────────────────────────────────────────────────────────────


@app.command(name="secrets")
def cmd_secrets(
    files: Annotated[List[Path], typer.Argument(help="Source file(s) to scan (Python or TypeScript)")],
    strict: _STRICT = False,
) -> None:
    """Detect hardcoded API keys, JWTs, and secret variable assignments.

    [bold]Rules (required):[/bold]
      Provider keys   Stripe sk_live_* / sk_test_* / pk_* / whsec_*
                      Slack xoxb-* / xoxp-*
                      GitHub ghp_* / ghs_* / github_pat_*
                      Google AIza*
                      AWS AKIA*
      JWT tokens      eyJ...eyJ... literals (non-test files only)
      Secret vars     password / secret / api_key / private_key / client_secret
                      assigned a non-placeholder string (non-test files only)

    Test files (test_*.py, *.spec.ts) are exempt from JWT and secret-variable
    checks but provider keys are always flagged.
    """
    from validate_cli._validators.hardcoded_secrets import validate_hardcoded_secrets
    _run_per_file(files, validate_hardcoded_secrets, strict)


# ── run (batch) ───────────────────────────────────────────────────────────────


@app.command(name="run")
def cmd_run(
    config_file: Annotated[Optional[Path], typer.Argument(help="JSON config file (default: stdin)")] = None,
) -> None:
    """Run multiple validators in one shot from a JSON config.

    Returns a JSON array — one report object per check.
    Designed for AI agents to reduce round-trips.

    [bold]Config schema[/bold] (all keys optional):

    [dim]{
      "imports":  "<grep -rn output>",
      "commits":  "<git log --format='%H %s' output>",
      "migration": "<migration file content>",
      "coverage": "<coverage.xml content>",
      "supply_chain": "<pyproject.toml or package.json content>",
      "project_layout": {
        "file_tree": "backend/Dockerfile\nfrontend/package.json\n...",
        "files": {"docker-compose.yml": "...", "backend/Dockerfile": "..."}
      },
      "env": { "settings_source": "...", "env_example": "..." },
      "tests":             [{ "filename": "test_foo.py", "source": "..." }],
      "logs":              [{ "filename": "foo.py",      "source": "..." }],
      "sensitive_logging": [{ "filename": "foo.py",      "source": "..." }],
      "secrets":           [{ "filename": "foo.py",      "source": "..." }]
    }[/dim]

    For per-file checks a plain string is also accepted (filename defaults to "source.py").
    """
    if config_file:
        raw = config_file.read_text()
    else:
        if sys.stdin.isatty():
            print_error("No config. Pass a JSON file or pipe config via stdin.", force_human=state.human)
            raise typer.Exit(1)
        raw = sys.stdin.read()

    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        print_error(f"Invalid JSON: {exc}", force_human=state.human)
        raise typer.Exit(1)

    results: list[dict] = []
    worst_exit = 0

    def _record(report_or_err: dict) -> None:
        nonlocal worst_exit
        results.append(report_or_err)
        s = report_or_err.get("status")
        if s == "violations":
            worst_exit = max(worst_exit, 2)
        elif s in ("warnings", "error"):
            worst_exit = max(worst_exit, 1)

    def _run_single(key: str, fn, *args):
        try:
            _record(report_to_dict(fn(*args)))
        except ValueError as exc:
            _record({"analysis": f"validate_{key}", "status": "error", "error": str(exc)})

    # ── single-text validators ────────────────────────────────────────────────
    from validate_cli._validators.imports import validate_import_directions
    from validate_cli._validators.commits import validate_commit_messages
    from validate_cli._validators.migration import validate_migration
    from validate_cli._validators.coverage import validate_coverage_distribution
    from validate_cli._validators.supply_chain import validate_supply_chain
    from validate_cli._validators.project_layout import validate_project_layout

    if "imports" in config:
        _run_single("imports", validate_import_directions, config["imports"])
    if "commits" in config:
        _run_single("commits", validate_commit_messages, config["commits"])
    if "migration" in config:
        _run_single("migration", validate_migration, config["migration"])
    if "coverage" in config:
        _run_single("coverage", validate_coverage_distribution, config["coverage"])
    if "supply_chain" in config:
        _run_single("supply_chain", validate_supply_chain, config["supply_chain"])
    if "project_layout" in config:
        layout = config["project_layout"]
        if isinstance(layout, str):
            _run_single("project_layout", validate_project_layout, layout, {})
        else:
            _run_single(
                "project_layout",
                validate_project_layout,
                layout.get("file_tree", ""),
                layout.get("files", {}),
            )

    # ── env ───────────────────────────────────────────────────────────────────
    from validate_cli._validators.env import validate_env_completeness

    if "env" in config:
        env = config["env"]
        _run_single("env", validate_env_completeness,
                    env.get("settings_source", ""), env.get("env_example", ""))

    # ── per-file validators ───────────────────────────────────────────────────
    from validate_cli._validators.tests import validate_test_names
    from validate_cli._validators.logs import validate_log_calls
    from validate_cli._validators.sensitive_logging import validate_sensitive_logging
    from validate_cli._validators.hardcoded_secrets import validate_hardcoded_secrets

    _PER_FILE = [
        ("tests", validate_test_names),
        ("logs", validate_log_calls),
        ("sensitive_logging", validate_sensitive_logging),
        ("secrets", validate_hardcoded_secrets),
    ]

    for key, fn in _PER_FILE:
        if key not in config:
            continue
        items = config[key]
        if isinstance(items, str):
            items = [{"filename": "source.py", "source": items}]
        elif isinstance(items, dict):
            items = [items]
        for item in items:
            _run_single(key, fn, item.get("source", ""), item.get("filename", "source.py"))

    indent = 2 if state.pretty else None
    print(json.dumps(results, indent=indent))

    if worst_exit:
        sys.exit(worst_exit)


# ── helpers ───────────────────────────────────────────────────────────────────


def _run_per_file(files: list[Path], validator, strict: bool) -> None:
    worst_exit = 0
    for path in files:
        try:
            report = validator(path.read_text(), str(path))
        except ValueError as exc:
            print_error(str(exc), force_human=state.human)
            worst_exit = max(worst_exit, 1)
            continue

        code = output_report(report, strict=strict, force_human=state.human, pretty=state.pretty, exit_on_done=False)
        worst_exit = max(worst_exit, code)

    if worst_exit:
        sys.exit(worst_exit)
