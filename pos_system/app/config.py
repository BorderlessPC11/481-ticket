from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    api_token: str
    payment_provider: str
    payment_api_key: str
    device_id: str
    timeout_seconds: float
    retry_limit: int
    database_path: str = "pos_system.db"
    asaas_api_base_url: str = "https://sandbox.asaas.com/api/v3"
    asaas_customer_id: str = ""
    asaas_billing_type: str = "PIX"
    payment_status_poll_attempts: int = 6
    payment_status_poll_interval_seconds: float = 2.0


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    load_dotenv()

    timeout_raw = os.getenv("TIMEOUT_SECONDS", "2").strip()
    retry_raw = os.getenv("RETRY_LIMIT", "5").strip()
    poll_attempts_raw = os.getenv("PAYMENT_STATUS_POLL_ATTEMPTS", "6").strip()
    poll_interval_raw = os.getenv("PAYMENT_STATUS_POLL_INTERVAL_SECONDS", "2").strip()
    database_path = os.getenv("DATABASE_PATH", "pos_system.db").strip()

    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("TIMEOUT_SECONDS must be a number") from exc

    try:
        retry_limit = int(retry_raw)
    except ValueError as exc:
        raise ValueError("RETRY_LIMIT must be an integer") from exc

    try:
        payment_status_poll_attempts = int(poll_attempts_raw)
    except ValueError as exc:
        raise ValueError("PAYMENT_STATUS_POLL_ATTEMPTS must be an integer") from exc

    try:
        payment_status_poll_interval_seconds = float(poll_interval_raw)
    except ValueError as exc:
        raise ValueError("PAYMENT_STATUS_POLL_INTERVAL_SECONDS must be a number") from exc

    if timeout_seconds <= 0:
        raise ValueError("TIMEOUT_SECONDS must be greater than zero")
    if retry_limit < 1:
        raise ValueError("RETRY_LIMIT must be at least 1")
    if payment_status_poll_attempts < 1:
        raise ValueError("PAYMENT_STATUS_POLL_ATTEMPTS must be at least 1")
    if payment_status_poll_interval_seconds <= 0:
        raise ValueError("PAYMENT_STATUS_POLL_INTERVAL_SECONDS must be greater than zero")

    payment_provider = os.getenv("PAYMENT_PROVIDER", "mock").strip() or "mock"
    asaas_api_base_url = os.getenv("ASAAS_API_BASE_URL", "https://sandbox.asaas.com/api/v3").strip()
    asaas_customer_id = os.getenv("ASAAS_CUSTOMER_ID", "").strip()
    asaas_billing_type = os.getenv("ASAAS_BILLING_TYPE", "PIX").strip() or "PIX"

    if payment_provider.lower() == "asaas" and not asaas_customer_id:
        raise ValueError("Missing required environment variable for Asaas provider: ASAAS_CUSTOMER_ID")

    return Settings(
        api_base_url=_required("API_BASE_URL"),
        api_token=_required("API_TOKEN"),
        payment_provider=payment_provider,
        payment_api_key=_required("PAYMENT_API_KEY"),
        device_id=_required("DEVICE_ID"),
        timeout_seconds=timeout_seconds,
        retry_limit=retry_limit,
        database_path=database_path,
        asaas_api_base_url=asaas_api_base_url,
        asaas_customer_id=asaas_customer_id,
        asaas_billing_type=asaas_billing_type,
        payment_status_poll_attempts=payment_status_poll_attempts,
        payment_status_poll_interval_seconds=payment_status_poll_interval_seconds,
    )
