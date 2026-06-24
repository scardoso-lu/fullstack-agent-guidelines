#!/usr/bin/env python3
"""
Generate a PR compliance table from the repository's criteria definitions.

Usage:
    # No assessments — all automated criteria shown as pending:
    python scripts/generate_compliance_table.py

    # With a JSON file of assessed criteria:
    python scripts/generate_compliance_table.py /path/to/assessments.json

Assessments JSON format — a list of objects, one per criterion:
    [
      {"criterion_id": "backend/dod/lint-clean", "command_output": "All checks passed."},
      {"criterion_id": "backend/dod/auth-on-routes", "code_snippet": "..."},
      {"criterion_id": "backend/dod/integration-testcontainers", "passed": true, "evidence": "conftest.py L12"}
    ]

Output: a Markdown document bounded by compliance-table-start/end HTML comments,
suitable for posting as a GitHub PR comment.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.entities.compliance import ComplianceCriterion
from src.infrastructure.criteria import ALL_CRITERIA

# ── Constants ────────────────────────────────────────────────────────────────

TABLE_START = "<!-- compliance-table-start -->"
TABLE_END = "<!-- compliance-table-end -->"

STACK_ICONS: dict[str, str] = {
    "backend": "🐍",
    "frontend": "🖥️",
    "agile": "🔄",
    "security": "🔒",
    "structure": "🏗️",
    "qa": "🧪",
    "infra": "⚙️",
    "architecture": "📐",
}

STATUS_ICON: dict[str, str] = {
    "pass": "✅",
    "fail": "❌",
    "pending": "⏳",
    "manual": "👤",
}

# Stack display order (same as ALL_CRITERIA declaration order)
STACK_ORDER = ["backend", "frontend", "agile", "security", "structure", "qa", "infra", "architecture"]


# ── Criterion evaluation (mirrors VerifyComplianceUseCase logic) ─────────────

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
    """Return (status, reason) where status is 'pass'|'fail'|'pending'|'manual'."""
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


# ── Markdown generation ──────────────────────────────────────────────────────

def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def generate_table(assessments: dict[str, dict]) -> str:
    # Evaluate every criterion
    by_stack: dict[str, list[tuple[ComplianceCriterion, str, str]]] = {s: [] for s in STACK_ORDER}
    for criterion in ALL_CRITERIA:
        if criterion.stack not in by_stack:
            by_stack[criterion.stack] = []
        assessment = assessments.get(criterion.id, {})
        if criterion.check_type == "manual" and not assessment:
            status, reason = "manual", "awaiting human review"
        else:
            status, reason = _evaluate(criterion, assessment)
        by_stack[criterion.stack].append((criterion, status, reason))

    # Compute per-stack stats
    stack_stats: dict[str, dict[str, int]] = {}
    for stack, rows in by_stack.items():
        stats: dict[str, int] = {"pass": 0, "fail": 0, "pending": 0, "manual": 0, "total": len(rows)}
        for _, status, _ in rows:
            stats[status] = stats.get(status, 0) + 1
        stack_stats[stack] = stats

    # Overall score (assessed = pass + fail only)
    total_pass = sum(s["pass"] for s in stack_stats.values())
    total_assessed = sum(s["pass"] + s["fail"] for s in stack_stats.values())
    total_criteria = sum(s["total"] for s in stack_stats.values())

    if total_assessed > 0:
        score_pct = round(total_pass / total_assessed * 100)
        overall_icon = "✅" if score_pct >= 90 else ("⚠️" if score_pct >= 50 else "❌")
        overall_line = f"{overall_icon} **{score_pct}%** ({total_pass}/{total_assessed} assessed, {total_criteria} total)"
    else:
        overall_line = f"⏳ **Pending** — {total_criteria} criteria awaiting assessment"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        TABLE_START,
        "## 📋 Guidelines Compliance Report",
        "",
        f"> Generated: {now} &nbsp;·&nbsp; {total_criteria} criteria across {len(by_stack)} stacks",
        "",
        f"### Overall: {overall_line}",
        "",
    ]

    # Summary table
    lines += [
        "| Stack | Total | ✅ Pass | ❌ Fail | ⏳ Pending | 👤 Manual | Score |",
        "|-------|------:|-------:|-------:|----------:|----------:|------:|",
    ]
    for stack in STACK_ORDER:
        s = stack_stats[stack]
        assessed = s["pass"] + s["fail"]
        score_cell = f"{round(s['pass'] / assessed * 100)}%" if assessed > 0 else "—"
        icon = STACK_ICONS.get(stack, "📦")
        lines.append(
            f"| {icon} **{stack}** | {s['total']} | {s['pass']} | {s['fail']}"
            f" | {s['pending']} | {s['manual']} | {score_cell} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed collapsible sections per stack
    for stack in STACK_ORDER:
        rows = by_stack[stack]
        s = stack_stats[stack]
        assessed = s["pass"] + s["fail"]
        score_label = f"{round(s['pass'] / assessed * 100)}%" if assessed > 0 else "pending"
        icon = STACK_ICONS.get(stack, "📦")

        lines.append("<details>")
        lines.append(
            f"<summary>{icon} <b>{stack.capitalize()}</b> — "
            f"{s['pass']}/{s['total']} criteria ({score_label})</summary>"
        )
        lines.append("")
        lines.append("| # | Criterion | Category | Severity | Type | Status | Details |")
        lines.append("|--:|-----------|----------|----------|------|:------:|---------|")

        for i, (criterion, status, reason) in enumerate(rows, 1):
            sev = "🔴 req" if criterion.severity == "required" else "🟡 rec"
            status_cell = f"{STATUS_ICON.get(status, '⏳')} {status}"
            lines.append(
                f"| {i} | {_truncate(criterion.text, 70)} "
                f"| {criterion.category} | {sev} | {criterion.check_type} "
                f"| {status_cell} | {_truncate(reason, 80)} |"
            )

        lines += ["", "</details>", ""]

    lines.append(TABLE_END)
    return "\n".join(lines)


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    assessments: dict[str, dict] = {}

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as fh:
            raw: list[dict] = json.load(fh)
        assessments = {item["criterion_id"]: item for item in raw if "criterion_id" in item}
    elif not sys.stdin.isatty():
        try:
            raw = json.load(sys.stdin)
            assessments = {item["criterion_id"]: item for item in raw if "criterion_id" in item}
        except (json.JSONDecodeError, ValueError):
            pass  # empty or invalid stdin — proceed with no assessments

    print(generate_table(assessments))


if __name__ == "__main__":
    main()
