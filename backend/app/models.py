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
    qr_payload = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    ticket_id = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)
