# MetroClock Cloud API

Small FastAPI service for MetroClock remote access. The Pi talks to this API
over outbound HTTPS; the iOS app talks to this API using the signed-in user's
Supabase Auth access token.

The web dashboard is internal/debug-only for now. User-facing onboarding and
control should be designed around the iOS app.

## Local Setup

```bash
cd cloud_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

On Windows PowerShell:

```powershell
cd cloud_api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

## Required Environment

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

The service role key must never be shipped to the Pi or browser clients.

## Deploy On Render

This repo includes a root-level `render.yaml` Blueprint that deploys
`cloud_api/` as a web service.

1. Push this repo to GitHub.
2. In Render, create a new Blueprint from the repo.
3. Render should detect `render.yaml`.
4. Add the required environment variables when prompted:
   - `SUPABASE_URL`
   - `SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `METROCLOCK_CORS_ORIGINS`
5. Deploy.
6. Test `https://<your-service>.onrender.com/health`.

For local testing, `METROCLOCK_CORS_ORIGINS` can include localhost origins. For
production, set it to the iOS/web origins that should be allowed. The iOS app
does not rely on browser CORS, but the internal dashboard will.

## Implemented App Endpoints

App endpoints require:

```http
Authorization: Bearer <supabase-user-access-token>
```

- `POST /api/pairing-tokens`
- `GET /api/me/devices`
- `POST /api/devices/{device_uid}/commands`

The pairing token is meant to be passed automatically from the iOS app to the
MetroClock during local setup. Users should not need to type it manually in the
normal flow.

## Internal Debug Page

`GET /debug` serves a tiny internal helper page for manual testing. It lets you
paste a Supabase user access token, create pairing tokens, list devices, and
send simple commands.

This is for development/debugging only. It should not be presented as a
customer dashboard.

## Implemented Pi Endpoints

- `POST /api/devices/pair`
- `POST /api/devices/{device_uid}/heartbeat`
- `GET /api/devices/{device_uid}/commands`
- `POST /api/devices/{device_uid}/commands/{command_id}/ack`

These match the contract in `../CLOUD_CONTROL.md`.
