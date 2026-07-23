"""§3 Invariant 3 — categorical denylists.

Two of them, neither confidence-tunable, neither overridable by L8 learning.
Chunk 1 wires the *exfiltrable* list into the gateway scope check. The
*destructive* list is data here for the later chunks (L7 ambient / bash) that
need it; it is not yet enforced because there is no bash tool to gate.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

# Exfiltrable: never leave below Level 3. Matched against file paths at egress.
EXFILTRABLE_GLOBS = [
    "*.env",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*_rsa",
    "*_dsa",
    "*_ed25519",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "*.credentials",
    "credentials.json",
    "*.secret",
    "secrets.*",
]

# Destructive: never ambient-suggested. Reserved for L7 / bash gating (later).
DESTRUCTIVE_SUBSTRINGS = [
    "rm -rf",
    "--hard",
    "--force",
    "-f ",
    " dd ",
    "drop table",
    "drop database",
    "| sh",
    "| bash",
    "curl | ",
]


def is_exfiltrable(path: str) -> bool:
    """True if `path` matches a categorical exfiltrable pattern.

    Checks both the basename and every path segment so a nested `.env` or a
    key inside a directory is caught, not just files at the root.
    """
    p = PurePosixPath(path.replace("\\", "/"))
    candidates = [p.name, *[seg for seg in p.parts]]
    for pattern in EXFILTRABLE_GLOBS:
        for cand in candidates:
            if fnmatch.fnmatch(cand.lower(), pattern.lower()):
                return True
    return False
