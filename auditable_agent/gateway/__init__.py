"""L0 — Gateway. The only package in the codebase with networking.

The grep-test invariant (§3.1) enforces that networking imports appear
*nowhere* outside this package. Provider adapters live under gateway/adapters/.
"""

from .gateway import Gateway, ScopeViolation

__all__ = ["Gateway", "ScopeViolation"]
