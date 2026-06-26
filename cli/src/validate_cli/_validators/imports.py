from __future__ import annotations

import re

from validate_cli._models import AnalysisReportDto, FindingDto

_FILE_LAYER: dict[str, re.Pattern[str]] = {
    "domain": re.compile(r"[/\\]domain[/\\]"),
    "application": re.compile(r"[/\\]application[/\\]"),
    "infrastructure": re.compile(r"[/\\]infrastructure[/\\]"),
    "presentation": re.compile(r"[/\\]presentation[/\\]"),
}

_IMPORT_LAYER: dict[str, re.Pattern[str]] = {
    "domain": re.compile(r"\bsrc\.domain\b"),
    "application": re.compile(r"\bsrc\.application\b"),
    "infrastructure": re.compile(r"\bsrc\.infrastructure\b"),
    "presentation": re.compile(r"\bsrc\.presentation\b"),
}

_FORBIDDEN: dict[str, list[str]] = {
    "domain": ["application", "infrastructure", "presentation"],
    "application": ["infrastructure", "presentation"],
    "infrastructure": ["presentation"],
}

_CONTRACT_RE = re.compile(r"\bsrc\.infrastructure\.repositories\.contract\b")
_GREP_LINE_RE = re.compile(r"^([^:]+):(\d+):(.+)$")

_LAYER_ALLOWED: dict[str, str] = {
    "domain": "domain only",
    "application": "domain (+ infrastructure.repositories.contract)",
    "infrastructure": "domain and application",
    "presentation": "all layers",
}


def _file_layer(path: str) -> str | None:
    for layer, pattern in _FILE_LAYER.items():
        if pattern.search(path):
            return layer
    return None


def _import_layers(stmt: str) -> list[str]:
    return [layer for layer, pattern in _IMPORT_LAYER.items() if pattern.search(stmt)]


def validate_import_directions(grep_output: str) -> AnalysisReportDto:
    if not grep_output.strip():
        raise ValueError(
            "grep_output is empty — run: "
            'grep -rn "^from\\|^import" src/ --include="*.py"'
        )

    lines = [
        line
        for line in grep_output.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    findings: list[FindingDto] = []
    seen_files: set[str] = set()

    for raw_line in lines:
        m = _GREP_LINE_RE.match(raw_line.strip())
        if not m:
            continue
        file_path, lineno, stmt = m.group(1), m.group(2), m.group(3).strip()
        seen_files.add(file_path)

        src_layer = _file_layer(file_path)
        if src_layer is None:
            continue

        forbidden_targets = _FORBIDDEN.get(src_layer, [])
        for target_layer in _import_layers(stmt):
            if target_layer not in forbidden_targets:
                continue
            if src_layer == "application" and target_layer == "infrastructure":
                if _CONTRACT_RE.search(stmt):
                    continue
            findings.append(FindingDto(
                rule_id=f"backend/imports/{src_layer}-no-{target_layer}",
                severity="required",
                location=f"{file_path}:{lineno}",
                message=f"{src_layer.capitalize()} layer must not import from {target_layer} layer",
                hint=(
                    f"Remove the cross-layer import. "
                    f"{src_layer.capitalize()} may only depend on: "
                    f"{_LAYER_ALLOWED[src_layer]}."
                ),
            ))

    required_count = sum(1 for f in findings if f.severity == "required")
    recommended_count = sum(1 for f in findings if f.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    total_files = len(seen_files)
    summary = (
        f"Scanned {total_files} file(s); found {required_count} import direction violation(s)."
        if required_count
        else f"All {total_files} file(s) respect the layer dependency rules."
    )

    return AnalysisReportDto(
        analysis="validate_import_directions",
        total_items=total_files,
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
