#!/usr/bin/env python3
"""
Validate that a compliance table is present and correctly formatted.

Usage:
    python scripts/validate_compliance_table.py <file>
    python scripts/validate_compliance_table.py < table.md   # from stdin

Exit codes:
    0 — table present and valid
    1 — table missing or malformed (errors printed to stderr)

The validator checks:
  1. Start marker  <!-- compliance-table-start -->  is present.
  2. End marker    <!-- compliance-table-end -->    is present.
  3. The required heading exists inside the markers.
  4. The summary table lists every stack defined in the criteria.
  5. Every stack row contains a numeric score column.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.criteria import ALL_CRITERIA

# ── Constants ────────────────────────────────────────────────────────────────

TABLE_START = "<!-- compliance-table-start -->"
TABLE_END = "<!-- compliance-table-end -->"
REQUIRED_HEADING = "## 📋 Guidelines Compliance Report"
REQUIRED_STACKS = sorted({c.stack for c in ALL_CRITERIA})

# A summary table row looks like: | icon **stack** | digits | ... | score |
# We match the stack name anywhere between pipes to be lenient about icons/bold.
_STACK_ROW_RE = re.compile(r"\|\s*(?:[^\|]*\s+)?(?:\*\*)?({stack})(?:\*\*)?\s*\|", re.IGNORECASE)

# Score column: a cell with a percentage like "87%" or an em-dash "—"
_SCORE_RE = re.compile(r"\|\s*(?:\d{1,3}%|—|-)\s*\|")


# ── Validation logic ─────────────────────────────────────────────────────────

def validate(content: str) -> list[str]:
    """Return a list of human-readable error strings. Empty list means valid."""
    errors: list[str] = []

    if TABLE_START not in content:
        errors.append(f"Missing start marker: `{TABLE_START}`")
        return errors  # cannot safely extract body without the marker

    if TABLE_END not in content:
        errors.append(f"Missing end marker: `{TABLE_END}`")

    start = content.index(TABLE_START) + len(TABLE_START)
    end = content.index(TABLE_END) if TABLE_END in content else len(content)
    body = content[start:end]

    if REQUIRED_HEADING not in body:
        errors.append(f"Missing required heading: `{REQUIRED_HEADING}`")

    if "| Stack |" not in body and "| stack |" not in body.lower():
        errors.append("Summary table is missing a `Stack` column header row")

    for stack in REQUIRED_STACKS:
        pattern = re.compile(
            r"\|\s*(?:[^\|]*\s+)?(?:\*\*)?(" + re.escape(stack) + r")(?:\*\*)?\s*\|",
            re.IGNORECASE,
        )
        if not pattern.search(body):
            errors.append(f"Stack `{stack}` is not listed in the summary table")

    # At least one score cell must be present
    if not _SCORE_RE.search(body):
        errors.append("No score column found (expected cells containing `N%` or `—`)")

    return errors


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as fh:
            content = fh.read()
    else:
        content = sys.stdin.read()

    errors = validate(content)
    if errors:
        print("Compliance table validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  • {err}", file=sys.stderr)
        sys.exit(1)

    stack_count = len(REQUIRED_STACKS)
    print(f"Compliance table validation PASSED ({stack_count} stacks present)")


if __name__ == "__main__":
    main()
