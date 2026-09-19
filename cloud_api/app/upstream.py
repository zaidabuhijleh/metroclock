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
from datetime import UTC, datetime
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

# The same AeroDataBox API is sold through three storefronts, each with its own
# host and auth header. Both are overridable: their published OpenAPI spec does
# not state the header names, so the value from the subscription dashboard wins
# over these defaults.
AERODATABOX_PLATFORMS = {
    "apimarket": (
        "https://prod.api.market/api/v1/aedbx/aerodatabox",
        {"x-api-market-key": "{key}"},
    ),
    "rapidapi": (
        "https://aerodatabox.p.rapidapi.com",
        {"X-RapidAPI-Key": "{key}", "X-RapidAPI-Host": "aerodatabox.p.rapidapi.com"},
    ),
    "direct": (
        "https://aerodatabox.p.sulu.sh/v1",
        {"Authorization": "Bearer {key}"},
    ),
}

# What the device is told, whatever the provider called it. Only these five
# reach a clock, so swapping provider never becomes a firmware change.
FLIGHT_STATUS_SCHEDULED = "scheduled"
FLIGHT_STATUS_ACTIVE = "active"
FLIGHT_STATUS_LANDED = "landed"
FLIGHT_STATUS_CANCELLED = "cancelled"
FLIGHT_STATUS_DIVERTED = "diverted"

# AeroDataBox's own vocabulary. Anything missing here is inferred from the
# times instead, so an unlisted status still behaves correctly.
_AERODATABOX_STATUS = {
    "unknown": "",
    "expected": FLIGHT_STATUS_SCHEDULED,
    "expectedapproach": FLIGHT_STATUS_ACTIVE,
    "checkin": FLIGHT_STATUS_SCHEDULED,
    "boarding": FLIGHT_STATUS_SCHEDULED,
    "gateclosed": FLIGHT_STATUS_SCHEDULED,
    "delayed": FLIGHT_STATUS_SCHEDULED,
    "departed": FLIGHT_STATUS_ACTIVE,
    "enroute": FLIGHT_STATUS_ACTIVE,
    "approaching": FLIGHT_STATUS_ACTIVE,
    "arrived": FLIGHT_STATUS_LANDED,
    "landed": FLIGHT_STATUS_LANDED,
    "canceled": FLIGHT_STATUS_CANCELLED,
    "cancelled": FLIGHT_STATUS_CANCELLED,
    "canceleduncertain": FLIGHT_STATUS_CANCELLED,
    "diverted": FLIGHT_STATUS_DIVERTED,
}

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


def flight_by_number(number: str, settings: Any, default_ttl_seconds: float = 300) -> dict[str, Any] | None:
    """Normalised flight record, or None when the flight is not found.

    Normalised rather than passthrough so that changing provider is a change
    here and not a firmware update on every clock. The shape is the subset of
    fields the widget reads, with every time given twice: ``*_utc`` for
    arithmetic and the local string for display.
    """
    number = number.strip().upper()
    cache_key = ("flight", number)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached["data"]

    if getattr(settings, "aerodatabox_api_key", ""):
        record = _aerodatabox_flight(number, settings)
    elif getattr(settings, "aviationstack_api_key", ""):
        record = _aviationstack_flight(number, settings.aviationstack_api_key)
    else:
        raise UpstreamError(503, "Flight tracking is not configured on the server")

    cache_put(cache_key, {"data": record}, flight_cache_ttl(record, default_ttl_seconds))
    return record


def flight_cache_ttl(record: dict[str, Any] | None, default_ttl_seconds: float) -> float:
    """How long this particular answer stays useful.

    A landed flight does not change again; one still sitting at the gate hours
    before departure changes slowly; one in the air changes constantly. Caching
    every answer for the same few minutes meant paying the provider for
    re-reads of facts that were already final.
    """
    if not isinstance(record, dict):
        # "Not found" is usually a flight that does not operate today.
        return max(default_ttl_seconds, 3600)

    status = str(record.get("flight_status") or "").lower()
    if status in {FLIGHT_STATUS_LANDED, FLIGHT_STATUS_CANCELLED, FLIGHT_STATUS_DIVERTED}:
        return 6 * 3600
    if status == FLIGHT_STATUS_ACTIVE:
        return default_ttl_seconds

    departure = record.get("departure") if isinstance(record.get("departure"), dict) else {}
    until_departure = _seconds_until(departure.get("estimated_utc") or departure.get("scheduled_utc"))
    if until_departure is None:
        return default_ttl_seconds
    if until_departure > 6 * 3600:
        return 3600
    if until_departure > 2 * 3600:
        return 900
    return default_ttl_seconds


def _seconds_until(value: Any) -> float | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    return parsed.timestamp() - time.time()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    # AeroDataBox writes "2026-09-18 22:55Z"; ISO parsing wants a "T" and an
    # explicit offset.
    text = text.replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# ------------------------------------------------------------- AeroDataBox


