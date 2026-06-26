from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FindingDto:
    rule_id: str
    severity: str    # "required" | "recommended"
    location: str    # "file:line", commit hash, "field:NAME", "layer:NAME", etc.
    message: str
    hint: str


@dataclass
class AnalysisReportDto:
    analysis: str
    total_items: int
    findings: list[FindingDto] = field(default_factory=list)
    required_count: int = 0
    recommended_count: int = 0
    status: str = "clean"   # "clean" | "warnings" | "violations"
    summary: str = ""
