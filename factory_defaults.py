"""The settings a factory-fresh clock boots with.

Two callers have to agree on this and must not drift apart:
``scripts/reset_device_config.sh`` when an SD card image is built, and
``core/power.py`` when a user factory-resets a clock in the field. If the two
disagreed, a reset unit would behave differently from a brand-new one, and that
is the kind of difference you only discover in a customer's living room.

Anything absent here falls through to ``config.py``, which stays the source of
truth for defaults. That is why this list is deliberately short.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Optional

# Only the values a factory unit should boot with.
FACTORY_DEFAULTS: dict[str, Any] = {
    "DISPLAY_MODE": "clock",
    "CLOCK_SHOW_AMPM": False,
    "CLOCK_SHOW_DATE": False,
    "DISPLAY_SLEEP": False,
    "SETUP_MODE": False,
    "WIFI_SETUP_ENABLED": True,
    "WIFI_SETUP_FORCE_HOTSPOT_UNPAIRED": True,
    "WIFI_SETUP_HOTSPOT_SSID": "MetroClock-Setup",
    "WIFI_SETUP_HOTSPOT_IP": "192.168.4.1",
    "WIFI_SETUP_HOTSPOT_PASSWORD": "metroclock",
    "METROCLOCK_CLOUD_ENABLED": False,
    "METROCLOCK_CLOUD_BASE_URL": "",
    "METROCLOCK_CLOUD_DEVICE_TOKEN": "",
    "METROCLOCK_CLOUD_PAIRING_CODE": "",
}

# Provider keys that an image may ship with. These are device provisioning
# rather than user data, so a field factory reset carries them forward: wiping
# them would leave a reset clock permanently unable to fetch weather without a
# re-flash, which is not what "factory" means.
SHIPPED_KEY_FIELDS: dict[str, str] = {
    "OPENWEATHER_API_KEY": "METROCLOCK_IMAGE_OPENWEATHER_API_KEY",
    "WMATA_API_KEY": "METROCLOCK_IMAGE_WMATA_API_KEY",
    "AVIATIONSTACK_API_KEY": "METROCLOCK_IMAGE_AVIATIONSTACK_API_KEY",
}


# Where the image records the keys it shipped with. Deliberately separate from
# the runtime config: a user can enter their own provider key in the app and it
# lands in the very same config field as a shipped one. A reset that carried
# "whatever key is in the config" forward would therefore hand the next owner
# the previous owner's personal credentials. This file only ever holds what we
# put in the image.
PROVISIONING_PATH = "/etc/metroclock/provisioning.json"


def provisioning_path() -> str:
    return os.environ.get("METROCLOCK_PROVISIONING_PATH", PROVISIONING_PATH)


def load_provisioned(path: Optional[str] = None) -> dict[str, str]:
    """Read the keys baked into this image. Missing file means none."""
    try:
        with open(path or provisioning_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v or "").strip() for k, v in data.items() if k in SHIPPED_KEY_FIELDS}


def build(
    provisioned: Optional[Mapping[str, Any]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Return the config a factory-fresh unit should have.

    Provider keys come from the environment during an image build, and from the
    provisioning file during a field reset. They never come from the runtime
    config, which is what makes a reset safe to hand to a new owner.
    """
    env = os.environ if env is None else env
    provisioned = provisioned or {}

    data = dict(FACTORY_DEFAULTS)
    for setting, env_var in SHIPPED_KEY_FIELDS.items():
        from_env = str(env.get(env_var, "") or "").strip()
        data[setting] = from_env or str(provisioned.get(setting, "") or "").strip()
    return data


def provisioning_payload(data: Mapping[str, Any]) -> dict[str, str]:
    """The subset of a built config that belongs in the provisioning file."""
    return {k: str(data.get(k, "") or "") for k in SHIPPED_KEY_FIELDS}


def cleared_keys(previous: Optional[Mapping[str, Any]] = None) -> list[str]:
    """Settings present before the reset that it removes."""
    previous = previous or {}
    known = set(FACTORY_DEFAULTS) | set(SHIPPED_KEY_FIELDS)
    return sorted(k for k in previous if k not in known)