def _aerodatabox_request(settings: Any, path: str, params: dict[str, Any]) -> Any:
    platform = str(getattr(settings, "aerodatabox_platform", "") or "apimarket").lower()
    default_base, default_headers = AERODATABOX_PLATFORMS.get(
        platform, AERODATABOX_PLATFORMS["apimarket"]
    )
    base_url = str(getattr(settings, "aerodatabox_base_url", "") or default_base).rstrip("/")
    key = settings.aerodatabox_api_key

    header_override = str(getattr(settings, "aerodatabox_auth_header", "") or "").strip()
    if header_override:
        headers = {header_override: key}
    else:
        headers = {name: template.format(key=key) for name, template in default_headers.items()}

    try:
        response = _session.get(
            f"{base_url}/{path.lstrip('/')}",
            params=params,
            headers=headers,
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
    except Exception:
        raise UpstreamError(502, "AeroDataBox unreachable")

    # A flight number that is not flying today is an answer, not a failure.
    if response.status_code in (204, 404):
        return None
    if response.status_code in (401, 403):
        raise UpstreamError(502, "AeroDataBox rejected the server's API key")
    if response.status_code == 429:
        raise UpstreamError(503, "AeroDataBox quota exhausted")
    if response.status_code >= 400:
        raise UpstreamError(502, f"AeroDataBox error {response.status_code}")

    try:
        return response.json()
    except Exception:
        raise UpstreamError(502, "AeroDataBox returned malformed data")


def _aerodatabox_flight(number: str, settings: Any) -> dict[str, Any] | None:
    payload = _aerodatabox_request(
        settings,
        f"flights/number/{number}",
        {"withAircraftImage": "false", "withLocation": "false"},
    )
    rows = payload if isinstance(payload, list) else (payload or {}).get("data")
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    if not rows:
        return None
    return _normalise_aerodatabox(_closest_leg(rows))


def _closest_leg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The leg a viewer means by "this flight number" right now.

    A number can return several days of legs. The one in the air beats one that
    has landed, and otherwise the nearest departure to now wins.
    """
    def sort_key(row: dict[str, Any]):
        departure = row.get("departure") if isinstance(row.get("departure"), dict) else {}
        times = _adb_times(departure)
        moment = _parse_iso(times.get("actual_utc") or times.get("estimated_utc") or times.get("scheduled_utc"))
        distance = abs(moment.timestamp() - time.time()) if moment else float("inf")
        return distance

    return min(rows, key=sort_key)


def _adb_times(section: dict[str, Any]) -> dict[str, Any]:
    """Flatten AeroDataBox's time objects into our record's fields.

    ``revisedTime`` is their estimate; ``runwayTime`` is what actually happened.
    """
    def pair(key: str) -> tuple[str | None, str | None]:
        value = section.get(key)
        if not isinstance(value, dict):
            return None, None
        utc = _parse_iso(value.get("utc"))
        return (utc.isoformat() if utc else None), (str(value.get("local") or "").strip() or None)

    scheduled_utc, scheduled_local = pair("scheduledTime")
    revised_utc, revised_local = pair("revisedTime")
    runway_utc, runway_local = pair("runwayTime")
    predicted_utc, predicted_local = pair("predictedTime")

    return {
        "scheduled_utc": scheduled_utc,
        "scheduled": scheduled_local or scheduled_utc,
        "estimated_utc": revised_utc or predicted_utc,
        "estimated": revised_local or predicted_local or revised_utc or predicted_utc,
        "actual_utc": runway_utc,
        "actual": runway_local or runway_utc,
    }


def _normalise_aerodatabox(row: dict[str, Any]) -> dict[str, Any]:
    def leg(name: str) -> dict[str, Any]:
        section = row.get(name)
        section = section if isinstance(section, dict) else {}
        airport = section.get("airport")
        airport = airport if isinstance(airport, dict) else {}
        return {
            "iata": airport.get("iata") or section.get("iata"),
            "icao": airport.get("icao") or section.get("icao"),
            "time_zone": airport.get("timeZone"),
            "terminal": section.get("terminal"),
            "gate": section.get("gate"),
            **_adb_times(section),
        }

    departure = leg("departure")
    arrival = leg("arrival")
    label = str(row.get("number") or "").replace(" ", "").upper()
    airline = row.get("airline") if isinstance(row.get("airline"), dict) else {}

    return {
        "flight_status": _aerodatabox_status(row, departure, arrival),
        "flight": {
            "iata": label or None,
            "icao": (str(airline.get("icao") or "").strip().upper() or None),
        },
        "departure": departure,
        "arrival": arrival,
        "provider": "aerodatabox",
    }


def _aerodatabox_status(row: dict[str, Any], departure: dict[str, Any], arrival: dict[str, Any]) -> str:
    """Their status if we recognise it, otherwise what the times prove.

    Their vocabulary has grown before and the published spec does not pin it
    down, so an unrecognised value falls through to the runway times, which say
    plainly whether the aircraft has left and whether it has arrived.
    """
    raw = str(row.get("status") or "").strip().lower().replace(" ", "").replace("-", "")
    mapped = _AERODATABOX_STATUS.get(raw)
    if mapped:
        return mapped

    if arrival.get("actual_utc"):
        return FLIGHT_STATUS_LANDED
    if departure.get("actual_utc"):
        return FLIGHT_STATUS_ACTIVE
    return FLIGHT_STATUS_SCHEDULED


# ------------------------------------------------------------ AviationStack


def _aviationstack_flight(number: str, api_key: str) -> dict[str, Any] | None:
    """Kept as a fallback for a deployment configured with only this key.

    Its times are local with a "+00:00" offset stuck on them, so they cannot be
    turned into instants here: the record carries the display strings and no
    ``*_utc`` fields, and a clock falls back to its old behaviour.
    """
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
    if not rows or not isinstance(rows[0], dict):
        return None
    return _normalise_aviationstack(rows[0])


def _normalise_aviationstack(row: dict[str, Any]) -> dict[str, Any]:
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
        "provider": "aviationstack",
    }
