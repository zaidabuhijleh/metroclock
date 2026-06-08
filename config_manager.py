import importlib
import json
import os
import threading

import config


EDITABLE_FIELDS = set(getattr(config, "RUNTIME_EDITABLE_FIELDS", set()))
CONFIG_LOCK = threading.RLock()
_LAST_RUNTIME_MTIME = None


def _runtime_config_mtime():
    try:
        return os.path.getmtime(_runtime_config_path())
    except FileNotFoundError:
        return None
    except Exception:
        return None


def reload_config(force=True):
    global _LAST_RUNTIME_MTIME
    with CONFIG_LOCK:
        current_mtime = _runtime_config_mtime()
        if not force and _LAST_RUNTIME_MTIME == current_mtime:
            return config
        reloaded = importlib.reload(config)
        _LAST_RUNTIME_MTIME = _runtime_config_mtime()
        return reloaded


def reload_config_if_changed():
    return reload_config(force=False)


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


def _apply_updates_to_live_config(updates: dict):
    for key, value in updates.items():
        if not hasattr(config, key):
            continue
        setattr(config, key, config._coerce_value(value, getattr(config, key)))


def read_config() -> dict:
    with CONFIG_LOCK:
        reload_config_if_changed()
        result = {}
        for field in EDITABLE_FIELDS:
            result[field] = getattr(config, field, None)
        return result


def write_config(updates: dict) -> dict:
    global _LAST_RUNTIME_MTIME
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
        _apply_updates_to_live_config(changed)
        _LAST_RUNTIME_MTIME = _runtime_config_mtime()
        return changed
