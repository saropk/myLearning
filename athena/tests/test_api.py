"""Daemon API tests — ATHENA.md, "Daemon API (localhost only)" and the security invariants."""

from __future__ import annotations

import contextlib
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from athena.config import (
    BrainConfig,
    Config,
    DaemonConfig,
    MemoryConfig,
    StateConfig,
    ValveConfig,
)
from athena.daemon import create_app
from athena.events import EventBus
from athena.llm import ChatResult, LLMUnavailable
from athena.memory.store import Store

# The daemon refuses any Host header that is not loopback, so the test client must look
# like a real local browser rather than starlette's default "testserver".
LOOPBACK = "http://127.0.0.1:8787"


class FakeLLM:
    def __init__(self, reachable: bool = True) -> None:
        self.reachable = reachable

    async def chat(self, model, messages, *, options=None):  # noqa: ANN001, ANN201
        if not self.reachable:
            raise LLMUnavailable("connection refused")
        return ChatResult(text="A local answer.", model=model)

    async def resident_models(self):  # noqa: ANN201
        if not self.reachable:
            raise LLMUnavailable("connection refused")
        return [{"name": "llama3.1:8b", "size_bytes": 5_100_000_000, "expires_at": None}]

    async def available_models(self):  # noqa: ANN201
        return ["llama3.1:8b"]

    async def aclose(self) -> None:
        return None


def make_config(tmp_path: Path) -> Config:
    return Config(
        daemon=DaemonConfig(),
        brain=BrainConfig(),
        state=StateConfig(),
        valve=ValveConfig(default_level=1),
        memory=MemoryConfig(db_path=tmp_path / "athena.db"),
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(make_config(tmp_path), store=Store(tmp_path / "athena.db"), llm=FakeLLM())
    with TestClient(app, base_url=LOOPBACK) as c:
        c.headers.update({"Authorization": f"Bearer {app.state.token}"})
        yield c


@pytest.fixture
def dead_brain_client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        make_config(tmp_path), store=Store(tmp_path / "athena.db"), llm=FakeLLM(reachable=False)
    )
    with TestClient(app, base_url=LOOPBACK) as c:
        c.headers.update({"Authorization": f"Bearer {app.state.token}"})
        yield c


# --- auth (security invariant 2) --------------------------------------------------


def test_api_requires_a_token(client: TestClient) -> None:
    for path in ("/api/state", "/api/status", "/api/valve"):
        assert client.get(path, headers={"Authorization": ""}).status_code == 401
    assert (
        client.post("/api/chat", json={"message": "hi"}, headers={"Authorization": ""}).status_code
        == 401
    )


def test_wrong_token_is_rejected(client: TestClient) -> None:
    resp = client.get("/api/state", headers={"Authorization": "Bearer not-the-token"})
    assert resp.status_code == 401


def test_token_may_ride_in_the_query_string_for_eventsource(client: TestClient) -> None:
    token = client.app.state.token
    resp = client.get(f"/api/state?token={token}", headers={"Authorization": ""})
    assert resp.status_code == 200


def test_token_is_persisted_across_daemon_restarts(tmp_path: Path) -> None:
    store = Store(tmp_path / "athena.db")
    first = store.ensure_token()
    store.close()
    store2 = Store(tmp_path / "athena.db")
    assert store2.ensure_token() == first
    store2.close()


def test_db_directory_is_chmod_700(tmp_path: Path) -> None:
    """Security invariant 8."""
    db_dir = tmp_path / "nested"
    store = Store(db_dir / "athena.db")
    assert (db_dir.stat().st_mode & 0o777) == 0o700
    store.close()


def test_non_loopback_host_header_is_refused(client: TestClient) -> None:
    """Defeats DNS rebinding: a name that resolves to 127.0.0.1 still cannot reach us."""
    resp = client.get("/api/state", headers={"Host": "athena.example.com"})
    assert resp.status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8787", "localhost:8787"])
def test_loopback_host_headers_pass(client: TestClient, host: str) -> None:
    assert client.get("/api/state", headers={"Host": host}).status_code == 200


# --- chat + state ------------------------------------------------------------------


def chat(client: TestClient, message: str) -> dict:
    resp = client.post("/api/chat", json={"message": message})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_full_text_conversation_with_mode_switching(client: TestClient) -> None:
    """The phase-1 acceptance criterion, end to end over the real API."""
    assert chat(client, "hello?")["route"] == "dormant"

    woke = chat(client, "Athena, initiate")
    assert woke["state"] == "ACTIVE" and woke["route"] == "control"

    answer = chat(client, "Athena, what is a black hole?")
    assert answer["route"] == "answer"
    assert answer["reply"] == "A local answer."
    assert answer["source"] == "local"

    serious = chat(client, "Athena, let's get serious")
    assert serious["state"] == "SERIOUS"

    assert chat(client, "Athena, keep going")["state"] == "SERIOUS"
    assert chat(client, "good session Athena")["state"] == "ACTIVE"
    assert chat(client, "That's enough for today Athena")["state"] == "DORMANT"


