from __future__ import annotations

import sqlite3
from typing import Any

from app.api.client import ExternalApiClient
from app.config import Settings, load_settings
from app.offline.queue import OfflineQueueService
from app.offline.worker import SyncWorker
from app.payments.base import PaymentProvider
from app.payments.asaas_provider import AsaasPaymentProvider
from app.payments.mock_provider import MockPaymentProvider
from app.qr.scanner import SimulatedQrScanner
from app.qr.service import QrService
from app.services.ticket_service import TicketService
from app.storage.repositories import PosRepository
from app.storage.schema import init_db
from app.utils.logger import ActionLogger


def _pick_product(products: list[dict[str, Any]]) -> dict[str, Any]:
    for idx, item in enumerate(products, start=1):
        print(f"{idx}. {item.get('name', 'unknown')} - {item.get('price_cents', 0)} cents")
    selection = int(input("Select product number: ").strip())
    if selection < 1 or selection > len(products):
        raise ValueError("Invalid product selection")
    return products[selection - 1]


def _build_payment_provider(settings: Settings) -> PaymentProvider:
    provider_name = settings.payment_provider
    normalized = provider_name.strip().lower()
    if normalized == "mock":
        return MockPaymentProvider(api_key=settings.payment_api_key)
    if normalized == "asaas":
        return AsaasPaymentProvider(
            api_key=settings.payment_api_key,
            customer_id=settings.asaas_customer_id,
            api_base_url=settings.asaas_api_base_url,
            billing_type=settings.asaas_billing_type,
            timeout_seconds=settings.timeout_seconds,
        )
    raise ValueError(f"Unsupported PAYMENT_PROVIDER: {provider_name}")


def run() -> None:
    settings = load_settings()
    logger = ActionLogger()

    conn = sqlite3.connect(settings.database_path)
    init_db(conn)
    repository = PosRepository(conn)

    api_client = ExternalApiClient(settings=settings)
    payment_provider = _build_payment_provider(settings)
    qr_service = QrService()
    scanner = SimulatedQrScanner()
    offline_queue = OfflineQueueService(repository=repository)
    ticket_service = TicketService(
        settings=settings,
        repository=repository,
        api_client=api_client,
        payment_provider=payment_provider,
        qr_service=qr_service,
        offline_queue=offline_queue,
        logger=logger,
    )
    worker = SyncWorker(
        repository=repository,
        api_client=api_client,
        logger=logger,
        retry_limit=settings.retry_limit,
    )

    menu = """
1 - Emit Ticket (Paid)
2 - Emit Ticket (Unpaid)
3 - Exit Payment
4 - Sync Offline Data
5 - Exit
"""
    while True:
        try:
            print(menu)
            option = input("Choose an option: ").strip()
            if option == "1":
                product = _pick_product(ticket_service.fetch_products())
                emit_result = ticket_service.emit_ticket(product=product, pay_now=True)
                for line in emit_result.report_lines:
                    print(line)
                print(f"Concluido. Ticket id: {emit_result.ticket.id}")
            elif option == "2":
                product = _pick_product(ticket_service.fetch_products())
                emit_result = ticket_service.emit_ticket(product=product, pay_now=False)
                for line in emit_result.report_lines:
                    print(line)
                print(f"Concluido. Ticket id: {emit_result.ticket.id}")
            elif option == "3":
                qr_payload = scanner.scan()
                result = ticket_service.process_exit_payment(qr_payload=qr_payload)
                if result.get("payment_status") in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH", "paid"}:
                    print(f"Exit payment ok: {result}")
                else:
                    print(f"Exit payment pending confirmation: {result}")
            elif option == "4":
                processed = worker.run_once()
                print(f"Offline sync processed items: {processed}")
            elif option == "5":
                break
            else:
                print("Invalid option")
        except Exception as exc:  # noqa: BLE001
            logger.log("cli_error", {"error": str(exc)}, "error")
            print(f"Error: {exc}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"Startup error: {exc}")
