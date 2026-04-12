"""
Network Auditor CLI
===================
Entry point for the automated network auditing tool.

Usage examples:

    # Simulate audit (no real SSH connections):
    python -m cli.main audit

    # Audit specific devices:
    python -m cli.main audit --device R1 --device SW1

    # Audit by tag:
    python -m cli.main audit --tag critical

    # Save JSON report:
    python -m cli.main audit --output report.json

    # Commission a new device:
    python -m cli.main commission --device R1 --template cisco_ios

    # Show inventory:
    python -m cli.main inventory
"""
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from auditor.inventory import DeviceInventory
from auditor.rules import RuleSet
from auditor.core import AuditEngine
from scripts.python.commission import commission_device

BASE_DIR = Path(__file__).parent.parent
DEVICES_YAML = BASE_DIR / "config" / "devices.yaml"
RULES_YAML = BASE_DIR / "config" / "audit_rules.yaml"
TEMPLATES_DIR = BASE_DIR / "config" / "templates"

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_time=False)],
    )


# ─── CLI Group ────────────────────────────────────────────────────────────────

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Automated Network Auditor — compliance checks across your device fleet."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# ─── audit ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--device", "-d", multiple=True, metavar="NAME",
    help="Audit only these device(s). Can be repeated.",
)
@click.option(
    "--tag", "-t", default=None, metavar="TAG",
    help="Audit devices with this tag only.",
)
@click.option(
    "--output", "-o", default=None, metavar="FILE",
    help="Save JSON report to FILE.",
)
@click.option(
    "--simulate/--no-simulate", default=True,
    help="Use simulated SSH output (default: True).",
)
@click.option(
    "--workers", "-w", default=5, show_default=True,
    help="Thread-pool size for concurrent device auditing.",
)
@click.option(
    "--detail/--no-detail", default=True,
    help="Print per-device rule detail tables.",
)
@click.pass_context
def audit(
    ctx: click.Context,
    device: tuple[str, ...],
    tag: str | None,
    output: str | None,
    simulate: bool,
    workers: int,
    detail: bool,
) -> None:
    """Run compliance audit across all (or filtered) devices."""
    console.rule("[bold cyan]Network Audit[/bold cyan]")

    try:
        inventory = DeviceInventory(DEVICES_YAML)
        rule_set = RuleSet(RULES_YAML)
    except FileNotFoundError as exc:
        console.print(f"[red]ERROR:[/red] {exc}")
        sys.exit(1)

    # Override simulate flag from CLI
    if not simulate:
        for d in inventory.get_all():
            d.simulate = False

    engine = AuditEngine(inventory, rule_set, max_workers=workers)
    reporter = engine.run(
        device_filter=list(device) or None,
        tag_filter=tag,
    )

    if detail:
        for report in reporter._reports:
            reporter.print_device_detail(report)

    reporter.print_summary()

    if output:
        reporter.save_json(output)

    # Exit non-zero if any device failed
    any_failed = any(r.status == "FAIL" for r in reporter._reports)
    sys.exit(1 if any_failed else 0)


# ─── commission ───────────────────────────────────────────────────────────────

@cli.command()
@click.option("--device", "-d", required=True, metavar="NAME", help="Device name from inventory.")
@click.option(
    "--template", "-t",
    type=click.Choice(["cisco_ios", "cisco_asa", "cisco_nxos", "linux"], case_sensitive=False),
    required=True, help="Baseline template to render and push.",
)
@click.option("--dry-run", is_flag=True, help="Render template only; do not push to device.")
@click.pass_context
def commission(ctx: click.Context, device: str, template: str, dry_run: bool) -> None:
    """Commission a device by pushing a rendered baseline config."""
    console.rule("[bold cyan]Device Commissioning[/bold cyan]")
    try:
        inventory = DeviceInventory(DEVICES_YAML)
    except FileNotFoundError as exc:
        console.print(f"[red]ERROR:[/red] {exc}")
        sys.exit(1)

    dev = inventory.get_by_name(device)
    if dev is None:
        console.print(f"[red]ERROR:[/red] Device '{device}' not found in inventory.")
        sys.exit(1)

    result = commission_device(
        device=dev,
        template_name=f"{template}_baseline.j2",
        templates_dir=TEMPLATES_DIR,
        dry_run=dry_run,
    )
    if result["success"]:
        console.print(f"[green]✓ {device} commissioned successfully.[/green]")
    else:
        console.print(f"[red]✗ Commissioning failed: {result.get('error')}[/red]")
        sys.exit(1)


# ─── inventory ────────────────────────────────────────────────────────────────

@cli.command(name="inventory")
@click.option("--tag", "-t", default=None, help="Filter by tag.")
@click.pass_context
def show_inventory(ctx: click.Context, tag: str | None) -> None:
    """List all devices in the inventory."""
    from rich.table import Table
    from rich import box

    try:
        inventory = DeviceInventory(DEVICES_YAML)
    except FileNotFoundError as exc:
        console.print(f"[red]ERROR:[/red] {exc}")
        sys.exit(1)

    devices = inventory.get_by_tag(tag) if tag else inventory.get_all()

    table = Table(title="Device Inventory", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("Name", style="bold")
    table.add_column("Host")
    table.add_column("Type")
    table.add_column("Role")
    table.add_column("Location")
    table.add_column("Tags")
    table.add_column("Simulate")

    for d in devices:
        table.add_row(
            d.name, d.host, d.device_type, d.role, d.location,
            ", ".join(d.tags),
            "[yellow]yes[/yellow]" if d.simulate else "[red]no[/red]",
        )

    console.print(table)
    console.print(f"[dim]{len(devices)} device(s) shown.[/dim]")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli(obj={})
