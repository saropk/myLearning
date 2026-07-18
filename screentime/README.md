# Screen Time Tracker — with a 3D scroll-driven report

A macOS wellbeing tool: a background tracker that logs application usage and
idle time locally, a menu bar widget with eye-break nudges, and a review
surface built as a scroll-scrubbed WebGL journey — eye → optic nerve → brain.

Full specification (including the settled Act II/III aesthetic direction):
[`docs/SPEC.md`](docs/SPEC.md).

## Layout

| path | what | status |
|---|---|---|
| `docs/` | project spec | — |
| `mac/` | Swift package: `screentimed` daemon + SQLite store (step 1), `screentimebar` menu bar widget + nudges (step 3) | ✅ built |
| `report/` | 2D report + local server (step 2), 3D report (steps 4–5) | ✅ 2D + Act I built |

## Build order (from the spec)

1. **Tracker daemon + local database** — done: see [`mac/`](mac/README.md).
2. **Plain 2D report + local server + suggestions engine** — done: see
   [`report/`](report/README.md).
3. **Menu bar widget + break nudges** — done: `screentimebar` in
   [`mac/`](mac/README.md).
4. **3D report, Act I (the eye)** — done: see [`report/web/`](report/web/README.md).
5. Acts II (optic nerve) and III (brain) — next.

All data stays on the machine. The tracker runs with zero permission prompts
in its default configuration.
