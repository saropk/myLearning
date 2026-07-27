# Athena

A fully local, always-listening voice assistant for macOS. **[ATHENA.md](ATHENA.md) is the
authoritative spec** — read it before changing anything here.

> Athena always listens — but nothing she hears ever leaves this machine except through one
> logged, user-tuned valve.

## Status: phase 1 of 6 complete

| Phase | What | State |
|---|---|---|
| 1 | Skeleton + text brain — daemon, config, state machine, `/api/chat`, `/api/status`, minimal Aegis page | **done** — see [docs/phase1_notes.md](docs/phase1_notes.md) |
| 2 | Voice loop — wake word, VAD, whisper, TTS, acoustic test protocol | not started |
| 3 | Brain + fast path + tools tier 1 & 1.5 (then the two-week daily-driver gate) | not started |
| 4 | Memory — hot / warm / cold tiers, nightly consolidation | not started |
| 5 | Gateway + valve — levels 0–3, redactor, audit log | not started |
| 6 | Aegis emblem (WebGL2) + launchd install | not started |

Each phase must pass its acceptance check before the next begins.

## Quickstart

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m athena          # prints the tokenised Aegis URL — open it
```

Optional but recommended, for real answers rather than a friendly failure message:

```sh
ollama pull llama3.1:8b && ollama serve
```

Try, in the chat box: `Athena, initiate` → ask her something → `Athena, let's get serious`
→ `That's enough for today Athena`.

## Development

```sh
.venv/bin/python -m pytest -q          # 108 tests
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format .
.venv/bin/python scripts/measure_ram.py   # footprint vs the budget table (daemon running)
```

Config lives in [athena.toml](athena.toml); every key is annotated with the phase that
reads it. The database (`settings` only, so far) is at
`~/Library/Application Support/Athena/athena.db`, in a `chmod 700` directory.
