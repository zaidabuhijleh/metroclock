from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from postgrest.exceptions import APIError
import requests
from supabase import Client

from app.settings import get_settings
from app.schemas import (
    CommandAckRequest,
    CommandListResponse,
    CreateCommandRequest,
    CreateCommandResponse,
    CreatePairingTokenRequest,
    CreatePairingTokenResponse,
    DeviceListResponse,
    DeviceSummary,
    PairDeviceRequest,
    PairDeviceResponse,
)
from app.security import generate_device_token, generate_pairing_token, hash_device_token
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


def _authenticate_user(authorization: str | None) -> dict[str, Any]:
    token = _bearer_token(authorization)
    current_settings = get_settings()
    if not current_settings.supabase_url or not current_settings.supabase_publishable_key:
        raise HTTPException(status_code=500, detail="Supabase user auth environment is not configured")

    response = requests.get(
        f"{current_settings.supabase_url.rstrip('/')}/auth/v1/user",
        headers={
            "apikey": current_settings.supabase_publishable_key,
            "Authorization": f"Bearer {token}",
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid user token")

    user = response.json()
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid user token")
    return user


def _ensure_profile(supabase: Client, user: dict[str, Any]):
    metadata = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    display_name = metadata.get("display_name") or metadata.get("name")
    supabase.table("profiles").upsert(
        {
            "id": user["id"],
            "display_name": display_name,
        },
        on_conflict="id",
    ).execute()


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


@app.post("/api/pairing-tokens", response_model=CreatePairingTokenResponse)
def create_pairing_token(
    request: CreatePairingTokenRequest,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)

    token = generate_pairing_token()
    expires_at = (datetime.now(UTC) + timedelta(seconds=request.ttl_seconds)).isoformat()
    supabase.table("pairing_codes").insert(
        {
            "code": token,
            "user_id": user["id"],
            "device_name": request.device_name,
            "expires_at": expires_at,
        }
    ).execute()
    return CreatePairingTokenResponse(pairing_token=token, expires_at=expires_at)


@app.get("/api/me/devices", response_model=DeviceListResponse)
def list_my_devices(
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)

    memberships_response = (
        supabase.table("device_memberships")
        .select("role, devices(id, device_uid, name, app_version, api_version, last_seen_at)")
        .eq("user_id", user["id"])
        .execute()
    )
    memberships = memberships_response.data or []
    device_ids = [
        row.get("devices", {}).get("id")
        for row in memberships
        if isinstance(row.get("devices"), dict) and row.get("devices", {}).get("id")
    ]

    statuses_by_device_id: dict[str, dict[str, Any]] = {}
    if device_ids:
        statuses_response = (
            supabase.table("device_status")
            .select("device_id, status")
            .in_("device_id", device_ids)
            .execute()
        )
        for row in statuses_response.data or []:
            statuses_by_device_id[row["device_id"]] = row.get("status") or {}

    devices: list[DeviceSummary] = []
    for membership in memberships:
        device = membership.get("devices")
        if not isinstance(device, dict):
            continue
        devices.append(
            DeviceSummary(
                id=device["id"],
                device_uid=device["device_uid"],
                name=device["name"],
                role=membership["role"],
                app_version=device.get("app_version"),
                api_version=device.get("api_version"),
                last_seen_at=device.get("last_seen_at"),
                status=statuses_by_device_id.get(device["id"]),
            )
        )
    return DeviceListResponse(devices=devices)


@app.post("/api/devices/{device_uid}/commands", response_model=CreateCommandResponse)
def create_device_command(
    device_uid: str,
    request: CreateCommandRequest,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)
    device = _fetch_device_by_uid(supabase, device_uid)

    membership_response = (
        supabase.table("device_memberships")
        .select("role")
        .eq("device_id", device["id"])
        .eq("user_id", user["id"])
        .in_("role", ["owner", "admin"])
        .limit(1)
        .execute()
    )
    if not _single_or_none(membership_response):
        raise HTTPException(status_code=403, detail="You do not have permission to control this device")

    command_response = (
        supabase.table("device_commands")
        .insert(
            {
                "device_id": device["id"],
                "requested_by": user["id"],
                "action": request.action,
                "payload": request.payload,
                "status": "pending",
            }
        )
        .execute()
    )
    command = _single_or_none(command_response)
    if not command:
        raise HTTPException(status_code=500, detail="Failed to create command")
    return CreateCommandResponse(id=command["id"], status=command["status"])


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
