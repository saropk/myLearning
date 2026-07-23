"""Tool registry — register, list (filtered by scope), and dispatch.

The valve filters the advertised tool list by scope *before* the model sees it
(§3a rationale for ToolDef.scope). Dispatch routes a ToolCall to its handler.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..contracts import ScopeLevel, ToolCall, ToolDef, ToolError, ToolResult

Handler = Callable[[ToolCall, Path], ToolResult]


class ToolRegistry:
    def __init__(self, root: Path):
        self._root = root
        self._defs: dict[str, ToolDef] = {}
        self._handlers: dict[str, Handler] = {}

    def register(self, definition: ToolDef, handler: Handler) -> None:
        self._defs[definition.name] = definition
        self._handlers[definition.name] = handler

    def available(self, scope: ScopeLevel) -> list[ToolDef]:
        """Tools permitted at `scope` — the model never sees the rest."""
        return [d for d in self._defs.values() if d.scope <= scope]

    def dispatch(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.name)
        if handler is None:
            return ToolResult(
                id=call.id,
                ok=False,
                data=None,
                error=ToolError("not_found", f"unknown tool: {call.name!r}"),
            )
        return handler(call, self._root)
