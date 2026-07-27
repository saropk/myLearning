"""The local brain transport: Ollama on 127.0.0.1.

## Why this module may import httpx

Security invariant 1 forbids networking imports outside `gateway/`. Core principle 2
carves out one exemption: "localhost calls to the daemon's own API and to Ollama on
127.0.0.1 are exempt — they never leave the machine." This module is that exemption, and
it is the *only* file that claims it (`tests/test_no_network_imports.py` allowlists this
path and nothing else).

The exemption is verified rather than promised: `OllamaClient` refuses to construct
against a non-loopback host, so a typo'd `ollama_host` in athena.toml cannot turn the
local brain into an egress path. Auditability over promises.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit  # stdlib URL *parsing* only — no urllib.request here

import httpx

LOOPBACK_HOSTNAMES = frozenset({"localhost", "ip6-localhost", "localhost.localdomain"})


class LLMUnavailable(RuntimeError):
    """Ollama could not be reached or errored. Callers must degrade, never crash."""


class NonLoopbackHost(ValueError):
    """The configured Ollama host is not on this machine. Fail closed at startup."""


def assert_loopback(url: str) -> None:
    """Raise unless `url`'s host is unambiguously this machine."""
    host = urlsplit(url).hostname
    if host is None:
        raise NonLoopbackHost(f"ollama_host has no host component: {url!r}")
    if host in LOOPBACK_HOSTNAMES:
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError as exc:  # not an IP literal at all — a real DNS name
        raise NonLoopbackHost(f"ollama_host must be a loopback address, got {host!r}") from exc
    raise NonLoopbackHost(f"ollama_host must be a loopback address, got {host!r}")


@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str
    eval_count: int | None = None
    total_duration_ms: float | None = None


class OllamaClient:
    """Minimal async Ollama client: chat, model list, resident-model report."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        timeout_s: float = 120.0,
        keep_alive: str = "10m",
    ) -> None:
        assert_loopback(base_url)
        self.base_url = base_url.rstrip("/")
        self.keep_alive = keep_alive
        # trust_env=False: no proxy env var can ever redirect a local brain call outbound.
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_s, trust_env=False)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        options: dict[str, Any] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if options:
            payload["options"] = options
        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(
                f"Ollama returned {exc.response.status_code} for model {model!r}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Ollama unreachable at {self.base_url}: {exc}") from exc
        except ValueError as exc:
            raise LLMUnavailable("Ollama returned a non-JSON response") from exc

        text = (data.get("message") or {}).get("content", "")
        duration = data.get("total_duration")
        return ChatResult(
            text=text.strip(),
            model=data.get("model", model),
            eval_count=data.get("eval_count"),
            total_duration_ms=duration / 1e6 if isinstance(duration, (int, float)) else None,
        )

    async def resident_models(self) -> list[dict[str, Any]]:
        """`/api/ps` — what Ollama currently holds in memory, for the RAM budget report."""
        try:
            resp = await self._client.get("/api/ps")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailable(f"Ollama unreachable at {self.base_url}: {exc}") from exc
        models = data.get("models") or []
        return [
            {
                "name": m.get("name") or m.get("model", "?"),
                "size_bytes": m.get("size_vram") or m.get("size") or 0,
                "expires_at": m.get("expires_at"),
            }
            for m in models
        ]

    async def available_models(self) -> list[str]:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailable(f"Ollama unreachable at {self.base_url}: {exc}") from exc
        return [m.get("name", "?") for m in data.get("models") or []]
