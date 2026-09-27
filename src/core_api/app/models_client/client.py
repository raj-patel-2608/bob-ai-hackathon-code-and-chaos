"""HTTP client for the model service (/v1 contract), with a circuit breaker.

core-api never loads a model itself. Every AI call goes through this client:
  POST /v1/decide    typed questions -> answers with probabilities (Laya)
  POST /v1/embed     texts -> vectors (Granite Embedding)
  POST /v1/generate  prompt (+ JSON schema) -> text/JSON (Granite LLM via watsonx)
  GET  /v1/health    loaded models, device per model, degraded flags

If the service is down or keeps failing, the breaker opens and callers get
ModelUnavailable immediately, so pipeline stages can fall back to rules
instead of waiting on timeouts.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import get_settings

log = logging.getLogger("crimefir.models")


class ModelUnavailable(Exception):
    """The model service (or one capability of it) cannot be used right now."""

    def __init__(self, message: str, *, transient: bool = True):
        super().__init__(message)
        self.transient = transient


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_after_s: float):
        self.failure_threshold = failure_threshold
        self.reset_after_s = reset_after_s
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            return "half_open" if time.monotonic() - self._opened_at >= self.reset_after_s else "open"

    def allow(self) -> bool:
        return self.state != "open"

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()


@dataclass
class ModelMeta:
    model_id: str | None
    device: str | None
    degraded: bool = False


class ModelClient:
    def __init__(self, base_url: str | None = None, timeout_s: float | None = None,
                 breaker: CircuitBreaker | None = None, transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self.base_url = (base_url or s.model_service_url).rstrip("/")
        self.breaker = breaker or CircuitBreaker(s.breaker_failure_threshold, s.breaker_reset_s)
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout_s or s.model_timeout_s,
                                  transport=transport)

    def _post(self, path: str, payload: dict) -> dict:
        if not self.breaker.allow():
            raise ModelUnavailable(f"model service circuit open ({self.base_url})")
        try:
            resp = self._http.post(path, json=payload)
        except httpx.HTTPError as exc:
            self.breaker.record_failure()
            raise ModelUnavailable(f"model service unreachable: {exc.__class__.__name__}") from exc
        if resp.status_code == 503:
            # capability not configured / not loaded (e.g. generator without watsonx credentials)
            detail = resp.json().get("detail", "unavailable") if resp.content else "unavailable"
            raise ModelUnavailable(str(detail), transient=False)
        if resp.status_code in (429,) or resp.status_code >= 500:
            self.breaker.record_failure()
            raise ModelUnavailable(f"model service error {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ValueError(f"model service rejected request ({resp.status_code}): {resp.text[:300]}")
        self.breaker.record_success()
        return resp.json()

    def health(self) -> dict[str, Any]:
        try:
            resp = self._http.get("/v1/health", timeout=3.0)
            resp.raise_for_status()
            return {"reachable": True, "breaker": self.breaker.state, **resp.json()}
        except httpx.HTTPError as exc:
            return {"reachable": False, "breaker": self.breaker.state, "error": exc.__class__.__name__}

    def decide(self, items: list[dict], checkpoint: str | None = None) -> tuple[list[dict], ModelMeta]:
        """items: [{"id", "text", "questions": {name: {type, instructions, criteria?}}}]"""
        data = self._post("/v1/decide", {"items": items, "checkpoint": checkpoint})
        return data["results"], ModelMeta(data.get("model_id"), data.get("device"), data.get("degraded", False))

    def embed(self, texts: list[str]) -> tuple[list[list[float]], ModelMeta]:
        data = self._post("/v1/embed", {"texts": texts})
        return data["vectors"], ModelMeta(data.get("model_id"), data.get("device"), data.get("degraded", False))

    def generate(self, *, system: str, prompt: str, json_schema: dict | None = None,
                 max_tokens: int = 700) -> tuple[dict, ModelMeta]:
        data = self._post("/v1/generate", {"system": system, "prompt": prompt, "json_schema": json_schema,
                                            "max_tokens": max_tokens})
        return data, ModelMeta(data.get("model_id"), data.get("device"), data.get("degraded", False))


_client: ModelClient | None = None
_client_lock = threading.Lock()


def get_model_client() -> ModelClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = ModelClient()
        return _client


def set_model_client(client: ModelClient | None) -> None:
    """Used by tests to inject a fake client."""
    global _client
    with _client_lock:
        _client = client
