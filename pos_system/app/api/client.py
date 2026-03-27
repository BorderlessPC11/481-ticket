from __future__ import annotations

from typing import Any

import requests

from app.config import Settings
from app.models.exceptions import ApiClientError


class ExternalApiClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.api_base_url.rstrip("/")
        self._timeout = settings.timeout_seconds
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {settings.api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def get_products(self) -> list[dict[str, Any]]:
        return self._request("GET", "/products")

    def post_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/tickets", json=payload)

    def get_pricing(self, qr_payload: str) -> dict[str, Any]:
        return self._request("GET", "/pricing", params={"qr_payload": qr_payload})

    def post_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/events", json=payload)

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
