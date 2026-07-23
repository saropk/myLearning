"""§3a Contracts — the stable core.

These types are expensive to change; everything else plugs into them. Written
in TypeScript notation in the schema, translated here as-is with dataclasses.
Nothing above the gateway (L0) knows about provider-specific formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal


class ScopeLevel(IntEnum):
    """§6 Data valve. For code the tunable dimension is scope, not anonymity."""

    SEALED = 0  # nothing leaves; local model only
    SCOPED = 1  # only files explicitly opened for this task
    REPO = 2    # full retrieval over current repository
    OPEN = 3    # repo + environment; per-payload consent


# §3a FailureCategory — L4's output, present on every failed result.
FailureCategory = Literal[
    "missing_dependency",
    "syntax_error",
    "wrong_directory",
    "permission",
    "not_found",
    "test_failure",
    "timeout",
    "unknown",
]

StopReason = Literal["end", "tool_use", "max_tokens", "refusal"]


# --- Tool schema: every tool speaks this -----------------------------------

@dataclass(frozen=True)
class ToolDef:
    """What the agent advertises to the model. `params` is provider-neutral."""

    name: str
    description: str
    params: dict[str, Any]          # JSONSchema
    scope: ScopeLevel               # minimum valve level required
    mutating: bool                  # touches disk or system state?


@dataclass(frozen=True)
class ToolCall:
    """What comes back from the model."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolError:
    category: FailureCategory
    message: str
    raw: str | None = None          # original stderr, post-L3 truncation


@dataclass
class ToolResult:
    """What every tool returns, always. `data` is shaped, never a raw string."""

    id: str                         # matches ToolCall.id
    ok: bool
    data: Any                       # typed per tool, shaped not raw
    truncated: bool = False         # did L3 elide anything?
    tokens: int = 0                 # cost accounting for L1's ceiling
    error: ToolError | None = None


# --- Gateway schema: the only module with network access -------------------

@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    content: Any


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cost: float = 0.0


@dataclass
class Request:
    messages: list[Message]
    tools: list[ToolDef]
    scope: ScopeLevel               # valve level for this request
    max_tokens: int
    model: str | None = None        # optional override; config supplies default
    # Audit-support field (not part of the model-facing payload): the loop
    # tracks which local files fed this request so the audit log can answer
    # "what did my agent send this week" with one grep. See AuditLog.
    files_included: list[str] = field(default_factory=list)


@dataclass
class Response:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    stop: StopReason
