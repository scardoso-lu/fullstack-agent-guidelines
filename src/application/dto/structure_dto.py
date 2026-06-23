from src.application.dto import BaseSchema


class StructureViolationDto(BaseSchema):
    rule_id: str
    severity: str
    file_path: str
    message: str
    hint: str
    guideline_slug: str | None = None


class StructureReportDto(BaseSchema):
    stack: str
    total_files: int
    violations: list[StructureViolationDto]
    required_violations: int
    recommended_violations: int
    status: str  # "compliant" | "warnings" | "non-compliant"
    summary: str
