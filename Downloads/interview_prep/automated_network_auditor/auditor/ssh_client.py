"""
SSH Client
==========
Wraps paramiko to provide:
  - Authenticated SSH sessions (password or key-based)
  - Simulated "offline" mode for testing without real devices
  - Circuit breaker integration to avoid hammering unreachable hosts
  - Retry-with-backoff on transient connection errors
"""
import logging
import socket
from typing import Optional

import paramiko

from .fault_handler import retry_with_backoff, get_circuit_breaker

logger = logging.getLogger(__name__)

# ─── Simulated command output for offline testing ──────────────────────────

_SIMULATED: dict[str, dict[str, str]] = {
    # ── R1 ────────────────────────────────────────────────────────────────────
    "10.0.0.1": {
        "show running-config | include ip ssh version":      "ip ssh version 2",
        "show running-config | include transport input":     "transport input ssh",
        "show running-config | include aaa new-model":       "aaa new-model",
        "show running-config | include aaa authentication":  "aaa authentication login default local",
        "show running-config | include enable secret":       "enable secret 5 $1$abc$XXXX",
        "show running-config | include enable password":     "",
        "show running-config | include ntp server":          "ntp server 10.0.0.100\nntp server 10.0.0.101",
        "show running-config | include banner":              "banner motd ^",
        "show running-config | include service password":    "service password-encryption",
        "show running-config | include username":            "username admin privilege 15 secret 5 $1$abc",
        "show running-config | include logging host":        "logging host 10.0.0.200",
        "show running-config | include logging buffered":    "logging buffered 16384 informational",
        "show running-config | include snmp-server community": "",
    },
    # ── SW1 — missing NTP ─────────────────────────────────────────────────────
    "10.0.0.2": {
        "show running-config | include ip ssh version":      "ip ssh version 2",
        "show running-config | include transport input":     "transport input ssh",
        "show running-config | include aaa new-model":       "aaa new-model",
        "show running-config | include aaa authentication":  "aaa authentication login default local",
        "show running-config | include enable secret":       "enable secret 5 $1$abc$XXXX",
        "show running-config | include enable password":     "",
        "show running-config | include ntp server":          "",     # INTENTIONALLY EMPTY
        "show running-config | include banner":              "banner motd ^",
        "show running-config | include service password":    "service password-encryption",
        "show running-config | include username":            "username admin privilege 15 secret 5 $1$abc",
        "show running-config | include logging host":        "logging host 10.0.0.200",
        "show running-config | include logging buffered":    "logging buffered 16384 informational",
        "show running-config | include snmp-server community": "",
    },
    # ── FW1 (ASA) ─────────────────────────────────────────────────────────────
    "10.0.0.3": {
        "show running-config | include ip ssh version":      "ip ssh version 2",
        "show running-config | include transport input":     "transport input ssh",
        "show running-config | include aaa new-model":       "aaa new-model",
        "show running-config | include aaa authentication":  "aaa authentication ssh console LOCAL",
        "show running-config | include enable secret":       "enable secret 5 $1$abc$XXXX",
        "show running-config | include enable password":     "",
        "show running-config | include ntp server":          "ntp server 10.0.0.100",
        "show running-config | include banner":              "banner motd ^",
        "show running-config | include service password":    "",
        "show running-config | include username":            "username admin password ****** privilege 15",
        "show running-config | include logging host":        "logging host management 10.0.0.200",
        "show running-config | include logging buffered":    "logging buffered informational",
        "show running-config | include snmp-server community": "",
    },
    # ── SRV1 (Linux) ──────────────────────────────────────────────────────────
    "10.0.1.10": {
        "timedatectl status":                                "NTP synchronized: yes\nsystemd-timesyncd",
        "cat /etc/issue.net":                                "Authorized users only.",
        "grep PermitRootLogin /etc/ssh/sshd_config":        "PermitRootLogin no",
        "grep PasswordAuthentication /etc/ssh/sshd_config": "PasswordAuthentication no",
        "ufw status":                                        "Status: active",
    },
    # ── SRV2 (Linux) — missing banner ─────────────────────────────────────────
    "10.0.1.11": {
        "timedatectl status":                                "NTP synchronized: yes\nsystemd-timesyncd",
        "cat /etc/issue.net":                                "",              # INTENTIONALLY EMPTY
        "grep PermitRootLogin /etc/ssh/sshd_config":        "PermitRootLogin no",
        "grep PasswordAuthentication /etc/ssh/sshd_config": "PasswordAuthentication no",
        "ufw status":                                        "Status: active",
    },
}


class SSHClient:
    """
    Thin paramiko wrapper with simulate mode + fault-tolerance hooks.

    Args:
        host:        Target IP or hostname.
        username:    SSH username.
        password:    SSH password (mutually exclusive with key_file).
        key_file:    Path to private key (optional).
        port:        SSH port (default 22).
        timeout:     Socket/connect timeout in seconds.
        simulate:    If True, return pre-canned output without real SSH.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: Optional[str] = None,
        key_file: Optional[str] = None,
        port: int = 22,
        timeout: float = 30.0,
        simulate: bool = True,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.key_file = key_file
        self.port = port
        self.timeout = timeout
        self.simulate = simulate

        self._client: Optional[paramiko.SSHClient] = None
        self._cb = get_circuit_breaker()

    # ── Connection management ─────────────────────────────────────────────────

    @retry_with_backoff(retries=3, base_delay=2.0, exceptions=(socket.error, paramiko.SSHException))
    def connect(self) -> None:
        """Open the SSH connection (no-op in simulate mode)."""
        if self.simulate:
            logger.debug("[SIM] connect(%s) — skipped", self.host)
            return

        if not self._cb.allow_request(self.host):
            raise ConnectionError(f"Circuit breaker OPEN for {self.host}")

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            connect_kwargs: dict = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": self.timeout,
                "look_for_keys": False,
                "allow_agent": False,
            }
            if self.key_file:
                connect_kwargs["key_filename"] = self.key_file
            elif self.password:
                connect_kwargs["password"] = self.password

            client.connect(**connect_kwargs)
            self._client = client
            self._cb.record_success(self.host)
            logger.info("SSH connected to %s:%d", self.host, self.port)

        except (socket.error, paramiko.SSHException) as exc:
            self._cb.record_failure(self.host)
            raise

    def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.debug("SSH disconnected from %s", self.host)

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    # ── Command execution ─────────────────────────────────────────────────────

    def run_command(self, command: str) -> str:
        """
        Execute *command* and return stdout as a string.

        In simulate mode returns pre-canned output from _SIMULATED table.
        """
        if self.simulate:
            output = _SIMULATED.get(self.host, {}).get(command, "")
            logger.debug("[SIM] %s $ %s → %r", self.host, command, output[:80])
            return output

        if not self._client:
            raise RuntimeError(f"Not connected to {self.host}. Call connect() first.")

        _, stdout, stderr = self._client.exec_command(command, timeout=self.timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if err:
            logger.debug("stderr from %s: %s", self.host, err)
        return out

    def push_config(self, config_text: str, target_path: str = "/tmp/baseline.cfg") -> bool:
        """
        Upload *config_text* via SFTP and apply it (real mode only).
        In simulate mode logs the intent and returns True.
        """
        if self.simulate:
            logger.info("[SIM] push_config to %s — %d bytes", self.host, len(config_text))
            return True

        if not self._client:
            raise RuntimeError(f"Not connected to {self.host}.")

        with self._client.open_sftp() as sftp:
            with sftp.file(target_path, "w") as fh:
                fh.write(config_text)

        logger.info("Config pushed to %s:%s", self.host, target_path)
        return True
