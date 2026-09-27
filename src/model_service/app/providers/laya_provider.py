"""Decision provider backed by Laya (open-source System-1 decision model, Apache 2.0, Convai Innovations)."""
from __future__ import annotations

from .base import DecisionProvider, LocalModel


class LayaDecisionProvider(DecisionProvider):
    def __init__(self, cfg: dict, queue_wait_s: float):
        self.model_id = cfg.get("model", "convaiinnovations/laya")
        self.checkpoint = cfg.get("checkpoint")

        def loader(device: str):
            import laya
            return laya.load(self.model_id, device=device, subfolder=self.checkpoint)

        self.local = LocalModel(f"laya/{self.checkpoint or 'base'}", loader, cfg.get("device", "auto"),
                                int(cfg.get("min_free_vram_mb", 1500)), queue_wait_s)

    def load(self) -> None:
        self.local.load()

    def decide(self, items: list[dict], checkpoint: str | None) -> list[dict]:
        if checkpoint and checkpoint != self.checkpoint:
            raise ValueError(f"checkpoint '{checkpoint}' is not loaded (loaded: '{self.checkpoint}')")

        def run(agent):
            return [{"id": item["id"], "answers": agent.predict(item["text"], item["questions"])["answers"]}
                    for item in items]
        return self.local.run(run)

    def info(self) -> dict:
        return {"provider": "laya", "model_id": f"{self.model_id}:{self.checkpoint or 'base'}", **self.local.info()}
