"""CrimeFIR core API.

Run:  .venv/Scripts/python -m uvicorn app.main:app --port 8000   (from src/core_api)
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from .api import batches, firs, intelligence, system
from .config import get_settings
from .db.engine import init_engine
from .pipeline.worker import start_worker, stop_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_engine()
    if get_settings().worker_enabled:
        start_worker()
    yield
    stop_worker()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="CrimeFIR Intelligence API", version="1.0.0", lifespan=lifespan,
                  description="FIR intelligence & crime pattern detector (IBM x NFSU Bob Hackathon, PS10). "
                              "Every link and flag is an investigation lead that requires human verification.")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["*"], allow_headers=["*"])
    for module in (batches, firs, intelligence, system):
        app.include_router(module.router)

    @app.exception_handler(OperationalError)
    async def database_busy(_request: Request, exc: OperationalError) -> JSONResponse:
        # a JSON 503 (with CORS headers) instead of a bare 500, so the UI can say "busy, try again"
        logging.getLogger("crimefir.api").warning("database error: %s", exc.orig)
        return JSONResponse(status_code=503, content={"detail": "The database is busy. Please try again in a moment."})

    return app


app = create_app()
