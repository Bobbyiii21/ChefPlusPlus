"""
Device Commissioning Script
============================
Renders a Jinja2 baseline template for a device and optionally
pushes it via SSH.

Callable both as a library (from CLI) and as a standalone script.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

logger = logging.getLogger(__name__)


def _render_template(
    template_name: str,
    templates_dir: Path,
    context: dict[str, Any],
) -> str:
    """Render a Jinja2 template file and return the result string."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        undefined=StrictUndefined,  # Fail loudly on missing variables
        trim_blocks=True,
        lstrip_blocks=True,
    )
    try:
        tmpl = env.get_template(template_name)
    except TemplateNotFound:
        raise FileNotFoundError(
            f"Template '{template_name}' not found in {templates_dir}"
        )
    return tmpl.render(**context)


def commission_device(
    device: Any,
    template_name: str,
    templates_dir: Path,
    dry_run: bool = True,
    extra_vars: dict | None = None,
) -> dict[str, Any]:
    """
    Render the baseline template for *device* and (optionally) push it.

    Args:
        device:        Device dataclass from inventory.
        template_name: Filename inside templates_dir (e.g. "cisco_ios_baseline.j2").
        templates_dir: Path to the templates directory.
        dry_run:       If True, render only — do not push to device.
        extra_vars:    Additional template variables (override defaults).

    Returns:
        dict with keys: success (bool), rendered (str), error (str|None)
    """
    context: dict[str, Any] = {
        "device": device,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "org_name": "CORP",
        "domain": "corp.local",
        "ntp_servers": ["10.0.0.100", "10.0.0.101"],
        "syslog_server": "10.0.0.200",
        **(extra_vars or {}),
    }

    try:
        rendered = _render_template(template_name, templates_dir, context)
    except (FileNotFoundError, Exception) as exc:
        logger.error("Template render failed for %s: %s", device.name, exc)
        return {"success": False, "rendered": "", "error": str(exc)}

    logger.info(
        "Template rendered for %s (%d chars).", device.name, len(rendered)
    )

    if dry_run:
        logger.info("[DRY-RUN] Would push config to %s — skipping.", device.name)
        return {"success": True, "rendered": rendered, "error": None, "dry_run": True}

    # Push via SSH
    from auditor.ssh_client import SSHClient

    try:
        with SSHClient(
            host=device.host,
            username=device.username,
            password=device.password,
            key_file=device.key_file,
            port=device.port,
            timeout=device.timeout,
            simulate=device.simulate,
        ) as ssh:
            ssh.push_config(rendered)
    except Exception as exc:
        logger.error("Push failed for %s: %s", device.name, exc)
        return {"success": False, "rendered": rendered, "error": str(exc)}

    return {"success": True, "rendered": rendered, "error": None}


# ── Standalone execution ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import yaml
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    BASE = Path(__file__).parent.parent.parent
    devices_path = BASE / "config" / "devices.yaml"
    templates_dir = BASE / "config" / "templates"

    with open(devices_path) as fh:
        data = yaml.safe_load(fh)

    # Commission first device as example
    raw = data["devices"][0]

    class _FakeDevice:
        def __init__(self, d: dict) -> None:
            defaults = data.get("defaults", {})
            merged = {**defaults, **d}
            self.name = merged["name"]
            self.host = merged["host"]
            self.device_type = merged["device_type"]
            self.username = merged["username"]
            self.password = merged.get("password")
            self.key_file = merged.get("key_file")
            self.port = int(merged.get("port", 22))
            self.timeout = float(merged.get("timeout", 30))
            self.simulate = bool(merged.get("simulate", True))
            self.location = merged.get("location", "")
            self.role = merged.get("role", "")

    device = _FakeDevice(raw)
    template_map = {
        "cisco_ios": "cisco_ios_baseline.j2",
        "cisco_asa": "cisco_asa_baseline.j2",
        "linux": "linux_server_baseline.j2",
    }
    template = template_map.get(device.device_type, "cisco_ios_baseline.j2")
    result = commission_device(device, template, templates_dir, dry_run=True)

    if result["success"]:
        print(f"[OK] Commission dry-run for {device.name} succeeded.")
        print("─" * 60)
        print(result["rendered"][:500], "…")
    else:
        print(f"[FAIL] {result['error']}")
        sys.exit(1)
