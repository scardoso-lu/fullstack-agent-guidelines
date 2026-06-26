from __future__ import annotations

import re

from validate_cli._models import AnalysisReportDto, FindingDto

_CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|chore|refactor|test|ci|perf|build|style|revert)"
    r"(\([^)]+\))?"
    r"(!)?"
    r": .+"
)
_MAX_SUBJECT_LEN = 72
_SKIP_RE = re.compile(r"^(Merge |Revert \")")


def validate_commit_messages(git_log: str) -> AnalysisReportDto:
    if not git_log.strip():
        raise ValueError(
            'git_log is empty — run: git log --format="%H %s" origin/main..HEAD'
        )

    raw_commits = [line.strip() for line in git_log.splitlines() if line.strip()]
    findings: list[FindingDto] = []
    checked = 0

    for raw in raw_commits:
        parts = raw.split(" ", 1)
        commit_hash = parts[0][:8]
        subject = parts[1] if len(parts) > 1 else ""

        if _SKIP_RE.match(subject):
            continue
        checked += 1

        if not _CONVENTIONAL_RE.match(subject):
            findings.append(FindingDto(
                rule_id="agile/commits/conventional-format",
                severity="required",
                location=commit_hash,
                message=f"Subject does not follow Conventional Commits: {subject!r}",
                hint=(
                    "Use: type(scope)?: description — "
                    "e.g. feat(auth): add JWT refresh token endpoint"
                ),
            ))

        if len(subject) > _MAX_SUBJECT_LEN:
            findings.append(FindingDto(
                rule_id="agile/commits/subject-length",
                severity="recommended",
                location=commit_hash,
                message=f"Subject is {len(subject)} chars (max {_MAX_SUBJECT_LEN}): {subject!r}",
                hint=(
                    f"Keep the subject line ≤{_MAX_SUBJECT_LEN} characters; "
                    "move details to the commit body."
                ),
            ))

    required_count = sum(1 for f in findings if f.severity == "required")
    recommended_count = sum(1 for f in findings if f.severity == "recommended")
    status = "violations" if required_count else ("warnings" if recommended_count else "clean")
    summary = (
        f"Checked {checked} commit(s); "
        f"found {required_count} format violation(s) and {recommended_count} recommendation(s)."
        if findings
        else f"All {checked} commit(s) follow the Conventional Commits format."
    )

    return AnalysisReportDto(
        analysis="validate_commit_messages",
        total_items=checked,
        findings=findings,
        required_count=required_count,
        recommended_count=recommended_count,
        status=status,
        summary=summary,
    )
