import json
import sys
import threading
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers import base  # noqa: E402
from app.providers.base import Busy, LocalModel, ProviderUnavailable  # noqa: E402
from app.providers.watsonx_generator import WatsonxGenerator  # noqa: E402


class CudaOOM(Exception):
    pass


CudaOOM.__name__ = "OutOfMemoryError"


def test_gpu_load_failure_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(base, "resolve_device", lambda policy, free: ("cuda", "GPU available"))

    def loader(device):
        if device == "cuda":
            raise CudaOOM("CUDA out of memory")
        return f"model@{device}"

    m = LocalModel("x", loader, "auto", 0, queue_wait_s=1)
    m.load()
    assert m.device == "cpu" and m.degraded and m.model == "model@cpu"


def test_gpu_runtime_error_switches_to_cpu(monkeypatch):
    monkeypatch.setattr(base, "resolve_device", lambda policy, free: ("cuda", "GPU available"))
    m = LocalModel("x", lambda device: device, "auto", 0, queue_wait_s=1)
    m.load()
    assert m.device == "cuda"

    def infer(model):
        if model == "cuda":
            raise CudaOOM("CUDA out of memory")
        return "ok on cpu"

    assert m.run(infer) == "ok on cpu"
    assert m.device == "cpu" and m.degraded


def test_non_gpu_errors_are_not_swallowed(monkeypatch):
    monkeypatch.setattr(base, "resolve_device", lambda policy, free: ("cpu", "configured"))
    m = LocalModel("x", lambda device: device, "cpu", 0, queue_wait_s=1)
    m.load()
    with pytest.raises(ValueError):
        m.run(lambda model: (_ for _ in ()).throw(ValueError("bad input")))


def test_busy_when_queue_wait_exceeded(monkeypatch):
    monkeypatch.setattr(base, "resolve_device", lambda policy, free: ("cpu", "configured"))
    m = LocalModel("x", lambda device: device, "cpu", 0, queue_wait_s=0.05)
    m.load()
    release = threading.Event()
    t = threading.Thread(target=lambda: m.run(lambda _: release.wait(2)))
    t.start()
    try:
        with pytest.raises(Busy):
            m.run(lambda _: None)
    finally:
        release.set()
        t.join()


def _watsonx_transport(chat_status=200, content='{"crime_minor": "cyber.job_task"}'):
    def handler(request: httpx.Request):
        if request.url.host == "iam.cloud.ibm.com":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer tok"
        if request.url.path.endswith("foundation_model_specs"):
            return httpx.Response(200, json={"resources": [{"model_id": "ibm/granite-3-3-8b-instruct"},
                                                           {"model_id": "meta-llama/llama-3-3-70b-instruct"}]})
        if request.url.path.endswith("/text/chat"):
            body = json.loads(request.content)
            assert body["model_id"] == "ibm/granite-3-3-8b-instruct" and body["project_id"] == "proj"
            if chat_status != 200:
                return httpx.Response(chat_status, json={"error": "x"})
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                                             "usage": {"prompt_tokens": 321, "completion_tokens": 45}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


CFG = {"model_candidates": ["ibm/granite-4-h-small", "ibm/granite-3-3-8b-instruct"], "api_version": "2024-05-31"}


def test_watsonx_selects_available_model_and_generates_json():
    g = WatsonxGenerator(CFG, "key", "proj", "https://us-south.ml.cloud.ibm.com", transport=_watsonx_transport())
    g.load()
    assert g.model_id == "ibm/granite-3-3-8b-instruct"          # first candidate not offered -> second chosen
    out = g.generate("sys", "prompt", {"type": "object"}, 300)
    assert out["json"] == {"crime_minor": "cyber.job_task"}
    assert out["usage"] == {"input_tokens": 321, "output_tokens": 45}


def test_watsonx_rate_limit_is_busy():
    g = WatsonxGenerator(CFG, "key", "proj", "https://x", transport=_watsonx_transport(chat_status=429))
    g.load()
    with pytest.raises(Busy):
        g.generate("sys", "prompt", None, 100)


def test_watsonx_without_credentials_is_unavailable():
    with pytest.raises(ProviderUnavailable):
        WatsonxGenerator(CFG, None, None, "https://x")
