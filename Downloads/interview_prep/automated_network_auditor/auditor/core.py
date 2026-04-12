"""
Audit Engine — Core Orchestrator
=================================
AuditEngine.run()  iterates over devices, collects command output,
evaluates rules, and populates an AuditReporter.

Designed for fault tolerance:
  - Per-device errors never crash the overall run.
  - Devices that cannot be reached are marked SKIP.
  - Circuit breaker state is shared across the run.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .inventory import Device, DeviceInventory
from .rules import RuleSet
from .config_checker import ConfigChecker
from .reporter import AuditReporter, DeviceReport

logger = logging.getLogger(__name__)


class AuditEngine:
    """
    Orchestrate a full compliance audit across all devices in *inventory*.

    Args:
        inventory:   Loaded DeviceInventory.
        rule_set:    Loaded RuleSet.
        max_workers: Thread pool size for concurrent device auditing.

    Example::

        engine = AuditEngine(inventory, rule_set, max_workers=5)
        reporter = engine.run()
        reporter.print_summary()
    """

    def __init__(
        self,
        inventory: DeviceInventory,
        rule_set: RuleSet,
        max_workers: int = 5,
    ) -> None:
        self.inventory = inventory
        self.rule_set = rule_set
        self.max_workers = max_workers

    def run(
        self,
        device_filter: Optional[list[str]] = None,
        tag_filter: Optional[str] = None,
    ) -> AuditReporter:
        """
        Run the audit and return a populated AuditReporter.

        Args:
            device_filter: If given, only audit devices with these names.
            tag_filter:    If given, only audit devices with this tag.
        """
        devices = self.inventory.get_all()

        if device_filter:
            devices = [d for d in devices if d.name in device_filter]
        if tag_filter:
            devices = [d for d in devices if tag_filter in d.tags]

        if not devices:
            logger.warning("No devices matched the given filters.")

        reporter = AuditReporter()

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._audit_device, d): d for d in devices}
            for future in as_completed(futures):
                device = futures[future]
                try:
                    report = future.result()
                except Exception as exc:
                    logger.error("Unexpected error auditing %s: %s", device.name, exc)
                    report = DeviceReport(
                        device_name=device.name,
                        device_type=device.device_type,
                        host=device.host,
                        location=device.location,
                        role=device.role,
                        error=str(exc),
                    )
                reporter.add(report)

        return reporter

    # ── Internal ──────────────────────────────────────────────────────────────

    def _audit_device(self, device: Device) -> DeviceReport:
        """Audit a single device — called in a thread pool worker."""
        logger.info("Auditing %s (%s) …", device.name, device.host)

        report = DeviceReport(
            device_name=device.name,
            device_type=device.device_type,
            host=device.host,
            location=device.location,
            role=device.role,
        )

        checker = ConfigChecker(device, self.rule_set)
        outputs = checker.collect()

        if not outputs:
            report.error = f"Could not connect to {device.host}"
            logger.warning("Skipping %s — no outputs collected.", device.name)
            return report

        rule_results = self.rule_set.evaluate_device(device.device_type, outputs)

        for rr in rule_results:
            report.results.append(rr.to_dict())
            if rr.passed:
                report.passed += 1
            else:
                report.failed += 1

        logger.info(
            "%s audit complete: %d pass, %d fail (%.1f%% compliant)",
            device.name, report.passed, report.failed, report.compliance_pct,
        )
        return report
