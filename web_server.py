import importlib
import socket
import subprocess
import threading

import config
import config_manager
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="web", static_url_path="")

_mode_lock = threading.Lock()
_display_mode = None
_weather_preview_lock = threading.Lock()
_weather_preview = None


def get_display_mode() -> str:
    with _mode_lock:
        global _display_mode
        if _display_mode is None:
            _display_mode = getattr(config, "DISPLAY_MODE", "metro")
        return _display_mode


def set_display_mode(mode: str):
    with _mode_lock:
        global _display_mode
        _display_mode = mode


def get_weather_preview():
    with _weather_preview_lock:
        return _weather_preview


def preview_weather_data(preview: str, units: str) -> dict:
    table = {
        "clear_day":    ("Clear",        "clear sky",      "01d"),
        "clear_night":  ("Clear",        "clear sky",      "01n"),
        "cloudy":       ("Clouds",       "overcast clouds","04d"),
        "drizzle":      ("Drizzle",      "light drizzle",  "09d"),
        "rain":         ("Rain",         "light rain",     "10d"),
        "thunderstorm": ("Thunderstorm", "thunderstorm",   "11d"),
        "snow":         ("Snow",         "light snow",     "13d"),
    }
    main, description, icon_code = table.get(preview, table["clear_day"])
    return {
        "main": {"temp": 72 if units == "imperial" else 22},
        "weather": [{"main": main, "description": description, "icon": icon_code}],
    }


def set_weather_preview(preview):
    with _weather_preview_lock:
        global _weather_preview
        _weather_preview = preview


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
    for k, v in cfg.items():
        if k in key_fields:
            result[k + "_set"] = bool(v)
        else:
            result[k] = v
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
    return jsonify(masked)


@app.route("/api/settings")
def api_settings_get():
    cfg = config_manager.read_config()
    return jsonify(_mask_config(cfg))


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.get_json(force=True) or {}
    try:
        changed = config_manager.write_config(data)
        if "DISPLAY_MODE" in changed:
            set_display_mode(changed["DISPLAY_MODE"])
        return jsonify({"ok": True, "changed": list(changed.keys())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mode", methods=["POST"])
def api_mode():
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "").lower()
    if mode not in ("metro", "weather", "flight", "ambient"):
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


@app.route("/api/wifi/scan")
def api_wifi_scan():
    try:
        output = subprocess.check_output(
            ["iwlist", "wlan0", "scan"], stderr=subprocess.DEVNULL, text=True
        )
        ssids = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("ESSID:"):
                ssid = line[len("ESSID:"):].strip().strip('"')
                if ssid and ssid not in ssids:
                    ssids.append(ssid)
        return jsonify({"ok": True, "ssids": ssids})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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
        with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w") as f:
            f.write(wpa_conf)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

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
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/reboot", methods=["POST"])
def api_reboot():
    try:
        subprocess.Popen(["reboot"])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def start_server():
    port = getattr(config, "WEB_SERVER_PORT", 80)

    def _run():
        app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
