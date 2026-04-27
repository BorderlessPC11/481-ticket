import unittest

from app.config import Settings
from app.payments.catraca_provider import CatracaPaymentProvider


class FakeApi:
    def __init__(self) -> None:
        self.last: dict | None = None

    def post_create_payment(
        self,
        *,
        cnpj: str,
        valor_pago: float,
        equipamento_id: int | str,
        ticket_id: str,
        quantidade: int,
    ) -> dict:
        eq = int(equipamento_id) if str(equipamento_id).strip().isdigit() else equipamento_id
        self.last = {
            "cnpj": cnpj,
            "valor_pago": valor_pago,
            "equipamento_id": eq,
            "ticket_id": ticket_id,
            "quantidade": quantidade,
        }
        return {"id": 99}


class CatracaProviderTests(unittest.TestCase):
    def test_charge_sends_brl_from_cents(self) -> None:
        st = Settings(
            api_base_url="https://x",
            api_token="t",
            api_csrf_token="",
            api_product_valor_unitario_in_cents=False,
            api_cnpj="12345678000190",
            api_equipamento_id="1",
            api_payment_quantidade=2,
            payment_provider="catraca",
            payment_api_key="k",
            device_id="d",
            timeout_seconds=2,
            retry_limit=1,
        )
        api = FakeApi()
        p = CatracaPaymentProvider(settings=st, api_client=api)  # type: ignore[arg-type]
        r = p.charge(amount_cents=15050, reference_id="TK-1")
        assert api.last is not None
        self.assertEqual(api.last["cnpj"], "12345678000190")
        self.assertEqual(api.last["valor_pago"], 150.5)
        self.assertEqual(api.last["equipamento_id"], 1)
        self.assertEqual(api.last["ticket_id"], "TK-1")
        self.assertEqual(api.last["quantidade"], 2)
        self.assertTrue(r.approved)
        self.assertEqual(r.provider, "catraca")
        self.assertEqual(r.transaction_id, "99")


if __name__ == "__main__":
    unittest.main()
