from __future__ import annotations

import re

from validate_cli._models import AnalysisReportDto, FindingDto

_DESTRUCTIVE_OPS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"\bop\.drop_column\s*\("),
        "backend/migration/no-drop-column",
        (
            "op.drop_column() is destructive — remove the column in a separate migration "
            "behind a feature flag to guard reads during the rollout window."
        ),
    ),
    (
        re.compile(r"\bop\.drop_table\s*\("),
        "backend/migration/no-drop-table",
        (
            "op.drop_table() is destructive — ensure all foreign keys and dependent data "
            "are migrated before dropping."
        ),
    ),
    (
        re.compile(r"\bop\.rename_table\s*\("),
        "backend/migration/no-rename-table",
        (
            "op.rename_table() is a breaking change — use a view or synonym during "
            "the transition and migrate in two phases."
        ),
    ),
    (
        re.compile(r"\bop\.rename_column\s*\("),
        "backend/migration/no-rename-column",
        (
            "op.rename_column() breaks existing code reading the old column name — "
            "add a new column, backfill, update code, then drop the old column."
        ),
    ),
]

_ADD_COLUMN_RE = re.compile(r"\bop\.add_column\s*\(")
_NULLABLE_FALSE_RE = re.compile(r"\bnullable\s*=\s*False\b")
_SERVER_DEFAULT_RE = re.compile(r"\bserver_default\s*=")
_ALTER_COLUMN_RE = re.compile(r"\bop\.alter_column\s*\(")
_EXECUTE_RE = re.compile(r"\bop\.execute\s*\(")
_LOOKAHEAD = 10


def validate_migration(source: str) -> AnalysisReportDto:
    if not source.strip():
        raise ValueError(
            "source is empty — paste the content of one or more Alembic migration files"
        )

    lines = source.splitlines()
    findings: list[FindingDto] = []

    for i, line in enumerate(lines, 1):
        for pattern, rule_id, hint in _DESTRUCTIVE_OPS:
            if pattern.search(line):
                findings.append(FindingDto(
                    rule_id=rule_id,
                    severity="required",
                    location=f"line:{i}",
                    message=f"Destructive migration operation: {line.strip()!r}",
                    hint=hint,
                ))

        if _ADD_COLUMN_RE.search(line):
            window = "\n".join(lines[i - 1: i - 1 + _LOOKAHEAD])
            if _NULLABLE_FALSE_RE.search(window) and not _SERVER_DEFAULT_RE.search(window):
                findings.append(FindingDto(
                    rule_id="backend/migration/add-column-nullable-false-needs-server-default",
                    severity="required",
                    location=f"line:{i}",
                    message=(
                        "op.add_column with nullable=False has no server_default — "
                        "existing rows will fail the constraint."
                    ),
                    hint=(
                        "Add server_default=sa.text(\"''\") or an appropriate sentinel, "
                        "then remove it in a follow-up migration once all rows are populated."
                    ),
                ))

        if _ALTER_COLUMN_RE.search(line):
            findings.append(FindingDto(
                rule_id="backend/migration/alter-column-type-risk",
                severity="recommended",
                location=f"line:{i}",
                message="op.alter_column() — verify the type change is backwards-compatible",
                hint=(
                    "Changing a column type can break existing reads. "
                    "Prefer adding a new column, backfilling, and dropping the old one in steps."
                ),
            ))

        if _EXECUTE_RE.search(line):
            findings.append(FindingDto(
                rule_id="backend/migration/raw-sql-execute",
                severity="recommended",
                location=f"line:{i}",
                message="op.execute() with raw SQL bypasses Alembic schema tracking",
                hint=(
                    "Use Alembic DDL constructs instead of raw SQL where possible. "
                    "If raw SQL is unavoidable, add a comment explaining why."
                ),
            ))

    required_count = sum(1 for f in findings if f.severity == "required")
    recommended_count = sum(1 for f in findings if f.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    summary = (
        f"Found {required_count} required and {recommended_count} recommended issue(s) "
        f"across {len(lines)} line(s)."
        if findings
        else f"No migration safety issues found across {len(lines)} line(s)."
    )

    return AnalysisReportDto(
        analysis="validate_migration",
        total_items=len(lines),
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
