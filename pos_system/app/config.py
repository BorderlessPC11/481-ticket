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


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    load_dotenv()

    timeout_raw = os.getenv("TIMEOUT_SECONDS", "2").strip()
    retry_raw = os.getenv("RETRY_LIMIT", "5").strip()
    database_path = os.getenv("DATABASE_PATH", "pos_system.db").strip()

    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("TIMEOUT_SECONDS must be a number") from exc

    try:
        retry_limit = int(retry_raw)
    except ValueError as exc:
        raise ValueError("RETRY_LIMIT must be an integer") from exc

    if timeout_seconds <= 0:
        raise ValueError("TIMEOUT_SECONDS must be greater than zero")
    if retry_limit < 1:
        raise ValueError("RETRY_LIMIT must be at least 1")

    return Settings(
        api_base_url=_required("API_BASE_URL"),
        api_token=_required("API_TOKEN"),
        payment_provider=os.getenv("PAYMENT_PROVIDER", "mock").strip() or "mock",
        payment_api_key=_required("PAYMENT_API_KEY"),
        device_id=_required("DEVICE_ID"),
        timeout_seconds=timeout_seconds,
        retry_limit=retry_limit,
        database_path=database_path,
    )
