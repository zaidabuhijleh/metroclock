import hmac
import importlib
import io
import os
import socket
import subprocess
import threading
import time
import uuid

import config
import config_manager
from core.modes import DEFAULT_MODE_CATALOG
from flask import Flask, Response, jsonify, request, send_from_directory

API_VERSION = "1.0"

CLOCK_FONT_STYLE_OPTIONS = ("matrix",)
CLOCK_SIZE_OPTIONS = (0.5, 0.75, 1.0)
CLOCK_WIDGET_SCROLL_MODE_OPTIONS = ("metro", "ticker")
CLOCK_WIDGET_PRESET_OPTIONS = (
    {"key": "auto", "label": "Auto (Layout + Count)", "layout": "mixed", "widget_count": None},
    {"key": "horizontal_single", "label": "Top Clock + Bottom Widget", "layout": "horizontal", "widget_count": 1},
    {"key": "horizontal_single_top", "label": "Top Widget + Bottom Clock", "layout": "horizontal", "widget_count": 1},
    {"key": "horizontal_split", "label": "Top Clock + Split Bottom Widgets", "layout": "horizontal", "widget_count": 2},
    {"key": "vertical_focus", "label": "Left Clock + Right Focus Widget", "layout": "vertical", "widget_count": 1},
    {"key": "vertical_split_focus", "label": "Left Clock Stack + Right Focus Widget", "layout": "vertical", "widget_count": 2},
    {"key": "vertical_split_focus_top", "label": "Left Mini + Left Clock + Right Focus Widget", "layout": "vertical", "widget_count": 2},
)

WRITE_ENDPOINTS = {
    "/api/settings",
    "/api/mode",
    "/api/weather/preview",
    "/api/ambient/scene",
    "/api/pomodoro/action",
    "/api/wifi/connect",
    "/api/restart",
    "/api/reboot",
}

app = Flask(__name__, static_folder="web", static_url_path="")


