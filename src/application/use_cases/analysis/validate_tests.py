from __future__ import annotations

import re
from collections import Counter

from src.application.dto.analysis_dto import AnalysisReportDto, FindingDto
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_test_names")

_TEST_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(", re.MULTILINE)
_MIN_TOKENS = 3  # tokens after "test_" for a name to be considered descriptive


def _token_count(name: str) -> int:
    """Count meaningful tokens in a test name (excluding the leading 'test_' prefix)."""
    return len(name.removeprefix("test_").split("_"))


class ValidateTestNamesUseCase:
    async def execute(self, source: str, filename: str = "test_file.py") -> AnalysisReportDto:
        if not source.strip():
            raise ValueError("source is empty — paste the content of a pytest test file")

        names = _TEST_DEF_RE.findall(source)
        if not names:
            raise ValueError(
                "No test functions found — make sure the source contains def test_*() functions"
            )

        findings: list[FindingDto] = []

        # Duplicate names within the same file (pytest silently skips duplicates)
        counts = Counter(names)
        for name, count in counts.items():
            if count > 1:
                findings.append(FindingDto(
                    rule_id="qa/tests/no-duplicate-test-names",
                    severity="required",
                    location=f"{filename}::{name}",
                    message=f"Test {name!r} is defined {count} times — pytest will silently skip duplicates",
                    hint="Rename the duplicate to reflect what it uniquely tests.",
                ))

        # Descriptiveness check (unique names only to avoid double-reporting)
        for name in set(names):
            if _token_count(name) < _MIN_TOKENS:
                findings.append(FindingDto(
                    rule_id="qa/tests/descriptive-test-names",
                    severity="recommended",
                    location=f"{filename}::{name}",
                    message=(
                        f"Test name {name!r} has fewer than {_MIN_TOKENS} tokens after 'test_'"
                    ),
                    hint=(
                        f"Follow the pattern test_<entity>_<action>_<expected_outcome> — "
                        f"e.g. {name}_returns_200_when_authenticated"
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
            f"Checked {len(names)} test(s); "
            f"found {required_count} duplicate(s) and {recommended_count} short name(s)."
            if findings
            else f"All {len(names)} test name(s) are unique and descriptive."
        )

        _logger.info(
            "validate_test_names tests=%d findings=%d status=%r",
            len(names),
            len(findings),
            status,
        )

        return AnalysisReportDto(
            analysis="validate_test_names",
            total_items=len(names),
            findings=findings,
            required_count=required_count,
            recommended_count=recommended_count,
            status=status,
            summary=summary,
        )
