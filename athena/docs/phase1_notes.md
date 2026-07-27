# Phase 1 — build notes, decisions, and deviations

ATHENA.md is authoritative. This file records the judgement calls made while building
phase 1, so nothing about the implementation is a surprise later. Anything here that
disagrees with ATHENA.md is a bug in this file, not in the spec.

## What phase 1 covers

> **1. Skeleton + text brain.** Daemon, config, state machine, `/api/chat` against Ollama,
> `/api/status`, minimal Aegis page with working chat. ✔ Accept: text conversation with
> mode switching via typed phrases; state events visible; measured RAM matches the budget
> table (correct the table if not).

| Acceptance clause | Where it is satisfied | Test |
|---|---|---|
| Text conversation | `POST /api/chat` → `brain.py` → Ollama | `test_api.py::test_full_text_conversation_with_mode_switching` |
| Mode switching via typed phrases | `state.py` phrase matching, pre-LLM | `test_state_machine.py` (whole file), `test_brain_routing.py` |
| State events visible | `/api/events` SSE, driven by `events.py` | `test_api.py::test_events_stream_snapshot_then_live_transitions` |
| Measured RAM vs budget | `/api/status` + `scripts/measure_ram.py` | `tests/phase1_ram.md` |
| Minimal Aegis page | `athena/ui/index.html` + `chat.js` | `test_api.py::test_ui_shell_and_assets_are_served` |

## Modules added beyond the spec's repository layout

The layout in ATHENA.md lists modules by responsibility, not exhaustively. Four files
exist that it does not name; each is a seam the spec implies rather than a new concept:

| File | Why |
|---|---|
| `config.py` | `athena.toml` has to be parsed somewhere, and `daemon.py` is specified as "FastAPI app, lifespan wiring, localhost binding". |
| `llm.py` | The Ollama transport. Isolating it is what makes the networking exemption auditable — see below. |
| `events.py` | The `/api/events` fan-out. Phase 2's voice pipeline is the second consumer, so it does not belong inside the HTTP layer. |
| `status.py` | RAM accounting against the budget table, kept out of the routing code. |

## The one networking exemption

Security invariant 1 forbids networking imports outside `gateway/`; core principle 2
exempts "localhost calls to the daemon's own API and to Ollama on 127.0.0.1". Those two
statements need a named place to meet, and it is `athena/llm.py` — the only file outside
`gateway/` that imports `httpx`.

The exemption is verified rather than promised, which is the spec's own standard:

- `OllamaClient` refuses to construct against a non-loopback host, so a typo in
  `athena.toml` cannot turn the local brain into an egress path.
- The client is built with `trust_env=False`, so no `HTTPS_PROXY` in the environment can
  redirect a local call off-machine.
- `tests/test_no_network_imports.py` allowlists exactly `{gateway, llm.py}`, asserts that
  the allowlist has not been widened, asserts that nothing else imports `httpx`, and
  checks the loopback guard against a table of remote hosts.

That test is only *mandatory* from phase 5 per the spec. It is here from phase 1 because
the cheapest moment to stop networking code from spreading is before it has spread.

## Decisions worth knowing

**Bearer token delivery.** Every `/api/*` route requires the token (header, or `?token=`
for `EventSource`, which cannot set headers). The UI shell and `/ui/*` assets are served
unauthenticated: they are identical bytes on every install and contain no user data, and a
`<script src>` cannot carry a header. The secret reaches the page through the launch URL
printed by `python -m athena`; `chat.js` moves it into `sessionStorage` and scrubs it from
the address bar. A test asserts the token never appears in the served HTML.

**Host-header check.** Binding to `127.0.0.1` stops remote connections but not DNS
rebinding, so the daemon also rejects any `Host` that is not loopback. (This is why the
tests point `TestClient` at `http://127.0.0.1:8787` instead of starlette's default
`testserver`.)

**Typed text is always directed.** The name-addressing convention exists because the room
is overheard. Someone reaching for the keyboard is not the room, so text into Aegis is
always treated as directed; only voice utterances need the name or the 8 s follow-up
window. The mic being closed by default in text sessions is the spec's own privacy win.

**SERIOUS does not idle out.** ATHENA.md scopes the idle timeout to ACTIVE sessions. A long
silence mid-debate is thinking, not absence, so SERIOUS stays put until a phrase moves it.

**Apostrophes are deleted, not spaced, in `normalize()`.** Whisper writes "let's" or "lets"
depending on its mood; folding the apostrophe out entirely makes both forms match the same
configured phrase. Other punctuation still becomes whitespace.

**Configured phrases add to the defaults.** ATHENA.md says the defaults "must always work",
so `athena.toml` phrases are unioned with them rather than replacing them.

**Deactivation is checked first.** "athena let's get serious, no — that's enough for today
athena" goes DORMANT. Security invariant 7 makes deactivation unconditional, so it wins
over any other phrase in the same utterance.

**Valve level is stored but not enforced.** There is no `gateway/` in this build, so no
module can make an outbound request at any level; the level is persisted so Aegis can tint
for it and phase 5 has something to read. `GET /api/valve` says `"enforced": false` in as
many words rather than implying a guarantee that does not exist yet.

**Honest stubs over silent ones.** "Athena, let's get talking" is matched, flips the
modality, and says the voice loop arrives in phase 2. "Athena, show me your mind" is
matched and says the brain view follows memory. Neither pretends to work.

## Deliberately not built (later phases own these)

- `voice/` — wake word, VAD, whisper, TTS, push-to-talk (phase 2). `speaking` and
  `amplitude` are already in the event payload so the contract does not change.
- Fast-path table and `tools/` (phase 3). The routing order in `brain.py` already has the
  fast-path lookup and the constrained-tool-intent slot in the right sequence; phase 3 adds
  rows, not plumbing.
- `memory/` beyond the `settings` table (phase 4). `SCHEMA_VERSION` is there to migrate
  from.
- `gateway/` (phase 5).
- The WebGL2 emblem (phase 6). The page ships a CSS placeholder that is labelled as one on
  screen — ATHENA.md forbids porting flat sketches to the real emblem, so this is a
  deliberate dead end to be deleted, not a foundation. `design/reference.png` is not in the
  repo yet; it is needed before phase 6 starts.

## Running it

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m athena          # prints the tokenised Aegis URL
.venv/bin/python -m pytest -q       # 108 tests
.venv/bin/python -m ruff check .
```

Ollama is optional for the tests (they inject a fake brain) but needed for real answers:
`ollama pull llama3.1:8b && ollama serve`. With Ollama down, Athena degrades — she says so
and every phrase still works.
