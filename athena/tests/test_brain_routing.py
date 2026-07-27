"""Brain routing tests — ATHENA.md, "Brain (brain.py)".

The recurring theme: control phrases are honoured even when the model is dead (security
invariant 7), and the answer path degrades instead of crashing.
"""

from __future__ import annotations

import pytest

from athena.brain import (
    ACTIVE_PROMPT,
    BRAIN_DOWN_REPLY,
    SERIOUS_PROMPT,
    Brain,
)
from athena.config import BrainConfig, StateConfig
from athena.llm import ChatResult, LLMUnavailable
from athena.state import AthenaState, Modality, State

pytestmark = pytest.mark.asyncio


class FakeLLM:
    """Stands in for Ollama. `fail=True` is a dead brain."""

    def __init__(self, reply: str = "It is half past four.", fail: bool = False) -> None:
        self.reply = reply
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    async def chat(self, model, messages, *, options=None):  # noqa: ANN001, ANN201
        self.calls.append({"model": model, "messages": messages, "options": options})
        if self.fail:
            raise LLMUnavailable("connection refused")
        return ChatResult(text=self.reply, model=model)


def make(fail: bool = False, reply: str = "ok") -> tuple[Brain, AthenaState, FakeLLM]:
    llm = FakeLLM(reply=reply, fail=fail)
    brain = Brain(BrainConfig(), llm)  # type: ignore[arg-type]
    return brain, AthenaState(StateConfig(), now=0.0), llm


async def test_dormant_ignores_ordinary_text_without_calling_the_model() -> None:
    brain, st, llm = make()
    reply = await brain.handle("what's the weather", st)
    assert reply.route == "dormant"
    assert llm.calls == []
    assert st.state is State.DORMANT


async def test_wake_phrase_activates_without_calling_the_model() -> None:
    brain, st, llm = make()
    reply = await brain.handle("Athena, initiate", st)
    assert reply.route == "control"
    assert st.state is State.ACTIVE
    assert llm.calls == []


async def test_deactivation_works_with_the_brain_down() -> None:
    """Security invariant 7 — string matching, independent of the model's availability."""
    brain, st, llm = make(fail=True)
    await brain.handle("Athena, initiate", st)
    reply = await brain.handle("That's enough for today Athena", st)
    assert st.state is State.DORMANT
    assert reply.route == "control"
    assert llm.calls == []


async def test_answer_path_degrades_when_the_brain_is_down() -> None:
    brain, st, _ = make(fail=True)
    await brain.handle("Athena, initiate", st)
    reply = await brain.handle("Athena, what is a black hole", st)
    assert reply.text == BRAIN_DOWN_REPLY
    assert reply.error and "refused" in reply.error
    assert st.state is State.ACTIVE  # a dead brain does not knock her over


async def test_active_prompt_is_the_concise_one() -> None:
    brain, st, llm = make(reply="Half four.")
    await brain.handle("Athena, initiate", st)
    await brain.handle("Athena, what time is it", st)
    assert llm.calls[0]["messages"][0]["content"] == ACTIVE_PROMPT


async def test_serious_prompt_switches_with_state() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st)
    await brain.handle("Athena, let's get serious", st)
    await brain.handle("Athena, argue with me", st)
    assert llm.calls[0]["messages"][0]["content"] == SERIOUS_PROMPT


async def test_mode_hint_overrides_the_prompt_without_changing_state() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st)
    await brain.handle("Athena, think hard", st, mode_hint="serious")
    assert llm.calls[0]["messages"][0]["content"] == SERIOUS_PROMPT
    assert st.state is State.ACTIVE


async def test_address_token_is_stripped_before_routing() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st)
    await brain.handle("Athena, what time is it?", st)
    assert llm.calls[0]["messages"][-1]["content"] == "what time is it?"


async def test_undirected_speech_is_context_not_command() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st)
    st.set_modality(Modality.VOICE)
    st.close_follow_up_window()
    reply = await brain.handle("bob did you see the game", st)
    assert reply.route == "overheard"
    assert reply.text == ""
    assert llm.calls == []
    assert st.session.turns == [{"role": "overheard", "content": "bob did you see the game"}]


async def test_follow_up_window_lets_the_next_utterance_through_unnamed() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st, now=0.0)
    st.set_modality(Modality.VOICE)
    await brain.handle("Athena, what time is it", st, now=1.0)  # opens the window
    reply = await brain.handle("and the date", st, now=5.0)
    assert reply.route == "answer"
    reply = await brain.handle("and the year", st, now=60.0)  # window long closed
    assert reply.route == "overheard"


async def test_session_context_is_carried_into_the_prompt() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st)
    await brain.handle("Athena, my name is Saro", st)
    await brain.handle("Athena, what is my name", st)
    roles = [m["role"] for m in llm.calls[-1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


async def test_overheard_turns_never_reach_the_model_as_context() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st, now=0.0)
    st.set_modality(Modality.VOICE)
    st.close_follow_up_window()
    await brain.handle("unrelated room chatter", st, now=1.0)
    await brain.handle("Athena, what time is it", st, now=2.0)
    contents = [m["content"] for m in llm.calls[-1]["messages"]]
    assert "unrelated room chatter" not in contents


async def test_bare_name_is_an_attention_getter() -> None:
    brain, st, llm = make()
    await brain.handle("Athena, initiate", st)
    reply = await brain.handle("Athena", st)
    assert reply.text == "Yes?"
    assert llm.calls == []


async def test_voice_handoff_is_honest_about_phase_two() -> None:
    brain, st, _ = make()
    await brain.handle("Athena, initiate", st)
    reply = await brain.handle("Athena, let's get talking", st)
    assert reply.route == "control"
    assert "phase 2" in reply.text
    assert st.modality is Modality.VOICE


async def test_every_reply_is_local_in_phase_one() -> None:
    """No gateway/ module exists yet; nothing can be cloud-sourced."""
    brain, st, _ = make()
    await brain.handle("Athena, initiate", st)
    for utterance in ("Athena, hello", "Athena, let's get serious", "Athena, tell me about Rome"):
        assert (await brain.handle(utterance, st)).source == "local"
