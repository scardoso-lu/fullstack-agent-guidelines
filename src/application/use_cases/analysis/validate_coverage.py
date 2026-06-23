from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict

from src.application.dto.analysis_dto import AnalysisReportDto, FindingDto
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_coverage_distribution")

_THRESHOLDS: dict[str, float] = {
    "domain": 90.0,
    "application": 85.0,
    "infrastructure": 65.0,
    "presentation": 55.0,
}


def _package_layer(name: str) -> str | None:
    """Extract the Clean Architecture layer from a Cobertura package name."""
    # Package names may be dotted ("src.domain.entities") or path-like ("src/domain/entities")
    parts = name.replace("/", ".").split(".")
    start = 1 if parts and parts[0] == "src" else 0
    layer = parts[start] if start < len(parts) else None
    return layer if layer in _THRESHOLDS else None


class ValidateCoverageDistributionUseCase:
    async def execute(self, cobertura_xml: str) -> AnalysisReportDto:
        if not cobertura_xml.strip():
            raise ValueError(
                "cobertura_xml is empty — generate it with: "
                "pytest --cov=src --cov-report=xml  then pass the content of coverage.xml"
            )

        try:
            root = ET.fromstring(cobertura_xml)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid XML: {exc}") from exc

        layer_valid: dict[str, int] = defaultdict(int)
        layer_covered: dict[str, int] = defaultdict(int)

        for pkg in root.iter("package"):
            name = pkg.get("name", "")
            layer = _package_layer(name)
            if layer is None:
                continue
            # coverage.py's Cobertura format puts line-rate (a ratio) on <package>,
            # not lines-valid/lines-covered.  Sum from individual <line hits="N"> elements.
            for line in pkg.iter("line"):
                layer_valid[layer] += 1
                if int(line.get("hits", "0")) > 0:
                    layer_covered[layer] += 1

        total_packages = sum(1 for _ in root.iter("package"))
        findings: list[FindingDto] = []

        for layer, threshold in _THRESHOLDS.items():
            valid = layer_valid.get(layer, 0)
            if valid == 0:
                continue  # no data for this layer — skip rather than false-positive
            covered = layer_covered.get(layer, 0)
            pct = (covered / valid) * 100

            if pct < threshold:
                findings.append(FindingDto(
                    rule_id=f"qa/coverage/{layer}-below-threshold",
                    severity="required",
                    location=f"layer:{layer}",
                    message=(
                        f"{layer.capitalize()} layer coverage is {pct:.1f}% "
                        f"(threshold: {threshold:.0f}%)"
                    ),
                    hint=(
                        f"Add tests for {layer} to reach {threshold:.0f}%. "
                        f"Currently {covered}/{valid} lines covered."
                    ),
                ))

        required_count = len(findings)

        status = "violations" if required_count > 0 else "clean"

        summary = (
            f"{required_count} layer(s) below threshold across {total_packages} package(s)."
            if findings
            else f"All tracked layers meet coverage thresholds ({total_packages} package(s) analysed)."
        )

        _logger.info(
            "validate_coverage packages=%d findings=%d status=%r",
            total_packages,
            len(findings),
            status,
        )

        return AnalysisReportDto(
            analysis="validate_coverage_distribution",
            total_items=total_packages,
            findings=findings,
            required_count=required_count,
            recommended_count=0,
            status=status,
            summary=summary,
        )
