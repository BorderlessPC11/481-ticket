from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.entities import PaymentResult


class PaymentProvider(ABC):
    @abstractmethod
    def charge(self, amount_cents: int, reference_id: str) -> PaymentResult:
        raise NotImplementedError
