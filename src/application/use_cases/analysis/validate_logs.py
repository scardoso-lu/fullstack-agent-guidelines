from __future__ import annotations

import re

from src.application.dto.analysis_dto import AnalysisReportDto, FindingDto
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_log_calls")

_PRINT_RE = re.compile(r"\bprint\s*\(")
_LOG_FSTRING_RE = re.compile(r"\b(?:logger|logging)\.\w+\s*\(\s*f[\"']")


class ValidateLogCallsUseCase:
    async def execute(self, source: str, filename: str = "source.py") -> AnalysisReportDto:
        if not source.strip():
            raise ValueError("source is empty — paste the content of a Python source file")

        lines = source.splitlines()
        findings: list[FindingDto] = []

        for i, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()
            if stripped.startswith("#"):
                continue

            if _PRINT_RE.search(raw_line):
                findings.append(FindingDto(
                    rule_id="backend/logging/no-print-statements",
                    severity="required",
                    location=f"{filename}:{i}",
                    message="print() detected — use the project logger instead",
                    hint=(
                        "Replace print() with logger.info() / logger.debug(). "
                        "Obtain the logger with: logger = get_logger(__name__)"
                    ),
                ))

            if _LOG_FSTRING_RE.search(raw_line):
                findings.append(FindingDto(
                    rule_id="backend/logging/no-fstring-in-log",
                    severity="recommended",
                    location=f"{filename}:{i}",
                    message="f-string used as logger message — prefer lazy % formatting",
                    hint=(
                        'Replace logger.info(f"msg {val}") with logger.info("msg %s", val) '
                        "to avoid eager string interpolation when the log level is disabled."
                    ),
                ))

        required_count = sum(1 for f in findings if f.severity == "required")
        recommended_count = sum(1 for f in findings if f.severity == "recommended")

        if required_count > 0:
            status = "violations"
        elif recommended_count > 0:
            status = "warnings"
        else:
            status = "clean"

        summary = (
            f"Found {required_count} print() call(s) and {recommended_count} f-string log(s) "
            f"in {len(lines)} line(s)."
            if findings
            else f"No logging issues found in {len(lines)} line(s)."
        )

        _logger.info(
            "validate_log_calls lines=%d findings=%d status=%r",
            len(lines),
            len(findings),
            status,
        )

        return AnalysisReportDto(
            analysis="validate_log_calls",
            total_items=len(lines),
            findings=findings,
            required_count=required_count,
            recommended_count=recommended_count,
            status=status,
            summary=summary,
        )
