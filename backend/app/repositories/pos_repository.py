from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Product, Ticket
from app.schemas import EventIn, TicketIn


class PosRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_products(self) -> list[Product]:
        return list(self._db.execute(select(Product).order_by(Product.name.asc())).scalars().all())

    def upsert_ticket(self, payload: TicketIn) -> Ticket:
        obj = self._db.get(Ticket, payload.id)
        if obj is None:
            obj = Ticket(id=payload.id)
            self._db.add(obj)
        obj.product_id = payload.product_id
        obj.product_name = payload.product_name
        obj.amount_cents = payload.amount_cents
        obj.paid = payload.paid
        obj.qr_payload = payload.qr_payload
        obj.created_at = payload.created_at
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def upsert_event(self, payload: EventIn) -> Event:
        obj = self._db.get(Event, payload.id)
        if obj is None:
            obj = Event(id=payload.id)
            self._db.add(obj)
        obj.event_type = payload.event_type
        obj.ticket_id = payload.ticket_id
        obj.payload = json.dumps(payload.payload, separators=(",", ":"), sort_keys=True)
        obj.created_at = payload.created_at
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self._db.get(Ticket, ticket_id)

    def seed_default_products(self) -> None:
        defaults = [
            Product(id="daily", name="Daily Pass", price_cents=1000, currency="BRL"),
            Product(id="hourly", name="Hourly Pass", price_cents=500, currency="BRL"),
            Product(id="vip", name="VIP Pass", price_cents=2000, currency="BRL"),
        ]
        for item in defaults:
            if self._db.get(Product, item.id) is None:
                self._db.add(item)
        self._db.commit()
