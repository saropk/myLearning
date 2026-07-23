"""Runtime configuration.

The model is a config value, not a dependency (§2 L0). Keep this declarative
about *what*, not *how* — the model layer goes stale fast (§5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import ScopeLevel


@dataclass
class Config:
    # Which provider adapter the gateway loads. "echo" is offline (no network,
    # Level 0 spirit); "anthropic" makes real calls. Adapter is a seam, not a
    # dependency of anything above L0.
    adapter: str = "echo"

    # Default model when a Request does not override it.
    model: str = "claude-sonnet-5"

    # Valve level for the session. UI ships 0 and 2 initially (§6).
    scope: ScopeLevel = ScopeLevel.REPO

    # L1 ceilings — the loop's explicit stop conditions.
    max_turns: int = 12
    max_cost: float = 1.00          # USD; fail closed when exceeded
    max_tokens: int = 4096          # per request

    # Where the verbatim audit log lives. Local, append-only, inspectable.
    audit_path: Path = field(default_factory=lambda: Path(".agent/audit.jsonl"))

    # Repo root the tools operate within.
    root: Path = field(default_factory=Path.cwd)

    @classmethod
    def from_env(cls) -> "Config":
        cfg = cls()
        cfg.adapter = os.environ.get("AGENT_ADAPTER", cfg.adapter)
        cfg.model = os.environ.get("AGENT_MODEL", cfg.model)
        if (lvl := os.environ.get("AGENT_SCOPE")) is not None:
            cfg.scope = ScopeLevel(int(lvl))
        return cfg
