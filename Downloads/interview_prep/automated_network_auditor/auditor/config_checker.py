"""
Config Checker
==============
Orchestrates command collection from a single device:
  1. Connects via SSHClient
  2. Runs all commands required by applicable rules
  3. Returns raw {command → output} mapping for rule evaluation
"""
import logging
from typing import Optional

from .inventory import Device
from .rules import RuleSet
from .ssh_client import SSHClient
from .fault_handler import retry_with_backoff

logger = logging.getLogger(__name__)


class ConfigChecker:
    """
    Fetch all required command outputs from *device* for the given *rule_set*.

    Args:
        device:   Device to audit.
        rule_set: Loaded RuleSet (determines which commands to run).

    Example::

        checker = ConfigChecker(device, rule_set)
        outputs = checker.collect()   # {command: output}
    """

    def __init__(self, device: Device, rule_set: RuleSet) -> None:
        self.device = device
        self.rule_set = rule_set

    def collect(self) -> dict[str, str]:
        """
        Connect to the device and run every command required by applicable rules.

        Returns a dict mapping command string → command output.
        On connection failure returns an empty dict so the audit engine
        can record a SKIPPED result rather than crashing.
        """
        applicable_rules = self.rule_set.rules_for_device_type(self.device.device_type)
        commands = list({r.command for r in applicable_rules})  # deduplicate

        if not commands:
            logger.info("No applicable rules for %s (%s)", self.device.name, self.device.device_type)
            return {}

        logger.info(
            "Collecting %d command(s) from %s (%s)",
            len(commands), self.device.name, self.device.host,
        )

        outputs: dict[str, str] = {}

        try:
            with SSHClient(
                host=self.device.host,
                username=self.device.username,
                password=self.device.password,
                key_file=self.device.key_file,
                port=self.device.port,
                timeout=self.device.timeout,
                simulate=self.device.simulate,
            ) as ssh:
                for cmd in commands:
                    try:
                        output = ssh.run_command(cmd)
                        outputs[cmd] = output
                    except Exception as exc:
                        logger.warning(
                            "Command failed on %s [%s]: %s", self.device.name, cmd, exc
                        )
                        outputs[cmd] = ""  # treat as empty output (rule will fail)

        except ConnectionError as exc:
            logger.error(
                "Circuit breaker blocked connection to %s: %s", self.device.name, exc
            )
        except Exception as exc:
            logger.error(
                "Failed to connect to %s (%s): %s", self.device.name, self.device.host, exc
            )

        return outputs
