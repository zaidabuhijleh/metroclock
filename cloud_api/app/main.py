from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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


@app.get("/debug", response_class=HTMLResponse)
def debug_dashboard():
    return HTMLResponse(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MetroClock Cloud Debug</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #101213;
      color: #f4f7f8;
    }
    body {
      margin: 0;
      padding: 32px;
      background: #101213;
    }
    main {
      max-width: 920px;
      margin: 0 auto;
    }
    h1 {
      font-size: 28px;
      margin: 0 0 6px;
    }
    h2 {
      font-size: 18px;
      margin: 0 0 14px;
    }
    p {
      color: #b8c1c5;
      line-height: 1.45;
    }
    section {
      border-top: 1px solid #2a3033;
      padding: 22px 0;
    }
    label {
      display: block;
      font-size: 13px;
      color: #c7d0d4;
      margin-bottom: 6px;
    }
    input, textarea, select {
      box-sizing: border-box;
      width: 100%;
      border: 1px solid #465056;
      background: #171a1c;
      color: #f4f7f8;
      padding: 10px 11px;
      border-radius: 6px;
      font: inherit;
      margin-bottom: 12px;
    }
    textarea {
      min-height: 84px;
      resize: vertical;
    }
    button {
      border: 0;
      border-radius: 6px;
      background: #30b47b;
      color: #07110c;
      font-weight: 700;
      padding: 10px 14px;
      cursor: pointer;
      margin-right: 8px;
      margin-bottom: 8px;
    }
    button.secondary {
      background: #2f373b;
      color: #eef4f5;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #080909;
      border: 1px solid #2a3033;
      border-radius: 6px;
      padding: 14px;
      min-height: 80px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    @media (max-width: 720px) {
      body { padding: 18px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<main>
  <h1>MetroClock Cloud Debug</h1>
  <p>Internal helper for pairing-token and command testing. Paste a Supabase user access token from a signed-in test session.</p>

  <section>
    <h2>Auth</h2>
    <label for="token">Supabase user access token</label>
    <textarea id="token" placeholder="eyJ..."></textarea>
    <button class="secondary" onclick="saveToken()">Save Token Locally</button>
    <button class="secondary" onclick="clearToken()">Clear</button>
  </section>

  <section>
    <h2>Create Pairing Token</h2>
    <div class="grid">
      <div>
        <label for="deviceName">Device name</label>
        <input id="deviceName" value="MetroClock Debug">
      </div>
      <div>
        <label for="ttl">TTL seconds</label>
        <input id="ttl" type="number" min="60" max="3600" value="600">
      </div>
    </div>
    <button onclick="createPairingToken()">Create Pairing Token</button>
    <pre id="pairingOut"></pre>
  </section>

  <section>
    <h2>Devices</h2>
    <button onclick="listDevices()">Refresh Devices</button>
    <pre id="devicesOut"></pre>
  </section>

  <section>
    <h2>Send Command</h2>
    <label for="deviceUid">Device UID</label>
    <input id="deviceUid" placeholder="device_id from /api/me/devices">
    <div class="grid">
      <div>
        <label for="action">Action</label>
        <select id="action">
          <option value="set_mode">set_mode</option>
          <option value="set_settings">set_settings</option>
        </select>
      </div>
      <div>
        <label for="mode">Mode for set_mode</label>
        <input id="mode" value="clock">
      </div>
    </div>
    <label for="payload">Payload JSON</label>
    <textarea id="payload">{"mode":"clock"}</textarea>
    <button onclick="fillModePayload()">Use Mode Payload</button>
    <button onclick="sendCommand()">Send Command</button>
    <pre id="commandOut"></pre>
  </section>
</main>

<script>
const tokenEl = document.getElementById("token");
tokenEl.value = localStorage.getItem("metroclockDebugToken") || "";

function saveToken() {
  localStorage.setItem("metroclockDebugToken", tokenEl.value.trim());
}

function clearToken() {
  tokenEl.value = "";
  localStorage.removeItem("metroclockDebugToken");
}

function authHeaders() {
  const token = tokenEl.value.trim();
  if (!token) throw new Error("Paste a Supabase user access token first.");
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`
  };
}

function show(id, value) {
  document.getElementById(id).textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function request(path, options) {
  const res = await fetch(path, options);
  const text = await res.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; }
  catch { body = text; }
  if (!res.ok) throw new Error(JSON.stringify(body));
  return body;
}

async function createPairingToken() {
  try {
    saveToken();
    const body = {
      device_name: document.getElementById("deviceName").value.trim() || null,
      ttl_seconds: Number(document.getElementById("ttl").value || 600)
    };
    const data = await request("/api/pairing-tokens", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body)
    });
    show("pairingOut", data);
  } catch (err) {
    show("pairingOut", String(err.message || err));
  }
}

async function listDevices() {
  try {
    saveToken();
    const data = await request("/api/me/devices", {
      method: "GET",
      headers: authHeaders()
    });
    show("devicesOut", data);
    if (data.devices && data.devices[0]) {
      document.getElementById("deviceUid").value = data.devices[0].device_uid;
    }
  } catch (err) {
    show("devicesOut", String(err.message || err));
  }
}

function fillModePayload() {
  const mode = document.getElementById("mode").value.trim() || "clock";
  document.getElementById("payload").value = JSON.stringify({ mode }, null, 2);
}

async function sendCommand() {
  try {
    saveToken();
    const deviceUid = document.getElementById("deviceUid").value.trim();
    if (!deviceUid) throw new Error("Device UID is required.");
    const payload = JSON.parse(document.getElementById("payload").value || "{}");
    const body = {
      action: document.getElementById("action").value,
      payload
    };
    const data = await request(`/api/devices/${encodeURIComponent(deviceUid)}/commands`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body)
    });
    show("commandOut", data);
  } catch (err) {
    show("commandOut", String(err.message || err));
  }
}
</script>
</body>
</html>"""
    )


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
