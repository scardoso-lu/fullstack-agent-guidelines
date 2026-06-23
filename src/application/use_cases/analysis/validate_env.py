from __future__ import annotations

import re

from src.application.dto.analysis_dto import AnalysisReportDto, FindingDto
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_env_completeness")

# Detects UPPER_SNAKE_CASE fields inside a Settings class body
_SETTINGS_FIELD_RE = re.compile(r"^\s{1,}([A-Z][A-Z0-9_]{1,})\s*(?::[^=\n#]+)?(?:\s*=|$)")
# Detects key definitions in .env.example
_ENV_KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=")


def _extract_settings_fields(source: str) -> list[str]:
    fields: list[str] = []
    in_settings = False
    for line in source.splitlines():
        if re.match(r"^class\s+\w*[Ss]ettings\w*\s*[\(:]", line):
            in_settings = True
            continue
        if in_settings:
            # A new top-level class or non-blank non-indented line ends the block
            if line and not line[0].isspace() and not line.startswith("#"):
                in_settings = False
                continue
            m = _SETTINGS_FIELD_RE.match(line)
            if m:
                fields.append(m.group(1))
    return fields


def _extract_env_keys(env_example: str) -> set[str]:
    keys: set[str] = set()
    for line in env_example.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _ENV_KEY_RE.match(stripped)
        if m:
            keys.add(m.group(1))
    return keys


class ValidateEnvCompletenessUseCase:
    async def execute(self, settings_source: str, env_example: str) -> AnalysisReportDto:
        if not settings_source.strip():
            raise ValueError(
                "settings_source is empty — paste the content of the file containing the Settings class"
            )
        if not env_example.strip():
            raise ValueError("env_example is empty — paste the content of .env.example")

        fields = _extract_settings_fields(settings_source)
        if not fields:
            raise ValueError(
                "No Settings fields detected — make sure the source contains a class "
                "whose name ends with 'Settings' and has UPPER_SNAKE_CASE field names"
            )

        env_keys = _extract_env_keys(env_example)
        findings: list[FindingDto] = []

        for field in fields:
            if field not in env_keys:
                findings.append(FindingDto(
                    rule_id="backend/env/missing-in-env-example",
                    severity="required",
                    location=f"field:{field}",
                    message=f"Settings field {field!r} has no entry in .env.example",
                    hint=(
                        f"Add '{field}=<example_value>' to .env.example "
                        "so new developers know the variable is required."
                    ),
                ))

        required_count = len(findings)
        recommended_count = 0

        if required_count > 0:
            status = "violations"
        else:
            status = "clean"

        summary = (
            f"Found {required_count} undocumented field(s) out of {len(fields)} total."
            if findings
            else f"All {len(fields)} Settings field(s) are documented in .env.example."
        )

        _logger.info(
            "validate_env fields=%d missing=%d status=%r",
            len(fields),
            required_count,
            status,
        )

        return AnalysisReportDto(
            analysis="validate_env_completeness",
            total_items=len(fields),
            findings=findings,
            required_count=required_count,
            recommended_count=recommended_count,
            status=status,
            summary=summary,
        )
