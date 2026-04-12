"""
Automated Network Auditor
=========================
Core auditing engine with SSH connectivity, rule evaluation,
fault tolerance, and rich report generation.
"""
from .core import AuditEngine
from .inventory import DeviceInventory
from .rules import RuleSet
from .reporter import AuditReporter

__all__ = ["AuditEngine", "DeviceInventory", "RuleSet", "AuditReporter"]
__version__ = "1.0.0"
