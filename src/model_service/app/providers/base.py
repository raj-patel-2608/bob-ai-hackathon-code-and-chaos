"""Provider interfaces and the shared GPU-first / CPU-fallback machinery for local models."""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable

from ..device import is_gpu_error, release_gpu_memory, resolve_device

log = logging.getLogger("model_service.providers")


class ProviderUnavailable(Exception):
    """Capability not configured or not loadable (HTTP 503)."""


class Busy(Exception):
    """The model is busy for longer than the allowed queue wait (HTTP 429)."""


class DecisionProvider(ABC):
    @abstractmethod
    def decide(self, items: list[dict], checkpoint: str | None) -> list[dict]:
        """items: [{"id", "text", "questions"}] -> [{"id", "answers"}] (Jev/Laya-style typed answers)"""

    @abstractmethod
    def info(self) -> dict: ...


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def info(self) -> dict: ...


class GeneratorProvider(ABC):
    @abstractmethod
    def generate(self, system: str, prompt: str, json_schema: dict | None, max_tokens: int) -> dict:
        """-> {"text", "json" (optional), "usage": {"input_tokens", "output_tokens"}}"""

    @abstractmethod
    def info(self) -> dict: ...


class LocalModel:
    """Loads a model on the GPU when possible, falls back to CPU on load failure or GPU errors at runtime,
    and serialises inference (one request on the device at a time; others wait up to `queue_wait_s`)."""

    def __init__(self, name: str, loader: Callable[[str], Any], device_policy: str, min_free_vram_mb: int,
                 queue_wait_s: float):
        self.name = name
        self._loader = loader
        self._policy = device_policy
        self._min_free = min_free_vram_mb
        self._queue_wait_s = queue_wait_s
        self._lock = threading.Lock()
        self.model: Any = None
        self.device = "unloaded"
        self.device_reason = ""
        self.degraded = False            # True when it wanted the GPU but runs on CPU after a failure

    def load(self) -> None:
        device, reason = resolve_device(self._policy, self._min_free)
        try:
            self.model = self._loader(device)
            self.device, self.device_reason = device, reason
        except Exception as exc:
            if device == "cuda" and is_gpu_error(exc):
                log.warning("%s: GPU load failed (%s); loading on CPU", self.name, exc)
                release_gpu_memory()
                self.model = self._loader("cpu")
                self.device, self.device_reason, self.degraded = "cpu", f"GPU load failed: {exc}", True
            else:
                raise
        log.info("%s loaded on %s (%s)", self.name, self.device, self.device_reason)

    def run(self, fn: Callable[[Any], Any]) -> Any:
        if self.model is None:
            raise ProviderUnavailable(f"{self.name} is not loaded")
        if not self._lock.acquire(timeout=self._queue_wait_s):
            raise Busy(f"{self.name} busy")
        try:
            try:
                return fn(self.model)
            except Exception as exc:
                if self.device != "cuda" or not is_gpu_error(exc):
                    raise
                log.warning("%s: GPU error during inference (%s); switching to CPU", self.name, exc)
                self.model = None
                release_gpu_memory()
                self.model = self._loader("cpu")
                self.device, self.device_reason, self.degraded = "cpu", f"GPU runtime error: {exc}", True
                return fn(self.model)
        finally:
            self._lock.release()

    def info(self) -> dict:
        return {"device": self.device, "device_reason": self.device_reason, "degraded": self.degraded}
