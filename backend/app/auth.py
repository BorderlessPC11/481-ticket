from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import load_settings


def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    settings = load_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
