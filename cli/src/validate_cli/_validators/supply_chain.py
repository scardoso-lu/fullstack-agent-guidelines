from __future__ import annotations

import re

from validate_cli._models import AnalysisReportDto, FindingDto

_TOML_VCS_RE = re.compile(r'\b(?:git|hg|svn)\s*=\s*["\']', re.IGNORECASE)
_TOML_URL_RE = re.compile(r'\burl\s*=\s*["\']https?://', re.IGNORECASE)
_TOML_PATH_RE = re.compile(r'\bpath\s*=\s*["\']\.\.?/', re.IGNORECASE)

_JSON_VCS_RE = re.compile(r':\s*"(?:git\+https?://|git\+ssh://|git://|github:|bitbucket:|gitlab:)')
_JSON_URL_RE = re.compile(r':\s*"https?://(?!registry\.npmjs\.org)')
_JSON_PATH_RE = re.compile(r':\s*"file:')

_PRERELEASE_RE = re.compile(
    r'"[\d.]+(?:a\d+|b\d+|rc\d+|\.dev\d*)"'
    r'|"[\d.]+-(?:alpha|beta|rc)[\d.]*"'
)

_WILDCARD_RE = re.compile(r'[=:]\s*["\'](?:\*|latest|any)["\']')


def _scan_line(line: str, lineno: int, findings: list[FindingDto]) -> None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("//"):
        return

    if _TOML_VCS_RE.search(line) or _JSON_VCS_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-vcs-source",
            severity="required",
            location=f"line:{lineno}",
            message=f"Dependency installed from a VCS source: {stripped!r}",
            hint=(
                "Install only from a package registry (PyPI / npmjs.org). "
                "VCS sources bypass registry integrity checks and can be silently replaced."
            ),
        ))

    if _TOML_URL_RE.search(line) or _JSON_URL_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-direct-url-source",
            severity="required",
            location=f"line:{lineno}",
            message=f"Dependency installed from a direct URL: {stripped!r}",
            hint=(
                "Publish the package to your internal registry and install from there. "
                "Direct URLs are not covered by registry vulnerability scanning."
            ),
        ))

    if _TOML_PATH_RE.search(line) or _JSON_PATH_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-local-path-source",
            severity="required",
            location=f"line:{lineno}",
            message=f"Dependency installed from a local path: {stripped!r}",
            hint=(
                "Local path dependencies cannot be reproduced in CI or audited. "
                "Publish to the internal registry before adding as a real dependency."
            ),
        ))

    if _WILDCARD_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-wildcard-version",
            severity="required",
            location=f"line:{lineno}",
            message=f"Unconstrained version specifier (* / latest): {stripped!r}",
            hint=(
                "Pin to an exact version or a tight range. "
                "Wildcards allow future malicious releases to be pulled in automatically."
            ),
        ))

    if _PRERELEASE_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-prerelease-version",
            severity="recommended",
            location=f"line:{lineno}",
            message=f"Pre-release version constraint detected: {stripped!r}",
            hint=(
                "Pre-release packages receive less security scrutiny than stable releases. "
                "Wait for a stable release, or document the exception in the decision record."
            ),
        ))


def validate_supply_chain(manifest: str) -> AnalysisReportDto:
    if not manifest.strip():
        raise ValueError(
            "manifest is empty — pass pyproject.toml (backend) or package.json (frontend)"
        )

    lines = manifest.splitlines()
    findings: list[FindingDto] = []

    for i, line in enumerate(lines, 1):
        _scan_line(line, i, findings)

    required_count = sum(1 for f in findings if f.severity == "required")
    recommended_count = sum(1 for f in findings if f.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    summary = (
        f"Found {required_count} supply chain risk(s) and "
        f"{recommended_count} recommendation(s) across {len(lines)} line(s)."
        if findings
        else f"No supply chain issues detected across {len(lines)} line(s)."
    )

    return AnalysisReportDto(
        analysis="validate_supply_chain",
        total_items=len(lines),
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