class RuntimeState:
    """Thread-safe runtime settings and memoized metadata."""

    _AMBIENT_UNSET = object()

    def __init__(self):
        self._mode_lock = threading.Lock()
        self._display_mode = None

        self._weather_preview_lock = threading.Lock()
        self._weather_preview = None

        self._ambient_scene_lock = threading.Lock()
        self._ambient_scene = self._AMBIENT_UNSET  # None = auto-cycle; scene key string = pinned

        self._pomodoro_lock = threading.Lock()
        self._pomodoro_state = None

        self._brightness_lock = threading.Lock()
        self._brightness = None

        self._device_id_lock = threading.Lock()
        self._device_id = None

        self._app_version_lock = threading.Lock()
        self._app_version = None

        self._preview_lock = threading.Lock()
        self._preview_frame = None  # latest PIL.Image, copied on read

    @staticmethod
    def _device_id_path():
        return os.environ.get("METROCLOCK_DEVICE_ID_PATH", "/etc/metroclock/device_id")

    def get_device_id(self):
        with self._device_id_lock:
            if self._device_id:
                return self._device_id

            env_id = str(os.environ.get("METROCLOCK_DEVICE_ID", "") or "").strip()
            if env_id:
                self._device_id = env_id
                return self._device_id

            path = self._device_id_path()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stored = f.read().strip()
                if stored:
                    self._device_id = stored
                    return self._device_id
            except Exception:
                pass

            generated = uuid.uuid4().hex
            directory = os.path.dirname(path)
            try:
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(generated + "\n")
            except Exception:
                # Keep generated id in-memory even if file write fails.
                pass

            self._device_id = generated
            return self._device_id

    def get_app_version(self):
        with self._app_version_lock:
            if self._app_version:
                return self._app_version

            env_version = str(os.environ.get("METROCLOCK_APP_VERSION", "") or "").strip()
            if env_version:
                self._app_version = env_version
                return self._app_version

            app_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                git_ver = subprocess.check_output(
                    ["git", "describe", "--tags", "--always", "--dirty"],
                    cwd=app_dir,
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                if git_ver:
                    self._app_version = git_ver
                    return self._app_version
            except Exception:
                pass

            for filename in ("version.txt", "VERSION"):
                try:
                    with open(os.path.join(app_dir, filename), "r", encoding="utf-8") as f:
                        file_ver = f.read().strip()
                    if file_ver:
                        self._app_version = file_ver
                        return self._app_version
                except Exception:
                    pass

            self._app_version = "dev"
            return self._app_version

    def get_display_mode(self) -> str:
        with self._mode_lock:
            if self._display_mode is None:
                self._display_mode = getattr(config, "DISPLAY_MODE", "metro")
            return self._display_mode

    def set_display_mode(self, mode: str):
        with self._mode_lock:
            self._display_mode = mode

    def get_brightness(self):
        with self._brightness_lock:
            if self._brightness is None:
                self._brightness = getattr(config, "MATRIX_BRIGHTNESS", 30)
            return self._brightness

    def set_brightness(self, brightness):
        with self._brightness_lock:
            self._brightness = max(1, min(100, int(brightness)))

    def set_latest_frame(self, image):
        # Keep a defensive copy; the render loop mutates its own buffer.
        try:
            snapshot = image.copy()
        except Exception:
            return
        with self._preview_lock:
            self._preview_frame = snapshot

    def get_latest_frame(self):
        with self._preview_lock:
            return self._preview_frame

    def get_weather_preview(self):
        with self._weather_preview_lock:
            return self._weather_preview

    @staticmethod
    def preview_weather_data(preview: str, units: str) -> dict:
        table = {
            "clear_day": ("Clear", "clear sky", "01d"),
            "clear_night": ("Clear", "clear sky", "01n"),
            "cloudy": ("Clouds", "overcast clouds", "04d"),
            "drizzle": ("Drizzle", "light drizzle", "09d"),
            "rain": ("Rain", "light rain", "10d"),
            "thunderstorm": ("Thunderstorm", "thunderstorm", "11d"),
            "snow": ("Snow", "light snow", "13d"),
        }
        main, description, icon_code = table.get(preview, table["clear_day"])
        return {
            "main": {"temp": 72 if units == "imperial" else 22},
            "weather": [{"main": main, "description": description, "icon": icon_code}],
        }

    def set_weather_preview(self, preview):
        with self._weather_preview_lock:
            self._weather_preview = preview

    @staticmethod
    def normalize_ambient_scene(scene):
        aliases = {
            "city_night": "city_day",
            "forest": "sunset_trail",
            "winter_cabin": "alpine_cabin",
            "space": "coral_reef",
        }
        if scene in aliases:
            scene = aliases[scene]

        if scene in ("", None, "auto"):
            return None
        return str(scene)

    def get_ambient_scene(self):
        with self._ambient_scene_lock:
            if self._ambient_scene is self._AMBIENT_UNSET:
                configured = getattr(config, "AMBIENT_SCENE", "auto")
                self._ambient_scene = self.normalize_ambient_scene(configured)
            return self._ambient_scene

    def set_ambient_scene(self, scene):
        with self._ambient_scene_lock:
            self._ambient_scene = self.normalize_ambient_scene(scene)

    @staticmethod
    def _coerce_int(value, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = int(default)
        return max(minimum, min(maximum, parsed))

    @staticmethod
    def _normalize_pomodoro_layout(value) -> str:
        raw = str(value or "mode_time_task").strip().lower()
        if raw in {"mode_time", "mode_time_task"}:
            return raw
        return "mode_time_task"

    @staticmethod
    def _parse_pomodoro_tasks(raw_value):
        text = str(raw_value or "")
        tasks = []
        for line in text.splitlines():
            item = line.strip()
            if item:
                tasks.append(item)
        return tasks

    def _pomodoro_settings(self) -> dict:
        return {
            "focus_minutes": self._coerce_int(getattr(config, "POMODORO_FOCUS_MINUTES", 25), 25, 1, 180),
            "short_break_minutes": self._coerce_int(getattr(config, "POMODORO_SHORT_BREAK_MINUTES", 5), 5, 1, 60),
            "long_break_minutes": self._coerce_int(getattr(config, "POMODORO_LONG_BREAK_MINUTES", 15), 15, 1, 120),
            "long_break_every": self._coerce_int(getattr(config, "POMODORO_LONG_BREAK_EVERY", 4), 4, 2, 12),
            "auto_start_breaks": bool(getattr(config, "POMODORO_AUTO_START_BREAKS", True)),
            "auto_start_focus": bool(getattr(config, "POMODORO_AUTO_START_FOCUS", False)),
            "layout": self._normalize_pomodoro_layout(getattr(config, "POMODORO_LAYOUT", "mode_time_task")),
            "tasks": self._parse_pomodoro_tasks(getattr(config, "POMODORO_TODO_ITEMS", "")),
        }

    @staticmethod
    def _phase_duration_seconds(phase: str, settings: dict) -> int:
        key = str(phase or "focus").strip().lower()
        if key == "short_break":
            return int(settings["short_break_minutes"]) * 60
        if key == "long_break":
            return int(settings["long_break_minutes"]) * 60
        return int(settings["focus_minutes"]) * 60

    def _ensure_pomodoro_state_locked(self, settings: dict):
        if self._pomodoro_state is not None:
            return
        self._pomodoro_state = {
            "phase": "focus",
            "running": False,
            "phase_end_ts": None,
            "remaining_seconds": self._phase_duration_seconds("focus", settings),
            "completed_focus_sessions": 0,
            "focus_sessions_in_cycle": 0,
        }

    def _advance_pomodoro_phase_locked(self, state: dict, settings: dict):
        phase = str(state.get("phase", "focus") or "focus").strip().lower()

        if phase == "focus":
            state["completed_focus_sessions"] = int(state.get("completed_focus_sessions", 0)) + 1
            state["focus_sessions_in_cycle"] = int(state.get("focus_sessions_in_cycle", 0)) + 1
            if state["focus_sessions_in_cycle"] >= int(settings["long_break_every"]):
                state["focus_sessions_in_cycle"] = 0
                next_phase = "long_break"
            else:
                next_phase = "short_break"
            auto_start = bool(settings["auto_start_breaks"])
        else:
            next_phase = "focus"
            auto_start = bool(settings["auto_start_focus"])

        state["phase"] = next_phase
        total_seconds = self._phase_duration_seconds(next_phase, settings)
        return auto_start, total_seconds

    def _sync_pomodoro_clock_locked(self, settings: dict, now: float):
        state = self._pomodoro_state
        if state is None:
            return

        if not bool(state.get("running", False)):
            phase_total = self._phase_duration_seconds(str(state.get("phase", "focus")), settings)
            state["remaining_seconds"] = max(0, min(int(state.get("remaining_seconds", phase_total)), phase_total))
            state["phase_end_ts"] = None
            return

        phase_end_ts = state.get("phase_end_ts")
        if phase_end_ts is None:
            remaining = max(1, int(state.get("remaining_seconds", self._phase_duration_seconds(state.get("phase", "focus"), settings))))
            state["phase_end_ts"] = now + remaining
            state["remaining_seconds"] = remaining
            return

        remaining_float = float(phase_end_ts) - float(now)
        if remaining_float > 0:
            state["remaining_seconds"] = max(0, int(remaining_float + 0.999))
            return

        overdue = -remaining_float
        while True:
            auto_start, next_total = self._advance_pomodoro_phase_locked(state, settings)
            if not auto_start:
                state["running"] = False
                state["phase_end_ts"] = None
                state["remaining_seconds"] = next_total
                return

            if overdue < next_total:
                remaining = max(0.0, float(next_total) - overdue)
                state["running"] = True
                state["phase_end_ts"] = now + remaining
                state["remaining_seconds"] = max(0, int(remaining + 0.999))
                return

            overdue -= float(next_total)

    def _pomodoro_public_state_locked(self, settings: dict, now: float) -> dict:
        state = self._pomodoro_state or {}
        phase = str(state.get("phase", "focus") or "focus").strip().lower()
        total_seconds = self._phase_duration_seconds(phase, settings)

        if bool(state.get("running", False)) and state.get("phase_end_ts") is not None:
            remaining_seconds = max(0, int(float(state["phase_end_ts"]) - float(now) + 0.999))
        else:
            remaining_seconds = max(0, int(state.get("remaining_seconds", total_seconds)))

        elapsed = max(0, total_seconds - remaining_seconds)
        progress = 0.0 if total_seconds <= 0 else min(1.0, max(0.0, float(elapsed) / float(total_seconds)))

        focus_in_cycle = int(state.get("focus_sessions_in_cycle", 0))
        long_every = int(settings["long_break_every"])
        if phase == "focus":
            cycle_position = min(long_every, max(1, focus_in_cycle + 1))
        elif phase == "long_break":
            cycle_position = long_every
        else:
            cycle_position = min(long_every, max(1, focus_in_cycle))

        return {
            "phase": phase,
            "running": bool(state.get("running", False)),
            "remaining_seconds": remaining_seconds,
            "total_seconds": total_seconds,
            "progress": progress,
            "completed_focus_sessions": int(state.get("completed_focus_sessions", 0)),
            "focus_sessions_in_cycle": focus_in_cycle,
            "cycle_position": cycle_position,
            "long_break_every": long_every,
            "auto_start_breaks": bool(settings["auto_start_breaks"]),
            "auto_start_focus": bool(settings["auto_start_focus"]),
            "layout": str(settings.get("layout", "mode_time_task")),
            "current_task": (settings.get("tasks") or [""])[0],
            "task_count": len(settings.get("tasks") or []),
        }

    def get_pomodoro_state(self) -> dict:
        with self._pomodoro_lock:
            settings = self._pomodoro_settings()
            self._ensure_pomodoro_state_locked(settings)
            now = time.time()
            self._sync_pomodoro_clock_locked(settings, now)
            return self._pomodoro_public_state_locked(settings, now)

    def pomodoro_action(self, action: str) -> dict:
        action_key = str(action or "").strip().lower()
        valid_actions = {"start", "pause", "toggle", "reset", "skip"}
        if action_key not in valid_actions:
            raise ValueError("Invalid action")

        with self._pomodoro_lock:
            settings = self._pomodoro_settings()
            self._ensure_pomodoro_state_locked(settings)
            now = time.time()
            self._sync_pomodoro_clock_locked(settings, now)
            state = self._pomodoro_state

            if action_key == "toggle":
                action_key = "pause" if bool(state.get("running", False)) else "start"

            if action_key == "start":
                if not bool(state.get("running", False)):
                    remaining = max(0, int(state.get("remaining_seconds", 0)))
                    if remaining <= 0:
                        remaining = self._phase_duration_seconds(str(state.get("phase", "focus")), settings)
                    state["running"] = True
                    state["phase_end_ts"] = now + float(remaining)
                    state["remaining_seconds"] = remaining
            elif action_key == "pause":
                if bool(state.get("running", False)):
                    remaining = max(0, int(float(state.get("phase_end_ts", now)) - now + 0.999))
                    state["running"] = False
                    state["phase_end_ts"] = None
                    state["remaining_seconds"] = remaining
            elif action_key == "reset":
                state["phase"] = "focus"
                state["running"] = False
                state["phase_end_ts"] = None
                state["remaining_seconds"] = self._phase_duration_seconds("focus", settings)
                state["completed_focus_sessions"] = 0
                state["focus_sessions_in_cycle"] = 0
            elif action_key == "skip":
                auto_start, next_total = self._advance_pomodoro_phase_locked(state, settings)
                if auto_start:
                    state["running"] = True
                    state["phase_end_ts"] = now + float(next_total)
                    state["remaining_seconds"] = next_total
                else:
                    state["running"] = False
                    state["phase_end_ts"] = None
                    state["remaining_seconds"] = next_total

            now = time.time()
            self._sync_pomodoro_clock_locked(settings, now)
            return self._pomodoro_public_state_locked(settings, now)


_runtime_state = RuntimeState()


def _configured_api_token():
    token = str(os.environ.get("METROCLOCK_API_TOKEN", "") or "").strip()
    return token or None


def _extract_api_token():
    header_token = request.headers.get("X-MetroClock-Token")
    if header_token:
        return str(header_token).strip()

    auth_header = request.headers.get("Authorization", "")
    if isinstance(auth_header, str) and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


@app.before_request
def _authorize_writes():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path not in WRITE_ENDPOINTS:
        return None

    expected_token = _configured_api_token()
    if not expected_token:
        return None

    provided_token = _extract_api_token() or ""
    if hmac.compare_digest(provided_token, expected_token):
        return None

    return jsonify({
        "ok": False,
        "error": "Unauthorized",
        "hint": "Provide X-MetroClock-Token or Authorization: Bearer <token>",
    }), 401


def _get_device_id():
    return _runtime_state.get_device_id()


def _get_app_version():
    return _runtime_state.get_app_version()


def get_display_mode() -> str:
    return _runtime_state.get_display_mode()


def set_display_mode(mode: str):
    _runtime_state.set_display_mode(mode)


def get_brightness():
    return _runtime_state.get_brightness()


def set_brightness(brightness):
    _runtime_state.set_brightness(brightness)


def set_latest_frame(image):
    _runtime_state.set_latest_frame(image)


def get_latest_frame():
    return _runtime_state.get_latest_frame()


def get_weather_preview():
    return _runtime_state.get_weather_preview()


def preview_weather_data(preview: str, units: str) -> dict:
    return _runtime_state.preview_weather_data(preview, units)


def set_weather_preview(preview):
    _runtime_state.set_weather_preview(preview)


def _normalize_ambient_scene(scene):
    return _runtime_state.normalize_ambient_scene(scene)


def get_ambient_scene():
    return _runtime_state.get_ambient_scene()


def set_ambient_scene(scene):
    _runtime_state.set_ambient_scene(scene)


def get_pomodoro_state():
    return _runtime_state.get_pomodoro_state()


def pomodoro_action(action: str):
    return _runtime_state.pomodoro_action(action)


def _get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def _mask_config(cfg: dict) -> dict:
    key_fields = {
        "WMATA_API_KEY",
        "OPENWEATHER_API_KEY",
        "AVIATIONSTACK_API_KEY",
    }
    result = {}
    for key, value in cfg.items():
        if key in key_fields:
            result[key + "_set"] = bool(value)
        else:
            result[key] = value
    return result


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/status")
def api_status():
    importlib.reload(config)
    cfg = config_manager.read_config()
    masked = _mask_config(cfg)
    masked["ip"] = _get_ip()
    masked["hostname"] = socket.gethostname()
    masked["display_mode"] = get_display_mode()
    masked["weather_preview"] = get_weather_preview()
    masked["ambient_scene"] = get_ambient_scene()
    masked["pomodoro_state"] = get_pomodoro_state()
    masked["device_id"] = _get_device_id()
    masked["app_version"] = _get_app_version()
    masked["api_version"] = API_VERSION
    masked["write_auth_required"] = bool(_configured_api_token())
    return jsonify(masked)


@app.route("/api/settings")
def api_settings_get():
    cfg = config_manager.read_config()
    return jsonify(_mask_config(cfg))


@app.route("/preview.png")
def preview_png():
    frame = get_latest_frame()
    if frame is None:
        return jsonify({"ok": False, "error": "No frame yet"}), 503
    buf = io.BytesIO()
    try:
        frame.convert("RGB").save(buf, format="PNG")
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return Response(
        buf.getvalue(),
        mimetype="image/png",
        headers={"Cache-Control": "no-store"},
    )


@app.route("/preview.mjpg")
def preview_mjpg():
    boundary = "frame"
    target_fps = 20
    target_interval = 1.0 / target_fps
    jpeg_quality = 85

    def generate():
        while True:
            frame = get_latest_frame()
            if frame is None:
                time.sleep(target_interval)
                continue
            buf = io.BytesIO()
            try:
                frame.convert("RGB").save(buf, format="JPEG", quality=jpeg_quality)
            except Exception:
                time.sleep(target_interval)
                continue
            jpeg = buf.getvalue()
            yield (
                b"--" + boundary.encode() + b"\r\n"
                + b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                + jpeg
                + b"\r\n"
            )
            time.sleep(target_interval)

    return Response(
        generate(),
        mimetype=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-store", "Connection": "close"},
    )


@app.route("/api/clock/styles")
def api_clock_styles():
    return jsonify({
        "clock_font_style": {
            "key": "CLOCK_FONT_STYLE",
            "default": "matrix",
            "options": list(CLOCK_FONT_STYLE_OPTIONS),
        },
        "clock_size": {
            "key": "CLOCK_SIZE",
            "default": 1.0,
            "options": list(CLOCK_SIZE_OPTIONS),
        },
        "clock_overlays": {
            "show_date_key": "CLOCK_SHOW_DATE",
            "show_ampm_key": "CLOCK_SHOW_AMPM",
            "defaults": {
                "show_date": True,
                "show_ampm": True,
            },
        },
        "clock_widget_preset": {
            "key": "CLOCK_WIDGET_PRESET",
            "default": "auto",
            "options": list(CLOCK_WIDGET_PRESET_OPTIONS),
        },
        "clock_widget_scroll_mode": {
            "keys": {
                "primary": "CLOCK_WIDGET_SCROLL_MODE_PRIMARY",
                "secondary": "CLOCK_WIDGET_SCROLL_MODE_SECONDARY",
                "legacy": "CLOCK_WIDGET_SCROLL_MODE",
            },
            "default": "metro",
            "options": list(CLOCK_WIDGET_SCROLL_MODE_OPTIONS),
            "scroll_widget_sources": ["metro", "stocks", "sports", "flight"],
        },
        "clock_color_overrides": {
            "format": "#RRGGBB",
            "allow_empty": True,
            "keys": [
                "CLOCK_COLOR_PRIMARY",
                "CLOCK_COLOR_ACCENT",
                "CLOCK_COLOR_ACCENT_2",
                "CLOCK_COLOR_DIM",
                "CLOCK_COLOR_BG",
            ],
        },
    })


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.get_json(force=True) or {}
    try:
        changed = config_manager.write_config(data)
        if "DISPLAY_MODE" in changed:
            set_display_mode(changed["DISPLAY_MODE"])
        if "MATRIX_BRIGHTNESS" in changed:
            set_brightness(changed["MATRIX_BRIGHTNESS"])
        if "AMBIENT_SCENE" in changed:
            set_ambient_scene(changed["AMBIENT_SCENE"])
        return jsonify({"ok": True, "changed": list(changed.keys())})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/mode", methods=["POST"])
def api_mode():
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "").lower()
    if not DEFAULT_MODE_CATALOG.is_supported(mode):
        return jsonify({"ok": False, "error": "Invalid mode"}), 400
    set_display_mode(mode)
    return jsonify({"ok": True, "mode": mode})


@app.route("/api/weather/preview", methods=["POST"])
def api_weather_preview():
    data = request.get_json(force=True) or {}
    preview = data.get("preview")

    if preview in ("", None, "live"):
        set_weather_preview(None)
        return jsonify({"ok": True, "preview": None})

    allowed_previews = {
        "clear_day",
        "clear_night",
        "cloudy",
        "drizzle",
        "rain",
        "thunderstorm",
        "snow",
    }
    if preview not in allowed_previews:
        return jsonify({"ok": False, "error": "Invalid weather preview"}), 400

    set_weather_preview(preview)
    return jsonify({"ok": True, "preview": preview})


@app.route("/api/ambient/scene", methods=["POST"])
def api_ambient_scene():
    data = request.get_json(force=True) or {}
    scene = _normalize_ambient_scene(data.get("scene"))

    allowed = {"beach", "city_day", "sunset_trail", "alpine_cabin", "coral_reef", "lofi_cat"}
    if scene is not None and scene not in allowed:
        return jsonify({"ok": False, "error": "Invalid scene"}), 400
    set_ambient_scene(scene)
    config_manager.write_config({"AMBIENT_SCENE": scene or "auto"})
    return jsonify({"ok": True, "scene": scene})


@app.route("/api/pomodoro/state")
def api_pomodoro_state():
    return jsonify({"ok": True, "state": get_pomodoro_state()})


@app.route("/api/pomodoro/action", methods=["POST"])
def api_pomodoro_action():
    data = request.get_json(force=True) or {}
    action = str(data.get("action", "") or "").strip().lower()
    try:
        state = pomodoro_action(action)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "state": state})


