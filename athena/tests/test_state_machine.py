"""State machine tests — ATHENA.md, "State machine" and "Name-addressing convention"."""

from __future__ import annotations

import pytest

from athena.config import PhraseConfig, StateConfig
from athena.state import (
    AthenaState,
    ControlKind,
    Modality,
    State,
    is_named_address,
    normalize,
    strip_address,
)


@pytest.fixture
def st() -> AthenaState:
    return AthenaState(StateConfig(), now=1000.0)


def wake(st: AthenaState, at: float = 1000.0) -> None:
    st.apply_state(State.ACTIVE, "athena, initiate", now=at)


def drive(st: AthenaState, utterance: str, at: float = 1000.0) -> State:
    """Apply whatever control phrase `utterance` contains, like the brain's step 1."""
    match = st.matcher.match(utterance, st.state)
    if match and match.kind is ControlKind.STATE and match.target_state:
        st.apply_state(match.target_state, match.phrase, now=at)
    elif match and match.kind is ControlKind.MODALITY and match.target_modality:
        st.set_modality(match.target_modality, now=at)
    return st.state


# --- normalization ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Athena, Initiate!", "athena initiate"),
        ("  athena   initiate  ", "athena initiate"),
        ("Athena, it's go time.", "athena its go time"),
        ("That's enough for today, Athena!!", "thats enough for today athena"),
    ],
)
def test_normalize_folds_case_and_punctuation(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


# --- the four documented transitions ----------------------------------------------


@pytest.mark.parametrize("phrase", ["athena, initiate", "athena, it's go time"])
def test_dormant_to_active(st: AthenaState, phrase: str) -> None:
    assert drive(st, phrase) is State.ACTIVE


@pytest.mark.parametrize("phrase", ["athena, let's get serious", "athena, let's get cracking"])
def test_active_to_serious(st: AthenaState, phrase: str) -> None:
    wake(st)
    assert drive(st, phrase) is State.SERIOUS


def test_serious_to_active(st: AthenaState) -> None:
    wake(st)
    drive(st, "athena, let's get serious")
    assert drive(st, "good session athena") is State.ACTIVE


@pytest.mark.parametrize("start", [State.ACTIVE, State.SERIOUS])
def test_deactivate_from_either_state(st: AthenaState, start: State) -> None:
    wake(st)
    if start is State.SERIOUS:
        drive(st, "athena, let's get serious")
    assert drive(st, "that's enough for today athena") is State.DORMANT


def test_deactivation_wins_over_other_phrases_in_the_same_utterance(st: AthenaState) -> None:
    """Security invariant 7: deactivation is honoured, whatever else is in the sentence."""
    wake(st)
    utterance = "athena let's get serious, no — that's enough for today athena"
    assert drive(st, utterance) is State.DORMANT


def test_transitions_tolerate_surrounding_words(st: AthenaState) -> None:
    assert drive(st, "ok so, athena initiate, please") is State.ACTIVE


def test_partial_word_does_not_trigger(st: AthenaState) -> None:
    """The word "initiated" is not "initiate" — whole-word matching only."""
    assert drive(st, "athena initiated the process") is State.DORMANT


def test_dormant_ignores_non_wake_phrases(st: AthenaState) -> None:
    assert st.matcher.match("athena, let's get serious", State.DORMANT) is None
    assert st.matcher.match("good session athena", State.DORMANT) is None
    assert st.state is State.DORMANT


def test_serious_phrase_from_dormant_needs_two_steps(st: AthenaState) -> None:
    drive(st, "athena, initiate")
    assert drive(st, "athena, let's get cracking") is State.SERIOUS


def test_configured_phrases_add_to_defaults_and_never_replace_them() -> None:
    cfg = StateConfig(phrases=PhraseConfig(activate=("athena, initiate", "wake up athena")))
    st = AthenaState(cfg, now=0.0)
    assert drive(st, "wake up athena") is State.ACTIVE
    st.apply_state(State.DORMANT, now=0.0)
    assert drive(st, "athena, initiate") is State.ACTIVE  # the spec default still works


# --- sessions and persistence hooks -----------------------------------------------


def test_session_starts_on_wake_and_ends_on_dormant(st: AthenaState) -> None:
    assert st.session is None
    wake(st)
    session_id = st.session.session_id
    drive(st, "athena, let's get serious")
    assert st.session.session_id == session_id  # SERIOUS continues the same session
    drive(st, "that's enough for today athena", at=1100.0)
    assert st.session is None
    assert st.last_session_end == 1100.0


# --- modality ---------------------------------------------------------------------


def test_text_is_the_cold_start_modality(st: AthenaState) -> None:
    """A text-initiated session keeps the mic closed until the talking phrase."""
    assert st.modality is Modality.TEXT
    wake(st)
    assert st.mic_open is False


def test_modality_phrases_do_not_touch_state(st: AthenaState) -> None:
    wake(st)
    drive(st, "athena, let's get serious")
    drive(st, "athena, let's get talking")
    assert st.state is State.SERIOUS
    assert st.modality is Modality.VOICE
    assert st.mic_open is True
    drive(st, "athena, let's get handsy")
    assert st.state is State.SERIOUS
    assert st.modality is Modality.TEXT
    assert st.mic_open is False


def test_modality_change_preserves_session_context(st: AthenaState) -> None:
    wake(st)
    st.session.add("user", "remember this")
    drive(st, "athena, let's get talking")
    assert st.session.turns == [{"role": "user", "content": "remember this"}]


def test_modality_phrases_are_inert_while_dormant(st: AthenaState) -> None:
    drive(st, "athena, let's get talking")
    assert st.state is State.DORMANT
    assert st.modality is Modality.TEXT


def test_dormant_resets_modality_to_quiet_default(st: AthenaState) -> None:
    wake(st)
    st.set_modality(Modality.VOICE)
    drive(st, "that's enough for today athena")
    assert st.modality is Modality.TEXT


def test_brain_view_phrase_is_recognised(st: AthenaState) -> None:
    wake(st)
    match = st.matcher.match("athena, show me your mind", st.state)
    assert match is not None and match.kind is ControlKind.VIEW


# --- name addressing --------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("Athena, what time is it?", True),
        ("What time is it, Athena?", True),
        ("what do you think athena", True),
        ("I was telling Bob that Athena is useful", False),
        ("pass the salt", False),
        ("", False),
    ],
)
def test_is_named_address(text: str, named: bool) -> None:
    assert is_named_address(text) is named


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Athena, what time is it?", "what time is it?"),
        ("What time is it, Athena?", "What time is it"),
        ("athena play some music", "play some music"),
        ("Athena", ""),
    ],
)
def test_strip_address(text: str, expected: str) -> None:
    assert strip_address(text) == expected


