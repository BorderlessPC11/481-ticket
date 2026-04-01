from __future__ import annotations

from datetime import date
from typing import Any

import requests

from app.models.entities import PaymentResult
from app.models.exceptions import PaymentError
from app.payments.base import PaymentProvider


class AsaasPaymentProvider(PaymentProvider):
    def __init__(
        self,
        api_key: str,
        customer_id: str,
        api_base_url: str = "https://sandbox.asaas.com/api/v3",
        billing_type: str = "PIX",
        timeout_seconds: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key:
            raise PaymentError("Asaas API key is missing")
        if not customer_id:
            raise PaymentError("Asaas customer id is missing")
        if timeout_seconds <= 0:
            raise PaymentError("Asaas timeout must be greater than zero")

        self._api_key = api_key
        self._customer_id = customer_id
        self._api_base_url = api_base_url.rstrip("/")
        self._billing_type = billing_type.strip().upper() or "PIX"
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "access_token": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def charge(self, amount_cents: int, reference_id: str) -> PaymentResult:
        if amount_cents <= 0:
            raise PaymentError("Amount must be greater than zero")

        payload = {
            "customer": self._customer_id,
            "billingType": self._billing_type,
            "value": round(amount_cents / 100, 2),
            "dueDate": date.today().isoformat(),
            "description": f"POS charge {reference_id}",
            "externalReference": reference_id,
        }
        url = f"{self._api_base_url}/payments"
        try:
            response = self._session.post(url=url, json=payload, timeout=self._timeout_seconds)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
        except requests.RequestException as exc:
            raise PaymentError(f"Asaas payment request failed: {exc}") from exc
        except ValueError as exc:
            raise PaymentError("Asaas returned an invalid JSON response") from exc

        transaction_id = str(data.get("id", "")).strip()
        if not transaction_id:
            raise PaymentError("Asaas response did not include payment id")

        status = str(data.get("status", "")).upper()
        approved_statuses = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}
        approved = status in approved_statuses

        return PaymentResult(
            approved=approved,
            provider="asaas",
            transaction_id=transaction_id,
            amount_cents=amount_cents,
            raw_response=data,
        )
