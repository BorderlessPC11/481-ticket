from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ActionLogger:
    def __init__(self, log_path: str = "pos.log") -> None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("pos_system")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.FileHandler(log_path)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def log(self, action: str, payload: dict[str, Any], status: str) -> None:
        safe_payload = self._redact(payload)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "payload": safe_payload,
            "status": status,
        }
        self._logger.info(json.dumps(entry, ensure_ascii=True))

    @staticmethod
    def _redact(payload: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = {}
        sensitive_keys = {"api_key", "token", "access_token", "authorization", "payment_api_key"}
        for key, value in payload.items():
            if key.lower() in sensitive_keys:
                redacted[key] = "***"
            else:
                redacted[key] = value
        return redacted
