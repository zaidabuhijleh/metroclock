from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_publishable_key: str
    supabase_service_role_key: str
    cors_origins: tuple[str, ...]
    debug_dashboard_enabled: bool
    # Provider keys for the data proxy. They live here so that a device never
    # holds credentials; see app/upstream.py.
    openweather_api_key: str
    aviationstack_api_key: str
    # AeroDataBox is the flight provider; AviationStack stays as a fallback for
    # a deployment that still only has that key. Platform decides the base URL
    # and auth header, since the same API is sold through three storefronts.
    aerodatabox_api_key: str
    aerodatabox_platform: str
    aerodatabox_base_url: str
    aerodatabox_auth_header: str


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    return Settings(
        supabase_url=os.environ.get("SUPABASE_URL", "").strip(),
        supabase_publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip(),
        supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        cors_origins=_split_csv(os.environ.get("METROCLOCK_CORS_ORIGINS", "")),
        debug_dashboard_enabled=_env_bool("METROCLOCK_DEBUG_DASHBOARD_ENABLED"),
        openweather_api_key=os.environ.get("OPENWEATHER_API_KEY", "").strip(),
        aviationstack_api_key=os.environ.get("AVIATIONSTACK_API_KEY", "").strip(),
        aerodatabox_api_key=os.environ.get("AERODATABOX_API_KEY", "").strip(),
        aerodatabox_platform=os.environ.get("AERODATABOX_PLATFORM", "apimarket").strip().lower(),
        # Both optional: set them only when the storefront's defaults below are
        # wrong, which is the one thing their published spec does not pin down.
        aerodatabox_base_url=os.environ.get("AERODATABOX_BASE_URL", "").strip(),
        aerodatabox_auth_header=os.environ.get("AERODATABOX_AUTH_HEADER", "").strip(),
    )
