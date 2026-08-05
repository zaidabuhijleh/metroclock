# MetroClock Cloud Control MVP

This is the first cloud milestone: a Pi device can pair with a cloud backend,
report status, poll for pending commands, and acknowledge command results. The
Pi always initiates outbound HTTPS requests; the backend never needs direct
network access to the device.

Commands use a hybrid realtime path:

- The Pi keeps a local polling fallback.
- The Pi also opens an outbound Server-Sent Events stream.
- When a command is created, the cloud API sends `commands_available`; the Pi
  immediately fetches pending commands and acknowledges results.

The SSE wake-up path is best-effort in the MVP deployment. It uses in-process
listeners and assumes one API process; polling is the correctness fallback if
the stream reconnects, the process restarts, or the API later runs more than
one worker.

## Pi Runtime Settings

These settings are optional and runtime-editable through the existing local API.
Cloud control is disabled unless both `METROCLOCK_CLOUD_ENABLED` and
`METROCLOCK_CLOUD_BASE_URL` are configured.

- `METROCLOCK_CLOUD_ENABLED`: boolean, default `false`
- `METROCLOCK_CLOUD_BASE_URL`: HTTPS backend origin, for example `https://api.example.com`
- `METROCLOCK_CLOUD_DEVICE_TOKEN`: bearer token issued by the backend after pairing
- `METROCLOCK_CLOUD_PAIRING_CODE`: short-lived code created in the user account
- `METROCLOCK_CLOUD_HEARTBEAT_SECONDS`: status report cadence, default `30`
- `METROCLOCK_CLOUD_COMMAND_POLL_SECONDS`: command poll cadence, default `5`

## Pairing Flow

1. The signed-in iOS app creates a short-lived pairing token with
   `POST /api/pairing-tokens`.
2. During local setup, the iOS app sends the cloud URL and pairing token to the
   MetroClock automatically with `POST /api/cloud/setup` on the local Pi API.
3. The Pi calls `POST /api/devices/pair`.
4. The backend validates the pairing code, assigns the device to the user, and
   returns a long-lived `device_token`.
5. The Pi stores `METROCLOCK_CLOUD_DEVICE_TOKEN` and clears the pairing code.

Manual entry can remain as a support/debug fallback, but it should not be the
default user experience.

## Local Pi Setup Endpoint

The local Pi API accepts cloud setup from the iOS app while the app is connected
to the device over setup Wi-Fi or the local network.

### `POST /api/cloud/setup`

Request:

```json
{
  "cloud_base_url": "https://metroclock-cloud-api.onrender.com",
  "pairing_token": "pair_...",
  "cloud_enabled": true
}
```

Response:

```json
{
  "ok": true,
  "changed": [
    "METROCLOCK_CLOUD_ENABLED",
    "METROCLOCK_CLOUD_BASE_URL",
    "METROCLOCK_CLOUD_PAIRING_CODE"
  ],
  "cloud": {
    "enabled": true,
    "configured": true,
    "base_url": "https://metroclock-cloud-api.onrender.com",
    "device_id": "stable-device-id",
    "device_token_set": false,
    "pairing_code_set": true
  }
}
```

### `GET /api/cloud/status`

Returns masked cloud setup state.

### `POST /api/cloud/disable`

Disables cloud control and clears any pending pairing token. Existing device
tokens are left in place so cloud can be re-enabled without re-pairing.

## App-Facing Endpoints

These endpoints are for the iOS app and internal debug dashboard. They require
a Supabase Auth user access token:

```http
Authorization: Bearer <supabase-user-access-token>
```

### `POST /api/pairing-tokens`

Creates a short-lived token that the app passes to the Pi during setup.

Request:

```json
{
  "device_name": "Kitchen MetroClock",
  "ttl_seconds": 600
}
```

Response:

```json
{
  "pairing_token": "pair_...",
  "expires_at": "2026-08-04T20:00:00+00:00"
}
```

### `GET /api/me/devices`

Returns devices visible to the signed-in user, plus latest status.

### `POST /api/devices/{device_uid}/commands`

Creates a pending command for a device the signed-in user owns/admins.

Request:

```json
{
  "action": "set_mode",
  "payload": {
    "mode": "clock"
  }
}
```

### `GET /api/devices/{device_uid}/settings`

Returns the latest settings/status payload reported by the Pi heartbeat. Secret
values are masked by the Pi before they reach the cloud API.

Response:

```json
{
  "settings": {
    "DISPLAY_MODE": "clock",
    "WEATHER_ZIP": "20001"
  },
  "reported_at": "2026-08-05T19:30:00+00:00"
}
```

### `PATCH /api/devices/{device_uid}/settings`

Queues a `set_settings` command for a device the signed-in user owns/admins.
The iOS app can poll the returned command id until it is acknowledged.

Request:

```json
{
  "settings": {
    "STOCKS_SYMBOLS": "AAPL,MSFT,SPY",
    "STOCKS_VIEW_MODE": "ticker"
  }
}
```

Response:

```json
{
  "id": "command-id",
  "status": "pending"
}
```

### `GET /api/devices/{device_uid}/commands/{command_id}`

Returns command status for app-created commands so clients can show success or
surface the Pi's failure message.

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

### `GET /api/devices/{device_id}/events`

Headers:

```http
Authorization: Bearer <device_token>
```

Server-Sent Events stream used to wake the Pi when commands are available.

Example event:

```text
event: commands_available
data: {"type":"commands_available","command_id":"cmd_123"}
```

The Pi should respond by calling `GET /api/devices/{device_id}/commands`.
Polling remains the fallback if the event stream disconnects.

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
