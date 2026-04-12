"""
Granular tests for the Rules Engine — regex matching, severity, absent_regex.
"""
import pytest
from auditor.rules import Rule, RuleResult, RuleSet
from pathlib import Path

BASE = Path(__file__).parent.parent


# ── Rule.evaluate() ───────────────────────────────────────────────────────────

class TestRuleEvaluate:

    def _rule(self, check_type: str, pattern: str) -> Rule:
        return Rule(
            id="TEST", name="Test Rule", description="test",
            severity="high", device_types=[],
            check_type=check_type, pattern=pattern,
            command="show test", remediation="fix it",
        )

    def test_regex_match_passes(self):
        rule = self._rule("regex", r"ntp server \d+\.\d+\.\d+\.\d+")
        assert rule.evaluate("ntp server 10.0.0.100") is True

    def test_regex_no_match_fails(self):
        rule = self._rule("regex", r"ntp server")
        assert rule.evaluate("no ntp configured") is False

    def test_regex_empty_output_fails(self):
        rule = self._rule("regex", r"ntp server")
        assert rule.evaluate("") is False

    def test_absent_regex_no_match_passes(self):
        rule = self._rule("absent_regex", r"transport input telnet")
        assert rule.evaluate("transport input ssh") is True

    def test_absent_regex_match_fails(self):
        rule = self._rule("absent_regex", r"transport input telnet")
        assert rule.evaluate("transport input telnet") is False

    def test_absent_regex_empty_passes(self):
        rule = self._rule("absent_regex", r"snmp-server community")
        assert rule.evaluate("") is True

    def test_case_insensitive(self):
        rule = self._rule("regex", r"aaa new-model")
        assert rule.evaluate("AAA NEW-MODEL") is True

    def test_multiline_matching(self):
        rule = self._rule("regex", r"^ntp server")
        output = "logging host 10.0.0.200\nntp server 10.0.0.100"
        assert rule.evaluate(output) is True

    def test_unknown_check_type_returns_false(self):
        rule = self._rule("unknown_type", r"anything")
        assert rule.evaluate("anything here") is False

    def test_applies_to_specific_type(self):
        rule = Rule(
            id="X", name="X", description="x", severity="low",
            device_types=["cisco_ios"], check_type="regex",
            pattern="x", command="cmd", remediation="r",
        )
        assert rule.applies_to("cisco_ios") is True
        assert rule.applies_to("linux") is False

    def test_applies_to_all_when_empty(self):
        rule = Rule(
            id="X", name="X", description="x", severity="low",
            device_types=[], check_type="regex",
            pattern="x", command="cmd", remediation="r",
        )
        assert rule.applies_to("cisco_ios") is True
        assert rule.applies_to("linux") is True


# ── RuleResult ────────────────────────────────────────────────────────────────

class TestRuleResult:
    def _make(self, passed: bool) -> RuleResult:
        rule = Rule(
            id="R1", name="SSH v2", description="desc", severity="critical",
            device_types=["cisco_ios"], check_type="regex",
            pattern="ip ssh version 2", command="show run | inc ssh",
            remediation="set ip ssh version 2",
        )
        return RuleResult(rule=rule, passed=passed, output="ip ssh version 2" if passed else "")

    def test_passed_to_dict_no_remediation(self):
        rr = self._make(passed=True)
        d = rr.to_dict()
        assert d["passed"] is True
        assert d["remediation"] == ""

    def test_failed_to_dict_has_remediation(self):
        rr = self._make(passed=False)
        d = rr.to_dict()
        assert d["passed"] is False
        assert "ip ssh version 2" in d["remediation"]

    def test_severity_from_rule(self):
        rr = self._make(passed=True)
        assert rr.severity == "critical"


# ── RuleSet integration ───────────────────────────────────────────────────────

class TestRuleSetIntegration:
    @pytest.fixture
    def rule_set(self):
        return RuleSet(BASE / "config" / "audit_rules.yaml")

    def test_all_severities_valid(self, rule_set):
        from auditor.rules import SEVERITIES
        for rule in rule_set._rules:
            assert rule.severity in SEVERITIES, f"Rule {rule.id} has invalid severity"

    def test_all_check_types_valid(self, rule_set):
        valid = {"regex", "absent_regex"}
        for rule in rule_set._rules:
            assert rule.check_type in valid, f"Rule {rule.id} has unknown check_type"

    def test_no_duplicate_ids(self, rule_set):
        ids = [r.id for r in rule_set._rules]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs found"

    def test_evaluate_r1_simulated(self, rule_set):
        """Full simulated output for R1 should yield all cisco rules passing."""
        from auditor.ssh_client import _SIMULATED
        outputs = _SIMULATED["10.0.0.1"]
        results = rule_set.evaluate_device("cisco_ios", outputs)
        failed = [r.rule.id for r in results if not r.passed]
        # R1 simulation is fully compliant
        assert failed == [], f"Unexpected failures: {failed}"

    def test_evaluate_sw1_ntp_fails(self, rule_set):
        from auditor.ssh_client import _SIMULATED
        outputs = _SIMULATED["10.0.0.2"]
        results = rule_set.evaluate_device("cisco_ios", outputs)
        failed = [r.rule.id for r in results if not r.passed]
        assert "NTP_CONFIGURED" in failed

    def test_evaluate_srv2_banner_fails(self, rule_set):
        from auditor.ssh_client import _SIMULATED
        outputs = _SIMULATED["10.0.1.11"]
        results = rule_set.evaluate_device("linux", outputs)
        failed = [r.rule.id for r in results if not r.passed]
        assert "LINUX_BANNER" in failed
