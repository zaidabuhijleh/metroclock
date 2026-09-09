"""Upstream data providers, called on a device's behalf.

Provider API keys live here, read from the environment, and never reach a
device. Shipping a key inside an SD card image would hand every customer working
credentials, which every provider's terms prohibit, so clocks ask this service
instead and it makes the upstream call.

Responses are cached, so upstream usage scales with the number of *distinct
queries* rather than with the number of clocks in the field: fifty clocks
tracking the same flight cost one upstream request, not fifty.

The cache and the rate limiter are in-process, so like the SSE listener registry
and the device preview store they assume a single worker. With more than one,
they simply cache less and rate-limit per worker - never incorrectly.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

# One session per provider host: a fresh TLS handshake costs more than the
# request itself.
_session = requests.Session()

_cache_lock = threading.Lock()
_cache: dict[tuple, tuple[float, Any]] = {}
_MAX_CACHE_ENTRIES = 2000

_rate_lock = threading.Lock()
_rate_windows: dict[tuple, list[float]] = {}
_RATE_WINDOW_SECONDS = 3600

OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"
AVIATIONSTACK_BASE = "https://api.aviationstack.com/v1"

UPSTREAM_TIMEOUT_SECONDS = 10


class UpstreamError(Exception):
    """A failure to satisfy a proxied request.

    ``status_code`` is what the device should be told. ``detail`` is safe to
    return: it never contains an API key, because provider errors are mapped to
    fixed strings rather than echoed.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ------------------------------------------------------------------- caching


def cache_get(key: tuple) -> Any | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= now:
            _cache.pop(key, None)
            return None
        return value


def cache_put(key: tuple, value: Any, ttl_seconds: float) -> Any:
    now = time.monotonic()
    with _cache_lock:
        if len(_cache) >= _MAX_CACHE_ENTRIES:
            for expired in [k for k, (exp, _) in _cache.items() if exp <= now]:
                _cache.pop(expired, None)
            if len(_cache) >= _MAX_CACHE_ENTRIES:
                _cache.pop(next(iter(_cache)), None)
        _cache[key] = (now + ttl_seconds, value)
    return value


def cache_clear() -> None:
    with _cache_lock:
        _cache.clear()


# -------------------------------------------------------------- rate limiting


def allow_request(device_id: str, bucket: str, limit_per_hour: int) -> bool:
    """Bound how much upstream quota one device can consume.

    A device polls on its own schedule, and a bug in that schedule should cost
    one clock's data rather than the whole fleet's monthly allowance.
    """
    key = (device_id, bucket)
    now = time.monotonic()
    with _rate_lock:
        window = [t for t in _rate_windows.get(key, []) if now - t < _RATE_WINDOW_SECONDS]
        if len(window) >= limit_per_hour:
            _rate_windows[key] = window
            return False
        window.append(now)
        _rate_windows[key] = window
        return True


def rate_reset() -> None:
    with _rate_lock:
        _rate_windows.clear()


# ----------------------------------------------------------------- providers


def _get_json(url: str, params: dict[str, Any], provider: str) -> Any:
    try:
        response = _session.get(url, params=params, timeout=UPSTREAM_TIMEOUT_SECONDS)
    except Exception:
        # Deliberately not echoing the exception: requests puts the full URL,
        # including the API key, in its error strings.
        raise UpstreamError(502, f"{provider} unreachable")

    if response.status_code == 401 or response.status_code == 403:
        raise UpstreamError(502, f"{provider} rejected the server's API key")
    if response.status_code == 429:
        raise UpstreamError(503, f"{provider} quota exhausted")
    if response.status_code >= 400:
        raise UpstreamError(502, f"{provider} error {response.status_code}")

    try:
        return response.json()
    except Exception:
        raise UpstreamError(502, f"{provider} returned malformed data")


def openweather(endpoint: str, api_key: str, params: dict[str, str], ttl_seconds: float) -> Any:
    """Passthrough of an OpenWeather response.

    Passthrough rather than normalised because the widget's existing parsing is
    already written against this shape and we are not planning to change
    provider here.
    """
    if endpoint not in {"weather", "forecast"}:
        raise UpstreamError(400, "Unsupported weather endpoint")
    if not api_key:
        raise UpstreamError(503, "Weather is not configured on the server")

    cache_key = ("openweather", endpoint, tuple(sorted(params.items())))
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    payload = _get_json(
        f"{OPENWEATHER_BASE}/{endpoint}",
        {**params, "appid": api_key},
        "OpenWeather",
    )
    return cache_put(cache_key, payload, ttl_seconds)


def flight_by_number(number: str, api_key: str, ttl_seconds: float) -> dict[str, Any] | None:
    """Normalised flight record, or None when the flight is not found.

    Normalised rather than passthrough so that changing flight provider is a
    change here and not a firmware update on every clock. The shape is the
    subset of fields the widget actually reads.
    """
    if not api_key:
        raise UpstreamError(503, "Flight tracking is not configured on the server")

    number = number.strip().upper()
    cache_key = ("flight", number)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached["data"]

    payload = _get_json(
        f"{AVIATIONSTACK_BASE}/flights",
        {"access_key": api_key, "flight_iata": number},
        "AviationStack",
    )

    # apilayer answers 200 with an error body for plan and quota problems, so a
    # 200 is not on its own a success.
    if isinstance(payload, dict) and payload.get("error"):
        code = str((payload.get("error") or {}).get("code") or "error")
        raise UpstreamError(502, f"AviationStack: {code}")

    rows = (payload or {}).get("data") or []
    record = _normalise_flight(rows[0]) if rows and isinstance(rows[0], dict) else None
    cache_put(cache_key, {"data": record}, ttl_seconds)
    return record


def _normalise_flight(row: dict[str, Any]) -> dict[str, Any]:
    def leg(name: str) -> dict[str, Any]:
        section = row.get(name)
        section = section if isinstance(section, dict) else {}
        return {
            "iata": section.get("iata"),
            "icao": section.get("icao"),
            "scheduled": section.get("scheduled"),
            "estimated": section.get("estimated"),
            "actual": section.get("actual"),
        }

    flight = row.get("flight")
    flight = flight if isinstance(flight, dict) else {}
    return {
        "flight_status": row.get("flight_status"),
        "flight": {"iata": flight.get("iata"), "icao": flight.get("icao")},
        "departure": leg("departure"),
        "arrival": leg("arrival"),
    }
