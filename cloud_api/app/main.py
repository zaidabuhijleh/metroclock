from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from postgrest.exceptions import APIError
import requests
from supabase import Client

from app.settings import get_settings
from app.schemas import (
    CommandAckRequest,
    CommandListResponse,
    CommandStatusResponse,
    CreateCommandRequest,
    CreateCommandResponse,
    CreatePairingTokenRequest,
    CreatePairingTokenResponse,
    DeviceSettingsResponse,
    DeviceListResponse,
    DeviceSummary,
    PairDeviceRequest,
    PairDeviceResponse,
    UpdateDeviceSettingsRequest,
)
from app.security import generate_device_token, generate_pairing_token, hash_device_token
from app.supabase_client import get_supabase


app = FastAPI(title="MetroClock Cloud API")
settings = get_settings()
_device_event_queues: dict[str, list[queue.Queue[dict[str, Any]]]] = {}
_device_event_lock = threading.Lock()
_device_preview_lock = threading.Lock()
_device_preview_frames: dict[str, "DevicePreviewFrame"] = {}
_max_preview_bytes = 256 * 1024
_max_preview_devices = 500
_preview_frame_ttl = timedelta(hours=1)
_allowed_preview_content_types = {"image/png", "image/jpeg"}


@dataclass(frozen=True)
class DevicePreviewFrame:
    content: bytes
    content_type: str
    updated_at: str
    received_at: datetime


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


def _register_device_listener(device_uid: str) -> queue.Queue[dict[str, Any]]:
    event_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=20)
    with _device_event_lock:
        _device_event_queues.setdefault(device_uid, []).append(event_queue)
    return event_queue


def _unregister_device_listener(device_uid: str, event_queue: queue.Queue[dict[str, Any]]):
    with _device_event_lock:
        queues = _device_event_queues.get(device_uid, [])
        if event_queue in queues:
            queues.remove(event_queue)
        if not queues:
            _device_event_queues.pop(device_uid, None)


def _notify_device(device_uid: str, event: dict[str, Any]):
    with _device_event_lock:
        queues = list(_device_event_queues.get(device_uid, []))
    for event_queue in queues:
        try:
            event_queue.put_nowait(event)
        except queue.Full:
            try:
                event_queue.get_nowait()
                event_queue.put_nowait(event)
            except Exception:
                pass


