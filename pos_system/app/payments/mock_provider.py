from __future__ import annotations

import time
import uuid

from app.models.entities import PaymentResult
from app.models.exceptions import PaymentError
from app.payments.base import PaymentProvider


class MockPaymentProvider(PaymentProvider):
    def __init__(self, api_key: str, approved: bool = True, latency_seconds: float = 0.2) -> None:
        self._api_key = api_key
        self._approved = approved
        self._latency_seconds = latency_seconds

    def charge(self, amount_cents: int, reference_id: str) -> PaymentResult:
        if not self._api_key:
            raise PaymentError("Payment API key is missing")
        if amount_cents <= 0:
            raise PaymentError("Amount must be greater than zero")

        time.sleep(self._latency_seconds)
        transaction_id = f"mock-{uuid.uuid4().hex[:12]}"

        return PaymentResult(
            approved=self._approved,
            provider="mock",
            transaction_id=transaction_id,
            amount_cents=amount_cents,
            raw_response={
                "reference_id": reference_id,
                "approved": self._approved,
                "provider": "mock",
            },
        )
