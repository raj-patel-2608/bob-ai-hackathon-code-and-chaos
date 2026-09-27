"""CrimeFIR model service: the only process that loads AI models.

Run:  .venv/Scripts/python -m uvicorn app.main:app --port 8100   (from src/model_service)

HTTP contract (/v1):
  POST /v1/decide    typed questions -> answers with probabilities   (Laya)
  POST /v1/embed     texts -> unit-length vectors                    (Granite Embedding)
  POST /v1/generate  system + prompt (+ json) -> text/json + usage    (Granite on watsonx.ai)
  GET  /v1/health    loaded models, device per model, degraded flags, GPU memory
Errors: 503 capability unavailable (not retried), 429 busy / rate-limited (retry), 502 upstream failure (retry).
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .device import gpu_memory
from .providers.base import Busy, ProviderUnavailable
from .registry import registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("model_service")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    started = time.perf_counter()
    registry.load()
    log.info("model service ready in %.1fs; unavailable: %s", time.perf_counter() - started, registry.errors or "none")
    yield


app = FastAPI(title="CrimeFIR Model Service", version="1.0.0", lifespan=lifespan)


class DecideItem(BaseModel):
    id: str
    text: str = Field(min_length=1)
    questions: dict


class DecideRequest(BaseModel):
    items: list[DecideItem] = Field(min_length=1, max_length=64)
    checkpoint: str | None = None


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=256)


class GenerateRequest(BaseModel):
    system: str
    prompt: str = Field(min_length=1)
    json_schema: dict | None = None
    max_tokens: int = Field(700, ge=16, le=4000)


def _require(capability: str):
    provider = getattr(registry, capability)
    if provider is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"{capability} unavailable: {registry.errors.get(capability, 'not loaded')}")
    return provider


def _call(fn):
    try:
        return fn()
    except Busy as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        log.exception("model call failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{exc.__class__.__name__}: {exc}") from exc


@app.post("/v1/decide")
def decide(req: DecideRequest) -> dict:
    provider = _require("decision")
    results = _call(lambda: provider.decide([i.model_dump() for i in req.items], req.checkpoint))
    info = provider.info()
    return {"results": results, "model_id": info["model_id"], "device": info["device"], "degraded": info["degraded"]}


@app.post("/v1/embed")
def embed(req: EmbedRequest) -> dict:
    provider = _require("embedding")
    vectors = _call(lambda: provider.embed(req.texts))
    info = provider.info()
    return {"vectors": vectors, "model_id": info["model_id"], "device": info["device"], "degraded": info["degraded"],
            "dim": len(vectors[0]) if vectors else 0}


@app.post("/v1/generate")
def generate(req: GenerateRequest) -> dict:
    provider = _require("generator")
    out = _call(lambda: provider.generate(req.system, req.prompt, req.json_schema, req.max_tokens))
    info = provider.info()
    return {**out, "model_id": info["model_id"], "device": info["device"], "degraded": info["degraded"]}


@app.get("/v1/health")
def health() -> dict:
    capabilities = {}
    for name in ("decision", "embedding", "generator"):
        provider = getattr(registry, name)
        capabilities[name] = {"available": True, **provider.info()} if provider else \
            {"available": False, "reason": registry.errors.get(name)}
    return {"status": "ok", "capabilities": capabilities, "gpu": gpu_memory()}
