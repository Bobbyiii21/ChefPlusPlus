"""
Audit Rules Engine
==================
Loads audit_rules.yaml and evaluates each rule against command output
received from the SSH client.

Check types:
  regex         — output must match the pattern (compliance = match found)
  absent_regex  — output must NOT match the pattern (compliance = no match)
"""
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

SEVERITIES = ("critical", "high", "medium", "low")


@dataclass
class Rule:
    id: str
    name: str
    description: str
    severity: str
    device_types: list[str]
    check_type: str        # "regex" | "absent_regex"
    pattern: str
    command: str
    remediation: str

    def applies_to(self, device_type: str) -> bool:
        """Return True if this rule applies to *device_type*."""
        return not self.device_types or device_type in self.device_types

    def evaluate(self, output: str) -> bool:
        """
        Evaluate the rule against *output*.
        Returns True if the device is **compliant**.
        """
        matched = bool(re.search(self.pattern, output, re.MULTILINE | re.IGNORECASE))
        if self.check_type == "regex":
            return matched
        if self.check_type == "absent_regex":
            return not matched
        logger.warning("Unknown check_type '%s' for rule %s", self.check_type, self.id)
        return False


@dataclass
class RuleResult:
    rule: Rule
    passed: bool
    output: str
    message: str = ""

    @property
    def severity(self) -> str:
        return self.rule.severity

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule.id,
            "rule_name": self.rule.name,
            "severity": self.severity,
            "passed": self.passed,
            "message": self.message,
            "remediation": "" if self.passed else self.rule.remediation,
            "command": self.rule.command,
        }


class RuleSet:
    """
    Load all audit rules from a YAML file and evaluate them against
    command output collected from a device.

    Args:
        path: Path to audit_rules.yaml.

    Example::

        rules = RuleSet("config/audit_rules.yaml")
        results = rules.evaluate_device("cisco_ios", outputs)
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._rules: list[Rule] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"Rules file not found: {self._path}")

        with open(self._path, "r") as fh:
            data = yaml.safe_load(fh)

        for raw in data.get("rules", []):
            try:
                rule = Rule(
                    id=raw["id"],
                    name=raw["name"],
                    description=raw["description"],
                    severity=raw.get("severity", "medium"),
                    device_types=raw.get("device_types", []),
                    check_type=raw["check_type"],
                    pattern=raw["pattern"],
                    command=raw["command"],
                    remediation=raw.get("remediation", ""),
                )
                if rule.severity not in SEVERITIES:
                    logger.warning("Rule %s has unknown severity '%s'", rule.id, rule.severity)
                self._rules.append(rule)
            except KeyError as exc:
                logger.error("Skipping malformed rule — missing field: %s", exc)

        logger.info("Rules loaded: %d rule(s) from %s", len(self._rules), self._path)

    def rules_for_device_type(self, device_type: str) -> list[Rule]:
        return [r for r in self._rules if r.applies_to(device_type)]

    def evaluate_device(
        self, device_type: str, command_outputs: dict[str, str]
    ) -> list[RuleResult]:
        """
        Evaluate all applicable rules for *device_type*.

        Args:
            device_type:     The device's type string (e.g. "cisco_ios").
            command_outputs: Mapping of {command_string: output_text}.

        Returns:
            List of RuleResult — one per applicable rule.
        """
        results: list[RuleResult] = []
        for rule in self.rules_for_device_type(device_type):
            output = command_outputs.get(rule.command, "")
            passed = rule.evaluate(output)
            msg = (
                f"PASS: {rule.name}"
                if passed
                else f"FAIL: {rule.name} — {rule.description}"
            )
            results.append(RuleResult(rule=rule, passed=passed, output=output, message=msg))
            log_fn = logger.debug if passed else logger.warning
            log_fn("[%s] %s", "PASS" if passed else "FAIL", rule.id)

        return results

    def __len__(self) -> int:
        return len(self._rules)
