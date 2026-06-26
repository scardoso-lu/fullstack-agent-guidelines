from __future__ import annotations

import re

from validate_cli._models import AnalysisReportDto, FindingDto

_SENSITIVE = (
    "password|passwd|token|secret|api_key|apikey|access_token|refresh_token|auth_token"
    "|credit_card|card_number|cvv|cvc|ssn|private_key|authorization"
)
_SENSITIVE_RE = re.compile(_SENSITIVE, re.IGNORECASE)
_LOG_CALL_RE = re.compile(r'\b(?:logger|logging|log)\.\w+\s*\(|\bprint\s*\(')
_FSTRING_VAR_RE = re.compile(
    r'\{(?:self\.)?(' + _SENSITIVE + r')(?:[.\[!:}\s])',
    re.IGNORECASE,
)
_PERCENT_VAR_RE = re.compile(r'%\((' + _SENSITIVE + r')\)', re.IGNORECASE)
_POSITIONAL_VAR_RE = re.compile(
    r'(?:,\s*|\(\s*)(?:self\.)?(' + _SENSITIVE + r')\s*[,)]',
    re.IGNORECASE,
)
_EXCEPTION_DUMP_RE = re.compile(
    r'\b(?:logger|logging|log)\.\w+\s*\(\s*(?:str\s*\(e\)|repr\s*\(e\)|e\b)'
)


def _line_leaks_sensitive_data(line: str) -> bool:
    if not _LOG_CALL_RE.search(line):
        return False
    return bool(
        _FSTRING_VAR_RE.search(line)
        or _PERCENT_VAR_RE.search(line)
        or _POSITIONAL_VAR_RE.search(line)
    )


def validate_sensitive_logging(source: str, filename: str = "source.py") -> AnalysisReportDto:
    if not source.strip():
        raise ValueError("source is empty — pass the content of a Python source file")

    lines = source.splitlines()
    findings: list[FindingDto] = []

    for i, raw_line in enumerate(lines, 1):
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            continue

        if _line_leaks_sensitive_data(raw_line):
            match = (
                _FSTRING_VAR_RE.search(raw_line)
                or _PERCENT_VAR_RE.search(raw_line)
                or _POSITIONAL_VAR_RE.search(raw_line)
            )
            field = match.group(1) if match else "sensitive field"
            findings.append(FindingDto(
                rule_id="security/logging/sensitive-data-in-log",
                severity="required",
                location=f"{filename}:{i}",
                message=f"Sensitive field {field!r} passed to a log/print call",
                hint=(
                    f"Remove {field!r} from the log statement. "
                    'Log a redacted placeholder (e.g. "[REDACTED]") or omit the field entirely.'
                ),
            ))

        if _EXCEPTION_DUMP_RE.search(raw_line):
            findings.append(FindingDto(
                rule_id="security/logging/raw-exception-dump",
                severity="recommended",
                location=f"{filename}:{i}",
                message="Raw exception object passed directly to logger — message may contain credentials",
                hint=(
                    "Log only e.__class__.__name__ or a safe summary. "
                    "Full exception strings can embed DB URLs, credentials, or tokens."
                ),
            ))

    required_count = sum(1 for f in findings if f.severity == "required")
    recommended_count = sum(1 for f in findings if f.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    summary = (
        f"Found {required_count} sensitive data leak(s) and "
        f"{recommended_count} exception dump(s) in {len(lines)} line(s)."
        if findings
        else f"No sensitive data logging detected in {len(lines)} line(s)."
    )

    return AnalysisReportDto(
        analysis="validate_sensitive_logging",
        total_items=len(lines),
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
