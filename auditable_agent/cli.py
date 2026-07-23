"""Chunk 1 entry point: ask a question about a file.

    python -m auditable_agent.cli "What does FirstProgram.py do?"

Uses the offline echo adapter by default (no API key needed). Set
AGENT_ADAPTER=anthropic and ANTHROPIC_API_KEY to use a real model.
"""

from __future__ import annotations

import sys

from .config import Config
from .gateway import Gateway
from .loop import AgentLoop
from .tools import ToolRegistry, read_file_def, run_read_file


def build_loop(config: Config | None = None) -> AgentLoop:
    config = config or Config.from_env()
    registry = ToolRegistry(config.root)
    registry.register(read_file_def, run_read_file)
    gateway = Gateway(config)
    return AgentLoop(gateway, registry, config)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2

    prompt = " ".join(argv)
    config = Config.from_env()
    loop = build_loop(config)
    result = loop.run(prompt)

    print(result.text)
    print(
        f"\n[turns={result.turns} cost=${result.cost:.4f} stop={result.stop} "
        f"files={result.files_read or '—'}]",
        file=sys.stderr,
    )
    print(f"[audit: {config.audit_path}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
