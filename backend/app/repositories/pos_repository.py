from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Payment, Product, Ticket, WebhookEvent
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
        obj.status = payload.status
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
        obj.status = payload.status
        obj.created_at = payload.created_at
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self._db.get(Ticket, ticket_id)

    def get_latest_payment_by_ticket(self, ticket_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.ticket_id == ticket_id).order_by(Payment.updated_at.desc()).limit(1)
        return self._db.execute(stmt).scalar_one_or_none()

    def upsert_payment(
        self,
        *,
        ticket_id: str,
        provider: str,
        provider_payment_id: str,
        billing_type: str,
        amount_cents: int,
        status: str,
        pix_payload: str,
        raw_payload: dict,
    ) -> Payment:
        now = datetime.now(timezone.utc).isoformat()
        stmt = select(Payment).where(Payment.provider_payment_id == provider_payment_id).limit(1)
        obj = self._db.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = Payment(
                ticket_id=ticket_id,
                provider=provider,
                provider_payment_id=provider_payment_id,
                billing_type=billing_type,
                amount_cents=amount_cents,
                status=status,
                pix_payload=pix_payload,
                raw_payload=json.dumps(raw_payload, separators=(",", ":"), sort_keys=True),
                created_at=now,
                updated_at=now,
            )
            self._db.add(obj)
        else:
            obj.ticket_id = ticket_id
            obj.status = status
            obj.amount_cents = amount_cents
            obj.billing_type = billing_type
            obj.pix_payload = pix_payload
            obj.raw_payload = json.dumps(raw_payload, separators=(",", ":"), sort_keys=True)
            obj.updated_at = now
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def save_webhook_event_if_new(self, *, provider: str, event_id: str, event_type: str, payload: dict) -> bool:
        stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id).limit(1)
        existing = self._db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return False
        item = WebhookEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=json.dumps(payload, separators=(",", ":"), sort_keys=True),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._db.add(item)
        self._db.commit()
        return True

    def mark_ticket_paid_closed(self, ticket_id: str) -> Ticket | None:
        obj = self._db.get(Ticket, ticket_id)
        if obj is None:
            return None
        obj.paid = True
        obj.status = "CLOSED"
        self._db.commit()
        self._db.refresh(obj)
        return obj

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
