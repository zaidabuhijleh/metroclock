from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    cors_origins: tuple[str, ...]


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def get_settings() -> Settings:
    return Settings(
        supabase_url=os.environ.get("SUPABASE_URL", "").strip(),
        supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        cors_origins=_split_csv(os.environ.get("METROCLOCK_CORS_ORIGINS", "")),
    )