@app.route("/api/wifi/scan")
def api_wifi_scan():
    try:
        output = subprocess.check_output(
            ["iwlist", "wlan0", "scan"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        ssids = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("ESSID:"):
                ssid = line[len("ESSID:"):].strip().strip('"')
                if ssid and ssid not in ssids:
                    ssids.append(ssid)
        return jsonify({"ok": True, "ssids": ssids})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/wifi/connect", methods=["POST"])
def api_wifi_connect():
    data = request.get_json(force=True) or {}
    ssid = data.get("ssid", "")
    password = data.get("password", "")
    if not ssid:
        return jsonify({"ok": False, "error": "SSID required"}), 400

    wpa_conf = (
        "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
        "update_config=1\ncountry=US\n\n"
        f'network={{\n    ssid="{ssid}"\n    psk="{password}"\n}}\n'
    )

    try:
        with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w", encoding="utf-8") as f:
            f.write(wpa_conf)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    config_manager.write_config({"SETUP_MODE": False})

    def _reconfigure():
        subprocess.call(["wpa_cli", "-i", "wlan0", "reconfigure"])

    threading.Thread(target=_reconfigure, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/restart", methods=["POST"])
def api_restart():
    try:
        subprocess.Popen(["systemctl", "restart", "metroclock"])
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/reboot", methods=["POST"])
def api_reboot():
    try:
        subprocess.Popen(["reboot"])
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


def start_server():
    port = getattr(config, "WEB_SERVER_PORT", 80)

    def _run():
        app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
