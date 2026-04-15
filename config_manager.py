import re
import os
import importlib

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")

EDITABLE_FIELDS = {
    "WMATA_API_KEY",
    "WMATA_STATION_CODE",
    "OPENWEATHER_API_KEY",
    "OPENWEATHER_CITY_ID",
    "WEATHER_UNITS",
    "AVIATIONSTACK_API_KEY",
    "FLIGHT_NUMBER",
    "DISPLAY_MODE",
    "MATRIX_BRIGHTNESS",
    "WEB_SERVER_PORT",
    "SETUP_MODE",
}


def read_config() -> dict:
    import config
    importlib.reload(config)
    result = {}
    for field in EDITABLE_FIELDS:
        result[field] = getattr(config, field, None)
    return result


def write_config(updates: dict) -> dict:
    filtered = {k: v for k, v in updates.items() if k in EDITABLE_FIELDS}
    if not filtered:
        return {}

    with open(CONFIG_PATH, "r") as f:
        content = f.read()

    changed = {}
    for key, value in filtered.items():
        if isinstance(value, str):
            new_val = f'"{value}"'
        elif isinstance(value, bool):
            new_val = "True" if value else "False"
        else:
            new_val = str(value)

        pattern = rf'^({re.escape(key)}\s*=\s*)(.+)$'
        replacement = rf'\g<1>{new_val}'
        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if count > 0:
            content = new_content
            changed[key] = value
        else:
            # Field not present — append it
            content += f'\n{key} = {new_val}\n'
            changed[key] = value

    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(content)
    os.replace(tmp_path, CONFIG_PATH)

    import config
    importlib.reload(config)

    return changed
