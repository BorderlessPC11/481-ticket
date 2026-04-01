from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

TICKET_STATUS_OPEN = "OPEN"
TICKET_STATUS_AWAITING_PAYMENT = "AWAITING_PAYMENT"
TICKET_STATUS_CLOSED = "CLOSED"

EVENT_STATUS_PENDING = "PENDING"
EVENT_STATUS_QUEUED = "QUEUED"
EVENT_STATUS_SENT = "SENT"


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    price_cents: int
    currency: str = "BRL"


@dataclass(frozen=True)
class Ticket:
    id: str
    product_id: str
    product_name: str
    amount_cents: int
    paid: bool
    qr_payload: str
    qr_path: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class PaymentResult:
    approved: bool
    provider: str
    transaction_id: str
    amount_cents: int
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class Event:
    id: str
    event_type: str
    ticket_id: str
    payload: dict[str, Any]
    status: str
    created_at: datetime
