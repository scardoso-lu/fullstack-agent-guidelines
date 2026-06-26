from __future__ import annotations

import re

from validate_cli._models import AnalysisReportDto, FindingDto

_PROVIDER_KEY_RE = re.compile(
    r'\b('
    r'sk_live_[a-zA-Z0-9_\-]{10,}'
    r'|sk_test_[a-zA-Z0-9_\-]{10,}'
    r'|pk_live_[a-zA-Z0-9_\-]{10,}'
    r'|pk_test_[a-zA-Z0-9_\-]{10,}'
    r'|rk_live_[a-zA-Z0-9_\-]{10,}'
    r'|whsec_[a-zA-Z0-9_\-]{10,}'
    r'|xoxb-[0-9a-zA-Z\-]{10,}'
    r'|xoxp-[0-9a-zA-Z\-]{10,}'
    r'|ghp_[a-zA-Z0-9]{36}'
    r'|ghs_[a-zA-Z0-9]{36}'
    r'|github_pat_[a-zA-Z0-9_]{82}'
    r'|AIza[0-9A-Za-z\-_]{35}'
    r'|AKIA[0-9A-Z]{16}'
    r')',
)
_JWT_RE = re.compile(r'\beyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\b')
_PLACEHOLDER_RE = re.compile(
    r'^(?:test|example|changeme|change_me|placeholder|dummy|fake|your_|<|{|\s*$)',
    re.IGNORECASE,
)
_GENERIC_SECRET_RE = re.compile(
    r'\b(password|passwd|secret|api_key|apikey|private_key|client_secret)'
    r'\s*=\s*["\']([^"\']{4,})["\']',
    re.IGNORECASE,
)
_SKIP_RE = re.compile(r'^\s*(?:#|//|/\*|\*)')
_TEST_FILE_RE = re.compile(r'(?:test_|_test\.|spec\.|\.spec\.)')


def validate_hardcoded_secrets(source: str, filename: str = "source.py") -> AnalysisReportDto:
    if not source.strip():
        raise ValueError("source is empty — pass the content of a source file")

    is_test_file = bool(_TEST_FILE_RE.search(filename))
    lines = source.splitlines()
    findings: list[FindingDto] = []

    for i, raw_line in enumerate(lines, 1):
        if _SKIP_RE.match(raw_line):
            continue

        m = _PROVIDER_KEY_RE.search(raw_line)
        if m:
            key_preview = m.group(1)[:12] + "..."
            findings.append(FindingDto(
                rule_id="security/secrets/hardcoded-provider-key",
                severity="required",
                location=f"{filename}:{i}",
                message=f"Provider API key literal detected: {key_preview!r}",
                hint=(
                    "Remove the key from source. Store it in an environment variable "
                    "and read it through the Settings class. Rotate the exposed key immediately."
                ),
            ))

        if not is_test_file and _JWT_RE.search(raw_line):
            findings.append(FindingDto(
                rule_id="security/secrets/hardcoded-jwt",
                severity="required",
                location=f"{filename}:{i}",
                message="Encoded JWT token literal detected in source",
                hint=(
                    "Remove the token from source. JWTs embedded in code can be extracted "
                    "from version control history even after deletion."
                ),
            ))

        if not is_test_file:
            gm = _GENERIC_SECRET_RE.search(raw_line)
            if gm and not _PLACEHOLDER_RE.match(gm.group(2)):
                var_name = gm.group(1)
                findings.append(FindingDto(
                    rule_id="security/secrets/hardcoded-secret-variable",
                    severity="required",
                    location=f"{filename}:{i}",
                    message=f"Sensitive variable {var_name!r} assigned a string literal",
                    hint=(
                        f"Move {var_name} to an environment variable. "
                        "Read it via the Settings class so it never appears in source code."
                    ),
                ))

    required_count = sum(1 for f in findings if f.severity == "required")
    recommended_count = sum(1 for f in findings if f.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    summary = (
        f"Found {required_count} hardcoded secret(s) in {len(lines)} line(s)."
        if findings
        else f"No hardcoded secrets detected in {len(lines)} line(s)."
    )

    return AnalysisReportDto(
        analysis="validate_hardcoded_secrets",
        total_items=len(lines),
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
