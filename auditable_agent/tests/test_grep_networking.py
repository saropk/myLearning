"""§3 Invariant 1 — the grep test.

The build fails if networking imports appear anywhere outside gateway/.
Written before there is much code to untangle; retrofitting is the expensive
version. This runs in CI and locally.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent      # auditable_agent/
GATEWAY = PKG_ROOT / "gateway"

# Modules whose import implies (or enables) networking.
NETWORKING = [
    "socket", "ssl", "http", "urllib", "requests", "httpx",
    "aiohttp", "websocket", "websockets", "anthropic", "openai",
    "ftplib", "smtplib", "telnetlib", "xmlrpc",
]

_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?P<mod1>[\w.]+)|from\s+(?P<mod2>[\w.]+)\s+import)",
    re.MULTILINE,
)


def _top(module: str) -> str:
    return module.split(".")[0]


class GrepNetworkingTest(unittest.TestCase):
    def test_no_networking_imports_outside_gateway(self):
        offenders: list[str] = []
        for py in PKG_ROOT.rglob("*.py"):
            if GATEWAY in py.parents or py == GATEWAY:
                continue
            src = py.read_text(encoding="utf-8")
            for m in _IMPORT_RE.finditer(src):
                mod = m.group("mod1") or m.group("mod2") or ""
                if _top(mod) in NETWORKING:
                    line = src[: m.start()].count("\n") + 1
                    offenders.append(f"{py.relative_to(PKG_ROOT)}:{line} -> {mod}")

        self.assertEqual(
            offenders,
            [],
            "networking imports must live only in gateway/:\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
