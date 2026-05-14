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

## Core Read Endpoints

### `GET /api/status`

Primary device status payload. Includes:

- `device_id`: stable device identifier
- `app_version`: app build/version string
- `api_version`: API contract version
- `write_auth_required`: boolean
- Existing runtime/config/status fields:
  - `hostname`, `ip`, `display_mode`
  - `weather_preview`, `ambient_scene`
  - runtime config fields from `/api/settings` (with secret masking)

### `GET /api/settings`

- Returns runtime-editable settings (secrets masked with `*_set` flags).

### `GET /api/clock/styles`

- Returns app-facing metadata for dynamic clock customization controls:
  - `CLOCK_FONT_STYLE` options/default
  - `CLOCK_SIZE` min/max/step/default
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

