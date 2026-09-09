from __future__ import annotations

import hashlib
import io
import json
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

    # A rejected pairing code or a revoked device token is a persistent failure.
    # Without backoff the agent loop retried it at the loop rate (~1 Hz) forever.
    #
    # The ceiling is deliberately low. Onboarding hands the clock its cloud
    # config while it is still hosting the setup hotspot, so the first pairing
    # attempts always fail for lack of internet — the backoff is already growing
    # before a success is even possible. Pairing tokens expire in ~600s, so a
    # 300s ceiling could burn half that window waiting to retry.
    PAIRING_BACKOFF_MIN_SECONDS = 5
    PAIRING_BACKOFF_MAX_SECONDS = 60
    EVENT_BACKOFF_MIN_SECONDS = 5
    EVENT_BACKOFF_MAX_SECONDS = 300

    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._event_thread: Optional[threading.Thread] = None
        self._command_poll_lock = threading.Lock()
        self._last_heartbeat_at = 0.0
        self._last_command_poll_at = 0.0
        self._last_preview_upload_at = 0.0
        self._last_preview_upload_success_at = 0.0
        self._last_preview_signature: str | None = None
        self._last_error_log_at = 0.0
        self._pairing_retry_at = 0.0
        self._pairing_backoff_seconds = self.PAIRING_BACKOFF_MIN_SECONDS
        self._pairing_backoff_code: str | None = None
        self._event_backoff_seconds = self.EVENT_BACKOFF_MIN_SECONDS
        # Keep-alive instead of a fresh TLS handshake per call. The preview
        # upload alone runs every 2s for the life of the device.
        #
        # Two sessions, not one: the polling thread and the SSE thread run
        # concurrently, the event stream holds its connection open for minutes,
        # and requests.Session is not documented as thread-safe.
        self._session = requests.Session()
        self._event_session = requests.Session()

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="metroclock-cloud-agent", daemon=True)
        self._thread.start()
        self._event_thread = threading.Thread(target=self._run_events, name="metroclock-cloud-events", daemon=True)
        self._event_thread.start()

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
                    self._attempt_pairing_if_due()

                if self._device_token():
                    self._heartbeat_if_due()
                    self._poll_commands_if_due()
                    self._upload_preview_if_due()
            except Exception as exc:
                self._log_error(f"Cloud agent error: {exc}")

            self._stop.wait(1)

    def _run_events(self):
        while not self._stop.is_set():
            try:
                config_manager.reload_config()
                if not self._enabled() or not self._device_token():
                    self._stop.wait(self.EVENT_BACKOFF_MIN_SECONDS)
                    continue
                self._listen_for_events()
                # A clean stream close is a normal reconnect, not a failure.
                self._stop.wait(self.EVENT_BACKOFF_MIN_SECONDS)
            except Exception as exc:
                self._log_error(f"Cloud events error: {exc}")
                self._stop.wait(self._event_backoff_seconds)
                self._event_backoff_seconds = min(
                    self.EVENT_BACKOFF_MAX_SECONDS,
                    self._event_backoff_seconds * 2,
                )

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
    def _preview_seconds() -> int:
        return MetroClockCloudAgent._coerce_interval("METROCLOCK_CLOUD_PREVIEW_SECONDS", 2, 1, 300)

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

    def _attempt_pairing_if_due(self):
        """Pair, but never faster than the current backoff.

        A code the backend rejects is a persistent failure, so retrying it at the
        agent loop rate just hammers the API until the user re-runs setup.
        """
        pairing_code = self._pairing_code()
        if pairing_code != self._pairing_backoff_code:
            # A new code means the user just re-ran setup — pair immediately.
            self._pairing_backoff_code = pairing_code
            self._pairing_retry_at = 0.0
            self._pairing_backoff_seconds = self.PAIRING_BACKOFF_MIN_SECONDS

        now = time.time()
        if now < self._pairing_retry_at:
            return
        try:
            self._attempt_pairing()
        except Exception:
            self._pairing_retry_at = time.time() + self._pairing_backoff_seconds
            self._pairing_backoff_seconds = min(
                self.PAIRING_BACKOFF_MAX_SECONDS,
                self._pairing_backoff_seconds * 2,
            )
            raise

    def _attempt_pairing(self):
        payload = {
            "device_id": web_server._get_device_id(),
            "pairing_code": self._pairing_code(),
            "status": self._status_payload(),
        }
        response = self._session.post(
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
        config_manager.reload_config()
        self._pairing_retry_at = 0.0
        self._pairing_backoff_seconds = self.PAIRING_BACKOFF_MIN_SECONDS
        print("MetroClock cloud pairing complete.", flush=True)

    def _heartbeat_if_due(self):
        now = time.time()
        if now - self._last_heartbeat_at < self._heartbeat_seconds():
            return
        self._last_heartbeat_at = now
        response = self._session.post(
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
        self._poll_commands_now()

    def _poll_commands_now(self):
        with self._command_poll_lock:
            self._last_command_poll_at = time.time()
            response = self._session.get(
                self._url(f"/api/devices/{web_server._get_device_id()}/commands"),
                headers=self._headers(),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
            commands = data.get("commands") or []
            if isinstance(commands, list):
                self._execute_commands(commands)

    def _upload_preview_if_due(self):
        now = time.time()
        interval = self._preview_seconds()
        if now - self._last_preview_upload_at < interval:
            return
        self._last_preview_upload_at = now

        frame = web_server.get_latest_frame()
        if frame is None:
            return

        # Hash the raw pixels, not the encoded bytes: the old order paid for a
        # PNG encode every 2s even when the frame had not changed at all.
        try:
            rgb = frame.convert("RGB")
            signature = hashlib.blake2s(rgb.tobytes(), digest_size=8).hexdigest()
        except Exception as exc:
            self._log_error(f"Cloud preview hash error: {exc}")
            return

        keepalive_seconds = max(60, interval * 30)
        if (
            signature == self._last_preview_signature
            and now - self._last_preview_upload_success_at < keepalive_seconds
        ):
            return

        buf = io.BytesIO()
        try:
            rgb.save(buf, format="PNG")
        except Exception as exc:
            self._log_error(f"Cloud preview encode error: {exc}")
            return
        content = buf.getvalue()

        try:
            response = self._session.post(
                self._url(f"/api/devices/{web_server._get_device_id()}/preview"),
                data=content,
                headers={**self._headers(), "Content-Type": "image/png"},
                timeout=10,
            )
            response.raise_for_status()
            self._last_preview_signature = signature
            self._last_preview_upload_success_at = now
        except Exception as exc:
            self._log_error(f"Cloud preview upload error: {exc}")

    def _listen_for_events(self):
        response = self._event_session.get(
            self._url(f"/api/devices/{web_server._get_device_id()}/events"),
            headers=self._headers(),
            stream=True,
            timeout=(10, 90),
        )
        response.raise_for_status()
        # The connection is up, so whatever failures preceded it are cleared.
        self._event_backoff_seconds = self.EVENT_BACKOFF_MIN_SECONDS
        print("MetroClock cloud realtime connected.", flush=True)
        event_name = None
        data_lines = []
        for raw_line in response.iter_lines(decode_unicode=True):
            if self._stop.is_set():
                break
            line = raw_line or ""
            if line.startswith(":"):
                continue
            if not line:
                self._handle_event_message(event_name, data_lines)
                event_name = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())

    def _handle_event_message(self, event_name, data_lines):
        if not data_lines:
            return
        try:
            payload = json.loads("\n".join(data_lines))
        except Exception:
            payload = {}
        event_type = str(event_name or payload.get("type") or "").strip()
        if event_type == "commands_available":
            self._poll_commands_now()

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
        if "AMBIENT_SCENE" in changed:
            web_server.set_ambient_scene(changed["AMBIENT_SCENE"])

    def _ack_command(self, command_id: str, result: Dict[str, Any]):
        response = self._session.post(
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
            "cloud_preview_seconds": MetroClockCloudAgent._preview_seconds(),
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
