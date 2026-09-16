from __future__ import annotations

from functools import lru_cache

import httpx
from fastapi import HTTPException
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.settings import get_settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="Supabase environment is not configured")
    # One client is shared by every request, and FastAPI runs sync endpoints on a
    # thread pool. postgrest-py's default httpx client speaks HTTP/2, and its h2
    # connection state is not safe to drive from several threads at once: when
    # the app's preview/status polls overlapped a device poll or a settings save,
    # a request would die client-side and surface as a bare 500 — sometimes after
    # PostgREST had already applied the write. HTTP/1.1 connections are pooled
    # per request under a lock, so concurrent threads each get their own.
    http_client = httpx.Client(
        http2=False,
        timeout=httpx.Timeout(15.0, connect=5.0),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
    )
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=SyncClientOptions(httpx_client=http_client),
    )
