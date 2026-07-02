"""A tiny JSON-file store for things Athena should remember between sessions.

Lives at ~/.athena/memory.json — outside the project, so nothing personal ends
up in git. Used by the memory skill and surfaced to Claude so it knows your facts.
"""

import json
import os
from pathlib import Path

STORE_DIR = Path(os.path.expanduser("~/.athena"))
STORE_FILE = STORE_DIR / "memory.json"

_DEFAULT = {"notes": []}


def load() -> dict:
    try:
        data = json.loads(STORE_FILE.read_text())
        data.setdefault("notes", [])
        return data
    except FileNotFoundError:
        return dict(_DEFAULT)
    except Exception as exc:  # corrupted file — start fresh rather than crash
        print(f"[store] could not read memory ({exc}); starting empty.")
        return dict(_DEFAULT)


def save(data: dict) -> None:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        STORE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        print(f"[store] could not save memory: {exc}")


def add_note(text: str) -> None:
    data = load()
    data["notes"].append(text)
    save(data)


def all_notes() -> list[str]:
    return load().get("notes", [])
