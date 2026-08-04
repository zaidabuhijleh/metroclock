from __future__ import annotations

import socket
import threading
import time
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urljoin

import requests

import config
import config_manager
import web_server
from core.modes import DEFAULT_MODE_CATALOG


class MetroClockCloudAgent:
    """Outbound-only bridge between the Pi and a MetroClock cloud backend."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_heartbeat_at = 0.0
        self._last_command_poll_at = 0.0
        self._last_error_log_at = 0.0

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="metroclock-cloud-agent", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                config_manager.reload_config()
                if not self._enabled():
                    self._stop.wait(10)
                    continue

                if self._pairing_code() and not self._device_token():
                    self._attempt_pairing()

                if self._device_token():
                    self._heartbeat_if_due()
                    self._poll_commands_if_due()
            except Exception as exc:
                self._log_error(f"Cloud agent error: {exc}")

            self._stop.wait(1)

    @staticmethod
    def _enabled() -> bool:
        return bool(getattr(config, "METROCLOCK_CLOUD_ENABLED", False)) and bool(
            str(getattr(config, "METROCLOCK_CLOUD_BASE_URL", "") or "").strip()
        )

    @staticmethod
    def _base_url() -> str:
        return str(getattr(config, "METROCLOCK_CLOUD_BASE_URL", "") or "").strip().rstrip("/") + "/"

    @staticmethod
    def _device_token() -> str:
        return str(getattr(config, "METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip()

    @staticmethod
    def _pairing_code() -> str:
        return str(getattr(config, "METROCLOCK_CLOUD_PAIRING_CODE", "") or "").strip()

    @staticmethod
    def _heartbeat_seconds() -> int:
        return MetroClockCloudAgent._coerce_interval("METROCLOCK_CLOUD_HEARTBEAT_SECONDS", 30, 5, 3600)

    @staticmethod
    def _poll_seconds() -> int:
        return MetroClockCloudAgent._coerce_interval("METROCLOCK_CLOUD_COMMAND_POLL_SECONDS", 5, 2, 300)

    @staticmethod
    def _coerce_interval(key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(getattr(config, key, default))
        except Exception:
            value = default
        return max(minimum, min(maximum, value))

    def _headers(self) -> Dict[str, str]:
        token = self._device_token()
        headers = {"User-Agent": f"MetroClock/{web_server._get_app_version()}"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _url(self, path: str) -> str:
        return urljoin(self._base_url(), path.lstrip("/"))

    def _attempt_pairing(self):
        payload = {
            "device_id": web_server._get_device_id(),
            "pairing_code": self._pairing_code(),
            "status": self._status_payload(),
        }
        response = requests.post(
            self._url("/api/devices/pair"),
            json=payload,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        token = str(data.get("device_token") or "").strip()
        if not token:
            raise RuntimeError("Pairing response did not include device_token")
        config_manager.write_config({
            "METROCLOCK_CLOUD_DEVICE_TOKEN": token,
            "METROCLOCK_CLOUD_PAIRING_CODE": "",
        })
        print("MetroClock cloud pairing complete.", flush=True)

    def _heartbeat_if_due(self):
        now = time.time()
        if now - self._last_heartbeat_at < self._heartbeat_seconds():
            return
        self._last_heartbeat_at = now
        response = requests.post(
            self._url(f"/api/devices/{web_server._get_device_id()}/heartbeat"),
            json=self._status_payload(),
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()

    def _poll_commands_if_due(self):
        now = time.time()
        if now - self._last_command_poll_at < self._poll_seconds():
            return
        self._last_command_poll_at = now
        response = requests.get(
            self._url(f"/api/devices/{web_server._get_device_id()}/commands"),
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        commands = data.get("commands") or []
        if isinstance(commands, list):
            self._execute_commands(commands)

    def _execute_commands(self, commands: Iterable[Dict[str, Any]]):
        for command in commands:
            if not isinstance(command, dict):
                continue
            command_id = str(command.get("id") or "").strip()
            result = self._execute_command(command)
            if command_id:
                self._ack_command(command_id, result)

    def _execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        action = str(command.get("action") or "").strip()
        payload = command.get("payload") if isinstance(command.get("payload"), dict) else {}
        try:
            if action == "set_settings":
                changed = config_manager.write_config(payload)
                self._apply_runtime_updates(changed)
                return {"ok": True, "changed": list(changed.keys())}
            if action == "set_mode":
                mode = str(payload.get("mode") or "").strip().lower()
                if not DEFAULT_MODE_CATALOG.is_supported(mode):
                    raise ValueError("Invalid mode")
                changed = config_manager.write_config({"DISPLAY_MODE": mode})
                self._apply_runtime_updates(changed)
                return {"ok": True, "mode": mode}
            if action == "restart":
                return {"ok": False, "error": "restart command is intentionally not enabled yet"}
            return {"ok": False, "error": f"Unsupported action: {action}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _apply_runtime_updates(changed: Dict[str, Any]):
        if "DISPLAY_MODE" in changed:
            web_server.set_display_mode(changed["DISPLAY_MODE"])
        if "MATRIX_BRIGHTNESS" in changed:
            web_server.set_brightness(changed["MATRIX_BRIGHTNESS"])
        if "AMBIENT_SCENE" in changed:
            web_server.set_ambient_scene(changed["AMBIENT_SCENE"])

    def _ack_command(self, command_id: str, result: Dict[str, Any]):
        response = requests.post(
            self._url(f"/api/devices/{web_server._get_device_id()}/commands/{command_id}/ack"),
            json=result,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()

    @staticmethod
    def _status_payload() -> Dict[str, Any]:
        cfg = web_server._mask_config(config_manager.read_config())
        cfg.update({
            "device_id": web_server._get_device_id(),
            "app_version": web_server._get_app_version(),
            "api_version": web_server.API_VERSION,
            "hostname": socket.gethostname(),
            "ip": web_server._get_ip(),
            "display_mode": web_server.get_display_mode(),
            "brightness": web_server.get_brightness(),
            "wifi_setup": web_server.get_wifi_setup_status(),
            "weather_preview": web_server.get_weather_preview(),
            "ambient_scene": web_server.get_ambient_scene(),
            "pomodoro_state": web_server.get_pomodoro_state(),
            "write_auth_required": bool(web_server._configured_api_token()),
            "reported_at": int(time.time()),
        })
        return cfg

    def _log_error(self, message: str):
        now = time.time()
        if now - self._last_error_log_at < 30:
            return
        self._last_error_log_at = now
        print(message, flush=True)
