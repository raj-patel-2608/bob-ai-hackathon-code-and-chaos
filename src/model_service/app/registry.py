"""Builds the configured providers from models.yaml. A capability that cannot load is recorded as
unavailable (with the reason) instead of crashing the whole service."""
from __future__ import annotations

import logging

from .config import get_settings, load_models_config
from .providers.base import ProviderUnavailable

log = logging.getLogger("model_service.registry")


class Registry:
    def __init__(self) -> None:
        self.decision = None
        self.embedding = None
        self.generator = None
        self.errors: dict[str, str] = {}

    def load(self, config: dict | None = None) -> None:
        s = get_settings()
        cfg = config or load_models_config()
        builders = {"decision": self._decision, "embedding": self._embedding, "generator": self._generator}
        for capability, build in builders.items():
            section = cfg.get(capability) or {}
            if not section or section.get("provider") in (None, "none"):
                self.errors[capability] = "disabled in models.yaml"
                continue
            try:
                provider = build(section, s)
                provider.load()
                setattr(self, capability, provider)
                self.errors.pop(capability, None)
            except ProviderUnavailable as exc:
                self.errors[capability] = str(exc)
                log.warning("%s unavailable: %s", capability, exc)
            except Exception as exc:                          # keep the other capabilities alive
                self.errors[capability] = f"{exc.__class__.__name__}: {exc}"
                log.exception("%s failed to load", capability)

    @staticmethod
    def _decision(section, s):
        if section["provider"] != "laya":
            raise ProviderUnavailable(f"unknown decision provider {section['provider']}")
        from .providers.laya_provider import LayaDecisionProvider
        return LayaDecisionProvider(section, s.queue_wait_s)

    @staticmethod
    def _embedding(section, s):
        if section["provider"] != "sentence_transformers":
            raise ProviderUnavailable(f"unknown embedding provider {section['provider']}")
        from .providers.st_embedding import SentenceTransformerEmbeddingProvider
        return SentenceTransformerEmbeddingProvider(section, s.queue_wait_s)

    @staticmethod
    def _generator(section, s):
        if section["provider"] != "watsonx":
            raise ProviderUnavailable(f"unknown generator provider {section['provider']}")
        from .providers.watsonx_generator import WatsonxGenerator
        return WatsonxGenerator(section, s.watsonx_api_key, s.watsonx_project_id, s.watsonx_url)


registry = Registry()
