from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_bearer_token
from app.config import load_settings
from app.database import get_db
from app.repositories.pos_repository import PosRepository
from app.schemas import ApiAck, EventIn, PaymentStatusOut, PricingOut, ProductOut, TicketIn
from app.services.pricing_service import PricingService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/products", response_model=list[ProductOut], dependencies=[Depends(require_bearer_token)])
@router.get("/api/products/", response_model=list[ProductOut], dependencies=[Depends(require_bearer_token)])
def get_products(db: Session = Depends(get_db)) -> list[ProductOut]:
    repo = PosRepository(db)
    return [ProductOut.model_validate(row, from_attributes=True) for row in repo.list_products()]


@router.post("/tickets", response_model=ApiAck, dependencies=[Depends(require_bearer_token)])
def post_ticket(payload: TicketIn, db: Session = Depends(get_db)) -> ApiAck:
    repo = PosRepository(db)
    obj = repo.upsert_ticket(payload)
    return ApiAck(status="stored", id=obj.id)


@router.post("/events", response_model=ApiAck, dependencies=[Depends(require_bearer_token)])
def post_event(payload: EventIn, db: Session = Depends(get_db)) -> ApiAck:
    repo = PosRepository(db)
    obj = repo.upsert_event(payload)
    return ApiAck(status="stored", id=obj.id)


@router.get("/pricing", response_model=PricingOut, dependencies=[Depends(require_bearer_token)])
def get_pricing(qr_payload: str, db: Session = Depends(get_db)) -> PricingOut:
    repo = PosRepository(db)
    settings = load_settings()
    pricing_service = PricingService(settings=settings)

    try:
        import json

        data = json.loads(qr_payload)
        ticket_id = str(data["ticket_id"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid qr_payload: {exc}") from exc

    ticket = repo.get_ticket(ticket_id)
    resolved_ticket_id, amount = pricing_service.compute_amount(qr_payload=qr_payload, ticket=ticket)
    return PricingOut(ticket_id=resolved_ticket_id, amount_cents=amount)


@router.get("/payments/status/{ticket_id}", response_model=PaymentStatusOut, dependencies=[Depends(require_bearer_token)])
def get_payment_status(ticket_id: str, db: Session = Depends(get_db)) -> PaymentStatusOut:
    repo = PosRepository(db)
    payment = repo.get_latest_payment_by_ticket(ticket_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found for ticket")
    paid = str(payment.status).upper() in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}
    return PaymentStatusOut(
        ticket_id=ticket_id,
        provider_payment_id=payment.provider_payment_id,
        status=payment.status,
        paid=paid,
        pix_payload=payment.pix_payload or "",
    )


@router.post("/webhooks/asaas", response_model=dict[str, str])
def asaas_webhook(
    payload: dict,
    db: Session = Depends(get_db),
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
) -> dict[str, str]:
    settings = load_settings()
    if settings.webhook_token and x_webhook_token != settings.webhook_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    event_id = str(payload.get("id", "")).strip()
    event_type = str(payload.get("event", "")).strip()
    payment_data = payload.get("payment") or {}
    provider_payment_id = str(payment_data.get("id", "")).strip()
    ticket_id = str(payment_data.get("externalReference", "")).strip()
    status = str(payment_data.get("status", "")).upper().strip()
    billing_type = str(payment_data.get("billingType", "PIX")).upper().strip() or "PIX"
    value = float(payment_data.get("value", 0.0) or 0.0)
    amount_cents = int(round(value * 100))
    pix_payload = str((payment_data.get("pixTransaction") or {}).get("payload", "")).strip()

    if not event_id or not event_type or not provider_payment_id or not ticket_id:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    repo = PosRepository(db)
    is_new = repo.save_webhook_event_if_new(provider="asaas", event_id=event_id, event_type=event_type, payload=payload)
    if not is_new:
        return {"status": "duplicate_ignored"}

    repo.upsert_payment(
        ticket_id=ticket_id,
        provider="asaas",
        provider_payment_id=provider_payment_id,
        billing_type=billing_type,
        amount_cents=amount_cents,
        status=status,
        pix_payload=pix_payload,
        raw_payload=payment_data,
    )
    if status in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}:
        repo.mark_ticket_paid_closed(ticket_id)
    return {"status": "processed"}
