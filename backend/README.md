# POS Backend (FastAPI)

## Run

1. Create env file:
   - `cp .env.example .env`
2. Install dependencies:
   - `python3 -m venv .venv`
   - `.venv/bin/python -m pip install -r requirements.txt`
3. Start API:
   - `.venv/bin/python -m uvicorn app.main:app --reload --port 8000`

## POS Client Integration

Set in `pos_system/.env`:

- `API_BASE_URL=http://localhost:8000`
- `API_TOKEN=dev-static-token` (or your configured `BACKEND_API_TOKEN`)

## Endpoints

- `GET /health`
- `GET /products` (Bearer)
- `POST /tickets` (Bearer)
- `GET /pricing?qr_payload=...` (Bearer)
- `POST /events` (Bearer)

## Pricing Logic

- Base amount starts from stored ticket amount.
- No extra charge during grace period (`BACKEND_PRICING_GRACE_MINUTES`).
- After grace period, adds `BACKEND_PRICING_STEP_CENTS` every `BACKEND_PRICING_STEP_MINUTES`.
