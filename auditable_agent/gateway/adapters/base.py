"""Adapter seam. One internal tool schema in, provider format hidden inside."""

from __future__ import annotations

from typing import Protocol

from ...contracts import Request, Response


class Adapter(Protocol):
    """Translate a neutral Request to a provider call and back to a Response.

    Implementations must not let any provider exception escape — provider
    errors become Response with stop="refusal" or are raised as the gateway
    normalizes them (§3a step 4). Adapters own their own networking.
    """

    name: str

    def complete(self, req: Request) -> Response: ...
