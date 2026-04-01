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

    def _execute_write(self, operation: str, query: str, params: tuple[Any, ...]) -> None:
        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.DatabaseError as exc:
            self._conn.rollback()
            raise StorageError(f"{operation} failed: {exc}") from exc

    def save_ticket(self, ticket: Ticket) -> None:
        self._execute_write(
            f"save ticket {ticket.id}",
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

    def update_ticket_status(self, ticket_id: str, status: str) -> None:
        self._execute_write("update ticket status", "UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))

    def save_event(self, event: Event) -> None:
        self._execute_write(
            f"save event {event.id}",
            """
            INSERT INTO events (id, event_type, ticket_id, payload, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event.id, event.event_type, event.ticket_id, json.dumps(event.payload), event.status, event.created_at.isoformat()),
        )

    def update_event_status(self, event_id: str, status: str) -> None:
        self._execute_write("update event status", "UPDATE events SET status=? WHERE id=?", (status, event_id))

    def save_transaction(self, ticket_id: str, payment_result: PaymentResult) -> None:
        provider_status = str(payment_result.raw_response.get("status", "")).upper()[:60]
        redacted_response = dict(payment_result.raw_response)
        for key in ("access_token", "api_key", "token"):
            if key in redacted_response:
                redacted_response[key] = "***"
        self._execute_write(
            f"save transaction {payment_result.transaction_id}",
            """
            INSERT INTO transactions (id, ticket_id, provider, provider_status, amount_cents, approved, payment_reference, raw_response, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_result.transaction_id,
                ticket_id,
                payment_result.provider,
                provider_status,
                payment_result.amount_cents,
                int(payment_result.approved),
                ticket_id,
                json.dumps(redacted_response),
                _utc_now_iso(),
            ),
        )

    def enqueue_sync(self, queue_type: str, endpoint: str, payload: dict[str, Any], idempotency_key: str, delay_seconds: int = 0) -> None:
        next_retry = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        self._execute_write(
            "enqueue sync",
            """
            INSERT INTO sync_queue (queue_type, endpoint, payload, idempotency_key, attempts, next_retry_at, status, last_error)
            VALUES (?, ?, ?, ?, 0, ?, 'pending', NULL)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (queue_type, endpoint, json.dumps(payload), idempotency_key, next_retry),
        )

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
        self._execute_write("mark sync done", "UPDATE sync_queue SET status='synced', last_error=NULL WHERE id=?", (row_id,))

    def mark_sync_failed_attempt(self, row_id: int, attempts: int, retry_in_seconds: int, error_message: str) -> None:
        next_retry = (datetime.now(timezone.utc) + timedelta(seconds=retry_in_seconds)).isoformat()
        self._execute_write(
            "mark sync failed attempt",
            """
            UPDATE sync_queue
            SET attempts=?, next_retry_at=?, last_error=?
            WHERE id=?
            """,
            (attempts, next_retry, error_message[:500], row_id),
        )

    def mark_sync_dead(self, row_id: int, error_message: str) -> None:
        self._execute_write("mark sync dead", "UPDATE sync_queue SET status='dead', last_error=? WHERE id=?", (error_message[:500], row_id))

    def get_ticket_by_id(self, ticket_id: str) -> sqlite3.Row | None:
        cursor = self._conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,))
        return cursor.fetchone()
