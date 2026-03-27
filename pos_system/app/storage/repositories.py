from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.entities import Event, PaymentResult, Ticket
from app.models.exceptions import StorageError


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PosRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    def save_ticket(self, ticket: Ticket) -> None:
        try:
            self._conn.execute(
                """
                INSERT INTO tickets
                (id, product_id, product_name, amount_cents, paid, qr_payload, qr_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.id,
                    ticket.product_id,
                    ticket.product_name,
                    ticket.amount_cents,
                    int(ticket.paid),
                    ticket.qr_payload,
                    ticket.qr_path,
                    ticket.status,
                    ticket.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.DatabaseError as exc:
            raise StorageError(f"Failed to save ticket {ticket.id}: {exc}") from exc

    def update_ticket_status(self, ticket_id: str, status: str) -> None:
        self._conn.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))
        self._conn.commit()

    def save_event(self, event: Event) -> None:
        self._conn.execute(
            """
            INSERT INTO events (id, event_type, ticket_id, payload, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event.id, event.event_type, event.ticket_id, json.dumps(event.payload), event.status, event.created_at.isoformat()),
        )
        self._conn.commit()

    def save_transaction(self, ticket_id: str, payment_result: PaymentResult) -> None:
        self._conn.execute(
            """
            INSERT INTO transactions (id, ticket_id, provider, amount_cents, approved, raw_response, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_result.transaction_id,
                ticket_id,
                payment_result.provider,
                payment_result.amount_cents,
                int(payment_result.approved),
                json.dumps(payment_result.raw_response),
                _utc_now_iso(),
            ),
        )
        self._conn.commit()

    def enqueue_sync(self, queue_type: str, endpoint: str, payload: dict[str, Any], idempotency_key: str, delay_seconds: int = 0) -> None:
        next_retry = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        self._conn.execute(
            """
            INSERT INTO sync_queue (queue_type, endpoint, payload, idempotency_key, attempts, next_retry_at, status, last_error)
            VALUES (?, ?, ?, ?, 0, ?, 'pending', NULL)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (queue_type, endpoint, json.dumps(payload), idempotency_key, next_retry),
        )
        self._conn.commit()

    def get_pending_sync(self, limit: int = 20) -> list[sqlite3.Row]:
        now = _utc_now_iso()
        cursor = self._conn.execute(
            """
            SELECT * FROM sync_queue
            WHERE status='pending' AND next_retry_at <= ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (now, limit),
        )
        return list(cursor.fetchall())

    def mark_sync_done(self, row_id: int) -> None:
        self._conn.execute("UPDATE sync_queue SET status='synced', last_error=NULL WHERE id=?", (row_id,))
        self._conn.commit()

    def mark_sync_failed_attempt(self, row_id: int, attempts: int, retry_in_seconds: int, error_message: str) -> None:
        next_retry = (datetime.now(timezone.utc) + timedelta(seconds=retry_in_seconds)).isoformat()
        self._conn.execute(
            """
            UPDATE sync_queue
            SET attempts=?, next_retry_at=?, last_error=?
            WHERE id=?
            """,
            (attempts, next_retry, error_message[:500], row_id),
        )
        self._conn.commit()

    def mark_sync_dead(self, row_id: int, error_message: str) -> None:
        self._conn.execute(
            "UPDATE sync_queue SET status='dead', last_error=? WHERE id=?",
            (error_message[:500], row_id),
        )
        self._conn.commit()

    def get_ticket_by_id(self, ticket_id: str) -> sqlite3.Row | None:
        cursor = self._conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
        return cursor.fetchone()
