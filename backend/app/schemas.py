from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: str
    name: str
    price_cents: int
    currency: str = "BRL"


class TicketIn(BaseModel):
    id: str
    product_id: str
    product_name: str
    amount_cents: int = Field(ge=0)
    paid: bool
    status: str = "OPEN"
    qr_payload: str
    created_at: str


class EventIn(BaseModel):
    id: str
    event_type: str
    ticket_id: str
    payload: dict[str, Any]
    status: str = "PENDING"
    created_at: str


class ApiAck(BaseModel):
    status: str
    id: str


class PricingOut(BaseModel):
    ticket_id: str
    amount_cents: int


class PaymentStatusOut(BaseModel):
    ticket_id: str
    provider_payment_id: str
    status: str
    paid: bool
    pix_payload: str = ""
