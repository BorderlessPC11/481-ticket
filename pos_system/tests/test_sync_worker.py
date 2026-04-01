from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.models.entities import Event
from app.models.exceptions import ApiClientError
from app.offline.worker import SyncWorker
from app.storage.repositories import PosRepository
from app.storage.schema import init_db
from app.utils.logger import ActionLogger


class FakeApiClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def post_ticket(self, payload):
        if self.fail:
            raise ApiClientError("fail")
        return {"ok": True}

    def post_event(self, payload):
        if self.fail:
            raise ApiClientError("fail")
        return {"ok": True}


class SyncWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        init_db(self.conn)
        self.repo = PosRepository(self.conn)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.logger = ActionLogger(log_path=str(Path(tmp.name) / "worker.log"))

    def test_sync_success(self) -> None:
        self.repo.enqueue_sync("ticket", "/tickets", {"id": "t1"}, "key1")
        worker = SyncWorker(self.repo, FakeApiClient(fail=False), self.logger, retry_limit=3)
        processed = worker.run_once()
        self.assertEqual(processed, 1)

    def test_sync_reaches_dead(self) -> None:
        self.repo.enqueue_sync("event", "/events", {"id": "e1"}, "key2")
        worker = SyncWorker(self.repo, FakeApiClient(fail=True), self.logger, retry_limit=1)
        processed = worker.run_once()
        self.assertEqual(processed, 0)
        row = self.repo.get_pending_sync(limit=10)
        self.assertEqual(len(row), 0)

    def test_sync_event_marks_event_sent(self) -> None:
        self.repo.save_event(
            event=Event(
                id="e123",
                event_type="ENTRY",
                ticket_id="t123",
                payload={"ticket_id": "t123"},
                status="QUEUED",
                created_at=datetime.now(timezone.utc),
            )
        )
        self.repo.enqueue_sync("event", "/events", {"id": "e123"}, "key-event-123")
        worker = SyncWorker(self.repo, FakeApiClient(fail=False), self.logger, retry_limit=3)

        processed = worker.run_once()
        self.assertEqual(processed, 1)

        cursor = self.conn.execute("SELECT status FROM events WHERE id='e123'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "SENT")


if __name__ == "__main__":
    unittest.main()
