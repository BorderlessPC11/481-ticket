# POS System

## Prerequisites

- Python 3.10+

## Setup

1. Create and activate a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy environment file:
   - `cp .env.example .env`
4. Update `.env` values as needed.

Required environment variables:
- `API_BASE_URL`
- `API_TOKEN`
- `PAYMENT_API_KEY`
- `DEVICE_ID`

Payment providers:
- `PAYMENT_PROVIDER=mock` uses local simulated payment approval.
- `PAYMENT_PROVIDER=asaas` uses Asaas API and requires:
  - `ASAAS_CUSTOMER_ID`
  - Optional `ASAAS_API_BASE_URL` (default: `https://sandbox.asaas.com/api/v3`)
  - Optional `ASAAS_BILLING_TYPE` (default: `PIX`)
  - Optional `PAYMENT_STATUS_POLL_ATTEMPTS` (default: `6`)
  - Optional `PAYMENT_STATUS_POLL_INTERVAL_SECONDS` (default: `2`)

## Run

From inside `pos_system/`:

- Preferred: `python3 run.py`
- Alternative: `python3 -m app.main`
- **Windows (sem `python` no PATH):** dê duplo clique em `run-pos.cmd` ou execute `.\run-pos.cmd` (usa `.\.venv\Scripts\python.exe`). Na raiz do repositório: `run-pos.cmd`.

## Tests

From inside `pos_system/`:

- `python3 -m unittest discover -s tests -v`

## Operations Notes

- Ticket is only closed after confirmed payment status (`RECEIVED`/`CONFIRMED`/`RECEIVED_IN_CASH`).
- If payment is pending, POS waits for backend-confirmed status polling window.
- Use menu option `4` to replay offline queue items.
