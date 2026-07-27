"""Egress containment — security invariant 1.

ATHENA.md makes this test mandatory from phase 5 on. It is here from phase 1 because the
cheapest time to stop networking code from spreading is before it has spread, and because
`athena/llm.py` claims the one documented exemption — a claim worth pinning down with a
test the moment it is made.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from athena.llm import NonLoopbackHost, OllamaClient, assert_loopback

PACKAGE = Path(__file__).resolve().parent.parent / "athena"
FORBIDDEN = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "aiohttp",
    "websockets",
    "ftplib",
}

# The only paths permitted to import a networking library, and why:
#   gateway/  — the single network chokepoint (core principle 2)
#   llm.py    — the loopback-only Ollama transport (core principle 2's stated exemption)
ALLOWED = {"gateway", "llm.py"}


def python_files() -> list[Path]:
    return sorted(p for p in PACKAGE.rglob("*.py"))


def is_allowed(path: Path) -> bool:
    rel = path.relative_to(PACKAGE)
    return rel.parts[0] in ALLOWED or rel.name in ALLOWED


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_networking_imports_outside_the_chokepoint() -> None:
    offenders: list[str] = []
    for path in python_files():
        if is_allowed(path):
            continue
        hits = imported_roots(path) & FORBIDDEN
        if hits:
            offenders.append(f"{path.relative_to(PACKAGE)} imports {sorted(hits)}")
    assert not offenders, "networking imports found outside gateway/: " + "; ".join(offenders)


def test_the_exemption_list_stays_short() -> None:
    """If this fails, someone widened the exemption. That is a spec decision, not a fix."""
    assert ALLOWED == {"gateway", "llm.py"}


def test_only_llm_and_gateway_import_httpx() -> None:
    importers = {
        str(p.relative_to(PACKAGE)) for p in python_files() if "httpx" in imported_roots(p)
    }
    assert importers <= {"llm.py"}, f"unexpected httpx importers: {importers}"


# --- the exemption is verified, not promised ---------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
        "http://127.0.0.53:11434",
    ],
)
def test_loopback_hosts_are_accepted(url: str) -> None:
    assert_loopback(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.10:11434",
        "https://api.anthropic.com",
        "http://ollama.example.com:11434",
        "http://10.0.0.1",
        "http://0.0.0.0:11434",
        "not-a-url",
    ],
)
def test_non_loopback_hosts_are_refused(url: str) -> None:
    with pytest.raises(NonLoopbackHost):
        assert_loopback(url)


def test_client_refuses_to_construct_against_a_remote_host() -> None:
    """A typo in athena.toml must not turn the local brain into an egress path."""
    with pytest.raises(NonLoopbackHost):
        OllamaClient(base_url="http://198.51.100.7:11434")


def test_client_ignores_proxy_environment_variables() -> None:
    """trust_env=False: no HTTPS_PROXY can redirect a local brain call off-machine."""
    client = OllamaClient(base_url="http://127.0.0.1:11434")
    assert client._client.trust_env is False


def test_no_telemetry_or_analytics_anywhere() -> None:
    """Security invariant 8: no telemetry, analytics, or crash reporting of any kind."""
    banned = ("sentry_sdk", "posthog", "segment", "mixpanel", "opentelemetry", "datadog")
    offenders = [
        str(p.relative_to(PACKAGE)) for p in python_files() if imported_roots(p) & set(banned)
    ]
    assert not offenders, f"telemetry imports found: {offenders}"
