from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException
from supabase import Client, create_client

from app.settings import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="Supabase environment is not configured")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
