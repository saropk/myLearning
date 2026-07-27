"""The state machine — single source of truth for what Athena is doing.

Everything in this module is pure, synchronous logic with no I/O and no model calls. That
is the point: security invariant 7 says deactivation phrases are honoured by string
matching, independent of any model's availability or opinion. Nothing here can fail
because Ollama is down.

State (DORMANT / ACTIVE / SERIOUS) and modality (VOICE / TEXT) are orthogonal — see
ATHENA.md, "Modality handoff".
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from .config import PhraseConfig, StateConfig


class State(StrEnum):
    DORMANT = "DORMANT"
    ACTIVE = "ACTIVE"
    SERIOUS = "SERIOUS"


class Modality(StrEnum):
    VOICE = "VOICE"
    TEXT = "TEXT"


class ControlKind(StrEnum):
    STATE = "state"
    MODALITY = "modality"
    VIEW = "view"


ADDRESS_TOKEN = "athena"
# Apostrophes are deleted, not spaced: whisper writes "let's" or "lets" depending on its
# mood, and "lets" must match either. Everything else becomes a space.
_APOSTROPHE = re.compile(r"['‘’ʼ`]")
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace.

    So "athena, it's go time" and "Athena its go time!" normalize identically. Configured
    phrases go through the same function, so the two sides always meet in the middle.
    """
    folded = _APOSTROPHE.sub("", text.lower())
    return _WS.sub(" ", _PUNCT.sub(" ", folded)).strip()


def contains_phrase(utterance: str, phrase: str) -> bool:
    """Whole-word containment, tolerant of leading/trailing words in the same utterance."""
    hay = f" {normalize(utterance)} "
    needle = f" {normalize(phrase)} "
    return needle in hay


@dataclass(frozen=True)
class ControlMatch:
    """A phrase matched before the LLM ever saw the text."""

    kind: ControlKind
    phrase: str
    target_state: State | None = None
    target_modality: Modality | None = None


@dataclass(frozen=True)
class Transition:
    from_state: State
    to_state: State
    phrase: str
    at: float


class PhraseMatcher:
    """Pre-LLM string matching for every control phrase Athena honours."""

    def __init__(self, phrases: PhraseConfig) -> None:
        self._phrases = phrases

    def _first(self, utterance: str, candidates: tuple[str, ...]) -> str | None:
        for phrase in candidates:
            if contains_phrase(utterance, phrase):
                return phrase
        return None

    def match(self, utterance: str, current: State) -> ControlMatch | None:
        """Return the control phrase in `utterance`, if any, given the current state.

        Deactivation is checked first so "that's enough for today athena" always wins,
        whatever else is in the sentence.
        """
        p = self._phrases

        phrase = self._first(utterance, p.deactivate)
        if phrase and current is not State.DORMANT:
            return ControlMatch(ControlKind.STATE, phrase, target_state=State.DORMANT)

        if current is State.DORMANT:
            phrase = self._first(utterance, p.activate)
            if phrase:
                return ControlMatch(ControlKind.STATE, phrase, target_state=State.ACTIVE)
            # Dormant means dormant: no other phrase does anything.
            return None

        if current is State.ACTIVE:
            phrase = self._first(utterance, p.serious)
            if phrase:
                return ControlMatch(ControlKind.STATE, phrase, target_state=State.SERIOUS)

        if current is State.SERIOUS:
            phrase = self._first(utterance, p.unserious)
            if phrase:
                return ControlMatch(ControlKind.STATE, phrase, target_state=State.ACTIVE)

        phrase = self._first(utterance, p.voice)
        if phrase:
            return ControlMatch(ControlKind.MODALITY, phrase, target_modality=Modality.VOICE)

        phrase = self._first(utterance, p.text)
        if phrase:
            return ControlMatch(ControlKind.MODALITY, phrase, target_modality=Modality.TEXT)

        phrase = self._first(utterance, p.brain_view)
        if phrase:
            return ControlMatch(ControlKind.VIEW, phrase)

        return None


def strip_address(text: str) -> str:
    """Remove a leading or trailing "Athena" address token before routing."""
    stripped = text.strip()
    # Leading: "Athena, what's the time" / "Athena what's the time"
    lead = re.match(rf"^\s*{ADDRESS_TOKEN}\b[\s,:.!?-]*", stripped, flags=re.IGNORECASE)
    if lead:
        stripped = stripped[lead.end() :]
    # Trailing: "what's the time, Athena?"
    trail = re.search(rf"[\s,:.!?-]*\b{ADDRESS_TOKEN}\s*[.!?]*\s*$", stripped, flags=re.IGNORECASE)
    if trail:
        stripped = stripped[: trail.start()]
    return stripped.strip()


