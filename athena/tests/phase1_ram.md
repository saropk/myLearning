# Phase 1 — RAM measurement against the budget table

ATHENA.md, *Hardware profile*: the budget numbers are design targets to be
"sanity-check[ed] against measured reality in phase 1 and correct[ed] … never silently
exceed[ed]". This file is that record. Re-run `python scripts/measure_ram.py` against a
live daemon and append a new dated block rather than editing an old one — the history of
what the daemon actually cost is worth keeping.

## How to measure

```sh
python -m athena                  # terminal 1
python scripts/measure_ram.py     # terminal 2 — dormant footprint
# then say "Athena, initiate" and ask her something (loads the brain), and re-run for the
# warm footprint
```

`/api/status` also reports the same numbers live, and Aegis shows `total/budget GB` in its
status chip — red when over.

---

## 2026-07-27 — phase 1 build, Linux dev container (NOT the target machine)

Measured with `scripts/measure_ram.py` against a live `python -m athena`.

| Component | Budget target | Measured | Verdict |
|---|---|---|---|
| Daemon + FastAPI (no wake word / VAD yet) | ≤ 0.5 GB (incl. wake word + VAD) | **0.056 GB** | well inside |
| whisper.cpp `small.en` | ~1 GB | not built (phase 2) | — |
| Ollama 8B brain (q4) | ~5 GB | not installed in this container | — |
| Embedding model | ~0.5 GB | not built (phase 4) | — |
| Warm total | ~7 GB | not yet measurable | — |
| DORMANT total | ≤ 0.6 GB | **0.056 GB** | well inside |

Environment: Python 3.11.15, Linux x86-64 container, 15.7 GB RAM. No Ollama, no
microphone, no macOS frameworks.

### What this does and does not tell us

- **Does:** the always-resident Python slice of Athena — daemon, FastAPI, uvicorn, SQLite,
  state machine, event bus — costs about **56 MB**, roughly one ninth of the 0.5 GB line
  it shares with the wake-word engine and VAD. That leaves ~0.44 GB of headroom for
  Porcupine + Silero in phase 2, which is comfortable.
- **Does not:** say anything trustworthy about the 16 GB Apple Silicon target. Python's
  RSS differs between platforms, and the two big line items (whisper, the 8B brain) are
  not present. **The table is therefore left as written — no correction is justified yet.**

### Required before phase 2 is accepted

Re-run this on the actual Mac and record a second block: dormant footprint, then warm
footprint after loading `llama3.1:8b` and whisper `small.en`. If the warm total exceeds
7 GB there, correct the table in ATHENA.md at that point (and consider whether
`brain.lite` should be the default on that machine) rather than treating the overrun as
acceptable.
