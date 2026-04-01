from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.api.client import ExternalApiClient
from app.config import Settings
from app.models.entities import (
    EVENT_STATUS_PENDING,
    EVENT_STATUS_QUEUED,
    EVENT_STATUS_SENT,
    TICKET_STATUS_AWAITING_PAYMENT,
    TICKET_STATUS_CLOSED,
    TICKET_STATUS_OPEN,
    Event,
    Ticket,
)
from app.models.exceptions import ApiClientError, PaymentError, ValidationError
from app.offline.queue import OfflineQueueService
from app.payments.base import PaymentProvider
from app.qr.service import QrService
from app.storage.repositories import PosRepository
from app.utils.logger import ActionLogger


class TicketService:
    def __init__(
        self,
        settings: Settings,
        repository: PosRepository,
        api_client: ExternalApiClient,
        payment_provider: PaymentProvider,
        qr_service: QrService,
        offline_queue: OfflineQueueService,
        logger: ActionLogger,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._api_client = api_client
        self._payment_provider = payment_provider
        self._qr_service = qr_service
        self._offline_queue = offline_queue
        self._logger = logger

    def fetch_products(self) -> list[dict[str, Any]]:
        products = self._api_client.get_products()
        self._logger.log("fetch_products", {"count": len(products)}, "ok")
        return products

    def emit_ticket(self, product: dict[str, Any], pay_now: bool) -> Ticket:
        ticket_id = str(uuid.uuid4())
        amount_cents = int(product["price_cents"])
        qr_payload_data = {
            "ticket_id": ticket_id,
            "product_id": product["id"],
            "device_id": self._settings.device_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        qr_payload = self._qr_service.encode_ticket_data(qr_payload_data)
        qr_path = self._qr_service.generate_qr(ticket_id=ticket_id, qr_payload=qr_payload)

        paid = False
        if pay_now:
            result = self._payment_provider.charge(amount_cents=amount_cents, reference_id=ticket_id)
            if not result.approved:
                raise PaymentError("Payment was not approved")
            paid = True
            self._repository.save_transaction(ticket_id=ticket_id, payment_result=result)
            self._logger.log("payment_charge", {"ticket_id": ticket_id, "tx_id": result.transaction_id}, "ok")

        ticket = Ticket(
            id=ticket_id,
            product_id=str(product["id"]),
            product_name=str(product.get("name", "unknown")),
            amount_cents=amount_cents,
            paid=paid,
            qr_payload=qr_payload,
            qr_path=qr_path,
            status=TICKET_STATUS_OPEN,
            created_at=datetime.now(timezone.utc),
        )
        self._repository.save_ticket(ticket)
        self._logger.log("ticket_created", {"ticket_id": ticket.id, "paid": paid}, "ok")

        ticket_payload = self._ticket_to_api_payload(ticket)
        self._send_or_enqueue("ticket", "/tickets", ticket_payload, f"ticket:{ticket.id}")

        event = Event(
            id=str(uuid.uuid4()),
            event_type="ENTRY",
            ticket_id=ticket.id,
            payload={"ticket_id": ticket.id, "paid": paid},
            status=EVENT_STATUS_PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._repository.save_event(event)
        self._send_or_enqueue_event(event)
        return ticket

    def process_exit_payment(self, qr_payload: str) -> dict[str, Any]:
        try:
            data = json.loads(qr_payload)
        except json.JSONDecodeError as exc:
            raise ValidationError("QR payload is not valid JSON") from exc
        ticket_id = str(data.get("ticket_id", "")).strip()
        if not ticket_id:
            raise ValidationError("QR payload is missing ticket_id")
        ticket = self._repository.get_ticket_by_id(ticket_id)
        if ticket is None:
            raise ValidationError("Ticket not found in local storage")

        pricing = self._api_client.get_pricing(qr_payload)
        amount_cents = int(pricing.get("amount_cents", ticket["amount_cents"]))
        payment_result = self._payment_provider.charge(amount_cents=amount_cents, reference_id=ticket_id)
        self._repository.save_transaction(ticket_id=ticket_id, payment_result=payment_result)
        if payment_result.approved:
            final_status = "CONFIRMED"
            self._repository.update_ticket_status(ticket_id=ticket_id, status=TICKET_STATUS_CLOSED)
        else:
            self._repository.update_ticket_status(ticket_id=ticket_id, status=TICKET_STATUS_AWAITING_PAYMENT)
            final_status = self._wait_for_payment_confirmation(ticket_id)
            if final_status in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}:
                self._repository.update_ticket_status(ticket_id=ticket_id, status=TICKET_STATUS_CLOSED)
            else:
                raise PaymentError("Exit payment is pending confirmation")

        event = Event(
            id=str(uuid.uuid4()),
            event_type="EXIT",
            ticket_id=ticket_id,
            payload={"ticket_id": ticket_id, "amount_cents": amount_cents, "payment_status": final_status},
            status=EVENT_STATUS_PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._repository.save_event(event)
        self._send_or_enqueue_event(event)
        self._logger.log("exit_payment", {"ticket_id": ticket_id, "amount_cents": amount_cents}, "ok")

        return {
            "ticket_id": ticket_id,
            "charged_amount_cents": amount_cents,
            "transaction_id": payment_result.transaction_id,
            "payment_status": final_status,
        }

    def _send_or_enqueue_event(self, event: Event) -> None:
        sent = self._send_or_enqueue("event", "/events", self._event_to_api_payload(event), f"event:{event.id}")
        event_status = EVENT_STATUS_SENT if sent else EVENT_STATUS_QUEUED
        self._repository.update_event_status(event.id, event_status)

    def _wait_for_payment_confirmation(self, ticket_id: str) -> str:
        latest_status = "PENDING"
        for _ in range(self._settings.payment_status_poll_attempts):
            try:
                payment = self._api_client.get_payment_status(ticket_id)
            except ApiClientError:
                time.sleep(self._settings.payment_status_poll_interval_seconds)
                continue
            latest_status = str(payment.get("status", "PENDING")).upper()
            if latest_status in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}:
                return latest_status
            time.sleep(self._settings.payment_status_poll_interval_seconds)
        return latest_status

    def _send_or_enqueue(self, queue_type: str, endpoint: str, payload: dict[str, Any], idempotency_key: str) -> bool:
        try:
            if endpoint == "/tickets":
                self._api_client.post_ticket(payload)
            elif endpoint == "/events":
                self._api_client.post_event(payload)
            else:
                raise ValueError(f"Unsupported endpoint: {endpoint}")
            self._logger.log("api_send", {"endpoint": endpoint, "idempotency_key": idempotency_key}, "ok")
            return True
        except ApiClientError:
            self._offline_queue.enqueue_api_call(
                queue_type=queue_type,
                endpoint=endpoint,
                payload=payload,
                idempotency_key=idempotency_key,
            )
            self._logger.log("api_enqueue_offline", {"endpoint": endpoint, "idempotency_key": idempotency_key}, "queued")
            return False

    @staticmethod
    def _ticket_to_api_payload(ticket: Ticket) -> dict[str, Any]:
        return {
            "id": ticket.id,
            "product_id": ticket.product_id,
            "product_name": ticket.product_name,
            "amount_cents": ticket.amount_cents,
            "paid": ticket.paid,
            "status": ticket.status,
            "qr_payload": ticket.qr_payload,
            "created_at": ticket.created_at.isoformat(),
        }

    @staticmethod
    def _event_to_api_payload(event: Event) -> dict[str, Any]:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "ticket_id": event.ticket_id,
            "payload": event.payload,
            "status": event.status,
            "created_at": event.created_at.isoformat(),
        }
