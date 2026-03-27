from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.routes.pos_routes import router as pos_router
from app.database import SessionLocal, init_db
from app.repositories.pos_repository import PosRepository

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backend")

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        PosRepository(db).seed_default_products()
    finally:
        db.close()
    yield


app = FastAPI(title="POS Backend", version="1.0.0", lifespan=lifespan)
app.include_router(pos_router)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        }
    )
    return response

