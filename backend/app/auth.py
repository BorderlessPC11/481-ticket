from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import load_settings


def _extract_token(authorization: str) -> str | None:
    for prefix in ("Bearer ", "Token "):
        if authorization.startswith(prefix):
            return authorization.removeprefix(prefix).strip()
    return None


def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    """Accepts both ``Authorization: Bearer <token>`` and ``Authorization: Token <token>``."""
    settings = load_settings()
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme; use Bearer or Token",
        )
    if not secrets.compare_digest(token, settings.api_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