def test_modality_handoff_over_the_api(client: TestClient) -> None:
    chat(client, "Athena, initiate")
    assert chat(client, "Athena, let's get talking")["mic_open"] is True
    assert chat(client, "Athena, let's get handsy")["mic_open"] is False


def test_text_session_starts_with_the_mic_closed(client: TestClient) -> None:
    assert client.get("/api/state").json()["mic_open"] is False
    assert chat(client, "Athena, initiate")["mic_open"] is False


def test_session_id_changes_between_sessions(client: TestClient) -> None:
    first = chat(client, "Athena, initiate")["session_id"]
    chat(client, "That's enough for today Athena")
    second = chat(client, "Athena, initiate")["session_id"]
    assert first and second and first != second


def test_last_session_end_is_persisted_on_deactivation(client: TestClient) -> None:
    chat(client, "Athena, initiate")
    chat(client, "That's enough for today Athena")
    assert client.app.state.store.get("last_session_end") is not None
    assert client.get("/api/state").json()["last_session_end"] is not None


def test_chat_rejects_an_empty_message(client: TestClient) -> None:
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_state_can_be_set_by_the_api_like_a_ui_button(client: TestClient) -> None:
    resp = client.post("/api/state", json={"state": "ACTIVE"})
    assert resp.status_code == 200 and resp.json()["state"] == "ACTIVE"
    assert client.post("/api/state", json={"modality": "VOICE"}).json()["mic_open"] is True
    assert client.post("/api/state", json={"state": "BANANAS"}).status_code == 422


def test_brain_down_still_leaves_state_transitions_working(dead_brain_client: TestClient) -> None:
    chat(dead_brain_client, "Athena, initiate")
    broken = chat(dead_brain_client, "Athena, explain entropy")
    assert broken["error"]
    assert "isn't answering" in broken["reply"]
    assert chat(dead_brain_client, "That's enough for today Athena")["state"] == "DORMANT"


# --- valve -------------------------------------------------------------------------


def test_valve_defaults_to_level_one_and_round_trips(client: TestClient) -> None:
    assert client.get("/api/valve").json()["level"] == 1
    assert client.post("/api/valve", json={"level": 0}).json()["level"] == 0
    assert client.get("/api/valve").json()["level"] == 0
    assert client.get("/api/state").json()["valve"] == 0


def test_valve_reports_that_phase_one_does_not_enforce_it(client: TestClient) -> None:
    body = client.get("/api/valve").json()
    assert body["enforced"] is False


@pytest.mark.parametrize("level", [-1, 4, 99])
def test_valve_rejects_out_of_range_levels(client: TestClient, level: int) -> None:
    assert client.post("/api/valve", json={"level": level}).status_code == 422


def test_valve_level_survives_a_restart(tmp_path: Path) -> None:
    store = Store(tmp_path / "athena.db")
    app = create_app(make_config(tmp_path), store=store, llm=FakeLLM())
    with TestClient(app, base_url=LOOPBACK) as c:
        c.headers.update({"Authorization": f"Bearer {app.state.token}"})
        c.post("/api/valve", json={"level": 3})
    app2 = create_app(make_config(tmp_path), store=store, llm=FakeLLM())
    with TestClient(app2, base_url=LOOPBACK) as c2:
        c2.headers.update({"Authorization": f"Bearer {app2.state.token}"})
        assert c2.get("/api/valve").json()["level"] == 3
    store.close()


# --- status ------------------------------------------------------------------------


