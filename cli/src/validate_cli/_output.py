from __future__ import annotations

import json
import sys

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from validate_cli._models import AnalysisReportDto

_console = Console()
_err = Console(stderr=True)

_STATUS_COLOR = {
    "clean": "green",
    "warnings": "yellow",
    "violations": "red",
}


def print_error(message: str) -> None:
    _err.print(f"[red]Error:[/red] {message}")


def output_report(report: AnalysisReportDto, as_json: bool, strict: bool) -> None:
    if as_json:
        _print_json(report)
    else:
        _print_rich(report)

    if report.status == "violations":
        sys.exit(2)
    if strict and report.status == "warnings":
        sys.exit(1)


def _print_json(report: AnalysisReportDto) -> None:
    data = {
        "analysis": report.analysis,
        "total_items": report.total_items,
        "status": report.status,
        "summary": report.summary,
        "required_count": report.required_count,
        "recommended_count": report.recommended_count,
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "location": f.location,
                "message": f.message,
                "hint": f.hint,
            }
            for f in report.findings
        ],
    }
    print(json.dumps(data, indent=2))


def _print_rich(report: AnalysisReportDto) -> None:
    color = _STATUS_COLOR.get(report.status, "white")
    _console.print()
    _console.print(
        f"[bold]{report.analysis}[/bold]  "
        f"[{color}]{report.status.upper()}[/{color}]  "
        f"({report.required_count} required, {report.recommended_count} recommended)"
    )
    _console.print(f"[dim]{report.summary}[/dim]")

    if not report.findings:
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Sev", min_width=9)
    table.add_column("Location", min_width=22, no_wrap=True)
    table.add_column("Message")
    table.add_column("Rule", style="dim", min_width=30)

    for f in report.findings:
        sev_style = "red bold" if f.severity == "required" else "yellow"
        table.add_row(
            Text(f.severity, style=sev_style),
            Text(f.location, overflow="fold"),
            f.message,
            f.rule_id,
        )

    _console.print(table)

    seen: set[str] = set()
    hints_printed = False
    for f in report.findings:
        if f.rule_id in seen:
            continue
        seen.add(f.rule_id)
        if not hints_printed:
            _console.print("[bold]Hints[/bold]")
            hints_printed = True
        _console.print(f"  [dim]{f.rule_id}[/dim]")
        _console.print(f"  {f.hint}")
        _console.print()
