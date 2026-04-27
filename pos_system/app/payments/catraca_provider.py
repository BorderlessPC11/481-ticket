from __future__ import annotations

from typing import Any

from app.api.client import ExternalApiClient
from app.config import Settings
from app.models.entities import PaymentResult
from app.models.exceptions import ApiClientError, PaymentError
from app.payments.base import PaymentProvider


class CatracaPaymentProvider(PaymentProvider):
    """Cobrança via API do cliente: ``POST /api/payments/``."""

    def __init__(self, settings: Settings, api_client: ExternalApiClient) -> None:
        self._settings = settings
        self._api = api_client

    def charge(self, amount_cents: int, reference_id: str) -> PaymentResult:
        if amount_cents <= 0:
            raise PaymentError("Amount must be greater than zero")
        if not reference_id.strip():
            raise PaymentError("reference_id (ticketId) is required")

        valor_pago = round(amount_cents / 100.0, 2)
        try:
            data = self._api.post_create_payment(
                cnpj=self._settings.api_cnpj,
                valor_pago=valor_pago,
                equipamento_id=self._settings.api_equipamento_id,
                ticket_id=reference_id,
                quantidade=self._settings.api_payment_quantidade,
            )
        except ApiClientError as exc:
            raise PaymentError(f"Catraca payment API failed: {exc}") from exc

        transaction_id = _extract_payment_id(data)
        if not transaction_id:
            transaction_id = reference_id

        return PaymentResult(
            approved=True,
            provider="catraca",
            transaction_id=transaction_id,
            amount_cents=amount_cents,
            raw_response=data,
        )


def _extract_payment_id(data: dict[str, Any]) -> str:
    if not data:
        return ""
    for key in ("id", "pk", "paymentId", "payment_id"):
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""