def _sse_message(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _reported_at_iso(status: dict[str, Any]) -> str:
    reported_at = status.get("reported_at")
    if isinstance(reported_at, (int, float)):
        return datetime.fromtimestamp(float(reported_at), UTC).isoformat()
    if isinstance(reported_at, str) and reported_at.strip():
        return reported_at.strip()
    return _now_iso()


def _settings_from_status(status: Any) -> dict[str, Any]:
    if not isinstance(status, dict):
        return {}
    return {key: value for key, value in status.items() if isinstance(key, str) and key.isupper()}


def _prune_device_preview_frames(now: datetime):
    expires_before = now - _preview_frame_ttl
    expired_device_ids = [
        device_id
        for device_id, frame in _device_preview_frames.items()
        if frame.received_at < expires_before
    ]
    for device_id in expired_device_ids:
        _device_preview_frames.pop(device_id, None)

    overflow = len(_device_preview_frames) - _max_preview_devices
    if overflow <= 0:
        return

    oldest_device_ids = sorted(
        _device_preview_frames,
        key=lambda device_id: _device_preview_frames[device_id].received_at,
    )
    for device_id in oldest_device_ids[:overflow]:
        _device_preview_frames.pop(device_id, None)


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


def _normalize_command_request(request: CreateCommandRequest) -> tuple[str, dict[str, Any]]:
    action = request.action
    payload = request.payload
    if isinstance(payload.get("payload"), dict):
        nested_action = str(payload.get("action") or "").strip()
        if nested_action:
            action = nested_action
        payload = payload["payload"]
    return action, payload


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


def _ensure_user_can_control_device(supabase: Client, user_id: str, device_id: str):
    membership_response = (
        supabase.table("device_memberships")
        .select("role")
        .eq("device_id", device_id)
        .eq("user_id", user_id)
        .in_("role", ["owner", "admin"])
        .limit(1)
        .execute()
    )
    if not _single_or_none(membership_response):
        raise HTTPException(status_code=403, detail="You do not have permission to control this device")


def _create_device_command(
    supabase: Client,
    device_id: str,
    device_uid: str,
    user_id: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    command_response = (
        supabase.table("device_commands")
        .insert(
            {
                "device_id": device_id,
                "requested_by": user_id,
                "action": action,
                "payload": payload,
                "status": "pending",
            }
        )
        .execute()
    )
    command = _single_or_none(command_response)
    if not command:
        raise HTTPException(status_code=500, detail="Failed to create command")
    _notify_device(device_uid, {"type": "commands_available", "command_id": command["id"]})
    return command


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
    current_settings = get_settings()
    if not current_settings.debug_dashboard_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    page = """<!doctype html>
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
  <p>Internal helper for pairing-token and command testing. Sign in with a Supabase test user to generate tokens and send commands.</p>

  <section>
    <h2>Auth</h2>
    <div class="grid">
      <div>
        <label for="email">Email</label>
        <input id="email" type="email" autocomplete="email">
      </div>
      <div>
        <label for="password">Password</label>
        <input id="password" type="password" autocomplete="current-password">
      </div>
    </div>
    <button onclick="signIn()">Sign In</button>
    <button class="secondary" onclick="signUp()">Sign Up</button>
    <button class="secondary" onclick="signOut()">Sign Out</button>
    <pre id="authOut"></pre>
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
    <p>Payload only. For set_mode, use <code>{"mode":"weather"}</code>.</p>
    <button onclick="fillModePayload()">Use Mode Payload</button>
    <button onclick="sendCommand()">Send Command</button>
    <pre id="commandOut"></pre>
  </section>
</main>

<script>
const SUPABASE_URL = __SUPABASE_URL__;
const SUPABASE_PUBLISHABLE_KEY = __SUPABASE_PUBLISHABLE_KEY__;
const tokenEl = document.getElementById("token");
tokenEl.value = localStorage.getItem("metroclockDebugToken") || "";
document.getElementById("email").value = localStorage.getItem("metroclockDebugEmail") || "";

captureSessionFromHash();

function saveToken() {
  localStorage.setItem("metroclockDebugToken", tokenEl.value.trim());
}

function clearToken() {
  tokenEl.value = "";
  localStorage.removeItem("metroclockDebugToken");
}

function authHeaders() {
  const token = tokenEl.value.trim();
  if (!token) throw new Error("Sign in first to get a Supabase user session.");
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`
  };
}

function show(id, value) {
  document.getElementById(id).textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function supabaseAuth(path, body) {
  if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
    throw new Error("Supabase debug auth is not configured on this server.");
  }
  const res = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": SUPABASE_PUBLISHABLE_KEY
    },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; }
  catch { data = text; }
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

function captureSessionFromHash() {
  if (!window.location.hash) return;
  const params = new URLSearchParams(window.location.hash.slice(1));
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  if (!accessToken) return;
  tokenEl.value = accessToken;
  saveToken();
  if (refreshToken) {
    localStorage.setItem("metroclockDebugRefreshToken", refreshToken);
  }
  history.replaceState(null, "", window.location.pathname);
  show("authOut", {
    signed_in: true,
    source: "email_confirmation_redirect",
    expires_in: params.get("expires_in")
  });
}

function authBody() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  if (!email || !password) throw new Error("Email and password are required.");
  localStorage.setItem("metroclockDebugEmail", email);
  return { email, password };
}

function storeSession(data) {
  if (!data.access_token) {
    show("authOut", {
      message: "No access token returned. If this was sign up, email confirmation may be required.",
      response: data
    });
    return;
  }
  tokenEl.value = data.access_token;
  saveToken();
  show("authOut", {
    signed_in: true,
    user: data.user ? { id: data.user.id, email: data.user.email } : null,
    expires_in: data.expires_in
  });
}

async function signIn() {
  try {
    const data = await supabaseAuth("token?grant_type=password", authBody());
    storeSession(data);
  } catch (err) {
    show("authOut", String(err.message || err));
  }
}

async function signUp() {
  try {
    const body = authBody();
    body.data = { display_name: "MetroClock Debug" };
    const redirectTo = `${window.location.origin}${window.location.pathname}`;
    const data = await supabaseAuth(`signup?redirect_to=${encodeURIComponent(redirectTo)}`, body);
    storeSession(data);
  } catch (err) {
    show("authOut", String(err.message || err));
  }
}

function signOut() {
  clearToken();
  show("authOut", { signed_in: false });
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
    page = page.replace("__SUPABASE_URL__", json.dumps(current_settings.supabase_url))
    page = page.replace("__SUPABASE_PUBLISHABLE_KEY__", json.dumps(current_settings.supabase_publishable_key))
    return HTMLResponse(page)


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


@app.get("/api/devices/{device_uid}/settings", response_model=DeviceSettingsResponse)
def get_device_settings(
    device_uid: str,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)
    device = _fetch_device_by_uid(supabase, device_uid)
    _ensure_user_can_control_device(supabase, user["id"], device["id"])

    status_response = (
        supabase.table("device_status")
        .select("status, reported_at")
        .eq("device_id", device["id"])
        .limit(1)
        .execute()
    )
    status_row = _single_or_none(status_response) or {}
    return DeviceSettingsResponse(
        settings=_settings_from_status(status_row.get("status")),
        reported_at=status_row.get("reported_at"),
    )


@app.patch("/api/devices/{device_uid}/settings", response_model=CreateCommandResponse)
def update_device_settings(
    device_uid: str,
    request: UpdateDeviceSettingsRequest,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)
    device = _fetch_device_by_uid(supabase, device_uid)
    _ensure_user_can_control_device(supabase, user["id"], device["id"])
    command = _create_device_command(
        supabase=supabase,
        device_id=device["id"],
        device_uid=device_uid,
        user_id=user["id"],
        action="set_settings",
        payload=request.settings,
    )
    return CreateCommandResponse(id=command["id"], status=command["status"])


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
    _ensure_user_can_control_device(supabase, user["id"], device["id"])

    action, payload = _normalize_command_request(request)
    command = _create_device_command(
        supabase=supabase,
        device_id=device["id"],
        device_uid=device_uid,
        user_id=user["id"],
        action=action,
        payload=payload,
    )
    return CreateCommandResponse(id=command["id"], status=command["status"])


@app.get("/api/devices/{device_uid}/commands/{command_id}", response_model=CommandStatusResponse)
def get_device_command_status(
    device_uid: str,
    command_id: str,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)
    device = _fetch_device_by_uid(supabase, device_uid)
    _ensure_user_can_control_device(supabase, user["id"], device["id"])

    response = (
        supabase.table("device_commands")
        .select("id, action, status, payload, result, error, created_at, sent_at, acknowledged_at")
        .eq("id", command_id)
        .eq("device_id", device["id"])
        .limit(1)
        .execute()
    )
    command = _single_or_none(response)
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    return CommandStatusResponse(
        id=command["id"],
        action=command["action"],
        status=command["status"],
        payload=command.get("payload") or {},
        result=command.get("result"),
        error=command.get("error"),
        created_at=command.get("created_at"),
        sent_at=command.get("sent_at"),
        acknowledged_at=command.get("acknowledged_at"),
    )


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


@app.post("/api/devices/{device_uid}/preview")
async def upload_device_preview(
    device_uid: str,
    request: Request,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    device = _authenticate_device(device_uid, authorization, supabase)
    content_type = str(request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type not in _allowed_preview_content_types:
        raise HTTPException(status_code=415, detail="Preview must be image/png or image/jpeg")

    content_length = str(request.headers.get("content-length") or "").strip()
    if content_length:
        try:
            if int(content_length) > _max_preview_bytes:
                raise HTTPException(status_code=413, detail="Preview image is too large")
        except ValueError:
            pass

    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Preview image is empty")
    if len(content) > _max_preview_bytes:
        raise HTTPException(status_code=413, detail="Preview image is too large")

    now = datetime.now(UTC)
    frame = DevicePreviewFrame(
        content=content,
        content_type=content_type,
        updated_at=now.isoformat(),
        received_at=now,
    )
    with _device_preview_lock:
        _device_preview_frames[device["id"]] = frame
        _prune_device_preview_frames(now)
    return {"ok": True, "updated_at": frame.updated_at}


@app.get("/api/devices/{device_uid}/preview")
def get_device_preview(
    device_uid: str,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    user = _authenticate_user(authorization)
    _ensure_profile(supabase, user)
    device = _fetch_device_by_uid(supabase, device_uid)
    _ensure_user_can_control_device(supabase, user["id"], device["id"])

    with _device_preview_lock:
        frame = _device_preview_frames.get(device["id"])
    if frame is None:
        raise HTTPException(status_code=404, detail="Preview is not available yet")

    return Response(
        content=frame.content,
        media_type=frame.content_type,
        headers={
            "Cache-Control": "no-store",
            "X-MetroClock-Preview-Updated-At": frame.updated_at,
        },
    )


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


@app.get("/api/devices/{device_uid}/events")
def stream_device_events(
    device_uid: str,
    authorization: str | None = Header(default=None),
    supabase: Client = Depends(get_supabase),
):
    _authenticate_device(device_uid, authorization, supabase)
    event_queue = _register_device_listener(device_uid)

    def event_stream():
        try:
            yield _sse_message("ready", {"ok": True, "device_uid": device_uid})
            while True:
                try:
                    event = event_queue.get(timeout=20)
                    yield _sse_message(str(event.get("type") or "message"), event)
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            _unregister_device_listener(device_uid, event_queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
