import re

from src.application.dto.compliance_dto import ComplianceTableValidationDto
from src.infrastructure.repositories.contract import CriteriaRepositoryInterface
from src.utils.logger import get_logger

_logger = get_logger("use_case.validate_compliance_table")

_TABLE_START = "<!-- compliance-table-start -->"
_TABLE_END = "<!-- compliance-table-end -->"
_REQUIRED_HEADING = "## 📋 Guidelines Compliance Report"
_SCORE_RE = re.compile(r"\|\s*(?:\d{1,3}%|—|-)\s*\|")


class ValidateComplianceTableUseCase:
    def __init__(self, repo: CriteriaRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, content: str) -> ComplianceTableValidationDto:
        all_criteria = await self.repo.get_all()
        required_stacks = sorted({c.stack for c in all_criteria})

        errors: list[str] = []

        if _TABLE_START not in content:
            errors.append(f"Missing start marker: `{_TABLE_START}`")
            _logger.info("validate_compliance_table valid=False errors=%d", len(errors))
            return ComplianceTableValidationDto(valid=False, errors=errors)

        if _TABLE_END not in content:
            errors.append(f"Missing end marker: `{_TABLE_END}`")

        start = content.index(_TABLE_START) + len(_TABLE_START)
        end = content.index(_TABLE_END) if _TABLE_END in content else len(content)
        body = content[start:end]

        if _REQUIRED_HEADING not in body:
            errors.append(f"Missing required heading: `{_REQUIRED_HEADING}`")

        # Extract only the summary table rows (Stack header → "---" divider or end of body)
        # so that detail-section rows cannot mask a missing summary entry.
        summary_match = re.search(
            r"(\| Stack \|.*?)(?:\n---|\Z)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        summary_section = summary_match.group(1) if summary_match else ""

        if not summary_section:
            errors.append("Summary table is missing a `Stack` column header row")

        for stack in required_stacks:
            pattern = re.compile(
                r"\|\s*(?:[^\|]*\s+)?(?:\*\*)?("
                + re.escape(stack)
                + r")(?:\*\*)?\s*\|",
                re.IGNORECASE,
            )
            if not pattern.search(summary_section):
                errors.append(f"Stack `{stack}` is not listed in the summary table")

        if not _SCORE_RE.search(body):
            errors.append("No score column found (expected cells containing `N%` or `—`)")

        valid = len(errors) == 0
        _logger.info("validate_compliance_table valid=%r errors=%d", valid, len(errors))
        return ComplianceTableValidationDto(valid=valid, errors=errors)
