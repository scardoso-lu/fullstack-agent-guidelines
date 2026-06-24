import re
from datetime import datetime, timezone

from src.application.dto.compliance_dto import ComplianceTableDto
from src.domain.entities.compliance import ComplianceCriterion
from src.infrastructure.repositories.contract import CriteriaRepositoryInterface
from src.utils.logger import get_logger

_logger = get_logger("use_case.generate_compliance_table")

_TABLE_START = "<!-- compliance-table-start -->"
_TABLE_END = "<!-- compliance-table-end -->"

_STACK_ICONS: dict[str, str] = {
    "backend": "🐍",
    "frontend": "🖥️",
    "agile": "🔄",
    "security": "🔒",
    "structure": "🏗️",
    "qa": "🧪",
    "infra": "⚙️",
    "architecture": "📐",
}

_STATUS_ICON: dict[str, str] = {
    "pass": "✅",
    "fail": "❌",
    "pending": "⏳",
    "manual": "👤",
}

_STACK_ORDER = [
    "backend", "frontend", "agile", "security",
    "structure", "qa", "infra", "architecture",
]


def _eval_command(criterion: ComplianceCriterion, output: str) -> tuple[str, str]:
    if not output or not output.strip():
        return "pending", "no command output provided"
    if criterion.fail_pattern and re.search(criterion.fail_pattern, output, re.MULTILINE):
        m = re.search(criterion.fail_pattern, output, re.MULTILINE)
        return "fail", f"fail pattern matched: `{m.group(0)[:80]}`"  # type: ignore[union-attr]
    if criterion.pass_pattern:
        m = re.search(criterion.pass_pattern, output)
        if m:
            return "pass", f"pass pattern matched: `{m.group(0)[:80]}`"
    return "fail", "output did not match pass pattern"


def _eval_code_pattern(criterion: ComplianceCriterion, snippet: str) -> tuple[str, str]:
    if not snippet or not snippet.strip():
        return "pending", "no code snippet provided"
    if criterion.forbidden_pattern:
        m = re.search(criterion.forbidden_pattern, snippet, re.MULTILINE)
        if m:
            return "fail", f"forbidden pattern found: `{m.group(0)[:80]}`"
    if criterion.required_pattern:
        m = re.search(criterion.required_pattern, snippet, re.MULTILINE)
        if m:
            return "pass", f"required pattern found: `{m.group(0)[:80]}`"
        return "fail", "required pattern not found in snippet"
    return "pass", "no forbidden pattern found"


def _evaluate(criterion: ComplianceCriterion, assessment: dict) -> tuple[str, str]:
    if criterion.check_type == "command":
        return _eval_command(criterion, assessment.get("command_output", ""))
    if criterion.check_type == "code_pattern":
        return _eval_code_pattern(criterion, assessment.get("code_snippet", ""))
    # manual
    if not assessment.get("evidence"):
        return "manual", "awaiting human review"
    passed = bool(assessment.get("passed", False))
    evidence = str(assessment.get("evidence", ""))[:100]
    return ("pass" if passed else "fail"), evidence


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


class GenerateComplianceTableUseCase:
    def __init__(self, repo: CriteriaRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, assessments: list[dict]) -> ComplianceTableDto:
        all_criteria = await self.repo.get_all()
        assessments_by_id = {
            a["criterion_id"]: a for a in assessments if "criterion_id" in a
        }

        by_stack: dict[str, list[tuple[ComplianceCriterion, str, str]]] = {
            s: [] for s in _STACK_ORDER
        }
        for criterion in all_criteria:
            if criterion.stack not in by_stack:
                by_stack[criterion.stack] = []
            assessment = assessments_by_id.get(criterion.id, {})
            if criterion.check_type == "manual" and not assessment:
                status, reason = "manual", "awaiting human review"
            else:
                status, reason = _evaluate(criterion, assessment)
            by_stack[criterion.stack].append((criterion, status, reason))

        stack_stats: dict[str, dict[str, int]] = {}
        for stack, rows in by_stack.items():
            stats: dict[str, int] = {
                "pass": 0, "fail": 0, "pending": 0, "manual": 0, "total": len(rows),
            }
            for _, status, _ in rows:
                stats[status] = stats.get(status, 0) + 1
            stack_stats[stack] = stats

        total_pass = sum(s["pass"] for s in stack_stats.values())
        total_assessed = sum(s["pass"] + s["fail"] for s in stack_stats.values())
        total_criteria = sum(s["total"] for s in stack_stats.values())

        if total_assessed > 0:
            score_pct = round(total_pass / total_assessed * 100)
            icon = "✅" if score_pct >= 90 else ("⚠️" if score_pct >= 50 else "❌")
            overall_line = (
                f"{icon} **{score_pct}%** "
                f"({total_pass}/{total_assessed} assessed, {total_criteria} total)"
            )
        else:
            overall_line = f"⏳ **Pending** — {total_criteria} criteria awaiting assessment"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines: list[str] = [
            _TABLE_START,
            "## 📋 Guidelines Compliance Report",
            "",
            f"> Generated: {now} &nbsp;·&nbsp; {total_criteria} criteria across {len(by_stack)} stacks",
            "",
            f"### Overall: {overall_line}",
            "",
            "| Stack | Total | ✅ Pass | ❌ Fail | ⏳ Pending | 👤 Manual | Score |",
            "|-------|------:|-------:|-------:|----------:|----------:|------:|",
        ]

        for stack in _STACK_ORDER:
            s = stack_stats[stack]
            assessed = s["pass"] + s["fail"]
            score_cell = f"{round(s['pass'] / assessed * 100)}%" if assessed > 0 else "—"
            icon = _STACK_ICONS.get(stack, "📦")
            lines.append(
                f"| {icon} **{stack}** | {s['total']} | {s['pass']} | {s['fail']}"
                f" | {s['pending']} | {s['manual']} | {score_cell} |"
            )

        lines += ["", "---", ""]

        for stack in _STACK_ORDER:
            rows = by_stack[stack]
            s = stack_stats[stack]
            assessed = s["pass"] + s["fail"]
            score_label = f"{round(s['pass'] / assessed * 100)}%" if assessed > 0 else "pending"
            icon = _STACK_ICONS.get(stack, "📦")

            lines.append("<details>")
            lines.append(
                f"<summary>{icon} <b>{stack.capitalize()}</b> — "
                f"{s['pass']}/{s['total']} criteria ({score_label})</summary>"
            )
            lines += [
                "",
                "| # | Criterion | Category | Severity | Type | Status | Details |",
                "|--:|-----------|----------|----------|------|:------:|---------|",
            ]

            for i, (criterion, status, reason) in enumerate(rows, 1):
                sev = "🔴 req" if criterion.severity == "required" else "🟡 rec"
                status_cell = f"{_STATUS_ICON.get(status, '⏳')} {status}"
                lines.append(
                    f"| {i} | {_truncate(criterion.text, 70)} "
                    f"| {criterion.category} | {sev} | {criterion.check_type} "
                    f"| {status_cell} | {_truncate(reason, 80)} |"
                )

            lines += ["", "</details>", ""]

        lines.append(_TABLE_END)
        table = "\n".join(lines)

        _logger.info(
            "generate_compliance_table total_criteria=%d total_pass=%d total_assessed=%d",
            total_criteria,
            total_pass,
            total_assessed,
        )
        return ComplianceTableDto(table=table)
