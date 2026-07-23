"""§3 Invariant 4 — audit is verbatim.

Log the payload, not a summary. One JSON object per line, append-only. The
write is flushed to disk *before* the network call (gateway step 2); if the
audit write fails, the send fails. "What did my agent send this week" must be
answerable exactly.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import Request


def _to_jsonable(obj: Any) -> Any:
    """Serialize dataclasses/enums verbatim, without dropping fields."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    # IntEnum serializes as its int value, which is what the schema shows.
    return obj


class AuditLog:
    """Append-only verbatim log of every outbound payload."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, req: Request, *, cost: float = 0.0) -> str:
        """Write one audit line for `req` and return its payload hash.

        Raises on any I/O failure — the caller (gateway) must treat a failed
        audit write as a failed send. The payload is serialized verbatim and
        fsync'd before this returns.
        """
        payload = {
            "messages": _to_jsonable(req.messages),
            "tools": _to_jsonable(req.tools),
        }
        payload_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        payload_hash = "sha256:" + hashlib.sha256(payload_bytes).hexdigest()

        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope": int(req.scope),
            "model": req.model,
            "payload_hash": payload_hash,
            "payload": payload,
            "files_included": list(req.files_included),
            "usage": {"cost": cost},
        }

        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        return payload_hash
