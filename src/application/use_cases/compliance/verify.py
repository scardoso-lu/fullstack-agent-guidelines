import re

from src.application.dto.compliance_dto import (
    AssessmentInputDto,
    ComplianceReportDto,
    CriterionResultDto,
    StackReportDto,
)
from src.domain.entities.compliance import ComplianceCriterion
from src.infrastructure.repositories.contract import CriteriaRepositoryInterface
from src.utils.logger import get_logger

_logger = get_logger("use_case.verify_compliance")


def _evaluate_command(criterion: ComplianceCriterion, output: str) -> tuple[bool, str]:
    if criterion.fail_pattern and re.search(criterion.fail_pattern, output, re.MULTILINE):
        match = re.search(criterion.fail_pattern, output, re.MULTILINE)
        return False, f"fail_pattern matched: {match.group(0)!r}"  # type: ignore[union-attr]
    if criterion.pass_pattern and re.search(criterion.pass_pattern, output, re.MULTILINE):
        match = re.search(criterion.pass_pattern, output, re.MULTILINE)
        return True, f"pass_pattern matched: {match.group(0)!r}"  # type: ignore[union-attr]
    return False, "output did not match pass_pattern"


def _evaluate_code_pattern(criterion: ComplianceCriterion, snippet: str) -> tuple[bool, str]:
    if criterion.forbidden_pattern:
        match = re.search(criterion.forbidden_pattern, snippet, re.MULTILINE)
        if match:
            return False, f"forbidden_pattern found: {match.group(0)!r}"
    if criterion.required_pattern:
        match = re.search(criterion.required_pattern, snippet, re.MULTILINE)
        if match:
            return True, f"required_pattern found: {match.group(0)!r}"
        return False, "required_pattern not found in snippet"
    # only forbidden_pattern defined and nothing matched → pass
    return True, "no forbidden pattern found"


def _compute_status(score: float, has_required_failure: bool) -> str:
    if has_required_failure or score < 0.5:
        return "non-compliant"
    if score >= 0.9:
        return "compliant"
    return "partial"


class VerifyComplianceUseCase:
    def __init__(self, repo: CriteriaRepositoryInterface) -> None:
        self.repo = repo

    async def execute(
        self,
        assessments: list[AssessmentInputDto],
        stacks: list[str] | None = None,
    ) -> ComplianceReportDto:
        if not assessments:
            raise ValueError("assessments cannot be empty")

        all_criteria = await self.repo.get_all()
        criteria_by_id: dict[str, ComplianceCriterion] = {c.id: c for c in all_criteria}

        results_by_stack: dict[str, list[CriterionResultDto]] = {}
        unknown_ids: list[str] = []

        for assessment in assessments:
            criterion = criteria_by_id.get(assessment.criterion_id)
            if criterion is None:
                _logger.warning("unknown criterion_id=%r", assessment.criterion_id)
                unknown_ids.append(assessment.criterion_id)
                continue

            if stacks is not None and criterion.stack not in stacks:
                continue

            passed, reason, validation = self._evaluate(criterion, assessment)

            result = CriterionResultDto(
                criterion_id=criterion.id,
                text=criterion.text,
                category=criterion.category,
                severity=criterion.severity,
                passed=passed,
                validation=validation,
                reason=reason,
            )
            results_by_stack.setdefault(criterion.stack, []).append(result)

        stack_reports: dict[str, StackReportDto] = {}
        for stack, results in results_by_stack.items():
            passed_count = sum(1 for r in results if r.passed)
            failed_count = sum(1 for r in results if not r.passed)
            total = passed_count + failed_count
            score = passed_count / total if total > 0 else 0.0
            has_required_failure = any(
                not r.passed and r.severity == "required" for r in results
            )
            stack_reports[stack] = StackReportDto(
                stack=stack,
                score=round(score, 4),
                status=_compute_status(score, has_required_failure),
                passed=passed_count,
                failed=failed_count,
                results=results,
            )

        if not stack_reports:
            overall_score = 0.0
            overall_status = "non-compliant"
        else:
            total_criteria = sum(r.passed + r.failed for r in stack_reports.values())
            total_passed = sum(r.passed for r in stack_reports.values())
            overall_score = round(total_passed / total_criteria, 4) if total_criteria else 0.0
            statuses = [r.status for r in stack_reports.values()]
            if "non-compliant" in statuses:
                overall_status = "non-compliant"
            elif "partial" in statuses:
                overall_status = "partial"
            else:
                overall_status = "compliant"

        _logger.info(
            "verify_compliance overall_score=%.4f overall_status=%r stacks=%r unknown=%d",
            overall_score,
            overall_status,
            list(stack_reports.keys()),
            len(unknown_ids),
        )

        return ComplianceReportDto(
            overall_score=overall_score,
            overall_status=overall_status,
            stacks=stack_reports,
            unknown_ids=unknown_ids,
        )

    @staticmethod
    def _evaluate(
        criterion: ComplianceCriterion,
        assessment: AssessmentInputDto,
    ) -> tuple[bool, str, str]:
        if criterion.check_type == "command":
            output = assessment.command_output or ""
            passed, reason = _evaluate_command(criterion, output)
            return passed, reason, "automated"

        if criterion.check_type == "code_pattern":
            snippet = assessment.code_snippet or ""
            passed, reason = _evaluate_code_pattern(criterion, snippet)
            return passed, reason, "automated"

        # manual
        if not assessment.evidence:
            return False, "manual check requires non-empty evidence", "manual"
        passed = bool(assessment.passed)
        return passed, assessment.evidence, "manual"
