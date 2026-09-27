"""Test setup: every test gets a fresh temporary SQLite database and a fake model client
(no GPU, no network). The background thread is disabled; tests drive the worker
synchronously with drain()."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["CRIMEFIR_WORKER_ENABLED"] = "false"
os.environ["CRIMEFIR_BACKOFF_BASE_S"] = "0"

from app.config import get_settings  # noqa: E402
from app.db import engine as db_engine  # noqa: E402
from app.models_client.client import ModelUnavailable, ModelMeta, set_model_client  # noqa: E402
from app.pipeline.decisions import rules_decide  # noqa: E402
from app.domain.taxonomy import get_taxonomy  # noqa: E402


class FakeModelClient:
    """Deterministic stand-in for the model service.

    decide:   keyword rules (confidence 0.9, or `low_confidence` for texts containing a marker)
    embed:    hashed bag-of-words vectors
    generate: returns `generate_payload` (or raises when `generator_available` is False)
    """

    def __init__(self):
        self.available = True
        self.generator_available = True
        self.low_confidence_marker = "LOWCONF"
        self.generate_payload: dict | None = None
        self.calls = {"decide": 0, "embed": 0, "generate": 0}

    def health(self):
        return {"reachable": self.available, "breaker": "closed"}

    def decide(self, items, checkpoint=None):
        if not self.available:
            raise ModelUnavailable("fake: down")
        self.calls["decide"] += 1
        tax = get_taxonomy()
        results = []
        for item in items:
            d = rules_decide(item["text"], tax)
            label = tax.minor_label(d["crime_minor"])
            conf = 0.2 if self.low_confidence_marker in item["text"] else 0.9
            answers = {"crime_minor": {"choice": label, "probabilities": {label: conf}, "answer_confidence": conf},
                       "victim_female": {"noul": 0.8 if " she " in f" {item['text'].lower()} " else 0.1},
                       "accused_identified": {"noul": 0.1}}
            for q in item["questions"]:
                if q.startswith("mo:"):
                    answers[q] = {"noul": 0.9 if q == "mo:asked_otp_or_card_details" and "otp" in item["text"].lower()
                                  else 0.05}
            results.append({"id": item["id"], "answers": answers})
        return results, ModelMeta("fake-laya", "cpu")

    def embed(self, texts):
        if not self.available:
            raise ModelUnavailable("fake: down")
        self.calls["embed"] += 1
        vectors = []
        for t in texts:
            v = np.zeros(64, dtype=np.float32)
            for word in t.lower().split():
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1.0
            vectors.append((v / (np.linalg.norm(v) or 1)).tolist())
        return vectors, ModelMeta("fake-embedding", "cpu")

    def generate(self, *, system, prompt, json_schema=None, max_tokens=700):
        if not self.available or not self.generator_available:
            raise ModelUnavailable("generator not configured", transient=False)
        self.calls["generate"] += 1
        payload = self.generate_payload or {"text": "Brief: nothing notable."}
        return {**payload, "usage": {"input_tokens": 500, "output_tokens": 120}}, ModelMeta("fake-granite", "remote")


@pytest.fixture()
def fake_models():
    client = FakeModelClient()
    set_model_client(client)
    yield client
    set_model_client(None)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CRIMEFIR_DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("CRIMEFIR_UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    db_engine.init_engine()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def worker(db, fake_models):
    from app.pipeline.worker import Worker
    return Worker()


def drain(worker, max_rounds: int = 500) -> None:
    """Run the worker synchronously until there is nothing left to do."""
    for _ in range(max_rounds):
        if not worker.run_once():
            return
    raise AssertionError("worker did not finish")
