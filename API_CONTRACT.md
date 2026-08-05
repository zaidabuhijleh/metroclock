# MetroClock API Contract v1.0

This document defines the alpha API contract used by the web UI and iOS app.

## Versioning

- `api_version`: returned by `GET /api/status`
- Current value: `1.0`
- Additive response fields are allowed in v1.x.
- Breaking request/response changes require `api_version` bump.

## Authentication

- Read endpoints are open by default.
- Write endpoints require auth **only if** `METROCLOCK_API_TOKEN` is set in the service environment.
- Provide token using either:
  - Header: `X-MetroClock-Token: <token>`
  - Header: `Authorization: Bearer <token>`

## Cloud Control

Cloud control is optional and outbound-only. When configured, the Pi talks to a
backend using the settings documented in `CLOUD_CONTROL.md`; the backend does
not call the local Flask server directly.

The local API exposes the cloud settings through `/api/settings` like other
runtime-editable fields. Secret fields are masked in read responses:

- `METROCLOCK_CLOUD_DEVICE_TOKEN`
- `METROCLOCK_CLOUD_PAIRING_CODE`

### Local Cloud Setup Endpoints

- `GET /api/cloud/status`
- `POST /api/cloud/setup`
- `POST /api/cloud/disable`

`POST /api/cloud/setup` is used by the iOS app during local setup. It stores
the cloud URL and short-lived pairing token so the Pi can pair outbound.

Request:

```json
{
  "cloud_base_url": "https://metroclock-cloud-api.onrender.com",
  "pairing_token": "pair_...",
  "cloud_enabled": true
}
```

## Core Read Endpoints

### `GET /api/status`

Primary device status payload. Includes:

- `device_id`: stable device identifier
- `app_version`: app build/version string
- `api_version`: API contract version
- `write_auth_required`: boolean
- Existing runtime/config/status fields:
  - `hostname`, `ip`, `display_mode`
  - `wifi_setup`: WiFi fallback/setup status, including hotspot SSID/IP when active
  - `weather_preview`, `ambient_scene`
  - runtime config fields from `/api/settings` (with secret masking)

### `GET /api/settings`

- Returns runtime-editable settings (secrets masked with `*_set` flags).

### `GET /api/clock/styles`

- Returns app-facing metadata for dynamic clock customization controls:
  - `CLOCK_FONT_STYLE` options/default
  - `CLOCK_SIZE` options/default (`0.5`=S, `0.75`=M, `1.0`=L)
  - `CLOCK_SHOW_DATE` and `CLOCK_SHOW_AMPM` metadata/defaults
  - Clock color override keys + expected `#RRGGBB` format

## Write Endpoints

- `POST /api/settings`
- `POST /api/mode`
- `POST /api/weather/preview`
- `POST /api/ambient/scene`
- `POST /api/wifi/connect`
- `POST /api/restart`
- `POST /api/reboot`

If token auth is enabled and token is missing/invalid, responses return:

- HTTP `401`
- JSON:
  - `ok: false`
  - `error: "Unauthorized"`
