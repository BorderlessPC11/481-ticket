import unittest

from app.api.client import (
    _normalize_product_row,
    _normalize_products_list,
    _tolerance_response_amount_cents,
)
from app.models.exceptions import ApiClientError


class NormalizeProductsTests(unittest.TestCase):
    def test_reais_to_cents_default(self) -> None:
        row = {"id": 1, "descricao": "Teste", "valorUnitario": 100}
        out = _normalize_product_row(row, valor_unitario_in_cents=False)
        self.assertEqual(out["id"], "1")
        self.assertEqual(out["name"], "Teste")
        self.assertEqual(out["price_cents"], 10000)
        self.assertEqual(out["currency"], "BRL")

    def test_valor_already_cents(self) -> None:
        row = {"id": 1, "descricao": "Teste", "valorUnitario": 100}
        out = _normalize_product_row(row, valor_unitario_in_cents=True)
        self.assertEqual(out["price_cents"], 100)

    def test_legacy_shape_passthrough(self) -> None:
        row = {"id": "daily", "name": "Daily", "price_cents": 1000, "currency": "BRL"}
        out = _normalize_product_row(row, valor_unitario_in_cents=False)
        self.assertEqual(out["id"], "daily")
        self.assertEqual(out["name"], "Daily")
        self.assertEqual(out["price_cents"], 1000)

    def test_list_and_results(self) -> None:
        raw = [
            {"id": 1, "descricao": "A", "valorUnitario": 1.5},
        ]
        out = _normalize_products_list(raw, False)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["price_cents"], 150)
        paged: dict = {"results": raw}
        out2 = _normalize_products_list(paged, False)
        self.assertEqual(out2[0]["id"], "1")


class ToleranceAmountTests(unittest.TestCase):
    def test_cents_key(self) -> None:
        self.assertEqual(_tolerance_response_amount_cents({"amount_cents": 99}), 99)

    def test_reais_key(self) -> None:
        self.assertEqual(_tolerance_response_amount_cents({"valor": 12.5}), 1250)

    def test_empty_raises(self) -> None:
        with self.assertRaises(ApiClientError):
            _tolerance_response_amount_cents({})


if __name__ == "__main__":
    unittest.main()
