# Auditable Local-First Coding Agent — working rules

The model is remote and swappable; the world stays local, bounded, and
inspectable. Full design in `../AGENT_SCHEMA.md`. This file is the short list of
things that must stay true no matter which layer you touch.

## Invariants (§3) — do not violate these

1. **Grep test.** Networking imports (`socket`, `ssl`, `http`, `urllib`,
   `requests`, `httpx`, `anthropic`, `openai`, …) may appear **only** inside
   `gateway/`. `tests/test_grep_networking.py` fails the build otherwise. Add a
   provider? It goes under `gateway/adapters/`.

2. **Fail closed.** Every ambiguity, classifier uncertainty, or network error
   routes to local processing. Ambiguity costs intelligence, never scope.

3. **Categorical denylists** (`denylist.py`) — neither confidence-tunable nor
   overridable by learning:
   - *Exfiltrable* (`.env`, keys, credentials, gitignored paths): never leave
     below Level 3. Enforced in the gateway scope check.
   - *Destructive* (`rm -rf`, `--hard`, `--force`, `DROP`, `dd`, pipe-to-shell):
     never ambient-suggested. (Enforced once bash/ambient land.)

4. **Audit is verbatim.** `audit/log.py` logs the exact payload — not a summary
   — flushed to disk *before* the network call. Audit write fails → send fails.

## The stable core (§3a) — expensive to change

`contracts.py` holds `ToolDef` / `ToolCall` / `ToolResult` / `Request` /
`Response` / `ScopeLevel` / `FailureCategory`. Everything else plugs into them.
Change these only with a very good reason.

- Tools **never** return raw strings. `ToolResult.data` is always shaped.
- `send()` does exactly four things, in order: scope check → audit write →
  adapt and send → normalize. No provider exception escapes the gateway.
- `ToolDef.scope` lets the valve filter the tool list *before* the model sees
  it — stronger than refusing after the fact.

## Layout

```
auditable_agent/
  contracts.py        §3a stable core
  config.py           model + scope + ceilings (declarative)
  denylist.py         §3 invariant 3 patterns
  audit/              verbatim JSONL log (L0 support)
  gateway/            L0 — the ONLY package with networking
    adapters/         echo (offline) + anthropic (real, stdlib urllib)
  tools/              L2 — read_file + registry
  loop/               L1 — send→tools→execute→feed-back, with ceilings
  cli.py              Chunk 1 entry point
  tests/              grep invariant + read_file + spine
```

## Run

```bash
python -m unittest discover -s auditable_agent/tests -t .   # tests
python -m auditable_agent.cli "What does FirstProgram.py do?"  # offline demo
```

Real model: `AGENT_ADAPTER=anthropic ANTHROPIC_API_KEY=… python -m auditable_agent.cli "…"`

## Build order

Chunk 1 (spine) is done. Next is Chunk 2: `edit_file` + `bash` + valve levels
0/2 wired to the UI. Specify deeply what is expensive to change (contracts,
invariants, valve semantics); specify shallowly what is cheap (tool
implementations, thresholds) — written honestly only after watching the model
fail at them. Build vertically: every chunk runs end-to-end.
