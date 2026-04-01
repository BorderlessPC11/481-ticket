from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String, Text

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="BRL")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String, primary_key=True)
    product_id = Column(String, nullable=False)
    product_name = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    paid = Column(Boolean, nullable=False)
    status = Column(String, nullable=False, default="OPEN")
    qr_payload = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    ticket_id = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(String, nullable=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    provider_payment_id = Column(String, nullable=False, unique=True)
    billing_type = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    pix_payload = Column(Text, nullable=False, default="")
    raw_payload = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String, nullable=False)
    event_id = Column(String, nullable=False, unique=True)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
