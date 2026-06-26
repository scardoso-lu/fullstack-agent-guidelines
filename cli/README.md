# validate-tools

Local CLI for fullstack code validation. Runs the same checks as the MCP server without the token overhead — pipe files in, get JSON out.

## Installation

```bash
pip install validate-tools
# or
uv tool install validate-tools
```

## Usage

```
validate-tools [--human] [--pretty] COMMAND [OPTIONS]
```

When stdout is **not** a TTY (piped to a script or agent), JSON is emitted automatically. No `--json` flag needed.

**Global flags:**

| Flag | Description |
|------|-------------|
| `--human` / `-H` | Force rich/table output even when piped |
| `--pretty` | Indent JSON output (default: compact) |

**Exit codes:** `0` = clean · `1` = warnings (with `--strict`) · `2` = violations

---

## Commands

### `imports` — Clean Architecture import directions

```bash
grep -rn "^from\|^import" src/ --include="*.py" | validate-tools imports
```

Rules: domain → no project imports; application → domain only; infrastructure → domain + application; presentation → all layers.

---

### `commits` — Conventional Commits format

```bash
git log --format="%H %s" origin/main..HEAD | validate-tools commits
```

Checks `type(scope)?: description` format (required) and ≤72-char subject (recommended).
Allowed types: `feat fix docs chore refactor test ci perf build style revert`

---

### `migration` — Alembic migration safety

```bash
validate-tools migration alembic/versions/*.py
```

Flags: `drop_column`, `drop_table`, `rename_table`, `rename_column`, `add_column` with `nullable=False` and no `server_default` (required); `alter_column`, `execute` (recommended).

---

### `env` — Settings ↔ .env.example completeness

```bash
validate-tools env --settings src/config/settings.py --example .env.example
```

Every `UPPER_SNAKE_CASE` field in `class *Settings*` must have a matching `KEY=` entry in `.env.example`.

---

### `tests` — pytest test name quality

```bash
validate-tools tests test/unit/test_auth.py
```

Flags duplicate `test_*` names (required) and names with fewer than 3 tokens after `test_` (recommended).

---

### `logs` — Logging anti-patterns

```bash
validate-tools logs src/application/use_cases/auth_use_case.py
```

Flags `print()` calls (required) and f-strings inside `logger.*()` (recommended).

---

### `coverage` — Per-layer coverage thresholds

```bash
pytest --cov=src --cov-report=xml
validate-tools coverage coverage.xml
```

Thresholds: `domain ≥90%` · `application ≥85%` · `infrastructure ≥65%` · `presentation ≥55%`

---

### `supply-chain` — Dependency manifest risks

```bash
validate-tools supply-chain pyproject.toml   # or package.json
```

Flags VCS/URL/local-path sources and wildcard versions (required); pre-release versions (recommended).

---

### `sensitive-logging` — Sensitive data in logs

```bash
validate-tools sensitive-logging src/application/use_cases/auth_use_case.py
```

Flags passwords, tokens, secrets, API keys, and card numbers passed to `log.*()` or `print()`.

---

### `secrets` — Hardcoded credentials

```bash
validate-tools secrets src/config/settings.py
```

Detects Stripe, Slack, GitHub, Google, and AWS key literals; JWT tokens; and sensitive variable assignments (`password = "..."`, `secret = "..."`).

---

## Batch mode (`run`) — for AI agents

Run multiple validators in a single invocation. Accepts a JSON config on stdin and returns a JSON array — one report per check.

```bash
cat <<'EOF' | validate-tools run
{
  "imports":  "<output of grep -rn ...>",
  "commits":  "<output of git log --format='%H %s' ...>",
  "supply_chain": "<content of pyproject.toml>",
  "secrets": [{ "filename": "settings.py", "source": "<file content>" }],
  "logs":    [{ "filename": "auth.py",     "source": "<file content>" }]
}
EOF
```

**Config keys** (all optional):

| Key | Value |
|-----|-------|
| `imports` | grep output (string) |
| `commits` | git log output (string) |
| `migration` | migration file content (string) |
| `coverage` | coverage.xml content (string) |
| `supply_chain` | pyproject.toml or package.json content (string) |
| `env` | `{"settings_source": "...", "env_example": "..."}` |
| `tests` | `[{"filename": "test_foo.py", "source": "..."}]` |
| `logs` | `[{"filename": "foo.py", "source": "..."}]` |
| `sensitive_logging` | `[{"filename": "foo.py", "source": "..."}]` |
| `secrets` | `[{"filename": "foo.py", "source": "..."}]` |

For per-file checks, a plain string is also accepted (filename defaults to `source.py`).

---

## Output format

Every command emits the same JSON schema:

```json
{
  "analysis": "validate_import_directions",
  "status": "clean | warnings | violations",
  "total_items": 42,
  "required_count": 0,
  "recommended_count": 0,
  "summary": "All 42 file(s) respect the layer dependency rules.",
  "findings": [
    {
      "rule_id": "backend/imports/domain-no-infrastructure",
      "severity": "required | recommended",
      "location": "src/domain/entities/user.py:12",
      "message": "Domain layer must not import from infrastructure layer",
      "hint": "Remove the cross-layer import. Domain may only depend on: domain only."
    }
  ]
}
```

Errors also follow a consistent schema when piped:

```json
{"status": "error", "error": "git_log is empty — run: ...", "analysis": "validate_commit_messages"}
```

## License

MIT
