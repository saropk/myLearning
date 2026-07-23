"""Provider adapters sit behind one internal tool schema (§2 L0).

The model is a config value rather than a dependency: pick an adapter by name.
Networking lives here (inside gateway/), and only here.
"""

from __future__ import annotations

from .base import Adapter


def load(name: str) -> Adapter:
    """Resolve an adapter by config name. Kept tiny on purpose."""
    if name == "echo":
        from .echo import EchoAdapter

        return EchoAdapter()
    if name == "anthropic":
        from .anthropic import AnthropicAdapter

        return AnthropicAdapter()
    raise ValueError(f"unknown adapter: {name!r}")


__all__ = ["Adapter", "load"]
