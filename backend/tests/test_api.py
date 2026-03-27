from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient

os.environ["BACKEND_API_TOKEN"] = "test-token"
os.environ["BACKEND_DB_PATH"] = "test_backend.db"

from app.main import app  # noqa: E402


def _headers(token: str = "test-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_auth_required() -> None:
    with TestClient(app) as client:
        response = client.get("/products")
        assert response.status_code == 401


def test_products_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/products", headers=_headers())
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1


def test_ticket_event_pricing_flow() -> None:
    now = datetime.now(timezone.utc).isoformat()
    ticket_payload = {
        "id": "t-1",
        "product_id": "daily",
        "product_name": "Daily Pass",
        "amount_cents": 1000,
        "paid": False,
        "qr_payload": json.dumps({"ticket_id": "t-1", "created_at": now}),
        "created_at": now,
    }
    event_payload = {
        "id": "e-1",
        "event_type": "ENTRY",
        "ticket_id": "t-1",
        "payload": {"ticket_id": "t-1"},
        "created_at": now,
    }

    with TestClient(app) as client:
        ticket_resp = client.post("/tickets", json=ticket_payload, headers=_headers())
        assert ticket_resp.status_code == 200
        event_resp = client.post("/events", json=event_payload, headers=_headers())
        assert event_resp.status_code == 200
        pricing_resp = client.get("/pricing", params={"qr_payload": ticket_payload["qr_payload"]}, headers=_headers())
        assert pricing_resp.status_code == 200
        assert pricing_resp.json()["ticket_id"] == "t-1"
        assert pricing_resp.json()["amount_cents"] >= 1000
