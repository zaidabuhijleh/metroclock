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
