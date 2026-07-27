#!/usr/bin/env python3
"""Measure Athena's real footprint against the budget table in ATHENA.md.

Phase 1 acceptance requires the budget table to be checked against measured reality and
corrected if it is wrong. Run this against a live daemon and paste the output into
`tests/phase1_ram.md`:

    python -m athena                        # terminal 1
    python scripts/measure_ram.py           # terminal 2

Reads /api/status, so it measures what the daemon reports about itself — daemon RSS plus
whatever Ollama says it currently holds resident. Talk to her first (which loads the
brain) if you want the warm number rather than the dormant one.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request  # noqa: F401 — see note below

# Note on the import above: this script is NOT part of the `athena` package (the
# forbidden-import test scans athena/ only). It is an operator tool that talks to the
# daemon's own localhost API, which core principle 2 exempts.


def fetch_status(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    # No proxy handler: a localhost call must never be redirected through one.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=10) as response:
        return json.load(response)


def discover_url_and_token() -> tuple[str, str]:
    """Ask the package for the tokenised launch URL, so no secret is typed by hand."""
    out = subprocess.run(
        [sys.executable, "-m", "athena", "--print-url"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    base, _, token = out.partition("/?token=")
    return base.rstrip("/"), token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=None, help="daemon base URL (default: discovered)")
    parser.add_argument("--token", default=None, help="bearer token (default: discovered)")
    args = parser.parse_args()

    base, token = discover_url_and_token()
    base = args.url or base
    token = args.token or token

    try:
        status = fetch_status(f"{base}/api/status", token)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"could not reach the daemon at {base}: {exc}", file=sys.stderr)
        print("start it with `python -m athena` first.", file=sys.stderr)
        return 1

    ram = status["ram"]
    budget = ram["detail"]["budget_table_gb"]
    verdict = "WITHIN BUDGET" if ram["within_budget"] else "OVER BUDGET"

    print(f"state              {status['state']}  (valve {status['valve']})")
    print(f"brain              {status['brain']['model']}", end="")
    print("" if status["brain"]["reachable"] else "  [unreachable]")
    print(
        f"machine RAM        {ram['machine_total_gb']} GB total, "
        f"{ram['machine_available_gb']} GB available"
    )
    print()
    print(f"daemon RSS         {ram['daemon_gb']:.3f} GB   (budget {budget['daemon']} GB)")
    print(f"models resident    {ram['models_gb']:.3f} GB")
    for model in status["models_loaded"]:
        print(f"  - {model['name']}: {model['size_bytes'] / 1024**3:.2f} GB")
    print(f"total              {ram['total_gb']:.3f} GB   (budget {ram['budget_gb']} GB)")
    print(f"verdict            {verdict}")
    print()
    print("If a number here disagrees with the table in ATHENA.md, correct the table —")
    print("never silently exceed it (ATHENA.md, Hardware profile).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
