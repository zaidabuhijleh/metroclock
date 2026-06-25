from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import config
import config_manager


WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"
HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.d/metroclock-setup.conf"


@dataclass
class WifiSetupStatus:
    enabled: bool = True
    active: bool = False
    connected: bool = False
    checking: bool = True
    reason: str = "Checking WiFi"
    interface: str = "wlan0"
    ssid: str = ""
    ip: str = ""
    hotspot_ssid: str = "MetroClock-Setup"
    hotspot_ip: str = "192.168.4.1"
    url: str = "http://192.168.4.1"
    last_error: str = ""
    updated_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "active": self.active,
            "connected": self.connected,
            "checking": self.checking,
            "reason": self.reason,
            "interface": self.interface,
            "ssid": self.ssid,
            "ip": self.ip,
            "hotspot_ssid": self.hotspot_ssid,
            "hotspot_ip": self.hotspot_ip,
            "url": self.url,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }


class WifiSetupManager:
    """Starts a setup hotspot when the Pi cannot join saved WiFi."""

    def __init__(self):
        self.interface = str(getattr(config, "WIFI_INTERFACE", "wlan0") or "wlan0")
        self.hotspot_ssid = str(getattr(config, "WIFI_SETUP_HOTSPOT_SSID", "MetroClock-Setup") or "MetroClock-Setup")
        self.hotspot_ip = str(getattr(config, "WIFI_SETUP_HOTSPOT_IP", "192.168.4.1") or "192.168.4.1")
        try:
            self.connect_timeout = max(5, int(getattr(config, "WIFI_CONNECT_TIMEOUT_SECONDS", 45)))
        except Exception:
            self.connect_timeout = 45
        self.enabled = bool(getattr(config, "WIFI_SETUP_ENABLED", True))
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = WifiSetupStatus(
            enabled=self.enabled,
            interface=self.interface,
            hotspot_ssid=self.hotspot_ssid,
            hotspot_ip=self.hotspot_ip,
            url=f"http://{self.hotspot_ip}",
        )

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="wifi-setup", daemon=True)
        self._thread.start()

    def status(self) -> Dict[str, object]:
        with self._lock:
            return self._status.as_dict()

    def should_show_setup_message(self) -> bool:
        status = self.status()
        return bool(status.get("active") or getattr(config, "SETUP_MODE", False))

    def connect_to_network(self, ssid: str, password: str = ""):
        ssid = str(ssid or "").strip()
        if not ssid:
            raise ValueError("SSID required")
        self._write_wpa_supplicant_network(ssid, str(password or ""))
        config_manager.write_config({"SETUP_MODE": False})
        self._set_status(active=False, checking=True, reason=f"Connecting to {ssid}", ssid=ssid, last_error="")

        def _connect():
            try:
                self._stop_hotspot()
                self._restart_wifi_client()
                if self._wait_for_connection(self.connect_timeout):
                    connected = self._connection_info()
                    self._set_status(
                        active=False,
                        connected=True,
                        checking=False,
                        reason="Connected",
                        ssid=connected.get("ssid", ssid),
                        ip=connected.get("ip", ""),
                    )
                else:
                    self._start_hotspot("Could not join WiFi")
            except Exception as exc:
                self._start_hotspot(f"WiFi connect failed: {exc}")

        threading.Thread(target=_connect, name="wifi-connect", daemon=True).start()

    def _run(self):
        if not self.enabled:
            self._set_status(enabled=False, checking=False, reason="WiFi setup fallback disabled")
            return
        if not self._interface_exists():
            self._set_status(
                active=False,
                connected=False,
                checking=False,
                reason=f"{self.interface} not found",
                last_error="WiFi interface is not available",
            )
            return

        self._set_status(checking=True, reason="Trying saved WiFi networks")
        if getattr(config, "SETUP_MODE", False):
            self._stop_hotspot()
            self._restart_wifi_client()

        if self._wait_for_connection(self.connect_timeout):
            connected = self._connection_info()
            self._set_status(
                active=False,
                connected=True,
                checking=False,
                reason="Connected",
                ssid=connected.get("ssid", ""),
                ip=connected.get("ip", ""),
            )
            config_manager.write_config({"SETUP_MODE": False})
            return

        self._start_hotspot("Could not join saved WiFi")

    def _wait_for_connection(self, timeout_seconds: int) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline and not self._stop_event.is_set():
            if self._is_connected():
                return True
            time.sleep(2)
        return self._is_connected()

    def _start_hotspot(self, reason: str):
        try:
            self._ensure_hotspot_config()
            self._run_command(["systemctl", "stop", "wpa_supplicant"], timeout=8)
            self._run_command(["systemctl", "stop", f"wpa_supplicant@{self.interface}"], timeout=8)
            self._run_command(["ip", "addr", "flush", "dev", self.interface], timeout=8, check=True)
            self._run_command(["ip", "addr", "add", f"{self.hotspot_ip}/24", "dev", self.interface], timeout=8, check=True)
            self._run_command(["ip", "link", "set", self.interface, "up"], timeout=8, check=True)
            self._run_command(["systemctl", "restart", "dnsmasq"], timeout=12, check=True)
            self._run_command(["systemctl", "restart", "hostapd"], timeout=12, check=True)
            config_manager.write_config({"SETUP_MODE": True})
            self._set_status(
                active=True,
                connected=False,
                checking=False,
                reason=reason,
                ssid="",
                ip=self.hotspot_ip,
                last_error="",
            )
        except Exception as exc:
            config_manager.write_config({"SETUP_MODE": True})
            self._set_status(
                active=True,
                connected=False,
                checking=False,
                reason=reason,
                ip=self.hotspot_ip,
                last_error=str(exc),
            )

    def _stop_hotspot(self):
        self._run_command(["systemctl", "stop", "hostapd"], timeout=8)
        self._run_command(["systemctl", "stop", "dnsmasq"], timeout=8)

    def _restart_wifi_client(self):
        self._run_command(["ip", "addr", "flush", "dev", self.interface], timeout=8)
        self._run_command(["ip", "link", "set", self.interface, "up"], timeout=8)
        self._run_command(["systemctl", "restart", "wpa_supplicant"], timeout=12)
        self._run_command(["systemctl", "restart", f"wpa_supplicant@{self.interface}"], timeout=12)
        self._run_command(["systemctl", "restart", "dhcpcd"], timeout=12)
        self._run_command(["wpa_cli", "-i", self.interface, "reconfigure"], timeout=8)

    def _ensure_hotspot_config(self):
        self._require_command("hostapd")
        self._require_command("dnsmasq")
        self._require_command("ip")
        os.makedirs(os.path.dirname(HOSTAPD_CONF), exist_ok=True)
        os.makedirs(os.path.dirname(DNSMASQ_CONF), exist_ok=True)
        self._write_file(
            HOSTAPD_CONF,
            "\n".join(
                [
                    f"interface={self.interface}",
                    "driver=nl80211",
                    f"ssid={self.hotspot_ssid}",
                    "hw_mode=g",
                    "channel=7",
                    "wmm_enabled=0",
                    "macaddr_acl=0",
                    "auth_algs=1",
                    "ignore_broadcast_ssid=0",
                    "",
                ]
            ),
        )
        self._write_file(
            DNSMASQ_CONF,
            "\n".join(
                [
                    f"interface={self.interface}",
                    "bind-dynamic",
                    "dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h",
                    f"address=/#/{self.hotspot_ip}",
                    "",
                ]
            ),
        )
        default_hostapd = "/etc/default/hostapd"
        if os.path.exists(default_hostapd):
            try:
                with open(default_hostapd, "r", encoding="utf-8") as f:
                    content = f.read()
                if "DAEMON_CONF=" in content:
                    content = re.sub(r'^\s*#?\s*DAEMON_CONF=.*$', f'DAEMON_CONF="{HOSTAPD_CONF}"', content, flags=re.MULTILINE)
                else:
                    content += f'\nDAEMON_CONF="{HOSTAPD_CONF}"\n'
                self._write_file(default_hostapd, content)
            except Exception:
                pass

    def _write_wpa_supplicant_network(self, ssid: str, password: str):
        header = 'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=US\n\n'
        try:
            with open(WPA_SUPPLICANT_CONF, "r", encoding="utf-8") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = header
        cleaned = self._remove_network_for_ssid(existing, ssid).strip()
        if "ctrl_interface=" not in cleaned:
            cleaned = header.strip()

        lines = ["network={", f"    ssid={self._wpa_quote(ssid)}"]
        if password:
            lines.append(f"    psk={self._wpa_quote(password)}")
        else:
            lines.append("    key_mgmt=NONE")
        lines.extend(["    priority=10", "}", ""])
        self._write_file(WPA_SUPPLICANT_CONF, cleaned + "\n\n" + "\n".join(lines))

    def _remove_network_for_ssid(self, content: str, ssid: str) -> str:
        blocks = []
        pattern = re.compile(r"network=\{", re.MULTILINE)
        for match in pattern.finditer(content):
            start = match.start()
            depth = 0
            end = None
            for idx in range(match.start(), len(content)):
                if content[idx] == "{":
                    depth += 1
                elif content[idx] == "}":
                    depth -= 1
                    if depth == 0:
                        end = idx + 1
                        break
            if end is None:
                continue
            blocks.append((start, end))

        if not blocks:
            return content

        out = []
        last = 0
        for start, end in blocks:
            block = content[start:end]
            out.append(content[last:start])
            if self._network_block_ssid(block) != ssid:
                out.append(block)
            last = end
        out.append(content[last:])
        return "".join(out)

    def _network_block_ssid(self, block: str) -> Optional[str]:
        match = re.search(r'^\s*ssid\s*=\s*("(?:\\.|[^"])*"|[^\s#]+)', block, flags=re.MULTILINE)
        if not match:
            return None
        raw = match.group(1).strip()
        if raw.startswith('"') and raw.endswith('"'):
            try:
                return json.loads(raw)
            except Exception:
                return raw[1:-1]
        return raw

    @staticmethod
    def _wpa_quote(value: str) -> str:
        return json.dumps(str(value or ""))

    def _is_connected(self) -> bool:
        info = self._connection_info()
        ip = info.get("ip", "")
        if not ip or ip == self.hotspot_ip:
            return False
        return bool(info.get("ssid") or self._has_default_route())

    def _connection_info(self) -> Dict[str, str]:
        return {
            "ssid": self._current_ssid(),
            "ip": self._interface_ipv4(),
        }

    def _current_ssid(self) -> str:
        result = self._run_command(["iwgetid", self.interface, "-r"], timeout=4, capture=True)
        return result.strip()

    def _interface_ipv4(self) -> str:
        result = self._run_command(["ip", "-4", "-o", "addr", "show", "dev", self.interface], timeout=4, capture=True)
        for part in result.split():
            if "/" not in part:
                continue
            try:
                iface = ipaddress.ip_interface(part)
                if iface.version == 4:
                    return str(iface.ip)
            except Exception:
                continue
        return ""

    def _has_default_route(self) -> bool:
        result = self._run_command(["ip", "route", "show", "default", "dev", self.interface], timeout=4, capture=True)
        return "default" in result

    def _interface_exists(self) -> bool:
        return os.path.exists(f"/sys/class/net/{self.interface}")

    def _require_command(self, command: str):
        if self._resolve_command(command) is None:
            raise RuntimeError(f"Missing required command: {command}")

    def _run_command(self, args, timeout=8, capture=False, check=False):
        command = self._resolve_command(args[0])
        if command is None:
            if check:
                raise RuntimeError(f"Missing required command: {args[0]}")
            return ""
        try:
            completed = subprocess.run(
                [command] + list(args[1:]),
                check=False,
                timeout=timeout,
                text=True,
                stdout=subprocess.PIPE if capture or check else subprocess.DEVNULL,
                stderr=subprocess.PIPE if capture or check else subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            if check:
                raise RuntimeError(f"Command timed out: {' '.join(args)}") from exc
            return ""
        if check and completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(error or f"Command failed: {' '.join(args)}")
        if capture:
            return completed.stdout or ""
        return ""

    @staticmethod
    def _resolve_command(command: str):
        found = shutil.which(command)
        if found:
            return found
        for directory in ("/usr/sbin", "/sbin", "/usr/bin", "/bin"):
            candidate = os.path.join(directory, command)
            if os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None

    def _write_file(self, path: str, content: str):
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)

    def _set_status(self, **updates):
        with self._lock:
            for key, value in updates.items():
                if hasattr(self._status, key):
                    setattr(self._status, key, value)
            self._status.enabled = self.enabled
            self._status.interface = self.interface
            self._status.hotspot_ssid = self.hotspot_ssid
            self._status.hotspot_ip = self.hotspot_ip
            self._status.url = f"http://{self.hotspot_ip}"
            self._status.updated_at = time.time()
