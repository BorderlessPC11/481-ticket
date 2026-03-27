from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from app.config import Settings
from app.models import Ticket


class PricingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def compute_amount(self, qr_payload: str, ticket: Ticket | None) -> tuple[str, int]:
        data = json.loads(qr_payload)
        ticket_id = str(data["ticket_id"])
        base_amount = int(ticket.amount_cents) if ticket else 1000

        created_at_raw = data.get("created_at")
        if created_at_raw:
            created = datetime.fromisoformat(str(created_at_raw))
        elif ticket:
            created = datetime.fromisoformat(ticket.created_at)
        else:
            created = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        minutes = max(0, int((now - created).total_seconds() / 60))
        if minutes <= self._settings.pricing_grace_minutes:
            return ticket_id, base_amount

        exceeded = minutes - self._settings.pricing_grace_minutes
        extra_steps = math.ceil(exceeded / self._settings.pricing_step_minutes)
        total = base_amount + (extra_steps * self._settings.pricing_step_cents)
        return ticket_id, total
