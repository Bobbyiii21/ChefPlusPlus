"""
Audit Reporter
==============
Formats and outputs audit results using the Rich library.

Outputs:
  - Console: coloured table with pass/fail/skip per device
  - Summary panel: overall compliance score
  - JSON: machine-readable report dict
"""
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

logger = logging.getLogger(__name__)

_SEVERITY_COLOUR = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
}

_STATUS_COLOUR = {
    "PASS": "bold green",
    "FAIL": "bold red",
    "SKIP": "bold yellow",
}


@dataclass
class DeviceReport:
    device_name: str
    device_type: str
    host: str
    location: str
    role: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    audited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped

    @property
    def compliance_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.passed / self.total, 1)

    @property
    def status(self) -> str:
        if self.error:
            return "SKIP"
        return "PASS" if self.failed == 0 else "FAIL"

    def to_dict(self) -> dict:
        return {
            "device_name": self.device_name,
            "device_type": self.device_type,
            "host": self.host,
            "location": self.location,
            "role": self.role,
            "status": self.status,
            "compliance_pct": self.compliance_pct,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "error": self.error,
            "audited_at": self.audited_at,
            "results": self.results,
        }


class AuditReporter:
    """
    Collect DeviceReport objects and render them to Rich console output
    and/or JSON.

    Example::

        reporter = AuditReporter()
        reporter.add(device_report)
        reporter.print_summary()
        reporter.save_json("audit_report.json")
    """

    def __init__(self) -> None:
        self._reports: list[DeviceReport] = []
        self._console = Console()

    def add(self, report: DeviceReport) -> None:
        self._reports.append(report)

    # ── Rendering ──────────────────────────────────────────────────────────────

    def print_device_detail(self, report: DeviceReport) -> None:
        """Print per-rule results for a single device."""
        title = f"[bold]{report.device_name}[/bold]  [{report.device_type}]  {report.host}"
        table = Table(
            title=title,
            box=box.ROUNDED,
            show_lines=True,
            header_style="bold magenta",
        )
        table.add_column("Rule ID", style="dim", width=22)
        table.add_column("Name", width=30)
        table.add_column("Severity", width=10)
        table.add_column("Status", width=6)
        table.add_column("Message", overflow="fold")

        for r in report.results:
            status = "PASS" if r["passed"] else "FAIL"
            sev_colour = _SEVERITY_COLOUR.get(r["severity"], "white")
            status_colour = _STATUS_COLOUR.get(status, "white")
            table.add_row(
                r["rule_id"],
                r["rule_name"],
                Text(r["severity"].upper(), style=sev_colour),
                Text(status, style=status_colour),
                r.get("remediation", "") if not r["passed"] else "[green]OK[/green]",
            )

        self._console.print(table)

    def print_summary(self) -> None:
        """Print a summary table for all audited devices."""
        table = Table(
            title="[bold cyan]Audit Summary[/bold cyan]",
            box=box.DOUBLE_EDGE,
            header_style="bold white",
            show_lines=True,
        )
        table.add_column("Device", style="bold", width=10)
        table.add_column("Type", width=12)
        table.add_column("Location", width=16)
        table.add_column("Role", width=20)
        table.add_column("Pass", justify="right", width=6)
        table.add_column("Fail", justify="right", width=6)
        table.add_column("Skip", justify="right", width=6)
        table.add_column("Compliance", justify="right", width=11)
        table.add_column("Status", width=6)

        total_pass = total_fail = total_skip = 0

        for rpt in self._reports:
            status_colour = _STATUS_COLOUR.get(rpt.status, "white")
            compliance_colour = "green" if rpt.compliance_pct >= 90 else (
                "yellow" if rpt.compliance_pct >= 70 else "red"
            )
            table.add_row(
                rpt.device_name,
                rpt.device_type,
                rpt.location,
                rpt.role,
                str(rpt.passed),
                str(rpt.failed),
                str(rpt.skipped),
                Text(f"{rpt.compliance_pct:.1f}%", style=compliance_colour),
                Text(rpt.status, style=status_colour),
            )
            total_pass += rpt.passed
            total_fail += rpt.failed
            total_skip += rpt.skipped

        self._console.print(table)

        # Overall compliance score
        total_checks = total_pass + total_fail + total_skip
        overall_pct = round(100.0 * total_pass / total_checks, 1) if total_checks else 0.0
        colour = "green" if overall_pct >= 90 else ("yellow" if overall_pct >= 70 else "red")
        panel_text = (
            f"Devices audited: [bold]{len(self._reports)}[/bold]   "
            f"Checks: [bold]{total_checks}[/bold]   "
            f"Pass: [bold green]{total_pass}[/bold green]   "
            f"Fail: [bold red]{total_fail}[/bold red]   "
            f"Overall: [{colour}]{overall_pct:.1f}%[/{colour}]"
        )
        self._console.print(Panel(panel_text, title="[bold]Overall Compliance[/bold]", border_style=colour))

    # ── Export ─────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        total_pass = sum(r.passed for r in self._reports)
        total_fail = sum(r.failed for r in self._reports)
        total_skip = sum(r.skipped for r in self._reports)
        total = total_pass + total_fail + total_skip
        return {
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "devices_audited": len(self._reports),
            "overall_compliance_pct": round(100.0 * total_pass / total, 1) if total else 0.0,
            "totals": {"passed": total_pass, "failed": total_fail, "skipped": total_skip},
            "devices": [r.to_dict() for r in self._reports],
        }

    def save_json(self, path: str) -> None:
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        logger.info("Report saved → %s", path)
        self._console.print(f"[dim]Report saved to [bold]{path}[/bold][/dim]")
