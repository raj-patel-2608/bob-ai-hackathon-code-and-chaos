"""Embedding provider backed by sentence-transformers (default: IBM Granite Embedding 30M English)."""
from __future__ import annotations

from .base import EmbeddingProvider, LocalModel


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, cfg: dict, queue_wait_s: float):
        self.model_id = cfg["model"]
        self.batch_size = int(cfg.get("batch_size", 32))

        def loader(device: str):
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer(self.model_id, device=device)

        self.local = LocalModel(self.model_id, loader, cfg.get("device", "auto"),
                                int(cfg.get("min_free_vram_mb", 300)), queue_wait_s)

    def load(self) -> None:
        self.local.load()

    def embed(self, texts: list[str]) -> list[list[float]]:
        def run(model):
            vectors = model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                   show_progress_bar=False)
            return [v.tolist() for v in vectors]
        return self.local.run(run)

    def info(self) -> dict:
        return {"provider": "sentence_transformers", "model_id": self.model_id, **self.local.info()}
