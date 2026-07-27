"""Routing: control phrase → fast path → tool intent → answer.

Phase 1 implements steps 1 and 4. Steps 2 and 3 are present as explicit, empty seams so
that the ordering guaranteed by ATHENA.md is established now and phases 3+ only fill
tables in — no re-plumbing.

Nothing in this module reaches the network. The answer path talks to the local brain via
`llm.OllamaClient` (loopback-pinned); cloud eligibility is decided by `gateway/valve.py`,
which does not exist until phase 5 — until then every answer is local, which is exactly
what valve Level 0 behaviour looks like.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .config import BrainConfig
from .llm import ChatResult, LLMUnavailable, OllamaClient
from .state import AthenaState, ControlKind, Modality, State, strip_address

# --- prompts ----------------------------------------------------------------------

ACTIVE_PROMPT = """You are Athena, a local voice assistant running entirely on the user's Mac.
You are in ACTIVE mode: be concise and tool-forward. Answer in at most two spoken \
sentences unless the user explicitly asks for more. No preamble, no restating the \
question, no offers of further help. Speak plainly — your words are read aloud, so never \
spell out file paths or URLs character by character."""

SERIOUS_PROMPT = """You are Athena, a local assistant running entirely on the user's Mac.
You are in SERIOUS mode: this is deep work. Reason at length when it helps, disagree when \
the user is wrong and say why, and ask for the missing piece instead of guessing. Prefer \
being useful and specific over being agreeable. You may reference earlier sessions when \
you have them; never invent a memory you do not hold."""

# Spoken when the local brain is unreachable. Athena degrades; she never goes silent.
BRAIN_DOWN_REPLY = (
    "My local brain isn't answering right now — Ollama looks like it's down. "
    "Everything else still works; try again once it's up."
)
DORMANT_REPLY = 'I\'m dormant. Say "Athena, initiate" when you want me.'
VOICE_PENDING_REPLY = (
    "Noted — but my ears aren't built yet. The voice loop arrives in phase 2; "
    "we're still in text for now."
)
BRAIN_VIEW_PENDING_REPLY = (
    "The brain view comes after memory lands in phase 4. Nothing to show you yet."
)


@dataclass
class Reply:
    """The result of routing one utterance."""

    text: str
    route: str  # "control" | "fast_path" | "tool" | "answer" | "dormant" | "overheard"
    source: str = "local"  # "local" | "cloud" — always local until phase 5
    spoken: bool = True
    control: str | None = None  # the matched control phrase, when route == "control"
    error: str | None = None
    meta: dict[str, object] = field(default_factory=dict)


# --- fast path (phase 3) -----------------------------------------------------------
# A table of (compiled pattern, handler) for high-frequency commands that must reach the
# action in under 100 ms with no LLM round-trip. It is empty in phase 1 because every
# entry needs a tool from tools/, and tools land in phase 3. The lookup stays in the
# routing order so that phase adds rows, not plumbing.
FastPathHandler = Callable[[str], Reply]
FAST_PATH: list[tuple[str, FastPathHandler]] = []


def match_fast_path(text: str) -> Reply | None:
    import re

    for pattern, handler in FAST_PATH:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return handler(text)
    return None


class Brain:
    def __init__(self, config: BrainConfig, llm: OllamaClient) -> None:
        self.config = config
        self.llm = llm

    def system_prompt(self, state: State) -> str:
        # Phase 4 prepends retrieved memory for SERIOUS; the seam is this method.
        return SERIOUS_PROMPT if state is State.SERIOUS else ACTIVE_PROMPT

    async def handle(
        self,
        utterance: str,
        st: AthenaState,
        *,
        now: float | None = None,
        mode_hint: str | None = None,
    ) -> Reply:
        """Route one utterance. `st` is mutated for state/modality changes."""

        # 1. Control phrases — absolute priority, string-matched, no model involved.
        match = st.matcher.match(utterance, st.state)
        if match is not None:
            if match.kind is ControlKind.STATE and match.target_state is not None:
                previous = st.state
                st.apply_state(match.target_state, match.phrase, now=now)
                return Reply(
                    text=_state_ack(previous, match.target_state),
                    route="control",
                    control=match.phrase,
                    meta={"from": previous.value, "to": match.target_state.value},
                )
            if match.kind is ControlKind.MODALITY and match.target_modality is not None:
                changed = st.set_modality(match.target_modality, now=now)
                if match.target_modality is Modality.VOICE:
                    # Honest phase-1 answer: the phrase is recognised and the modality is
                    # recorded, but voice/ has nothing to open yet.
                    return Reply(
                        text=VOICE_PENDING_REPLY,
                        route="control",
                        control=match.phrase,
                        meta={"modality": st.modality.value, "changed": changed},
                    )
                return Reply(
                    text="Hands on keyboard. Same session, same context.",
                    route="control",
                    control=match.phrase,
                    meta={"modality": st.modality.value, "changed": changed},
                )
            if match.kind is ControlKind.VIEW:
                return Reply(
                    text=BRAIN_VIEW_PENDING_REPLY,
                    route="control",
                    control=match.phrase,
                    meta={"view": "brain"},
                )

        # DORMANT and no wake phrase: she is asleep. No transcription, no model call,
        # no session context written.
        if st.state is State.DORMANT:
            return Reply(text=DORMANT_REPLY, route="dormant", spoken=False)

        # Addressing: in voice, unnamed room speech is context, never a command.
        if not st.is_directed(utterance, now=now):
            if st.session is not None:
                st.session.add("overheard", utterance)
            return Reply(text="", route="overheard", spoken=False)

        text = strip_address(utterance)
        if not text:
            # Just her name, nothing else — treat as an attention-getter.
            st.open_follow_up_window(now)
            return Reply(text="Yes?", route="answer")

        st.touch(now)
        st.close_follow_up_window()

        # 2. Fast path (phase 3).
        fast = match_fast_path(text)
        if fast is not None:
            st.open_follow_up_window(now)
            return fast

        # 3. Constrained tool intent (phase 3): the local model emits structured output
        #    against a strict JSON schema via Ollama's `format` parameter, so a malformed
        #    tool call is impossible by construction. Needs tools/registry.py.

        # 4. Answer path.
        return await self._answer(text, st, now=now, mode_hint=mode_hint)

    async def _answer(
        self,
        text: str,
        st: AthenaState,
        *,
        now: float | None,
        mode_hint: str | None,
    ) -> Reply:
        state = st.state
        if mode_hint == "serious":
            state = State.SERIOUS
        elif mode_hint == "active":
            state = State.ACTIVE

        messages: list[dict[str, str]] = [{"role": "system", "content": self.system_prompt(state)}]
        if st.session is not None:
            messages += [t for t in st.session.turns if t["role"] in ("user", "assistant")]
        messages.append({"role": "user", "content": text})

        if st.session is not None:
            st.session.add("user", text)

        try:
            result: ChatResult = await self.llm.chat(
                self.config.active_model,
                messages,
                options={"num_predict": 220 if state is State.ACTIVE else 1024},
            )
        except LLMUnavailable as exc:
            # Fail soft on the answer path; state handling above is unaffected.
            return Reply(text=BRAIN_DOWN_REPLY, route="answer", error=str(exc))

        if st.session is not None:
            st.session.add("assistant", result.text)
        st.open_follow_up_window(now)
        return Reply(
            text=result.text,
            route="answer",
            meta={"model": result.model, "latency_ms": result.total_duration_ms},
        )


def _state_ack(previous: State, to_state: State) -> str:
    """Short spoken acknowledgements. ACTIVE-mode brevity applies to Athena's own voice."""
    if to_state is State.ACTIVE and previous is State.DORMANT:
        return "I'm listening."
    if to_state is State.SERIOUS:
        return "Serious mode. Go."
    if to_state is State.ACTIVE and previous is State.SERIOUS:
        return "Good session. Back to normal."
    if to_state is State.DORMANT:
        return "Going quiet. Talk later."
    return f"{to_state.value.title()}."