def test_undirected_room_speech_is_not_directed_in_voice(st: AthenaState) -> None:
    wake(st)
    st.set_modality(Modality.VOICE)
    assert st.is_directed("so anyway I told him no", now=1001.0) is False
    assert st.is_directed("athena, volume up", now=1001.0) is True


def test_typed_text_is_always_directed(st: AthenaState) -> None:
    wake(st)
    assert st.is_directed("volume up", now=1001.0) is True


def test_follow_up_window_is_eight_seconds(st: AthenaState) -> None:
    wake(st)
    st.set_modality(Modality.VOICE)
    st.open_follow_up_window(now=1000.0)
    assert st.is_directed("and the one after that", now=1007.9) is True
    assert st.is_directed("and the one after that", now=1008.1) is False


def test_new_named_address_closes_the_follow_up_window(st: AthenaState) -> None:
    wake(st)
    st.set_modality(Modality.VOICE)
    st.open_follow_up_window(now=1000.0)
    st.close_follow_up_window()
    assert st.is_directed("unnamed follow-up", now=1001.0) is False


# --- idle timeout -----------------------------------------------------------------


def test_active_idles_out_after_the_timeout(st: AthenaState) -> None:
    wake(st, at=1000.0)
    assert st.check_idle(now=1119.0) is None
    transition = st.check_idle(now=1121.0)
    assert transition is not None
    assert transition.to_state is State.DORMANT
    assert st.last_session_end == 1121.0


def test_activity_defers_the_idle_timeout(st: AthenaState) -> None:
    wake(st, at=1000.0)
    st.touch(now=1100.0)
    assert st.check_idle(now=1180.0) is None
    assert st.check_idle(now=1221.0) is not None


def test_serious_does_not_idle_out(st: AthenaState) -> None:
    """ATHENA.md scopes the idle timeout to ACTIVE; deep work is allowed long silences."""
    wake(st, at=1000.0)
    st.apply_state(State.SERIOUS, now=1000.0)
    assert st.check_idle(now=9999.0) is None
    assert st.state is State.SERIOUS


def test_idle_check_is_a_noop_while_dormant(st: AthenaState) -> None:
    assert st.check_idle(now=99999.0) is None


# --- event contract ---------------------------------------------------------------


def test_snapshot_carries_the_documented_event_shape(st: AthenaState) -> None:
    snap = st.snapshot()
    for key in ("state", "valve", "modality", "speaking", "amplitude"):
        assert key in snap
