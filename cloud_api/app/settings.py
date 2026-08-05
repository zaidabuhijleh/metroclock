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
    )
