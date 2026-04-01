from __future__ import annotations

import unittest

from app.models.exceptions import PaymentError
from app.payments.asaas_provider import AsaasPaymentProvider


class _FakeResponse:
    def __init__(self, payload, should_raise: bool = False) -> None:
        self._payload = payload
        self._should_raise = should_raise

    def raise_for_status(self) -> None:
        if self._should_raise:
            raise ValueError("http error")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.headers = {}
        self.last_post = None

    def post(self, url, json, timeout):  # noqa: A002
        self.last_post = {"url": url, "json": json, "timeout": timeout}
        return self._response


class AsaasPaymentProviderTests(unittest.TestCase):
    def test_charge_returns_payment_result(self) -> None:
        session = _FakeSession(_FakeResponse({"id": "pay_123", "status": "CONFIRMED"}))
        provider = AsaasPaymentProvider(
            api_key="key",
            customer_id="cus_123",
            session=session,
            timeout_seconds=2,
        )

        result = provider.charge(amount_cents=1500, reference_id="ticket-1")
        self.assertTrue(result.approved)
        self.assertEqual(result.provider, "asaas")
        self.assertEqual(result.transaction_id, "pay_123")
        self.assertEqual(result.amount_cents, 1500)
        self.assertEqual(session.last_post["url"], "https://sandbox.asaas.com/api/v3/payments")

    def test_charge_rejects_missing_payment_id(self) -> None:
        session = _FakeSession(_FakeResponse({"status": "CONFIRMED"}))
        provider = AsaasPaymentProvider(api_key="key", customer_id="cus_123", session=session)

        with self.assertRaises(PaymentError):
            provider.charge(amount_cents=1000, reference_id="ticket-2")

    def test_charge_marks_unknown_status_as_not_approved(self) -> None:
        session = _FakeSession(_FakeResponse({"id": "pay_9", "status": "FAILED"}))
        provider = AsaasPaymentProvider(api_key="key", customer_id="cus_123", session=session)

        result = provider.charge(amount_cents=1000, reference_id="ticket-3")
        self.assertFalse(result.approved)

    def test_charge_marks_pending_as_not_approved(self) -> None:
        session = _FakeSession(_FakeResponse({"id": "pay_10", "status": "PENDING"}))
        provider = AsaasPaymentProvider(api_key="key", customer_id="cus_123", session=session)

        result = provider.charge(amount_cents=1000, reference_id="ticket-4")
        self.assertFalse(result.approved)


if __name__ == "__main__":
    unittest.main()
