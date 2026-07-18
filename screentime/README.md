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
| `tracker/` | Swift daemon + SQLite store (build step 1) | ✅ built |
| `report/` | 2D report + local server (step 2), then 3D acts (steps 4–5) | ⬜ next |
| `widget/` | menu bar app + 20-20-20 nudges (step 3) | ⬜ |

## Build order (from the spec)

1. **Tracker daemon + local database** — done: see [`tracker/`](tracker/README.md).
2. Plain 2D report — prove the data and insights are good.
3. Menu bar widget + break nudges — where the wellbeing benefit lives.
4. 3D report, Act I (the eye) only.
5. Acts II (optic nerve) and III (brain).

All data stays on the machine. The tracker runs with zero permission prompts
in its default configuration.
