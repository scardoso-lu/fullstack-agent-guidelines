from __future__ import annotations

from src.application.dto import BaseSchema


class FindingDto(BaseSchema):
    rule_id: str
    severity: str    # "required" | "recommended"
    location: str    # "file:line", commit hash, field name, etc.
    message: str
    hint: str


class AnalysisReportDto(BaseSchema):
    analysis: str        # tool identifier, e.g. "validate_import_directions"
    total_items: int     # files, commits, lines, etc.
    findings: list[FindingDto]
    required_count: int
    recommended_count: int
    status: str          # "clean" | "warnings" | "violations"
    summary: str
