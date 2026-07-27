"""Config loading for Athena.

Reads `athena.toml` if present and merges it over the built-in defaults. Every default
here is the value written in ATHENA.md; the file only overrides. No networking, no I/O
beyond reading the one TOML file.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- spec defaults (ATHENA.md, "State machine") -----------------------------------
# These must always work even if athena.toml lists different phrases, so they are
# baked in here and unioned with the user's list rather than replaced by it.
DEFAULT_ACTIVATE = ("athena, initiate", "athena, it's go time")
DEFAULT_SERIOUS = ("athena, let's get serious", "athena, let's get cracking")
DEFAULT_UNSERIOUS = ("good session athena",)
DEFAULT_DEACTIVATE = ("that's enough for today athena",)
DEFAULT_VOICE = ("athena, let's get talking",)
DEFAULT_TEXT = ("athena, let's get handsy",)
DEFAULT_BRAIN_VIEW = ("athena, show me your mind",)


def default_db_path() -> Path:
    """macOS location from the spec; a sane XDG fallback elsewhere (CI, dev on Linux)."""
    mac = Path.home() / "Library" / "Application Support"
    if mac.is_dir():
        return mac / "Athena" / "athena.db"
    return Path.home() / ".local" / "share" / "Athena" / "athena.db"


@dataclass(frozen=True)
class PhraseConfig:
    activate: tuple[str, ...] = DEFAULT_ACTIVATE
    serious: tuple[str, ...] = DEFAULT_SERIOUS
    unserious: tuple[str, ...] = DEFAULT_UNSERIOUS
    deactivate: tuple[str, ...] = DEFAULT_DEACTIVATE
    voice: tuple[str, ...] = DEFAULT_VOICE
    text: tuple[str, ...] = DEFAULT_TEXT
    brain_view: tuple[str, ...] = DEFAULT_BRAIN_VIEW


@dataclass(frozen=True)
class DaemonConfig:
    host: str = "127.0.0.1"
    port: int = 8787


@dataclass(frozen=True)
class BrainConfig:
    model: str = "llama3.1:8b"
    lite_model: str = "llama3.2:3b"
    lite: bool = False
    ollama_host: str = "http://127.0.0.1:11434"
    keep_alive: str = "10m"
    request_timeout_s: float = 120.0

    @property
    def active_model(self) -> str:
        """The model actually loaded, honouring the brain.lite escape hatch."""
        return self.lite_model if self.lite else self.model


@dataclass(frozen=True)
class StateConfig:
    idle_timeout_s: float = 120.0
    follow_up_window_s: float = 8.0
    phrases: PhraseConfig = field(default_factory=PhraseConfig)


@dataclass(frozen=True)
class ValveConfig:
    default_level: int = 1


@dataclass(frozen=True)
class MemoryConfig:
    db_path: Path = field(default_factory=default_db_path)


@dataclass(frozen=True)
class UIConfig:
    open_browser_on_start: bool = False


@dataclass(frozen=True)
class Config:
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)
    state: StateConfig = field(default_factory=StateConfig)
    valve: ValveConfig = field(default_factory=ValveConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    source_path: Path | None = None


def _phrases(raw: dict[str, Any]) -> PhraseConfig:
    """Union the user's phrases with the spec defaults — defaults must always work."""

    def merge(key: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
        extra = raw.get(key, ())
        if isinstance(extra, str):
            extra = [extra]
        merged = list(defaults) + [p for p in extra if p not in defaults]
        return tuple(merged)

    return PhraseConfig(
        activate=merge("activate", DEFAULT_ACTIVATE),
        serious=merge("serious", DEFAULT_SERIOUS),
        unserious=merge("unserious", DEFAULT_UNSERIOUS),
        deactivate=merge("deactivate", DEFAULT_DEACTIVATE),
        voice=merge("voice", DEFAULT_VOICE),
        text=merge("text", DEFAULT_TEXT),
        brain_view=merge("brain_view", DEFAULT_BRAIN_VIEW),
    )


def find_config(start: Path | None = None) -> Path | None:
    """Look for athena.toml next to the package, then in the cwd."""
    candidates = [
        Path(__file__).resolve().parent.parent / "athena.toml",
        (start or Path.cwd()) / "athena.toml",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_config(path: Path | None = None) -> Config:
    path = path or find_config()
    if path is None or not path.is_file():
        return Config()

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    daemon_raw = raw.get("daemon", {})
    brain_raw = raw.get("brain", {})
    state_raw = raw.get("state", {})
    valve_raw = raw.get("valve", {})
    memory_raw = raw.get("memory", {})
    ui_raw = raw.get("ui", {})

    db_path = memory_raw.get("db_path")

    return Config(
        daemon=DaemonConfig(
            host=daemon_raw.get("host", "127.0.0.1"),
            port=int(daemon_raw.get("port", 8787)),
        ),
        brain=BrainConfig(
            model=brain_raw.get("model", "llama3.1:8b"),
            lite_model=brain_raw.get("lite_model", "llama3.2:3b"),
            lite=bool(brain_raw.get("lite", False)),
            ollama_host=brain_raw.get("ollama_host", "http://127.0.0.1:11434"),
            keep_alive=brain_raw.get("keep_alive", "10m"),
            request_timeout_s=float(brain_raw.get("request_timeout_s", 120.0)),
        ),
        state=StateConfig(
            idle_timeout_s=float(state_raw.get("idle_timeout_s", 120.0)),
            follow_up_window_s=float(state_raw.get("follow_up_window_s", 8.0)),
            phrases=_phrases(state_raw.get("phrases", {})),
        ),
        valve=ValveConfig(default_level=int(valve_raw.get("default_level", 1))),
        memory=MemoryConfig(db_path=Path(db_path).expanduser() if db_path else default_db_path()),
        ui=UIConfig(open_browser_on_start=bool(ui_raw.get("open_browser_on_start", False))),
        source_path=path,
    )
