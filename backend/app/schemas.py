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
    qr_payload: str
    created_at: str


class EventIn(BaseModel):
    id: str
    event_type: str
    ticket_id: str
    payload: dict[str, Any]
    created_at: str


class ApiAck(BaseModel):
    status: str
    id: str


class PricingOut(BaseModel):
    ticket_id: str
    amount_cents: int
