import importlib
import json
import os
import threading
import time

import config


EDITABLE_FIELDS = set(getattr(config, "RUNTIME_EDITABLE_FIELDS", set()))
CONFIG_LOCK = threading.RLock()

# Reloading re-executes all of config.py and re-reads the runtime JSON from
# disk. Callers on the render path ask for it several times per frame, so
# coalesce those into one reload per interval. Writers pass force=True, which
# means a setting change still takes effect immediately.
RELOAD_MIN_INTERVAL_SECONDS = 0.5
_last_reload_at = 0.0


def reload_config(force: bool = False):
    global _last_reload_at
    with CONFIG_LOCK:
        now = time.monotonic()
        if not force and (now - _last_reload_at) < RELOAD_MIN_INTERVAL_SECONDS:
            return config
        _last_reload_at = now
        return importlib.reload(config)


def _runtime_config_path() -> str:
    return getattr(config, "get_runtime_config_path", lambda: "/etc/metroclock/config.json")()


def _load_runtime_config() -> dict:
    path = _runtime_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_runtime_config(data: dict):
    path = _runtime_config_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, path)


def read_config() -> dict:
    with CONFIG_LOCK:
        reload_config()
        result = {}
        for field in EDITABLE_FIELDS:
            result[field] = getattr(config, field, None)
        return result


def write_config(updates: dict) -> dict:
    filtered = {k: v for k, v in updates.items() if k in EDITABLE_FIELDS}
    if not filtered:
        return {}

    with CONFIG_LOCK:
        runtime_data = _load_runtime_config()
        changed = {}
        for key, value in filtered.items():
            runtime_data[key] = value
            changed[key] = value

        _save_runtime_config(runtime_data)
        reload_config(force=True)  # a write must be visible immediately
        return changed
