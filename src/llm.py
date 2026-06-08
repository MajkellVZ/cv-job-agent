"""Local LLM access via Ollama (https://ollama.com).

No API key, no data leaving the machine. Every AI step in the agent
(CV parsing, job scoring) goes through `LocalLLM.chat()`.

Make sure Ollama is running and the model is pulled:
    ollama serve            # usually already running after install
    ollama pull llama3.1    # or qwen2.5, mistral, gemma2, ...

The client talks to Ollama's native /api/chat endpoint and uses its
`format: json` mode to force valid JSON for the parsing/scoring steps.
"""

from __future__ import annotations

import json
import os

import requests


class LLMError(RuntimeError):
    pass


class LocalLLM:
    def __init__(self, model: str | None = None, host: str | None = None,
                 temperature: float = 0.2, timeout: int = 300):
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def chat(self, system: str, user: str, json_mode: bool = False,
             max_tokens: int = 1500) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(
                f"{self.host}/api/chat", json=payload, timeout=self.timeout
            )
        except requests.ConnectionError as exc:
            raise LLMError(
                f"Could not reach Ollama at {self.host}. Is it running? "
                f"Try `ollama serve` and `ollama pull {self.model}`."
            ) from exc

        if resp.status_code == 404:
            raise LLMError(
                f"Model '{self.model}' not found on the Ollama server. "
                f"Run `ollama pull {self.model}`."
            )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()

    def health_check(self) -> None:
        """Raise a clear error early if the server or model isn't ready."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                f"Could not reach Ollama at {self.host}. Start it with `ollama serve`."
            ) from exc
        models = {m.get("name", "").split(":")[0] for m in resp.json().get("models", [])}
        if self.model.split(":")[0] not in models:
            raise LLMError(
                f"Model '{self.model}' is not pulled. Run `ollama pull {self.model}`. "
                f"Available: {', '.join(sorted(models)) or 'none'}"
            )


def loads_json(text: str) -> dict | list:
    """Parse JSON from a model response, tolerating code fences / stray text."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    # Prefer an object, else an array.
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(text)  # last resort: surface the real error
