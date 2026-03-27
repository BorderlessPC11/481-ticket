from __future__ import annotations

from app.storage.repositories import PosRepository


class OfflineQueueService:
    def __init__(self, repository: PosRepository) -> None:
        self._repository = repository

    def enqueue_api_call(self, queue_type: str, endpoint: str, payload: dict, idempotency_key: str) -> None:
        self._repository.enqueue_sync(
            queue_type=queue_type,
            endpoint=endpoint,
            payload=payload,
            idempotency_key=idempotency_key,
        )
