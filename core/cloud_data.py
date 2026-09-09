"""Client for the cloud data proxy.

A clock holds no provider API keys. Shipping credentials inside an SD card image
would hand every customer working keys, which provider terms prohibit, so the
cloud service makes upstream calls on the device's behalf and this module talks
to it. See cloud_api/app/upstream.py for the other half.

A locally configured key still wins: developer units and anyone who supplies
their own key keep calling the provider directly, and nothing depends on the
cloud being reachable.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests

import config
import web_server

# Reused so a fetch does not pay a fresh TLS handshake; the handshake costs more
# than the request itself on a Pi Zero.
_session = requests.Session()

DEFAULT_TIMEOUT_SECONDS = 12


class CloudDataError(Exception):
    """The proxy could not answer. Carries a short reason fit for a 64px panel."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def is_available() -> bool:
    """True when this clock is paired and can use the proxy."""
    return bool(
        getattr(config, "METROCLOCK_CLOUD_ENABLED", False)
        and str(getattr(config, "METROCLOCK_CLOUD_BASE_URL", "") or "").strip()
        and str(getattr(config, "METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip()
    )


def signature() -> tuple:
    """Fold into a widget's config signature.

    Without this a clock that pairs during onboarding would not notice: the
    flight widget sleeps up to six hours between polls, so it would sit on a
    placeholder long after it could have fetched. The token itself is reduced to
    a boolean rather than copied around.
    """
    return (
        bool(getattr(config, "METROCLOCK_CLOUD_ENABLED", False)),
        str(getattr(config, "METROCLOCK_CLOUD_BASE_URL", "") or "").strip(),
        bool(str(getattr(config, "METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip()),
    )


def get(path: str, params: dict[str, Any], timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    """GET from this device's data proxy, or raise CloudDataError."""
    if not is_available():
        raise CloudDataError("not paired")

    base_url = str(getattr(config, "METROCLOCK_CLOUD_BASE_URL", "") or "").strip().rstrip("/") + "/"
    token = str(getattr(config, "METROCLOCK_CLOUD_DEVICE_TOKEN", "") or "").strip()
    device_id = web_server._get_device_id()
    url = urljoin(base_url, f"api/devices/{device_id}/data/{path.lstrip('/')}")

    try:
        response = _session.get(
            url,
            params={k: v for k, v in params.items() if v not in (None, "")},
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
    except Exception:
        raise CloudDataError("no network")

    if response.status_code == 401 or response.status_code == 403:
        raise CloudDataError("not paired")
    if response.status_code == 429:
        raise CloudDataError("rate limited")
    if response.status_code == 503:
        raise CloudDataError("unavailable")
    if response.status_code >= 400:
        raise CloudDataError(f"http {response.status_code}")

    try:
        return response.json()
    except Exception:
        raise CloudDataError("bad data")
