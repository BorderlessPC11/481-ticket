from __future__ import annotations

import json

from app.api.client import ExternalApiClient
from app.models.exceptions import ApiClientError
from app.storage.repositories import PosRepository
from app.utils.logger import ActionLogger


class SyncWorker:
    def __init__(self, repository: PosRepository, api_client: ExternalApiClient, logger: ActionLogger, retry_limit: int) -> None:
        self._repository = repository
        self._api_client = api_client
        self._logger = logger
        self._retry_limit = retry_limit

    def run_once(self, limit: int = 20) -> int:
        processed = 0
        pending = self._repository.get_pending_sync(limit=limit)
        for item in pending:
            row_id = int(item["id"])
            queue_type = item["queue_type"]
            endpoint = item["endpoint"]
            payload = json.loads(item["payload"])
            attempts = int(item["attempts"])
            try:
                self._dispatch(endpoint, payload)
                self._repository.mark_sync_done(row_id)
                self._logger.log("sync_success", {"row_id": row_id, "queue_type": queue_type}, "ok")
                processed += 1
            except ApiClientError as exc:
                next_attempt = attempts + 1
                if next_attempt >= self._retry_limit:
                    self._repository.mark_sync_dead(row_id, str(exc))
                    self._logger.log("sync_dead", {"row_id": row_id, "queue_type": queue_type}, "error")
                else:
                    backoff_seconds = min(2 ** next_attempt, 60)
                    self._repository.mark_sync_failed_attempt(row_id, next_attempt, backoff_seconds, str(exc))
                    self._logger.log("sync_retry", {"row_id": row_id, "attempt": next_attempt}, "retry")
        return processed

    def _dispatch(self, endpoint: str, payload: dict) -> None:
        if endpoint == "/tickets":
            self._api_client.post_ticket(payload)
        elif endpoint == "/events":
            self._api_client.post_event(payload)
        else:
            raise ApiClientError(f"Unsupported sync endpoint: {endpoint}")
