from __future__ import annotations

import sqlite3
from typing import Any

from app.api.client import ExternalApiClient
from app.config import load_settings
from app.offline.queue import OfflineQueueService
from app.offline.worker import SyncWorker
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


def run() -> None:
    settings = load_settings()
    logger = ActionLogger()

    conn = sqlite3.connect(settings.database_path)
    init_db(conn)
    repository = PosRepository(conn)

    api_client = ExternalApiClient(settings=settings)
    payment_provider = MockPaymentProvider(api_key=settings.payment_api_key)
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
                ticket = ticket_service.emit_ticket(product=product, pay_now=True)
                print(f"Ticket issued: {ticket.id}, QR file: {ticket.qr_path}")
            elif option == "2":
                product = _pick_product(ticket_service.fetch_products())
                ticket = ticket_service.emit_ticket(product=product, pay_now=False)
                print(f"Ticket issued without payment: {ticket.id}, QR file: {ticket.qr_path}")
            elif option == "3":
                qr_payload = scanner.scan()
                result = ticket_service.process_exit_payment(qr_payload=qr_payload)
                print(f"Exit payment ok: {result}")
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
    run()
