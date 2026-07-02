"""Minimal HTTP helpers built on the standard library (no extra dependencies).

`urllib` automatically honours HTTP(S)_PROXY environment variables, so this
works behind corporate proxies too. Every call is wrapped so a network failure
returns None instead of raising — skills can then degrade gracefully.
"""

import json
import urllib.parse
import urllib.request

USER_AGENT = "Athena/0.2 (personal assistant)"


def get_json(url: str, params: dict | None = None, timeout: int = 8):
    """GET a URL and parse JSON. Returns the decoded object, or None on failure."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network, TLS, timeout, bad JSON — all non-fatal
        print(f"[http] request failed for {url.split('?')[0]}: {exc}")
        return None


def get_text(url: str, timeout: int = 8) -> str | None:
    """GET a URL and return the body text, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[http] request failed for {url.split('?')[0]}: {exc}")
        return None
