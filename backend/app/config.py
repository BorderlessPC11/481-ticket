from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_token: str
    webhook_token: str
    db_path: str
    pricing_grace_minutes: int
    pricing_step_minutes: int
    pricing_step_cents: int


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BACKEND_API_TOKEN", "dev-static-token").strip() or "dev-static-token"
    webhook_token = os.getenv("BACKEND_WEBHOOK_TOKEN", "").strip()

    db_path = os.getenv("BACKEND_DB_PATH", "backend.db").strip() or "backend.db"
    grace = int(os.getenv("BACKEND_PRICING_GRACE_MINUTES", "15"))
    step_minutes = int(os.getenv("BACKEND_PRICING_STEP_MINUTES", "30"))
    step_cents = int(os.getenv("BACKEND_PRICING_STEP_CENTS", "500"))
    return Settings(
        api_token=token,
        webhook_token=webhook_token,
        db_path=db_path,
        pricing_grace_minutes=grace,
        pricing_step_minutes=step_minutes,
        pricing_step_cents=step_cents,
    )
