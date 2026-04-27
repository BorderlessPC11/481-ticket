from __future__ import annotations

from typing import Any

import requests

from app.config import Settings
from app.models.exceptions import ApiClientError

_TOLERANCE_AMOUNT_KEYS = (
    "amount_cents",
    "valorCents",
    "valor_cents",
    "valorEmCentavos",
    "totalCents",
)
_TOLERANCE_REAIS_KEYS = (
    "valor",
    "valorTotal",
    "valorAjustado",
    "total",
    "valorCobranca",
    "amount",
)


def _normalize_product_row(item: dict[str, Any], valor_unitario_in_cents: bool) -> dict[str, Any]:
    """Map API shapes to the internal POS shape: id, name, price_cents, currency."""
    if "price_cents" in item and "name" in item:
        out = dict(item)
        out["id"] = str(out.get("id", ""))
        return out

    descricao = item.get("descricao", "")
    nome = item.get("name", descricao)
    raw_id = item.get("id", "")
    raw_val = item.get("valorUnitario")
    if raw_val is None:
        raw_val = item.get("price_cents", 0)
    try:
        val = float(raw_val)
    except (TypeError, ValueError):
        val = 0.0
    if valor_unitario_in_cents:
        cents = int(round(val))
    else:
        cents = int(round(val * 100))
    return {
        "id": str(raw_id) if raw_id is not None else "",
        "name": str(nome) if nome is not None else "",
        "price_cents": cents,
        "currency": str(item.get("currency", "BRL")),
    }


def _normalize_products_list(
    raw: Any,
    valor_unitario_in_cents: bool,
) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict) and "results" in raw:
        rows = raw["results"]
        if not isinstance(rows, list):
            rows = []
    else:
        raise ApiClientError("GET /api/products/: expected a JSON array or paginated object with results")
    return [_normalize_product_row(row, valor_unitario_in_cents) for row in rows if isinstance(row, dict)]


def _tolerance_response_amount_cents(data: dict[str, Any]) -> int:
    """Extrai o valor a cobrar (centavos) da resposta de ``calculate-tolerance`` (várias chaves possíveis)."""
    if not data:
        raise ApiClientError("calculate-tolerance: empty response")
    for key in _TOLERANCE_AMOUNT_KEYS:
        if key in data and data[key] is not None:
            try:
                return int(data[key])
            except (TypeError, ValueError):
                break
    for key in _TOLERANCE_REAIS_KEYS:
        if key in data and data[key] is not None:
            try:
                return int(round(float(data[key]) * 100))
            except (TypeError, ValueError):
                continue
    raise ApiClientError(
        f"calculate-tolerance: could not read amount (keys: {list(data.keys())!r})",
    )


class ExternalApiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.api_base_url.rstrip("/")
        self._timeout = settings.timeout_seconds
        self._session = requests.Session()
        headers: dict[str, str] = {
            "Authorization": f"Token {settings.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if settings.api_csrf_token:
            headers["X-CSRFToken"] = settings.api_csrf_token
        self._session.headers.update(headers)

    def get_products(self) -> list[dict[str, Any]]:
        raw = self._request("GET", "/api/products/")
        return _normalize_products_list(raw, self._settings.api_product_valor_unitario_in_cents)

    def post_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/tickets", json=payload)

    def get_pricing(self, qr_payload: str) -> dict[str, Any]:
        return self._request("GET", "/pricing", params={"qr_payload": qr_payload})

    def post_calculate_tolerance(
        self,
        *,
        produto_id: int | str,
        cnpj: str,
        data_hora_pagamento: str,
    ) -> dict[str, Any]:
        """POST /api/payments/calculate-tolerance/ (campos obrigatórios do backend catraca)."""
        p = str(produto_id).strip()
        pid: int | str = int(p) if p.isdigit() else produto_id
        payload = {
            "produtoId": pid,
            "cnpj": cnpj,
            "dataHoraPagamento": data_hora_pagamento,
        }
        return self._request("POST", "/api/payments/calculate-tolerance/", json=payload)

    def calculate_exit_amount_cents(
        self,
        *,
        produto_id: int | str,
        cnpj: str,
        data_hora_pagamento: str,
    ) -> int:
        """POST calculate-tolerance e devolve o valor em centavos."""
        raw = self.post_calculate_tolerance(
            produto_id=produto_id,
            cnpj=cnpj,
            data_hora_pagamento=data_hora_pagamento,
        )
        return _tolerance_response_amount_cents(raw)

    def post_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/events", json=payload)

    def get_payment_status(self, ticket_id: str) -> dict[str, Any]:
        return self._request("GET", f"/payments/status/{ticket_id}")

    def post_create_payment(
        self,
        *,
        cnpj: str,
        valor_pago: float,
        equipamento_id: int | str,
        ticket_id: str,
        quantidade: int,
    ) -> dict[str, Any]:
        """
        POST /api/payments/ — corpo alinhado ao serializer do backend (campos obrigatórios do catraca).
        """
        payload: dict[str, Any] = {
            "cnpj": cnpj,
            "valorPago": valor_pago,
            "equipamentoId": int(equipamento_id) if str(equipamento_id).strip().isdigit() else equipamento_id,
            "ticketId": ticket_id,
            "quantidade": quantidade,
        }
        return self._request("POST", "/api/payments/", json=payload)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.request(method=method, url=url, timeout=self._timeout, **kwargs)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except requests.RequestException as exc:
            raise ApiClientError(f"API request failed for {method} {path}: {exc}") from exc