def test_status_reports_ram_against_the_budget(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["phase"] == 1
    assert body["brain"]["reachable"] is True
    ram = body["ram"]
    for key in ("daemon_gb", "models_gb", "total_gb", "budget_gb", "within_budget"):
        assert key in ram
    assert ram["detail"]["budget_table_gb"]["warm_total"] == 7.0
    assert body["models_loaded"][0]["name"] == "llama3.1:8b"


def test_status_budget_follows_the_state(client: TestClient) -> None:
    assert client.get("/api/status").json()["ram"]["budget_gb"] == 0.6  # DORMANT
    chat(client, "Athena, initiate")
    assert client.get("/api/status").json()["ram"]["budget_gb"] == 7.0  # talking


def test_status_survives_an_unreachable_brain(dead_brain_client: TestClient) -> None:
    body = dead_brain_client.get("/api/status").json()
    assert body["brain"]["reachable"] is False
    assert body["models_loaded"] == []
    assert body["last_errors"]


# --- events ------------------------------------------------------------------------


def parse_sse(chunk: str) -> tuple[str, dict]:
    name = chunk.split("event: ", 1)[1].split("\n", 1)[0]
    return name, json.loads(chunk.split("data: ", 1)[1].split("\n", 1)[0])


@contextlib.contextmanager
def running_daemon(app) -> Iterator[tuple[str, dict[str, str]]]:  # noqa: ANN001
    """Serve `app` with uvicorn on an ephemeral loopback port for the duration of a test."""
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started, "uvicorn did not start"
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}", {"Authorization": f"Bearer {app.state.token}"}
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_events_stream_snapshot_then_live_transitions(tmp_path: Path) -> None:
    """`/api/events` is how Aegis sees state, so drive it against a real running daemon.

    Neither starlette's TestClient nor httpx's ASGITransport can read an endless SSE body
    incrementally — both wait for a response that never ends — so this one test spins up
    uvicorn on an ephemeral loopback port.
    """
    app = create_app(make_config(tmp_path), store=Store(tmp_path / "athena.db"), llm=FakeLLM())
    with running_daemon(app) as (base_url, headers):
        with httpx.Client(base_url=base_url, timeout=10.0) as hc:
            with hc.stream("GET", "/api/events", headers=headers) as stream:
                assert stream.status_code == 200
                assert stream.headers["content-type"].startswith("text/event-stream")
                chunks = stream.iter_text()

                name, snapshot = parse_sse(next(chunks))
                assert name == "state"
                assert snapshot["state"] == "DORMANT"
                assert set(snapshot) >= {"state", "valve", "modality", "speaking", "amplitude"}

                # A chat that wakes her must show up on the stream, unprompted.
                with httpx.Client(base_url=base_url, timeout=10.0) as hc2:
                    hc2.post("/api/chat", json={"message": "Athena, initiate"}, headers=headers)
                    name, event = parse_sse(next(chunks))
                    assert name == "state" and event["state"] == "ACTIVE"

                    # So must a valve change.
                    hc2.post("/api/valve", json={"level": 0}, headers=headers)
                    _, event = parse_sse(next(chunks))
                    assert event["valve"] == 0


def test_events_require_the_token(client: TestClient) -> None:
    assert client.get("/api/events", headers={"Authorization": ""}).status_code == 401


@pytest.mark.asyncio
async def test_bus_fans_state_changes_out_to_subscribers() -> None:
    bus = EventBus()
    with bus.subscribe() as queue:
        bus.publish("state", {"state": "ACTIVE"})
        bus.publish("notice", {"text": "going quiet"})
        assert (await queue.get()).data == {"state": "ACTIVE"}
        assert (await queue.get()).name == "notice"
    assert bus.subscriber_count == 0


@pytest.mark.asyncio
async def test_bus_drops_history_rather_than_blocking_on_a_wedged_client() -> None:
    from athena.events import QUEUE_MAX

    bus = EventBus()
    with bus.subscribe() as queue:
        for i in range(QUEUE_MAX + 10):
            bus.publish("state", {"n": i})
        assert queue.qsize() <= QUEUE_MAX
        assert queue.get_nowait().data["n"] != 0  # the oldest were shed


# --- UI shell ----------------------------------------------------------------------


def test_ui_shell_and_assets_are_served(client: TestClient) -> None:
    page = client.get("/", headers={"Authorization": ""})
    assert page.status_code == 200
    assert "ATH" in page.text and "ENA" in page.text
    assert client.get("/ui/chat.js", headers={"Authorization": ""}).status_code == 200


def test_ui_asset_route_refuses_path_traversal(client: TestClient) -> None:
    assert client.get("/ui/..%2f..%2fATHENA.md").status_code == 404


def test_ui_shell_contains_no_token(client: TestClient) -> None:
    """The shell is public bytes; the secret arrives in the launch URL, not in the HTML."""
    assert client.app.state.token not in client.get("/").text


# --- idle watchdog -----------------------------------------------------------------


def test_idle_watchdog_returns_her_to_dormant_with_a_spoken_notice(tmp_path: Path) -> None:
    """The daemon's background tick, not just the state-machine logic.

    Phase 1 has no mouth, so the "brief spoken confirmation" the spec asks for goes out as
    a `notice` event; phase 2's speak.py subscribes to the same event.
    """
    config = make_config(tmp_path)
    config = Config(
        daemon=config.daemon,
        brain=config.brain,
        state=StateConfig(idle_timeout_s=0.5, follow_up_window_s=8.0),
        valve=config.valve,
        memory=config.memory,
    )
    app = create_app(config, store=Store(tmp_path / "athena.db"), llm=FakeLLM())
    with running_daemon(app) as (base_url, headers):
        with httpx.Client(base_url=base_url, timeout=10.0) as hc:
            with hc.stream("GET", "/api/events", headers=headers) as stream:
                chunks = stream.iter_text()
                next(chunks)  # opening snapshot

                with httpx.Client(base_url=base_url, timeout=10.0) as hc2:
                    hc2.post("/api/chat", json={"message": "Athena, initiate"}, headers=headers)
                    _, event = parse_sse(next(chunks))
                    assert event["state"] == "ACTIVE"

                    name, notice = parse_sse(next(chunks))
                    assert name == "notice" and "quiet" in notice["text"].lower()
                    _, event = parse_sse(next(chunks))
                    assert event["state"] == "DORMANT"

                    assert hc2.get("/api/state", headers=headers).json()["state"] == "DORMANT"
