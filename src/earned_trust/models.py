"""Model access behind one interface. Stdlib only.

Backends:
  gemini  - Google Generative Language API (Gemma models)      env: GOOGLE_API_KEY, GEMMA_MODEL
  openai  - any OpenAI-compatible /chat/completions endpoint   env: NVIDIA_API_KEY, NVIDIA_BASE_URL, NEMOTRON_MODEL
            (NVIDIA build / Verda / Junction gateway / OpenAI)

Every call returns a ModelReply that records which model *actually* answered and
how many attempts it took. A failed call is an explicit `error`, never an empty
"no findings" (a reviewer that didn't answer is *unknown*, not *clean*).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            v = v.split(" #", 1)[0].strip()
            if v and k.strip() not in os.environ:
                os.environ[k.strip()] = v


@dataclass
class ModelReply:
    text: str
    model: str
    family: str
    attempts: int
    error: str | None = None
    usage: dict | None = None


def _post(url: str, body: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


class Model:
    family = "?"

    def __init__(self, models: list[str]):
        self.models = models

    def _call(self, model: str, system: str, user: str, json_mode: bool, timeout: int = 180) -> tuple[str, dict]:
        raise NotImplementedError

    def complete(self, system: str, user: str, json_mode: bool = True, retries: int = 2, timeout: int | None = None) -> ModelReply:
        timeout = timeout or int(os.environ.get("ET_MODEL_TIMEOUT", "180"))
        attempts, last = 0, "no models configured"
        for model in self.models:                       # primary first, then fallbacks
            for i in range(retries):
                attempts += 1
                try:
                    text, usage = self._call(model, system, user, json_mode, timeout)
                    return ModelReply(text, model, self.family, attempts, usage=usage)
                except urllib.error.HTTPError as e:
                    last = f"{model}: HTTP {e.code} {e.read()[:200]!r}"
                    if e.code in (400, 401, 403, 404):
                        break                           # not transient: try next model
                except Exception as e:                  # timeouts, bad JSON, connection resets
                    last = f"{model}: {type(e).__name__}: {e}"
                time.sleep(2 * (i + 1))
        return ModelReply("", self.models[0] if self.models else "?", self.family, attempts, error=last)


class Gemini(Model):
    family = "google-gemma"

    def __init__(self, models: list[str] | None = None):
        load_env()
        primary = os.environ.get("GEMMA_MODEL", "gemma-4-31b-it")
        super().__init__(models or [primary, "gemma-4-26b-a4b-it"])
        self.key = os.environ["GOOGLE_API_KEY"]

    def _call(self, model, system, user, json_mode, timeout=180):
        # Gemma on this API has no system role: prepend the system text to the user turn.
        body = {"contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
                "generationConfig": {"temperature": 0.2}}
        r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                  body, {"x-goog-api-key": self.key}, timeout)
        parts = r["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return text, r.get("usageMetadata", {})


class OpenAICompat(Model):
    family = "nvidia-nemotron"

    def __init__(self, base_url: str | None = None, key: str | None = None, models: list[str] | None = None, family: str | None = None):
        load_env()
        self.base = (base_url or os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")).rstrip("/")
        self.key = key or os.environ["NVIDIA_API_KEY"]
        super().__init__(models or [os.environ["NEMOTRON_MODEL"]])
        if family:
            self.family = family

    def _call(self, model, system, user, json_mode, timeout=180):
        body = {"model": model, "temperature": 0.2,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        r = _post(f"{self.base}/chat/completions", body, {"Authorization": f"Bearer {self.key}"}, timeout)
        return r["choices"][0]["message"]["content"], r.get("usage", {})


def get_reviewer(name: str) -> Model:
    name = name.lower()
    if name in ("gemma", "gemini"):
        return Gemini()
    if name in ("nemotron", "nvidia"):
        return OpenAICompat()
    if name == "openai":
        load_env()
        return OpenAICompat("https://api.openai.com/v1", os.environ["OPENAI_API_KEY"], ["gpt-5-mini"], "openai")
    raise ValueError(f"unknown reviewer {name}")


def extract_json(text: str):
    """Pull the first JSON object/array out of a model reply (models wrap JSON in prose or ``` fences)."""
    s = text.strip()
    if "```" in s:
        chunks = s.split("```")
        for c in chunks[1::2]:
            c = c.split("\n", 1)[1] if c.lstrip().startswith(("json", "JSON")) else c
            try:
                return json.loads(c)
            except json.JSONDecodeError:
                continue
    for open_, close in (("{", "}"), ("[", "]")):
        i, j = s.find(open_), s.rfind(close)
        if i != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError("no JSON in model reply")
