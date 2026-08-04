from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from postgrest.exceptions import APIError
from supabase import Client

from app.settings import get_settings
from app.schemas import CommandAckRequest, CommandListResponse, PairDeviceRequest, PairDeviceResponse
from app.security import generate_device_token, hash_device_token
from app.supabase_client import get_supabase


app = FastAPI(title="MetroClock Cloud API")
settings = get_settings()

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _reported_at_iso(status: dict[str, Any]) -> str:
    reported_at = status.get("reported_at")
    if isinstance(reported_at, (int, float)):
        return datetime.fromtimestamp(float(reported_at), UTC).isoformat()
    if isinstance(reported_at, str) and reported_at.strip():
        return reported_at.strip()
    return _now_iso()


def _single_or_none(response) -> dict[str, Any] | None:
    data = response.data
    if isinstance(data, list):
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def _bearer_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = value[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _fetch_device_by_uid(supabase: Client, device_uid: str) -> dict[str, Any]:
    response = (
        supabase.table("devices")
        .select("*")
        .eq("device_uid", device_uid)
        .limit(1)
        .execute()
    )
    device = _single_or_none(response)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _authenticate_device(
    device_uid: str,
    authorization: str | None,
    supabase: Client,
) -> dict[str, Any]:
    token_hash = hash_device_token(_bearer_token(authorization))
    token_response = (
        supabase.table("device_tokens")
        .select("id, device_id")
        .eq("token_hash", token_hash)
        .is_("revoked_at", "null")
        .limit(1)
        .execute()
    )
    token_row = _single_or_none(token_response)
    if not token_row:
        raise HTTPException(status_code=401, detail="Invalid device token")

    device = _fetch_device_by_uid(supabase, device_uid)
    if device["id"] != token_row["device_id"]:
        raise HTTPException(status_code=403, detail="Token does not belong to this device")

    supabase.table("device_tokens").update({"last_used_at": _now_iso()}).eq("id", token_row["id"]).execute()
    return device


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/devices/pair", response_model=PairDeviceResponse)
def pair_device(request: PairDeviceRequest, supabase: Client = Depends(get_supabase)):
    now = _now_iso()
    pairing_response = (
        supabase.table("pairing_codes")
        .select("*")
        .eq("code", request.pairing_code)
        .is_("claimed_at", "null")
        .gt("expires_at", now)
        .limit(1)
        .execute()
    )
    pairing = _single_or_none(pairing_response)
    if not pairing:
        raise HTTPException(status_code=400, detail="Invalid or expired pairing code")

    device_name = pairing.get("device_name") or request.status.get("hostname") or "MetroClock"
    app_version = request.status.get("app_version")
    api_version = request.status.get("api_version")
    device_response = (
        supabase.table("devices")
        .upsert(
            {
                "device_uid": request.device_id,
                "name": device_name,
                "app_version": app_version,
                "api_version": api_version,
                "last_seen_at": now,
            },
            on_conflict="device_uid",
        )
        .execute()
    )
    device = _single_or_none(device_response)
    if not device:
        device = _fetch_device_by_uid(supabase, request.device_id)

    supabase.table("device_memberships").upsert(
        {
            "device_id": device["id"],
            "user_id": pairing["user_id"],
            "role": "owner",
        },
        on_conflict="device_id,user_id",
    ).execute()

    raw_token = generate_device_token()
    supabase.table("device_tokens").insert(
        {
            "device_id": device["id"],
            "token_hash": hash_device_token(raw_token),
            "name": "primary",
        }
    ).execute()

    supabase.table("device_status").upsert(
        {
            "device_id": device["id"],
            "status": request.status,
            "reported_at": now,
        },
        on_conflict="device_id",
    ).execute()

    supabase.table("pairing_codes").update(
        {
            "claimed_at": now,
            "claimed_device_id": device["id"],
        }
    ).eq("id", pairing["id"]).execute()

    return PairDeviceResponse(device_token=raw_token)


@app.post("/api/devices/{device_uid}/heartbeat")
def device_heartbeat(
    device_uid: str,
    status: dict[str, Any],
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    device = _authenticate_device(device_uid, authorization, supabase)
    now = _now_iso()
    supabase.table("devices").update(
        {
            "app_version": status.get("app_version"),
            "api_version": status.get("api_version"),
            "last_seen_at": now,
        }
    ).eq("id", device["id"]).execute()
    supabase.table("device_status").upsert(
        {
            "device_id": device["id"],
            "status": status,
            "reported_at": _reported_at_iso(status),
        },
        on_conflict="device_id",
    ).execute()
    return {"ok": True}


@app.get("/api/devices/{device_uid}/commands", response_model=CommandListResponse)
def list_device_commands(
    device_uid: str,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    device = _authenticate_device(device_uid, authorization, supabase)
    response = (
        supabase.table("device_commands")
        .select("id, action, payload")
        .eq("device_id", device["id"])
        .eq("status", "pending")
        .order("created_at")
        .limit(25)
        .execute()
    )
    commands = response.data or []
    command_ids = [command["id"] for command in commands]
    if command_ids:
        supabase.table("device_commands").update({"status": "sent", "sent_at": _now_iso()}).in_("id", command_ids).execute()
    return CommandListResponse(commands=commands)


@app.post("/api/devices/{device_uid}/commands/{command_id}/ack")
def acknowledge_device_command(
    device_uid: str,
    command_id: str,
    ack: CommandAckRequest,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    device = _authenticate_device(device_uid, authorization, supabase)
    result = ack.result or {}
    if ack.changed is not None:
        result["changed"] = ack.changed
    update = {
        "status": "succeeded" if ack.ok else "failed",
        "result": result,
        "error": ack.error,
        "acknowledged_at": _now_iso(),
    }
    try:
        response = (
            supabase.table("device_commands")
            .update(update)
            .eq("id", command_id)
            .eq("device_id", device["id"])
            .execute()
        )
    except APIError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not response.data:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"ok": True}
