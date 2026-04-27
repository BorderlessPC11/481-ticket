from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.models.exceptions import ApiClientError, PaymentError
from app.offline.queue import OfflineQueueService
from app.payments.mock_provider import MockPaymentProvider
from app.qr.service import QrService
from app.services.ticket_service import TicketService
from app.storage.repositories import PosRepository
from app.storage.schema import init_db
from app.utils.logger import ActionLogger


class FakeApiClient:
    def __init__(self, fail_post: bool = False, payment_status: str = "CONFIRMED") -> None:
        self.fail_post = fail_post
        self.payment_status = payment_status

    def get_products(self):
        return [{"id": "p1", "name": "Daily", "price_cents": 1000}]

    def post_ticket(self, payload):
        if self.fail_post:
            raise ApiClientError("offline")
        return {"ok": True, "payload": payload}

    def get_pricing(self, qr_payload):
        return {"amount_cents": 1500, "qr_payload": qr_payload}

    def calculate_exit_amount_cents(self, **kwargs):
        return 1500

    def post_event(self, payload):
        if self.fail_post:
            raise ApiClientError("offline")
        return {"ok": True, "payload": payload}

    def get_payment_status(self, ticket_id):
        return {"ticket_id": ticket_id, "status": self.payment_status, "paid": self.payment_status in {"CONFIRMED", "RECEIVED"}}


class TicketServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.conn = sqlite3.connect(":memory:")
        init_db(self.conn)
        self.repo = PosRepository(self.conn)
        self.settings = Settings(
            api_base_url="https://example.com/api",
            api_token="token",
            api_csrf_token="",
            api_product_valor_unitario_in_cents=False,
            api_cnpj="00000000000100",
            api_equipamento_id="",
            api_payment_quantidade=1,
            payment_provider="mock",
            payment_api_key="pay-key",
            device_id="POS-01",
            timeout_seconds=2,
            retry_limit=3,
            database_path=":memory:",
        )
        self.logger = ActionLogger(log_path=str(self.tmp_path / "test.log"))
        self.qr = QrService(output_dir=str(self.tmp_path / "qrs"))

    def tearDown(self) -> None:
        self.conn.close()
        self.logger.close()
        self.tmp.cleanup()

    def _build_service(self, fail_post: bool = False, payment_status: str = "CONFIRMED", approved: bool = True) -> TicketService:
        return TicketService(
            settings=self.settings,
            repository=self.repo,
            api_client=FakeApiClient(fail_post=fail_post, payment_status=payment_status),
            payment_provider=MockPaymentProvider(api_key="pay-key", approved=approved, latency_seconds=0),
            qr_service=self.qr,
            offline_queue=OfflineQueueService(repository=self.repo),
            logger=self.logger,
        )

    def test_emit_ticket_paid(self) -> None:
        service = self._build_service()
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        result = service.emit_ticket(product=product, pay_now=True)
        self.assertTrue(result.ticket.paid)
        self.assertTrue(any("Pagamento: aprovado" in x for x in result.report_lines))

    def test_emit_ticket_paid_rejected_persists_nothing(self) -> None:
        service = self._build_service(approved=False)
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        with self.assertRaises(PaymentError):
            service.emit_ticket(product=product, pay_now=True)
        n_tickets = self.conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
        n_tx = self.conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
        n_q = self.conn.execute("SELECT COUNT(*) AS c FROM sync_queue").fetchone()["c"]
        self.assertEqual(n_tickets, 0)
        self.assertEqual(n_tx, 0)
        self.assertEqual(n_q, 0)

    def test_emit_ticket_unpaid(self) -> None:
        service = self._build_service()
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        result = service.emit_ticket(product=product, pay_now=False)
        self.assertFalse(result.ticket.paid)

    def test_enqueue_when_api_offline(self) -> None:
        service = self._build_service(fail_post=True)
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        service.emit_ticket(product=product, pay_now=False)
        pending = self.repo.get_pending_sync()
        self.assertGreaterEqual(len(pending), 1)

    def test_exit_payment_flow(self) -> None:
        service = self._build_service()
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        ticket = service.emit_ticket(product=product, pay_now=False).ticket
        result = service.process_exit_payment(ticket.qr_payload)
        self.assertEqual(result["ticket_id"], ticket.id)
        self.assertEqual(result["charged_amount_cents"], 1500)

    def test_exit_payment_pending_then_confirmed(self) -> None:
        service = self._build_service(payment_status="CONFIRMED", approved=False)
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        ticket = service.emit_ticket(product=product, pay_now=False).ticket
        result = service.process_exit_payment(ticket.qr_payload)
        self.assertIn(result["payment_status"], {"CONFIRMED", "RECEIVED"})

    def test_event_marked_queued_when_api_offline(self) -> None:
        service = self._build_service(fail_post=True)
        product = {"id": "p1", "name": "Daily", "price_cents": 1000}
        ticket = service.emit_ticket(product=product, pay_now=False).ticket

        cursor = self.conn.execute("SELECT status FROM events WHERE ticket_id=? ORDER BY created_at DESC LIMIT 1", (ticket.id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "QUEUED")


if __name__ == "__main__":
    unittest.main()
