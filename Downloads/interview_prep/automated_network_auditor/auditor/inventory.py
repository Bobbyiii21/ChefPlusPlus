"""
Device Inventory
================
Loads and validates the devices.yaml file.
Merges device-level settings with top-level defaults.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

SUPPORTED_DEVICE_TYPES = {"cisco_ios", "cisco_asa", "cisco_nxos", "linux"}


@dataclass
class Device:
    name: str
    host: str
    device_type: str
    username: str
    port: int = 22
    timeout: float = 30.0
    simulate: bool = True
    retry_attempts: int = 3
    retry_delay: float = 2.0
    location: str = ""
    role: str = ""
    tags: list[str] = field(default_factory=list)
    password: Optional[str] = None
    key_file: Optional[str] = None

    def __post_init__(self) -> None:
        if self.device_type not in SUPPORTED_DEVICE_TYPES:
            raise ValueError(
                f"Device '{self.name}': unsupported device_type '{self.device_type}'. "
                f"Supported: {SUPPORTED_DEVICE_TYPES}"
            )
        if not self.host:
            raise ValueError(f"Device '{self.name}': host is required.")

    @property
    def is_cisco(self) -> bool:
        return self.device_type.startswith("cisco")

    @property
    def is_linux(self) -> bool:
        return self.device_type == "linux"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "host": self.host,
            "device_type": self.device_type,
            "username": self.username,
            "port": self.port,
            "location": self.location,
            "role": self.role,
            "tags": self.tags,
            "simulate": self.simulate,
        }


class DeviceInventory:
    """
    Load and query the device inventory from a YAML file.

    Args:
        path: Absolute or relative path to devices.yaml.

    Example::

        inv = DeviceInventory("config/devices.yaml")
        for device in inv.get_all():
            print(device.name, device.host)
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._devices: list[Device] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"Inventory file not found: {self._path}")

        with open(self._path, "r") as fh:
            data = yaml.safe_load(fh)

        defaults: dict = data.get("defaults", {})
        raw_devices: list[dict] = data.get("devices", [])

        if not raw_devices:
            logger.warning("No devices found in %s", self._path)
            return

        for raw in raw_devices:
            merged = {**defaults, **raw}
            # tags should always be a list
            merged.setdefault("tags", [])
            try:
                device = Device(
                    name=merged["name"],
                    host=merged["host"],
                    device_type=merged["device_type"],
                    username=merged["username"],
                    port=int(merged.get("port", 22)),
                    timeout=float(merged.get("timeout", 30)),
                    simulate=bool(merged.get("simulate", True)),
                    retry_attempts=int(merged.get("retry_attempts", 3)),
                    retry_delay=float(merged.get("retry_delay", 2.0)),
                    location=merged.get("location", ""),
                    role=merged.get("role", ""),
                    tags=list(merged.get("tags", [])),
                    password=merged.get("password"),
                    key_file=merged.get("key_file"),
                )
                self._devices.append(device)
                logger.debug("Loaded device: %s (%s)", device.name, device.host)
            except (KeyError, ValueError) as exc:
                logger.error("Skipping malformed device entry: %s — %s", raw.get("name", "?"), exc)

        logger.info("Inventory loaded: %d device(s) from %s", len(self._devices), self._path)

    # ── Query API ─────────────────────────────────────────────────────────────

    def get_all(self) -> list[Device]:
        return list(self._devices)

    def get_by_name(self, name: str) -> Optional[Device]:
        return next((d for d in self._devices if d.name == name), None)

    def get_by_tag(self, tag: str) -> list[Device]:
        return [d for d in self._devices if tag in d.tags]

    def get_by_type(self, device_type: str) -> list[Device]:
        return [d for d in self._devices if d.device_type == device_type]

    def filter_by_role(self, role: str) -> list[Device]:
        return [d for d in self._devices if d.role == role]

    def __len__(self) -> int:
        return len(self._devices)

    def __repr__(self) -> str:
        return f"DeviceInventory({self._path}, {len(self._devices)} devices)"
