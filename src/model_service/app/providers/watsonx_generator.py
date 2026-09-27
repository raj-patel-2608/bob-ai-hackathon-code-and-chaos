"""Generator provider backed by IBM watsonx.ai (Granite chat models) over the REST API.

Auth: IBM Cloud API key -> IAM bearer token (cached until shortly before expiry).
Chat: POST {WATSONX_URL}/ml/v1/text/chat?version=<api_version>
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time

import httpx

from .base import Busy, GeneratorProvider, ProviderUnavailable

log = logging.getLogger("model_service.watsonx")
IAM_URL = "https://iam.cloud.ibm.com/identity/token"


class WatsonxGenerator(GeneratorProvider):
    def __init__(self, cfg: dict, api_key: str | None, project_id: str | None, base_url: str,
                 transport: httpx.BaseTransport | None = None):
        if not api_key or not project_id:
            raise ProviderUnavailable("watsonx credentials not configured (WATSONX_API_KEY / WATSONX_PROJECT_ID)")
        self.api_key, self.project_id = api_key, project_id
        self.base_url = base_url.rstrip("/")
        self.api_version = str(cfg.get("api_version", "2024-05-31"))
        self.temperature = float(cfg.get("temperature", 0))
        self.candidates = list(cfg.get("model_candidates") or [])
        self.model_id: str | None = None
        self._http = httpx.Client(timeout=float(cfg.get("timeout_s", 60)), transport=transport)
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    # -------------------------------------------------------------- auth
    def _bearer(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_expiry - 120:
                return self._token
            resp = self._http.post(IAM_URL, data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                                                  "apikey": self.api_key},
                                   headers={"Accept": "application/json"})
            if resp.status_code != 200:
                raise ProviderUnavailable(f"IBM Cloud IAM token request failed ({resp.status_code})")
            data = resp.json()
            self._token = data["access_token"]
            self._token_expiry = time.time() + int(data.get("expires_in", 3600))
            return self._token

    # -------------------------------------------------------------- model selection
    def load(self) -> None:
        """Pick the first configured candidate that this watsonx region offers for chat."""
        resp = self._http.get(f"{self.base_url}/ml/v1/foundation_model_specs",
                              params={"version": self.api_version, "limit": 200, "filters": "function_text_chat"},
                              headers={"Authorization": f"Bearer {self._bearer()}"})
        if resp.status_code != 200:
            raise ProviderUnavailable(f"could not list watsonx models ({resp.status_code}): {resp.text[:200]}")
        available = {m["model_id"] for m in resp.json().get("resources", [])}
        for candidate in self.candidates:
            if candidate in available:
                self.model_id = candidate
                log.info("watsonx generator model: %s", candidate)
                return
        raise ProviderUnavailable(f"none of {self.candidates} is available; region offers "
                                  f"{sorted(m for m in available if 'granite' in m)}")

    # -------------------------------------------------------------- generation
    def generate(self, system: str, prompt: str, json_schema: dict | None, max_tokens: int) -> dict:
        if not self.model_id:
            raise ProviderUnavailable("watsonx model not selected")
        body = {"model_id": self.model_id, "project_id": self.project_id, "max_tokens": max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_schema is not None:
            body["response_format"] = {"type": "json_object"}
        resp = self._http.post(f"{self.base_url}/ml/v1/text/chat", params={"version": self.api_version},
                               json=body, headers={"Authorization": f"Bearer {self._bearer()}"})
        if resp.status_code == 429:
            raise Busy("watsonx rate limit reached")
        if resp.status_code >= 400:
            raise RuntimeError(f"watsonx chat failed ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        out = {"text": text, "usage": {"input_tokens": usage.get("prompt_tokens", 0),
                                       "output_tokens": usage.get("completion_tokens", 0)}}
        if json_schema is not None:
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                try:
                    out["json"] = json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass                          # core-api validates and asks for a repair
        return out

    def info(self) -> dict:
        return {"provider": "watsonx", "model_id": self.model_id, "device": "remote",
                "region": self.base_url, "degraded": False}
