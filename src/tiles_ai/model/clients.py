"""Model clients — the thin, swappable layer over an actual LLM endpoint.

Every client implements one method: `complete(prompt, system) -> str`. This is
all a tile needs; richer surfaces (streaming, tools) can grow later behind the
same boundary.

v0 ships four:
  * EchoModelClient   — offline, deterministic. The default for tests and for
                        proving the wiring before any key is configured.
  * OllamaClient      — local models (the "no data leaves my machine" showcase).
  * AnthropicClient   — hosted, via the Messages API.
  * OpenAIClient      — hosted, via the Chat Completions API.

Real HTTP goes through one stdlib helper (`_post_json`) run off the event loop,
so there is no third-party HTTP dependency. Network clients are only constructed
when actually used; tests inject the echo client and never touch the network.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable


@runtime_checkable
class ModelClient(Protocol):
    """The one method a tile relies on."""

    async def complete(self, prompt: str, *, system: str | None = None) -> str: ...


class ModelClientError(Exception):
    """A model call failed (transport, auth, or bad response)."""


class EchoModelClient:
    """Offline, deterministic client. Returns a marked echo of the prompt.

    Used as the default in tests and as a zero-config way to prove a tile's
    wiring before a real brain is connected. The marker makes it obvious in
    output that no real model ran.
    """

    def __init__(self, model: str = "echo") -> None:
        self.model = model

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        return f"[echo:{self.model}] {head[:200]}"


class OllamaClient:
    """Local models via an Ollama-compatible `/api/generate` endpoint."""

    def __init__(self, endpoint: str, model: str) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        data = await _post_json(f"{self.endpoint}/api/generate", payload)
        return str(data.get("response", "")).strip()


class AnthropicClient:
    """Hosted models via the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str, *, max_tokens: int = 1024) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        data = await _post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


class OpenAIClient:
    """Hosted models via the OpenAI Chat Completions API.

    `base_url` is overridable so any OpenAI-compatible endpoint (Azure OpenAI,
    Together, a local server, ...) works through the same client.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        data = await _post_json(
            f"{self.base_url}/chat/completions",
            {"model": self.model, "messages": messages},
            headers={"authorization": f"Bearer {self.api_key}"},
        )
        choices = data.get("choices", [])
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", "")).strip()


async def _post_json(url: str, payload: dict, *, headers: dict | None = None) -> dict:
    """POST JSON and parse JSON back, off the event loop. stdlib only."""

    def _do() -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("content-type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # surface the server's message
            detail = exc.read().decode("utf-8", "replace")
            raise ModelClientError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ModelClientError(f"could not reach {url}: {exc.reason}") from exc

    return await asyncio.to_thread(_do)
