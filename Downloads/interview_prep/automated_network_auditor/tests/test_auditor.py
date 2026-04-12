"""
Tests for AuditEngine and ConfigChecker (integration-style with simulate=True).
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from auditor.inventory import DeviceInventory, Device
from auditor.rules import RuleSet
from auditor.core import AuditEngine
from auditor.config_checker import ConfigChecker
from auditor.reporter import DeviceReport

BASE = Path(__file__).parent.parent
DEVICES_YAML = BASE / "config" / "devices.yaml"
RULES_YAML   = BASE / "config" / "audit_rules.yaml"


@pytest.fixture
def inventory():
    return DeviceInventory(DEVICES_YAML)


@pytest.fixture
def rule_set():
    return RuleSet(RULES_YAML)


@pytest.fixture
def cisco_device():
    return Device(
        name="R1", host="10.0.0.1", device_type="cisco_ios",
        username="admin", simulate=True,
    )


@pytest.fixture
def linux_device():
    return Device(
        name="SRV1", host="10.0.1.10", device_type="linux",
        username="sysadmin", simulate=True,
    )


# ── Inventory loading ─────────────────────────────────────────────────────────

class TestInventory:
    def test_loads_all_devices(self, inventory):
        assert len(inventory) == 5

    def test_get_by_name(self, inventory):
        dev = inventory.get_by_name("R1")
        assert dev is not None
        assert dev.host == "10.0.0.1"
        assert dev.device_type == "cisco_ios"

    def test_get_by_name_missing(self, inventory):
        assert inventory.get_by_name("NONEXISTENT") is None

    def test_get_by_tag_critical(self, inventory):
        critical = inventory.get_by_tag("critical")
        names = [d.name for d in critical]
        assert "R1" in names
        assert "FW1" in names
        assert "SW1" not in names

    def test_get_by_type_linux(self, inventory):
        linux = inventory.get_by_type("linux")
        assert all(d.device_type == "linux" for d in linux)
        assert len(linux) == 2

    def test_simulate_default_true(self, inventory):
        for d in inventory.get_all():
            assert d.simulate is True

    def test_missing_inventory_file(self):
        with pytest.raises(FileNotFoundError):
            DeviceInventory("/nonexistent/devices.yaml")

    def test_is_cisco_property(self, cisco_device):
        assert cisco_device.is_cisco is True
        assert cisco_device.is_linux is False


# ── Rule evaluation ───────────────────────────────────────────────────────────

class TestRuleSet:
    def test_loads_rules(self, rule_set):
        assert len(rule_set) > 0

    def test_rules_for_cisco_ios(self, rule_set):
        rules = rule_set.rules_for_device_type("cisco_ios")
        ids = [r.id for r in rules]
        assert "SSH_VERSION" in ids
        assert "NTP_CONFIGURED" in ids
        assert "AAA_AUTH" in ids

    def test_rules_for_linux(self, rule_set):
        rules = rule_set.rules_for_device_type("linux")
        ids = [r.id for r in rules]
        assert "SSH_ROOT_DISABLED" in ids
        assert "LINUX_BANNER" in ids
        assert "NTP_LINUX" in ids

    def test_regex_rule_pass(self, rule_set):
        rule = next(r for r in rule_set._rules if r.id == "SSH_VERSION")
        assert rule.evaluate("ip ssh version 2") is True
        assert rule.evaluate("ip ssh version 1") is False
        assert rule.evaluate("") is False

    def test_absent_regex_rule_pass(self, rule_set):
        rule = next(r for r in rule_set._rules if r.id == "TELNET_DISABLED")
        assert rule.evaluate("transport input ssh") is True       # no telnet → PASS
        assert rule.evaluate("transport input telnet") is False   # telnet present → FAIL

    def test_evaluate_device_returns_results(self, rule_set):
        outputs = {
            "show running-config | include ip ssh version": "ip ssh version 2",
            "show running-config | include transport input": "transport input ssh",
        }
        results = rule_set.evaluate_device("cisco_ios", outputs)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_missing_rules_file(self):
        with pytest.raises(FileNotFoundError):
            RuleSet("/nonexistent/rules.yaml")


# ── ConfigChecker (simulate mode) ────────────────────────────────────────────

class TestConfigChecker:
    def test_collect_cisco(self, cisco_device, rule_set):
        checker = ConfigChecker(cisco_device, rule_set)
        outputs = checker.collect()
        assert isinstance(outputs, dict)
        assert len(outputs) > 0
        # R1 simulated output should have SSH v2
        key = "show running-config | include ip ssh version"
        assert key in outputs
        assert "ip ssh version 2" in outputs[key]

    def test_collect_linux(self, linux_device, rule_set):
        checker = ConfigChecker(linux_device, rule_set)
        outputs = checker.collect()
        assert "timedatectl status" in outputs

    def test_collect_returns_empty_on_connection_failure(self, rule_set):
        device = Device(
            name="DEAD", host="10.99.99.99", device_type="cisco_ios",
            username="admin", simulate=False,  # real mode → will fail
        )
        checker = ConfigChecker(device, rule_set)
        # Should return empty dict, not raise
        outputs = checker.collect()
        assert outputs == {}


# ── Full audit run (simulate mode) ───────────────────────────────────────────

class TestAuditEngine:
    def test_full_run_returns_reporter(self, inventory, rule_set):
        engine = AuditEngine(inventory, rule_set, max_workers=2)
        reporter = engine.run()
        assert len(reporter._reports) == 5

    def test_r1_passes_all_rules(self, inventory, rule_set):
        engine = AuditEngine(inventory, rule_set)
        reporter = engine.run(device_filter=["R1"])
        report = next(r for r in reporter._reports if r.device_name == "R1")
        assert report.failed == 0
        assert report.compliance_pct == 100.0

    def test_sw1_fails_ntp(self, inventory, rule_set):
        """SW1 is intentionally missing NTP — must fail NTP_CONFIGURED."""
        engine = AuditEngine(inventory, rule_set)
        reporter = engine.run(device_filter=["SW1"])
        report = next(r for r in reporter._reports if r.device_name == "SW1")
        failed_ids = [r["rule_id"] for r in report.results if not r["passed"]]
        assert "NTP_CONFIGURED" in failed_ids

    def test_srv2_fails_banner(self, inventory, rule_set):
        """SRV2 has no banner — must fail LINUX_BANNER."""
        engine = AuditEngine(inventory, rule_set)
        reporter = engine.run(device_filter=["SRV2"])
        report = next(r for r in reporter._reports if r.device_name == "SRV2")
        failed_ids = [r["rule_id"] for r in report.results if not r["passed"]]
        assert "LINUX_BANNER" in failed_ids

    def test_filter_by_tag(self, inventory, rule_set):
        engine = AuditEngine(inventory, rule_set)
        reporter = engine.run(tag_filter="server")
        names = [r.device_name for r in reporter._reports]
        assert "SRV1" in names
        assert "SRV2" in names
        assert "R1" not in names

    def test_reporter_to_dict(self, inventory, rule_set):
        engine = AuditEngine(inventory, rule_set)
        reporter = engine.run(device_filter=["R1"])
        data = reporter.to_dict()
        assert "devices" in data
        assert "overall_compliance_pct" in data
        assert data["devices_audited"] == 1

    def test_json_save(self, inventory, rule_set, tmp_path):
        engine = AuditEngine(inventory, rule_set)
        reporter = engine.run(device_filter=["R1"])
        out = tmp_path / "report.json"
        reporter.save_json(str(out))
        assert out.exists()
        import json
        data = json.loads(out.read_text())
        assert data["devices_audited"] == 1
