"""Entrypoint: `python -m athena`.

Prints the tokenised launch URL — that is how the Aegis page gets its bearer token. The
token itself lives in the SQLite settings table, never in a file in the repo and never in
a log line other than this one local, interactive print.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import uvicorn

from .config import load_config
from .daemon import create_app
from .llm import NonLoopbackHost
from .memory.store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena", description="Run the Athena daemon.")
    parser.add_argument("--config", type=Path, default=None, help="path to athena.toml")
    parser.add_argument("--port", type=int, default=None, help="override the configured port")
    parser.add_argument(
        "--print-url", action="store_true", help="print the tokenised UI URL and exit"
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    port = args.port or config.daemon.port

    store = Store(config.memory.db_path)
    token = store.ensure_token()
    url = f"http://{config.daemon.host}:{port}/?token={token}"

    if args.print_url:
        store.close()
        print(url)
        return 0

    store.close()

    try:
        app = create_app(config)
    except NonLoopbackHost as exc:
        print(f"refusing to start: {exc}", file=sys.stderr)
        return 2

    print(f"Athena listening on http://{config.daemon.host}:{port}")
    print(f"Aegis:  {url}")
    if config.ui.open_browser_on_start:
        webbrowser.open(url)

    # host comes from config and is 127.0.0.1 by default; security invariant 2 means it
    # should stay that way.
    uvicorn.run(app, host=config.daemon.host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
