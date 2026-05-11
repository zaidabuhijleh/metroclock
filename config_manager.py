import importlib
import json
import os

import config


EDITABLE_FIELDS = set(getattr(config, "RUNTIME_EDITABLE_FIELDS", set()))


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
    importlib.reload(config)
    result = {}
    for field in EDITABLE_FIELDS:
        result[field] = getattr(config, field, None)
    return result


def write_config(updates: dict) -> dict:
    filtered = {k: v for k, v in updates.items() if k in EDITABLE_FIELDS}
    if not filtered:
        return {}

    runtime_data = _load_runtime_config()
    changed = {}
    for key, value in filtered.items():
        runtime_data[key] = value
        changed[key] = value

    _save_runtime_config(runtime_data)
    importlib.reload(config)
    return changed
