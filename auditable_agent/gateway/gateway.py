"""L0 Gateway — send() does exactly four things, in this order (§3a).

  1. Scope check.   Reject anything above req.scope. Any path matching the
                    exfiltrable denylist is a hard failure — no override.
  2. Audit write.   Serialize the exact outbound payload, flush to disk,
                    BEFORE the network call. Audit write fails -> send fails.
  3. Adapt and send. Translate to the provider format, call, translate back.
  4. Normalize.     Provider errors become Response-shaped; none escape.
"""

from __future__ import annotations

from ..audit import AuditLog
from ..config import Config
from ..contracts import Message, Request, Response, ScopeLevel
from ..denylist import is_exfiltrable
from . import adapters


class ScopeViolation(Exception):
    """Raised when a payload exceeds the request's valve level, or references
    an exfiltrable path below Level 3. Fail closed (§3 invariant 2)."""


class Gateway:
    def __init__(self, config: Config, audit: AuditLog | None = None):
        self._config = config
        self._audit = audit or AuditLog(config.audit_path)
        self._adapter = adapters.load(config.adapter)

    def send(self, req: Request) -> Response:
        if req.model is None:
            req.model = self._config.model

        self._scope_check(req)              # 1
        cost_hint = 0.0
        self._audit.record(req, cost=cost_hint)  # 2  (raises -> send fails)
        response = self._adapter.complete(req)    # 3 + 4 (adapter normalizes)
        return response

    # --- step 1 --------------------------------------------------------------

    def _scope_check(self, req: Request) -> None:
        # Exfiltrable paths are a hard failure below Level 3 — checked first,
        # with no confidence threshold and no override.
        if req.scope < ScopeLevel.OPEN:
            for path in req.files_included:
                if is_exfiltrable(path):
                    raise ScopeViolation(
                        f"exfiltrable path blocked below Level 3: {path!r}"
                    )

        # A request may not advertise tools requiring a higher valve level than
        # the request itself. The valve filters the tool list *before* the model
        # sees it — the model cannot request what it is not permitted to do.
        for tool in req.tools:
            if tool.scope > req.scope:
                raise ScopeViolation(
                    f"tool {tool.name!r} requires scope {int(tool.scope)}, "
                    f"request is scope {int(req.scope)}"
                )
