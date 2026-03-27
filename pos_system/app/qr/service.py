from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import qrcode


class QrService:
    def __init__(self, output_dir: str = "qrcodes") -> None:
        self._output_dir = output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def encode_ticket_data(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def generate_qr(self, ticket_id: str, qr_payload: str) -> str:
        img = qrcode.make(qr_payload)
        path = os.path.join(self._output_dir, f"{ticket_id}.png")
        img.save(path)
        return path
