# MetroClock Cloud API

Small FastAPI service for MetroClock remote access. The Pi talks to this API
over outbound HTTPS; browser/mobile clients use Supabase Auth plus the public
tables/policies.

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
- `SUPABASE_SERVICE_ROLE_KEY`

The service role key must never be shipped to the Pi or browser clients.

## Implemented Device Endpoints

- `POST /api/devices/pair`
- `POST /api/devices/{device_uid}/heartbeat`
- `GET /api/devices/{device_uid}/commands`
- `POST /api/devices/{device_uid}/commands/{command_id}/ack`

These match the contract in `../CLOUD_CONTROL.md`.
