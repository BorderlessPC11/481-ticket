# POS Backend (FastAPI)

## Run

1. Create env file:
   - `cp .env.example .env`
2. Install dependencies:
   - `python3 -m venv .venv`
   - `.venv/bin/python -m pip install -r requirements.txt`
3. Start API:
   - `.venv/bin/python -m uvicorn app.main:app --reload --port 8000`
   - **Windows:** `run-backend.cmd` (em `backend/` ou na raiz do repositório) evita depender de `python` no PATH.

## POS Client Integration

Set in `pos_system/.env`:

- `API_BASE_URL=http://localhost:8000`
- `API_TOKEN=dev-static-token` (or your configured `BACKEND_API_TOKEN`)

Set in `backend/.env`:

- `BACKEND_WEBHOOK_TOKEN=<shared-secret-used-by-asaas-webhook>`

## Endpoints

- `GET /health`
- `GET /ready`
- `GET /products` (Bearer)
- `POST /tickets` (Bearer)
- `GET /pricing?qr_payload=...` (Bearer)
- `POST /events` (Bearer)
- `GET /payments/status/{ticket_id}` (Bearer)
- `POST /webhooks/asaas` (`X-Webhook-Token` when configured)

## Pricing Logic

- Base amount starts from stored ticket amount.
- No extra charge during grace period (`BACKEND_PRICING_GRACE_MINUTES`).
- After grace period, adds `BACKEND_PRICING_STEP_CENTS` every `BACKEND_PRICING_STEP_MINUTES`.

## Webhook Replay

- Duplicate Asaas events are ignored by `event_id`.
- You can replay events safely by re-sending the same payload and header token.