def is_named_address(text: str) -> bool:
    """True if the utterance starts or ends with "Athena" (the addressing convention)."""
    words = normalize(text).split()
    if not words:
        return False
    return words[0] == ADDRESS_TOKEN or words[-1] == ADDRESS_TOKEN


@dataclass
class Session:
    """One continuous conversation. Survives modality changes, ends at DORMANT."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started_at: float = field(default_factory=time.time)
    turns: list[dict[str, str]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content})


class AthenaState:
    """Owns state, modality, session context, and the timing windows.

    The daemon owns exactly one instance of this and is the only writer (core principle 4:
    one consciousness). Persistence and event broadcasting live in the daemon, not here.
    """

    def __init__(self, config: StateConfig, valve_level: int = 1, now: float | None = None) -> None:
        self.config = config
        self.matcher = PhraseMatcher(config.phrases)
        self.state: State = State.DORMANT
        # A text-initiated session starts mic-closed by default (ATHENA.md, Modality
        # handoff). TEXT is therefore the correct cold-start modality.
        self.modality: Modality = Modality.TEXT
        self.valve_level = valve_level
        self.speaking = False
        self.amplitude = 0.0
        self.session: Session | None = None
        self.last_activity: float = now if now is not None else time.time()
        self.last_session_end: float | None = None
        self._follow_up_until: float = 0.0

    # --- introspection -------------------------------------------------------------
    @property
    def mic_open(self) -> bool:
        return self.modality is Modality.VOICE and self.state is not State.DORMANT

    def snapshot(self) -> dict[str, object]:
        """The `/api/events` payload shape: {state, valve, modality, speaking, amplitude}."""
        return {
            "state": self.state.value,
            "valve": self.valve_level,
            "modality": self.modality.value,
            "speaking": self.speaking,
            "amplitude": round(self.amplitude, 4),
            "mic_open": self.mic_open,
            "session_id": self.session.session_id if self.session else None,
        }

    # --- addressing ----------------------------------------------------------------
    def touch(self, now: float | None = None) -> None:
        self.last_activity = now if now is not None else time.time()

    def open_follow_up_window(self, now: float | None = None) -> None:
        """Called when Athena finishes a reply or asks a question."""
        base = now if now is not None else time.time()
        self._follow_up_until = base + self.config.follow_up_window_s

    def close_follow_up_window(self) -> None:
        self._follow_up_until = 0.0

    def in_follow_up_window(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self._follow_up_until

    def is_directed(self, text: str, now: float | None = None) -> bool:
        """Directed at Athena? Named address, or inside the 8 s follow-up window.

        Text typed into Aegis is always directed — the user reached for the keyboard on
        purpose. Only the room is overheard.
        """
        if self.modality is Modality.TEXT:
            return True
        if is_named_address(text):
            return True
        return self.in_follow_up_window(now)

    # --- transitions ---------------------------------------------------------------
    def apply_state(
        self, to_state: State, phrase: str = "", now: float | None = None
    ) -> Transition | None:
        """Move to `to_state`. Returns the Transition, or None if it was a no-op."""
        at = now if now is not None else time.time()
        if to_state is self.state:
            self.touch(at)
            return None

        previous = self.state
        self.state = to_state

        if to_state is State.DORMANT:
            self.session = None
            self.last_session_end = at
            self.speaking = False
            self.amplitude = 0.0
            self.close_follow_up_window()
            # Leaving DORMANT is the only way back in, so drop to the quiet default.
            self.modality = Modality.TEXT
        elif previous is State.DORMANT:
            self.session = Session()

        self.touch(at)
        return Transition(previous, to_state, phrase, at)

    def set_modality(self, modality: Modality, now: float | None = None) -> bool:
        """Switch channel without touching state or losing context. True if it changed."""
        if self.state is State.DORMANT or modality is self.modality:
            return False
        self.modality = modality
        self.touch(now)
        return True

    def check_idle(self, now: float | None = None) -> Transition | None:
        """ACTIVE auto-returns to DORMANT after the idle timeout.

        SERIOUS is deliberately exempt: ATHENA.md scopes the timeout to ACTIVE sessions,
        and a long silence mid-debate is thinking, not absence.
        """
        at = now if now is not None else time.time()
        if self.state is not State.ACTIVE:
            return None
        if at - self.last_activity < self.config.idle_timeout_s:
            return None
        return self.apply_state(State.DORMANT, phrase="<idle timeout>", now=at)
