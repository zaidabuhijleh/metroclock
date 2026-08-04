# MetroClock Cloud Control MVP

This is the first cloud milestone: a Pi device can pair with a cloud backend,
report status, poll for pending commands, and acknowledge command results. The
Pi always initiates outbound HTTPS requests; the backend never needs direct
network access to the device.

## Pi Runtime Settings

These settings are optional and runtime-editable through the existing local API.
Cloud control is disabled unless both `METROCLOCK_CLOUD_ENABLED` and
`METROCLOCK_CLOUD_BASE_URL` are configured.

- `METROCLOCK_CLOUD_ENABLED`: boolean, default `false`
- `METROCLOCK_CLOUD_BASE_URL`: backend origin, for example `https://api.example.com`
- `METROCLOCK_CLOUD_DEVICE_TOKEN`: bearer token issued by the backend after pairing
- `METROCLOCK_CLOUD_PAIRING_CODE`: short-lived code created in the user account
- `METROCLOCK_CLOUD_HEARTBEAT_SECONDS`: status report cadence, default `30`
- `METROCLOCK_CLOUD_COMMAND_POLL_SECONDS`: command poll cadence, default `5`

## Pairing Flow

1. User creates a pairing code from the future web/mobile account UI.
2. User enters `METROCLOCK_CLOUD_BASE_URL`, `METROCLOCK_CLOUD_PAIRING_CODE`,
   and sets `METROCLOCK_CLOUD_ENABLED=true` on the device.
3. The Pi calls `POST /api/devices/pair`.
4. The backend validates the pairing code, assigns the device to the user, and
   returns a long-lived `device_token`.
5. The Pi stores `METROCLOCK_CLOUD_DEVICE_TOKEN` and clears the pairing code.

## Backend Endpoints Expected By The Pi

### `POST /api/devices/pair`

Request:

```json
{
  "device_id": "stable-device-id",
  "pairing_code": "123456",
  "status": {}
}
```

Response:

```json
{
  "device_token": "opaque-device-token"
}
```

### `POST /api/devices/{device_id}/heartbeat`

Headers:

```http
Authorization: Bearer <device_token>
```

Body: current status/settings payload. This mirrors the local `/api/status`
shape and includes `device_id`, `app_version`, `api_version`, `display_mode`,
`wifi_setup`, `weather_preview`, `ambient_scene`, and editable settings.

### `GET /api/devices/{device_id}/commands`

Headers:

```http
Authorization: Bearer <device_token>
```

Response:

```json
{
  "commands": [
    {
      "id": "cmd_123",
      "action": "set_mode",
      "payload": {
        "mode": "clock"
      }
    }
  ]
}
```

Supported MVP commands:

- `set_mode`: payload `{ "mode": "clock" }`
- `set_settings`: payload is any subset of existing runtime-editable settings

`restart` is recognized but intentionally disabled until update rollout has
rollback/health-check protection.

### `POST /api/devices/{device_id}/commands/{command_id}/ack`

Headers:

```http
Authorization: Bearer <device_token>
```

Request:

```json
{
  "ok": true,
  "changed": ["DISPLAY_MODE"]
}
```

## Suggested Backend Data Model

- `users`: identity provider user profile
- `devices`: `device_id`, name, current version, last heartbeat, last status
- `device_memberships`: user/device access and role
- `pairing_codes`: short-lived code, user id, expiry, claimed timestamp
- `device_tokens`: hashed token, device id, created/revoked timestamps
- `device_commands`: action, payload, status, result, timestamps

## Next Backend MVP

Build the cloud service with:

1. User login.
2. Pairing code creation.
3. The four device endpoints above.
4. A simple web page that shows one paired device and can send `set_mode` or
   `set_settings`.
