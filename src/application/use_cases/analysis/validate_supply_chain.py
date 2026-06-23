from __future__ import annotations

import re

from src.application.dto.analysis_dto import AnalysisReportDto, FindingDto
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_supply_chain")

# ── patterns ──────────────────────────────────────────────────────────────────

# VCS sources in TOML: git = "https://..." or hg/svn variants
_TOML_VCS_RE = re.compile(r'\b(?:git|hg|svn)\s*=\s*["\']', re.IGNORECASE)
# Direct URL source in TOML: url = "https://..."
_TOML_URL_RE = re.compile(r'\burl\s*=\s*["\']https?://', re.IGNORECASE)
# Local path in TOML: path = "../..." or path = "./..."
_TOML_PATH_RE = re.compile(r'\bpath\s*=\s*["\']\.\.?/', re.IGNORECASE)

# VCS/URL/local in JSON/npm manifest values
_JSON_VCS_RE = re.compile(r':\s*"(?:git\+https?://|git\+ssh://|git://|github:|bitbucket:|gitlab:)')
_JSON_URL_RE = re.compile(r':\s*"https?://(?!registry\.npmjs\.org)')
_JSON_PATH_RE = re.compile(r':\s*"file:')

# Pre-release version markers (Python: a1/b2/rc3/.dev; npm: -alpha/-beta/-rc)
_PRERELEASE_RE = re.compile(
    r'"[\d.]+(?:a\d+|b\d+|rc\d+|\.dev\d*)"'   # PEP 440: 1.0.0b2, 2.0.0.dev1
    r'|"[\d.]+-(?:alpha|beta|rc)[\d.]*"'        # npm semver: 1.0.0-beta.1
)

# Wildcard / completely unconstrained
_WILDCARD_RE = re.compile(r'[=:]\s*["\'](?:\*|latest|any)["\']')

# Extract dependency name for context (TOML: name = ..., JSON: "name": ...)
_TOML_NAME_RE = re.compile(r'^([\w][\w\-\.]*)\s*=', re.MULTILINE)
_JSON_NAME_RE = re.compile(r'"([\w][\w\-\./]*)"\s*:')


def _scan_line(
    line: str,
    lineno: int,
    findings: list[FindingDto],
) -> None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("//"):
        return

    # VCS source
    if _TOML_VCS_RE.search(line) or _JSON_VCS_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-vcs-source",
            severity="required",
            location=f"line:{lineno}",
            message=f"Dependency installed from a VCS source: {stripped!r}",
            hint=(
                "Install only from a package registry (PyPI / npmjs.org). "
                "VCS sources bypass registry integrity checks and can be silently replaced. "
                "Fork the package to an internal registry if you need a patched version."
            ),
        ))

    # Direct URL source
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

    # Local path source
    if _TOML_PATH_RE.search(line) or _JSON_PATH_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-local-path-source",
            severity="required",
            location=f"line:{lineno}",
            message=f"Dependency installed from a local path: {stripped!r}",
            hint=(
                "Local path dependencies are development-only conveniences — "
                "they cannot be reproduced in CI or audited. "
                "Publish to the internal registry before adding as a real dependency."
            ),
        ))

    # Wildcard / unconstrained
    if _WILDCARD_RE.search(line):
        findings.append(FindingDto(
            rule_id="supply-chain/no-wildcard-version",
            severity="required",
            location=f"line:{lineno}",
            message=f"Unconstrained version specifier (*  /  latest): {stripped!r}",
            hint=(
                "Pin to an exact version or a tight range. "
                "Wildcards allow future malicious releases to be pulled in automatically."
            ),
        ))

    # Pre-release version
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


class ValidateSupplyChainUseCase:
    async def execute(self, manifest: str) -> AnalysisReportDto:
        if not manifest.strip():
            raise ValueError(
                "manifest is empty — paste the content of pyproject.toml "
                "(backend) or package.json (frontend)"
            )

        lines = manifest.splitlines()
        findings: list[FindingDto] = []

        for i, line in enumerate(lines, 1):
            _scan_line(line, i, findings)

        required_count = sum(1 for f in findings if f.severity == "required")
        recommended_count = sum(1 for f in findings if f.severity == "recommended")

        if required_count > 0:
            status = "violations"
        elif recommended_count > 0:
            status = "warnings"
        else:
            status = "clean"

        summary = (
            f"Found {required_count} supply chain risk(s) and "
            f"{recommended_count} recommendation(s) across {len(lines)} line(s)."
            if findings
            else f"No supply chain issues detected across {len(lines)} line(s)."
        )

        _logger.info(
            "validate_supply_chain lines=%d findings=%d status=%r",
            len(lines),
            len(findings),
            status,
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
