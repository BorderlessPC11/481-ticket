from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_bearer_token
from app.config import load_settings
from app.database import get_db
from app.repositories.pos_repository import PosRepository
from app.schemas import ApiAck, EventIn, PricingOut, ProductOut, TicketIn
from app.services.pricing_service import PricingService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/products", response_model=list[ProductOut], dependencies=[Depends(require_bearer_token)])
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
