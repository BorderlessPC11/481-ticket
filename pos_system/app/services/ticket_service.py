from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
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


@dataclass(frozen=True)
class EmitTicketResult:
    ticket: Ticket
    report_lines: tuple[str, ...] = ()


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

    def emit_ticket(self, product: dict[str, Any], pay_now: bool) -> EmitTicketResult:
        if pay_now:
            return self._emit_ticket_paid_scenario1(product)
        return self._emit_ticket_unpaid(product)

    def _emit_ticket_paid_scenario1(self, product: dict[str, Any]) -> EmitTicketResult:
        """
        Cenário 1: produto -> pagamento -> (se aprovado) ticket + QR -> API.
        Nada é persistido nem enviado se o pagamento falhar.
        """
        report: list[str] = []
        ticket_id = str(uuid.uuid4())
        amount_cents = int(product["price_cents"])

        result = self._payment_provider.charge(amount_cents=amount_cents, reference_id=ticket_id)
        if not result.approved:
            self._logger.log("payment_charge", {"ticket_id": ticket_id, "approved": False}, "error")
            raise PaymentError(
                "Pagamento nao aprovado: nenhum ticket, QR ou envio para API serao criados (Cenario 1)."
            )

        self._logger.log("payment_charge", {"ticket_id": ticket_id, "tx_id": result.transaction_id}, "ok")
        report.append("Pagamento: aprovado")

        self._repository.save_transaction(ticket_id=ticket_id, payment_result=result)

        entry_at = datetime.now(timezone.utc)
        qr_payload_data = {
            "ticket_id": ticket_id,
            "product_id": product["id"],
            "device_id": self._settings.device_id,
            "created_at": entry_at.isoformat(),
        }
        qr_payload = self._qr_service.encode_ticket_data(qr_payload_data)
        qr_path = self._qr_service.generate_qr(ticket_id=ticket_id, qr_payload=qr_payload)
        report.append(f"QR: gerado em {qr_path}")

        ticket = Ticket(
            id=ticket_id,
            product_id=str(product["id"]),
            product_name=str(product.get("name", "unknown")),
            amount_cents=amount_cents,
            paid=True,
            qr_payload=qr_payload,
            qr_path=qr_path,
            status=TICKET_STATUS_OPEN,
            created_at=entry_at,
        )
        self._repository.save_ticket(ticket)
        self._logger.log("ticket_created", {"ticket_id": ticket.id, "paid": True}, "ok")
        report.append(f"Ticket: criado (pago) — id={ticket.id} — entrada em {entry_at.isoformat()}")

        sent_ticket = self._send_or_enqueue("ticket", "/tickets", self._ticket_to_api_payload(ticket), f"ticket:{ticket.id}")
        report.append("API: ticket " + ("enviado (POST /tickets) com paid=true" if sent_ticket else "enfileirado (POST /tickets) — aguarda sincronizacao"))

        event = Event(
            id=str(uuid.uuid4()),
            event_type="ENTRY",
            ticket_id=ticket.id,
            payload={
                "ticket_id": ticket.id,
                "paid": True,
                "entry_at": entry_at.isoformat(),
            },
            status=EVENT_STATUS_PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._repository.save_event(event)
        sent_event = self._send_or_enqueue("event", "/events", self._event_to_api_payload(event), f"event:{event.id}")
        self._safe_update_event_status(event.id, sent_event)
        report.append("API: evento ENTRY " + ("registrado (POST /events)" if sent_event else "enfileirado (POST /events) — aguarda sincronizacao"))

        return EmitTicketResult(ticket=ticket, report_lines=tuple(report))

    def _emit_ticket_unpaid(self, product: dict[str, Any]) -> EmitTicketResult:
        """
        Cenário 2: emissao sem pagamento imediato (QR antes de possivel pagamento na saida).
        """
        report: list[str] = []
        ticket_id = str(uuid.uuid4())
        amount_cents = int(product["price_cents"])
        entry_at = datetime.now(timezone.utc)
        qr_payload_data = {
            "ticket_id": ticket_id,
            "product_id": product["id"],
            "device_id": self._settings.device_id,
            "created_at": entry_at.isoformat(),
        }
        qr_payload = self._qr_service.encode_ticket_data(qr_payload_data)
        qr_path = self._qr_service.generate_qr(ticket_id=ticket_id, qr_payload=qr_payload)
        report.append(f"QR: gerado em {qr_path}")

        ticket = Ticket(
            id=ticket_id,
            product_id=str(product["id"]),
            product_name=str(product.get("name", "unknown")),
            amount_cents=amount_cents,
            paid=False,
            qr_payload=qr_payload,
            qr_path=qr_path,
            status=TICKET_STATUS_OPEN,
            created_at=entry_at,
        )
        self._repository.save_ticket(ticket)
        self._logger.log("ticket_created", {"ticket_id": ticket.id, "paid": False}, "ok")
        report.append(f"Ticket: criado (aguarda pagamento) — id={ticket.id}")

        sent_ticket = self._send_or_enqueue("ticket", "/tickets", self._ticket_to_api_payload(ticket), f"ticket:{ticket.id}")
        report.append("API: ticket " + ("enviado (POST /tickets)" if sent_ticket else "enfileirado (POST /tickets)"))

        event = Event(
            id=str(uuid.uuid4()),
            event_type="ENTRY",
            ticket_id=ticket.id,
            payload={"ticket_id": ticket.id, "paid": False, "entry_at": entry_at.isoformat()},
            status=EVENT_STATUS_PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self._repository.save_event(event)
        sent_event = self._send_or_enqueue("event", "/events", self._event_to_api_payload(event), f"event:{event.id}")
        self._safe_update_event_status(event.id, sent_event)
        report.append("API: evento ENTRY " + ("registrado" if sent_event else "enfileirado"))

        return EmitTicketResult(ticket=ticket, report_lines=tuple(report))

    def _safe_update_event_status(self, event_id: str, sent: bool) -> None:
        event_status = EVENT_STATUS_SENT if sent else EVENT_STATUS_QUEUED
        self._repository.update_event_status(event_id, event_status)

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

        produto_id = str(data.get("product_id", "")).strip() or str(ticket.get("product_id", "")).strip()
        if not produto_id:
            raise ValidationError("Missing product_id for calculate-tolerance (QR or ticket)")
        cnpj = (self._settings.api_cnpj or "").strip()
        if not cnpj:
            raise ValidationError("API_CNPJ is required for exit payment (POST /api/payments/calculate-tolerance/)")
        data_hora_pagamento = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            amount_cents = self._api_client.calculate_exit_amount_cents(
                produto_id=produto_id,
                cnpj=cnpj,
                data_hora_pagamento=data_hora_pagamento,
            )
        except ApiClientError as exc:
            raise ValidationError(f"Failed to calculate exit amount: {exc}") from exc
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
