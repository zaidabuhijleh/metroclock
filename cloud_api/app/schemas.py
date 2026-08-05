from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PairDeviceRequest(BaseModel):
    device_id: str = Field(min_length=1)
    pairing_code: str = Field(min_length=1)
    status: dict[str, Any] = Field(default_factory=dict)


class PairDeviceResponse(BaseModel):
    device_token: str


class Command(BaseModel):
    id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandListResponse(BaseModel):
    commands: list[Command]


class CommandAckRequest(BaseModel):
    ok: bool
    changed: list[str] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class CreatePairingTokenRequest(BaseModel):
    device_name: str | None = None
    ttl_seconds: int = Field(default=600, ge=60, le=3600)


class CreatePairingTokenResponse(BaseModel):
    pairing_token: str
    expires_at: str


class DeviceSummary(BaseModel):
    id: str
    device_uid: str
    name: str
    role: str
    app_version: str | None = None
    api_version: str | None = None
    last_seen_at: str | None = None
    status: dict[str, Any] | None = None


class DeviceListResponse(BaseModel):
    devices: list[DeviceSummary]


class CreateCommandRequest(BaseModel):
    action: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class CreateCommandResponse(BaseModel):
    id: str
    status: str


class DeviceSettingsResponse(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)
    reported_at: str | None = None


class UpdateDeviceSettingsRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class CommandStatusResponse(BaseModel):
    id: str
    action: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    sent_at: str | None = None
    acknowledged_at: str | None = None
