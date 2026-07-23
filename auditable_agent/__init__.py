"""Auditable local-first coding agent.

The model is remote and swappable; the world stays local, bounded, and
inspectable. See AGENT_SCHEMA.md for the full design and CLAUDE.md for the
invariants every module must uphold.

Chunk 1 (the spine): read a file, answer a question about it, log every
outbound payload verbatim before it leaves the machine.
"""

__all__ = ["contracts", "config"]
